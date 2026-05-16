"""
손실 함수: WMSE, Knowledge-Infused Penalty, 복합 손실

NSF-MAP 논문의 손실 함수 설계를 따른다:
  - Weighted MSE (클래스 불균형 대응)
  - CrossEntropy (분류)
  - Sensor Range Penalty (Knowledge Infusion, P3 방식)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

import config


class WeightedMSELoss(nn.Module):
    """
    가중 MSE 손실 (논문 Eq.9).
    클래스별 샘플 가중치를 적용하여 소수 클래스의 오차에 더 큰 페널티를 부여한다.
    """

    def __init__(self, class_weights: torch.Tensor = None):
        super().__init__()
        self.class_weights = class_weights

    def forward(self, predictions: torch.Tensor, targets: torch.Tensor,
                labels: torch.Tensor = None) -> torch.Tensor:
        mse = (predictions - targets) ** 2

        if self.class_weights is not None and labels is not None:
            weights = self.class_weights.to(predictions.device)
            sample_weights = weights[labels]
            mse = mse * sample_weights.unsqueeze(1)

        return mse.mean()


class KnowledgePenalty(nn.Module):
    """
    Knowledge-Infused Penalty (논문 Eq.8).

    센서 값이 정상 범위 안인데 anomaly로 예측하거나,
    범위 밖인데 normal로 예측하면 페널티를 부과한다.

    Args:
        sensor_ranges: dict[int, tuple(min, max)] - 센서별 허용 범위
                       예: {0: (6000, 8000), 1: (1400, 1500)}
    """

    def __init__(self, sensor_ranges: dict = None, lambda_penalty: float = 0.1):
        super().__init__()
        self.sensor_ranges = sensor_ranges or {}
        self.lambda_penalty = lambda_penalty

    def forward(self, predicted_values: torch.Tensor,
                predicted_labels: torch.Tensor,
                true_labels: torch.Tensor) -> torch.Tensor:
        """
        Args:
            predicted_values: (B, num_sensors) 예측 센서 값
            predicted_labels: (B, num_classes) 예측 로짓 (softmax 전)
            true_labels: (B,) 실제 라벨
        """
        if not self.sensor_ranges:
            return torch.tensor(0.0, device=predicted_values.device)

        pred_class = predicted_labels.argmax(dim=1)
        penalty = torch.zeros(1, device=predicted_values.device)

        for sensor_idx, (r_min, r_max) in self.sensor_ranges.items():
            if sensor_idx >= predicted_values.shape[1]:
                continue

            vals = predicted_values[:, sensor_idx]
            in_range = (vals >= r_min) & (vals <= r_max)

            is_anomaly_pred = pred_class != 0
            is_normal_pred = pred_class == 0

            # Case 1: 센서 값이 범위 내인데 이상으로 예측 → 페널티
            false_alarm = in_range & is_anomaly_pred
            # Case 2: 센서 값이 범위 밖인데 정상으로 예측 → 페널티
            missed_detection = ~in_range & is_normal_pred

            penalty += (false_alarm.float().sum() + missed_detection.float().sum())

        return self.lambda_penalty * penalty / predicted_values.shape[0]


class CombinedLoss(nn.Module):
    """
    분류 + 재구성 + Knowledge Penalty를 결합한 복합 손실 함수.

    L = α * CrossEntropy + β * ReconstructionMSE + γ * KnowledgePenalty
    """

    def __init__(self, class_weights: torch.Tensor = None,
                 sensor_ranges: dict = None,
                 alpha: float = 1.0,
                 beta: float = 0.1,
                 gamma: float = 0.1,
                 use_knowledge_penalty: bool = True):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

        if class_weights is not None:
            self.ce_loss = nn.CrossEntropyLoss(weight=class_weights)
        else:
            self.ce_loss = nn.CrossEntropyLoss()

        self.recon_loss = nn.MSELoss()

        self.use_kp = use_knowledge_penalty
        if use_knowledge_penalty:
            self.knowledge_penalty = KnowledgePenalty(
                sensor_ranges=sensor_ranges,
                lambda_penalty=config.PENALTY_LAMBDA,
            )

    def forward(self, logits: torch.Tensor, labels: torch.Tensor,
                reconstructed: torch.Tensor = None,
                original: torch.Tensor = None,
                predicted_values: torch.Tensor = None) -> dict:
        """
        Returns:
            dict with "total", "ce", "recon", "penalty" 키
        """
        ce = self.ce_loss(logits, labels)
        total = self.alpha * ce

        result = {"ce": ce.item(), "recon": 0.0, "penalty": 0.0}

        if reconstructed is not None and original is not None:
            recon = self.recon_loss(reconstructed, original)
            total += self.beta * recon
            result["recon"] = recon.item()

        if self.use_kp and predicted_values is not None:
            penalty = self.knowledge_penalty(predicted_values, logits, labels)
            total += self.gamma * penalty
            result["penalty"] = penalty.item()

        result["total"] = total
        return result
