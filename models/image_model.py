"""
이미지 브랜치: ResNet18 기반 이미지 분류기 (Transfer Learning)

논문에서는 EfficientNet-B0을 사용하지만, 프로젝트 계획에 따라
ResNet18을 기본으로 하되 EfficientNet-B0도 선택 가능하게 구성한다.
"""
import torch
import torch.nn as nn
from torchvision import models

import config


class ImageClassifier(nn.Module):
    """
    ImageNet 사전학습 모델 기반 이미지 분류기.

    구조:
        [사전학습 Backbone] → [Feature Vector] → [FC] → [분류]

    backbone 옵션:
        - "resnet18": ResNet18 (경량, 빠른 학습)
        - "efficientnet_b0": EfficientNet-B0 (논문 방식)
    """

    def __init__(self, num_classes: int = config.NUM_CLASSES,
                 backbone: str = "resnet18",
                 dropout: float = config.DROPOUT_RATE,
                 freeze_backbone: bool = False):
        super().__init__()
        self.backbone_name = backbone

        if backbone == "resnet18":
            self.backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            feature_dim = self.backbone.fc.in_features  # 512
            self.backbone.fc = nn.Identity()
        elif backbone == "efficientnet_b0":
            self.backbone = models.efficientnet_b0(
                weights=models.EfficientNet_B0_Weights.DEFAULT
            )
            feature_dim = self.backbone.classifier[1].in_features  # 1280
            self.backbone.classifier = nn.Identity()
        else:
            raise ValueError(f"지원하지 않는 backbone: {backbone}")

        if freeze_backbone:
            for param in self.backbone.parameters():
                param.requires_grad = False

        self.feature_dim = feature_dim

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feature_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(128, num_classes),
        )

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """분류 헤드 제거 후 특징 벡터만 추출 (Fusion에서 사용)"""
        return self.backbone(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        logits = self.classifier(features)
        return logits


class ImageFeatureExtractor(nn.Module):
    """
    Fusion 모델에서 사용할 이미지 특징 추출기.
    사전학습된 ImageClassifier에서 backbone만 가져와 고정한다.
    """

    def __init__(self, pretrained_model: ImageClassifier = None,
                 backbone: str = "resnet18"):
        super().__init__()
        if pretrained_model is not None:
            self.backbone = pretrained_model.backbone
            self.feature_dim = pretrained_model.feature_dim
        else:
            if backbone == "resnet18":
                self.backbone = models.resnet18(
                    weights=models.ResNet18_Weights.DEFAULT
                )
                self.feature_dim = self.backbone.fc.in_features
                self.backbone.fc = nn.Identity()
            elif backbone == "efficientnet_b0":
                self.backbone = models.efficientnet_b0(
                    weights=models.EfficientNet_B0_Weights.DEFAULT
                )
                self.feature_dim = self.backbone.classifier[1].in_features
                self.backbone.classifier = nn.Identity()

        for param in self.backbone.parameters():
            param.requires_grad = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.backbone(x)
