"""Local shape/NaN sanity check for CrossAttentionFusion before pushing to Kaggle."""
import torch
import torch.nn as nn
from torchvision import models

NUM_CLASSES = 5
DROPOUT = 0.5
NUM_SENSOR_FEATURES = 22
SEQUENCE_LENGTH = 50


class CrossAttentionFusion(nn.Module):
    """
    Cross-Attention Fusion (개선안 Ⓐ, 최우선):
      [Image]  -> ResNet18 layer4 (frozen) -> spatial map [B,512,7,7] -> 49 image tokens
      [Sensor] -> BiLSTM -> f_sensor (256) -> query
      sensor(Q)가 image tokens(K,V)에 attention -> image_context
      z = concat([f_sensor, image_context]) -> FC -> class
    이미지가 없거나(마스킹) attention 가중이 낮으면 image_context가 작아져
    f_sensor 경로가 분류를 지배 -> 센서 정보로 자동 폴백.
    """
    def __init__(self, sensor_input_dim, num_classes=NUM_CLASSES, dropout=DROPOUT,
                 d_model=256, n_heads=4):
        super().__init__()
        # Image branch: ResNet18에서 avgpool/fc 제거 -> spatial feature map 유지
        resnet = models.resnet18(weights=None)  # 테스트는 가중치 없이
        self.image_backbone = nn.Sequential(*list(resnet.children())[:-2])  # -> [B,512,7,7]
        for p in self.image_backbone.parameters():
            p.requires_grad = False
        self.img_proj = nn.Linear(512, d_model)

        # Sensor branch
        self.sensor_lstm = nn.LSTM(
            sensor_input_dim, 128, 2,
            batch_first=True, dropout=dropout, bidirectional=True,
        )
        self.sensor_proj = nn.Linear(256, d_model)

        # Cross-attention: query=sensor, key/value=image tokens
        self.cross_attn = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )
        self.attn_norm = nn.LayerNorm(d_model)

        # Fusion head: [f_sensor(256) ; image_context(d_model)]
        self.fusion_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(256 + d_model, 256),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, sensor_seq, images, has_image=None):
        # Sensor features
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)      # [B,256]
        q = self.sensor_proj(f_sensor).unsqueeze(1)           # [B,1,d]

        # Image tokens (frozen backbone)
        with torch.no_grad():
            fmap = self.image_backbone(images)                # [B,512,7,7]
        tokens = fmap.flatten(2).transpose(1, 2)              # [B,49,512]
        tokens = self.img_proj(tokens)                        # [B,49,d]

        attn_out, attn_w = self.cross_attn(q, tokens, tokens) # [B,1,d]
        attn_out = self.attn_norm(attn_out.squeeze(1))        # [B,d]

        # 이미지 없는 샘플은 image_context를 0으로 -> 센서로 폴백
        if has_image is not None:
            attn_out = attn_out * has_image.float().unsqueeze(1)

        z = torch.cat([f_sensor, attn_out], dim=1)            # [B,256+d]
        return self.fusion_head(z)


# ---- sanity test ----
B = 8
model = CrossAttentionFusion(sensor_input_dim=NUM_SENSOR_FEATURES)
sensor = torch.randn(B, SEQUENCE_LENGTH, NUM_SENSOR_FEATURES)
images = torch.randn(B, 3, 224, 224)
has_img = torch.tensor([1, 1, 0, 1, 0, 1, 1, 0])  # 일부 이미지 없음

model.train()
out = model(sensor, images, has_img)
print("output shape:", tuple(out.shape), "(expected (8,5))")
print("NaN in output:", torch.isnan(out).any().item())

# backward 확인
loss = out.sum()
loss.backward()
n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
n_total = sum(p.numel() for p in model.parameters())
print(f"trainable params: {n_train:,} / total {n_total:,}")
print("image_backbone frozen:", not any(p.requires_grad for p in model.image_backbone.parameters()))

# eval mode + 모두 이미지 없음 (전부 센서 폴백) NaN 체크
model.eval()
with torch.no_grad():
    out2 = model(sensor, images, torch.zeros(B))
print("all-no-image NaN:", torch.isnan(out2).any().item(), "shape", tuple(out2.shape))
print("OK")
