"""
센서 브랜치: LSTM 기반 시계열 분류기 + Autoencoder (논문 방식)

두 가지 아키텍처를 제공한다:
  1) SensorLSTM: 프로젝트 계획서 기반 LSTM 분류기
  2) SensorAutoencoder: NSF-MAP 논문 방식 오토인코더-디코더
"""
import torch
import torch.nn as nn

import config


class SensorLSTM(nn.Module):
    """
    LSTM 기반 시계열 이상 탐지 분류기.

    구조:
        [시계열 입력 (B, T, F)] → [LSTM] → [마지막 hidden] → [FC] → [분류]

    프로젝트 계획서에서 RNN/LSTM을 사용하기로 했으므로 이 모델을 기본으로 한다.
    """

    def __init__(self, input_dim: int = config.NUM_SENSOR_FEATURES,
                 hidden_dim: int = config.LSTM_HIDDEN_SIZE,
                 num_layers: int = config.LSTM_NUM_LAYERS,
                 num_classes: int = config.NUM_CLASSES,
                 dropout: float = config.DROPOUT_RATE,
                 bidirectional: bool = True):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        self.num_directions = 2 if bidirectional else 1

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional,
        )

        self.feature_dim = hidden_dim * self.num_directions

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes),
        )

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """LSTM 마지막 hidden state를 특징 벡터로 반환 (Fusion용)"""
        lstm_out, (h_n, _) = self.lstm(x)
        if self.bidirectional:
            hidden = torch.cat([h_n[-2], h_n[-1]], dim=1)
        else:
            hidden = h_n[-1]
        return hidden

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.extract_features(x)
        logits = self.classifier(features)
        return logits


class SensorAutoencoder(nn.Module):
    """
    NSF-MAP 논문 방식 오토인코더-디코더.

    구조:
        Encoder: [입력(F)] → [Linear(hidden)] → [ReLU] → [Linear(latent)]
        Decoder: [latent]  → [Linear(hidden)] → [ReLU] → [Linear(F)]

    Transfer Learning (P2):
        학습 후 Encoder를 freeze하고 Decoder만 fine-tune한다.

    Fusion에서 사용 시:
        Encoder의 latent representation을 이미지 특징과 concat한다.
    """

    def __init__(self, input_dim: int = config.NUM_SENSOR_FEATURES,
                 hidden_dim: int = config.AE_HIDDEN_DIM,
                 latent_dim: int = config.AE_LATENT_DIM):
        super().__init__()
        self.latent_dim = latent_dim

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, latent_dim),
            nn.ReLU(),
        )

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

        self.feature_dim = latent_dim

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)

    def forward(self, x: torch.Tensor) -> tuple:
        """
        Returns:
            reconstructed: 재구성된 센서 값
            latent: 잠재 표현 (fusion에 사용)
        """
        latent = self.encode(x)
        reconstructed = self.decode(latent)
        return reconstructed, latent

    def freeze_encoder(self):
        """Transfer Learning: Encoder 파라미터를 동결한다."""
        for param in self.encoder.parameters():
            param.requires_grad = False

    def unfreeze_encoder(self):
        for param in self.encoder.parameters():
            param.requires_grad = True


class SensorAutoencoderClassifier(nn.Module):
    """
    오토인코더 + 분류 헤드를 결합한 모델.
    오토인코더로 특징을 추출하고, 분류 레이어에서 이상 유형을 예측한다.
    """

    def __init__(self, input_dim: int = config.NUM_SENSOR_FEATURES,
                 hidden_dim: int = config.AE_HIDDEN_DIM,
                 latent_dim: int = config.AE_LATENT_DIM,
                 num_classes: int = config.NUM_CLASSES,
                 dropout: float = config.DROPOUT_RATE):
        super().__init__()
        self.autoencoder = SensorAutoencoder(input_dim, hidden_dim, latent_dim)

        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> tuple:
        reconstructed, latent = self.autoencoder(x)
        logits = self.classifier(latent)
        return logits, reconstructed
