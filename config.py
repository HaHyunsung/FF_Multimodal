"""
프로젝트 전역 설정 및 하이퍼파라미터
"""
import os

# ──────────────────────────────────────────────
# 경로 설정 (FF Dataset 다운로드 후 경로 수정 필요)
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")            # 원본 JSON + 이미지
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")      # 전처리 완료 CSV/이미지
IMAGE_DIR = os.path.join(PROCESSED_DIR, "images")        # 크롭된 ROI 이미지
CHECKPOINT_DIR = os.path.join(BASE_DIR, "checkpoints")
RESULT_DIR = os.path.join(BASE_DIR, "results")

# ──────────────────────────────────────────────
# 데이터 설정
# ──────────────────────────────────────────────
# 이상 유형 클래스 (NSF-MAP 논문 기준)
ANOMALY_CLASSES = [
    "NoAnomaly",
    "NoBody1",
    "NoNose",
    "NoNose_NoBody2",
    "NoNose_NoBody2_NoBody1",
]
NUM_CLASSES = len(ANOMALY_CLASSES)

# 시계열 센서 변수 (NSF-MAP에서 사용한 주요 3변수 기준, 확장 가능)
# 실제 데이터 로드 후 변수 수에 맞게 조정
NUM_SENSOR_FEATURES = 3       # 기본: 센서값1, 센서값2, anomaly_label
SEQUENCE_LENGTH = 50          # LSTM 입력 시퀀스 길이 (시계열 윈도우)

# 이미지 설정
IMAGE_SIZE = 224              # EfficientNet/ResNet 입력 크기
IMAGE_MEAN = [0.485, 0.456, 0.406]   # ImageNet 정규화
IMAGE_STD = [0.229, 0.224, 0.225]

# 분석 대상 사이클 상태 (논문: state 4, 9에서 부품이 보임)
TARGET_CYCLE_STATES = [4, 9]

# ──────────────────────────────────────────────
# 학습 하이퍼파라미터
# ──────────────────────────────────────────────
BATCH_SIZE = 32
EPOCHS = 50
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
DROPOUT_RATE = 0.5

# Transfer Learning
FREEZE_ENCODER = True         # 오토인코더 encoder 동결 여부 (P2 방식)

# Knowledge Infusion
USE_KNOWLEDGE_PENALTY = True  # 센서 범위 기반 페널티 사용 여부 (P3 방식)
PENALTY_LAMBDA = 0.1          # 페널티 강도 하이퍼파라미터

# 학습률 스케줄러
LR_PATIENCE = 5               # ReduceLROnPlateau patience
EARLY_STOP_PATIENCE = 10      # Early stopping patience

# 데이터 분할
TRAIN_RATIO = 0.8             # 80-20 split (cycle-wise)
RANDOM_SEED = 42

# ──────────────────────────────────────────────
# 모델 아키텍처
# ──────────────────────────────────────────────
# LSTM (센서 브랜치)
LSTM_HIDDEN_SIZE = 128
LSTM_NUM_LAYERS = 2

# Autoencoder (논문 방식)
AE_HIDDEN_DIM = 64
AE_LATENT_DIM = 128

# Fusion
FUSION_HIDDEN_DIM = 256       # 융합 FC 레이어 히든 차원

# ──────────────────────────────────────────────
# 장치 설정
# ──────────────────────────────────────────────
import torch
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
