"""
멀티모달 융합 모델: 이미지 + 센서 Decision-Level Fusion

NSF-MAP 논문의 3가지 융합 전략을 구현한다:
  P1: Decision-Level Fusion (DLF)
  P2: DLF + Transfer Learning (encoder freeze)
  P3: DLF + TL + Knowledge-Infused Learning (sensor range penalty)
"""
import torch
import torch.nn as nn
from torchvision import models

import config


class MultimodalFusionNet(nn.Module):
    """
    Decision-Level Fusion 모델.

    센서 브랜치(LSTM 또는 Autoencoder)와 이미지 브랜치(ResNet/EfficientNet)의
    특징을 concat하여 최종 분류를 수행한다.

    구조:
        [이미지] → [Backbone(frozen)] → f_V (이미지 특징)
        [센서]  → [LSTM/AE Encoder]   → f_T (센서 특징)
                                           ↓
                                    z = [f_V ; f_T]  (concat)
                                           ↓
                                    [FC + Dropout] → [분류]

    Args:
        sensor_branch: "lstm" 또는 "autoencoder"
        image_backbone: "resnet18" 또는 "efficientnet_b0"
        fusion_strategy: "concat" (feature-level) 또는 "attention"
    """

    def __init__(self,
                 sensor_input_dim: int = config.NUM_SENSOR_FEATURES,
                 num_classes: int = config.NUM_CLASSES,
                 sensor_branch: str = "lstm",
                 image_backbone: str = "resnet18",
                 fusion_strategy: str = "concat",
                 dropout: float = config.DROPOUT_RATE,
                 freeze_image_backbone: bool = True):
        super().__init__()
        self.sensor_branch_type = sensor_branch
        self.fusion_strategy = fusion_strategy

        # ── 이미지 브랜치 ──
        if image_backbone == "resnet18":
            self.image_backbone = models.resnet18(
                weights=models.ResNet18_Weights.DEFAULT
            )
            image_feature_dim = self.image_backbone.fc.in_features  # 512
            self.image_backbone.fc = nn.Identity()
        elif image_backbone == "efficientnet_b0":
            self.image_backbone = models.efficientnet_b0(
                weights=models.EfficientNet_B0_Weights.DEFAULT
            )
            image_feature_dim = self.image_backbone.classifier[1].in_features
            self.image_backbone.classifier = nn.Identity()
        else:
            raise ValueError(f"지원하지 않는 backbone: {image_backbone}")

        if freeze_image_backbone:
            for param in self.image_backbone.parameters():
                param.requires_grad = False

        # ── 센서 브랜치 ──
        if sensor_branch == "lstm":
            self.sensor_encoder = nn.LSTM(
                input_size=sensor_input_dim,
                hidden_size=config.LSTM_HIDDEN_SIZE,
                num_layers=config.LSTM_NUM_LAYERS,
                batch_first=True,
                dropout=dropout if config.LSTM_NUM_LAYERS > 1 else 0,
                bidirectional=True,
            )
            sensor_feature_dim = config.LSTM_HIDDEN_SIZE * 2  # bidirectional
        elif sensor_branch == "autoencoder":
            self.sensor_encoder = nn.Sequential(
                nn.Linear(sensor_input_dim, config.AE_HIDDEN_DIM),
                nn.ReLU(),
                nn.Linear(config.AE_HIDDEN_DIM, config.AE_LATENT_DIM),
                nn.ReLU(),
            )
            sensor_feature_dim = config.AE_LATENT_DIM

            self.sensor_decoder = nn.Sequential(
                nn.Linear(config.AE_LATENT_DIM, config.AE_HIDDEN_DIM),
                nn.ReLU(),
                nn.Linear(config.AE_HIDDEN_DIM, sensor_input_dim),
            )
        else:
            raise ValueError(f"지원하지 않는 sensor_branch: {sensor_branch}")

        self.image_feature_dim = image_feature_dim
        self.sensor_feature_dim = sensor_feature_dim

        # ── Fusion 레이어 ──
        if fusion_strategy == "concat":
            fusion_input_dim = image_feature_dim + sensor_feature_dim
        elif fusion_strategy == "attention":
            self.attention_fc = nn.Sequential(
                nn.Linear(image_feature_dim + sensor_feature_dim, 64),
                nn.Tanh(),
                nn.Linear(64, 2),
                nn.Softmax(dim=1),
            )
            common_dim = max(image_feature_dim, sensor_feature_dim)
            self.image_proj = nn.Linear(image_feature_dim, common_dim)
            self.sensor_proj = nn.Linear(sensor_feature_dim, common_dim)
            fusion_input_dim = common_dim
        else:
            raise ValueError(f"지원하지 않는 fusion_strategy: {fusion_strategy}")

        self.fusion_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(fusion_input_dim, config.FUSION_HIDDEN_DIM),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(config.FUSION_HIDDEN_DIM, num_classes),
        )

    def extract_image_features(self, images: torch.Tensor) -> torch.Tensor:
        if any(not p.requires_grad for p in self.image_backbone.parameters()):
            with torch.no_grad():
                return self.image_backbone(images)
        return self.image_backbone(images)

    def extract_sensor_features(self, sensor_data: torch.Tensor) -> torch.Tensor:
        if self.sensor_branch_type == "lstm":
            lstm_out, (h_n, _) = self.sensor_encoder(sensor_data)
            features = torch.cat([h_n[-2], h_n[-1]], dim=1)
        elif self.sensor_branch_type == "autoencoder":
            features = self.sensor_encoder(sensor_data)
        return features

    def reconstruct_sensor(self, latent: torch.Tensor) -> torch.Tensor:
        """Autoencoder 방식일 때 센서 재구성 (loss 계산용)"""
        if self.sensor_branch_type == "autoencoder":
            return self.sensor_decoder(latent)
        return None

    def fuse(self, image_feat: torch.Tensor,
             sensor_feat: torch.Tensor) -> torch.Tensor:
        """두 모달리티의 특징을 결합한다."""
        if self.fusion_strategy == "concat":
            return torch.cat([image_feat, sensor_feat], dim=1)
        elif self.fusion_strategy == "attention":
            combined = torch.cat([image_feat, sensor_feat], dim=1)
            weights = self.attention_fc(combined)  # (B, 2)
            img_proj = self.image_proj(image_feat)
            sen_proj = self.sensor_proj(sensor_feat)
            fused = weights[:, 0:1] * img_proj + weights[:, 1:2] * sen_proj
            return fused

    def forward(self, sensor_data: torch.Tensor,
                images: torch.Tensor,
                has_image: torch.Tensor = None) -> dict:
        """
        Args:
            sensor_data: (B, T, F) 시계열 시퀀스 또는 (B, F) 단일 시점
            images: (B, 3, 224, 224) 이미지
            has_image: (B,) bool 텐서, 이미지 존재 여부

        Returns:
            dict with keys: "logits", "sensor_reconstructed" (autoencoder일 때)
        """
        sensor_feat = self.extract_sensor_features(sensor_data)
        image_feat = self.extract_image_features(images)

        # 이미지가 없는 샘플은 센서 특징만 사용
        if has_image is not None:
            mask = has_image.float().unsqueeze(1)
            image_feat = image_feat * mask

        fused = self.fuse(image_feat, sensor_feat)
        logits = self.fusion_head(fused)

        result = {"logits": logits}

        if self.sensor_branch_type == "autoencoder":
            result["sensor_reconstructed"] = self.reconstruct_sensor(sensor_feat)

        return result

    def freeze_sensor_encoder(self):
        """Transfer Learning (P2): 센서 Encoder를 동결한다."""
        if self.sensor_branch_type == "autoencoder":
            for param in self.sensor_encoder.parameters():
                param.requires_grad = False
        elif self.sensor_branch_type == "lstm":
            for param in self.sensor_encoder.parameters():
                param.requires_grad = False
