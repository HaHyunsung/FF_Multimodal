# -*- coding: utf-8 -*-
# 멀티모달 제조 공정 이상탐지 — 최종 코드 (val/test 분리 + 분류예시 2x2) | 3조 김주헌·하현성


# # Multimodal Deep Learning for Manufacturing Anomaly Detection
# ## 멀티모달 딥러닝 기반 제조 공정 이상 탐지 (이미지 + 시계열 센서)
# 
# **Dataset**: Future Factories (FF) Dataset - University of South Carolina
# 
# **목표**: 이미지 단독, 센서 단독, 멀티모달 융합 모델의 이상 탐지 성능을 비교
# 
# | Model | Architecture | Input |
# |-------|-------------|-------|
# | Model 1 | BiLSTM | 시계열 센서 (22 features) |
# | Model 2 | ResNet18 (Transfer Learning) | 카메라 이미지 (224x224) |
# | Model 3 | Decision-Level Fusion | 센서 + 이미지 |
# 
# ---
# 
# ### Kaggle 실행 시 필요한 Input Datasets
# 1. `ff-multimodal-csv` - 전처리 완료 CSV (직접 업로드)
# 2. `ramyharik/ff-2023-12-12-multi-modal-dataset-16` - 이미지 파트 1
# 
# Settings > Accelerator > **GPU T4 x2** 로 설정 후 실행
# 
# > ※ 이미지는 **2개 파트** 사용: `ff-2023-12-12-multi-modal-dataset-16` **및 `-26`** 모두 Add Input 필요.


# ## 1. Setup & Configuration

import os
import re
import time
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score, precision_score, recall_score,
)
from collections import Counter

warnings.filterwarnings("ignore")
plt.rcParams["figure.figsize"] = (12, 6)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

# ============================================================
# 경로 설정 - 자동 탐색
# ============================================================
import glob

KAGGLE_BASE = "/kaggle/input"
ON_KAGGLE = os.path.exists(KAGGLE_BASE)

# CSV 자동 탐색
CSV_PATH = None
if ON_KAGGLE:
    results = glob.glob("/kaggle/input/**/FF_Multimodal.csv", recursive=True)
    if results:
        CSV_PATH = results[0]
        print(f"CSV found: {CSV_PATH}")

if CSV_PATH is None and os.path.exists("data/Multi-modal Dataset/FF_Multimodal.csv"):
    CSV_PATH = "data/Multi-modal Dataset/FF_Multimodal.csv"
    ON_KAGGLE = False

if CSV_PATH is None:
    raise FileNotFoundError("CSV not found. Check input datasets.")

# 이미지 경로 자동 탐색
KAGGLE_IMAGE_ROOTS = glob.glob("/kaggle/input/**/BATCH*", recursive=True)
if KAGGLE_IMAGE_ROOTS:
    # BATCH 폴더의 부모 경로 추출
    IMAGE_BASE_DIRS = list(set(os.path.dirname(p) for p in KAGGLE_IMAGE_ROOTS))
    print(f"Image dirs found: {len(KAGGLE_IMAGE_ROOTS)} BATCH folders")
    print(f"Base dirs: {IMAGE_BASE_DIRS[:3]}")
else:
    IMAGE_BASE_DIRS = []
    print("No image BATCH folders found.")

print(f"ON_KAGGLE: {ON_KAGGLE}")

# ============================================================
# Hyperparameters
# ============================================================
BATCH_SIZE = 32
EPOCHS = 20  # iter2: 런타임 바운드(early stopping 보유)
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
DROPOUT = 0.5
SEQUENCE_LENGTH = 50
IMAGE_SIZE = 224
TRAIN_RATIO = 0.8

SENSOR_COLUMNS = [
    "I_R01_Gripper_Load", "I_R02_Gripper_Load",
    "I_R03_Gripper_Load", "I_R04_Gripper_Load",
    "I_R01_Gripper_Pot", "I_R02_Gripper_Pot",
    "I_R03_Gripper_Pot", "I_R04_Gripper_Pot",
    "Q_VFD1_Temperature", "Q_VFD2_Temperature",
    "Q_VFD3_Temperature", "Q_VFD4_Temperature",
    "M_Conv1_Speed_mmps", "M_Conv2_Speed_mmps",
    "M_Conv3_Speed_mmps", "M_Conv4_Speed_mmps",
    "M_R01_SJointAngle_Degree", "M_R01_LJointAngle_Degree",
    "M_R01_UJointAngle_Degree",
    "M_R04_SJointAngle_Degree", "M_R04_LJointAngle_Degree",
    "M_R04_UJointAngle_Degree",
]
NUM_SENSOR_FEATURES = len(SENSOR_COLUMNS)
print(f"Sensor features: {NUM_SENSOR_FEATURES}")


# ## 2. Data Loading & EDA

print("Loading CSV...")
df = pd.read_csv(CSV_PATH, low_memory=False)
print(f"Raw shape: {df.shape}")
print(f"Columns: {list(df.columns)}")

# 라벨 정리: 소수 클래스 병합, E_STOPPED 제거
label_map = {
    "Normal": "Normal",
    "NoBody1": "NoBody1",
    "NoNose": "NoNose",
    "NoNose,NoBody2": "NoNose_NoBody2",
    "NoNose,NoBody2,NoBody1": "NoNose_NoBody2_NoBody1",
    "NoBody2": "NoBody1",
    "NoBody2,NoBody1": "NoBody1",
}

df = df[df["actual_state"] != "E_STOPPED"].copy()
df["label"] = df["actual_state"].map(label_map)
df = df.dropna(subset=["label"]).reset_index(drop=True)

le = LabelEncoder()
df["label_encoded"] = le.fit_transform(df["label"])
CLASS_NAMES = list(le.classes_)
NUM_CLASSES = len(CLASS_NAMES)

print(f"Cleaned shape: {df.shape}")
print(f"\nClasses ({NUM_CLASSES}): {CLASS_NAMES}")
print(f"\nLabel distribution:")
print(df["label"].value_counts())

# EDA 시각화
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# 클래스 분포
df["label"].value_counts().plot(kind="bar", ax=axes[0], color="steelblue")
axes[0].set_title("Anomaly Type Distribution")
axes[0].set_ylabel("Count")
axes[0].tick_params(axis="x", rotation=30)

# Cycle State 분포
df["CycleState"].value_counts().sort_index().plot(kind="bar", ax=axes[1], color="coral")
axes[1].set_title("Cycle State Distribution")
axes[1].set_ylabel("Count")

# 센서 분포: Normal vs Anomaly
normal = df[df["label"] == "Normal"]["I_R04_Gripper_Load"]
anomaly = df[df["label"] != "Normal"]["I_R04_Gripper_Load"]
axes[2].hist(normal, bins=50, alpha=0.6, label="Normal", density=True)
axes[2].hist(anomaly, bins=50, alpha=0.6, label="Anomaly", density=True)
axes[2].set_title("R04 Gripper Load: Normal vs Anomaly")
axes[2].legend()

plt.tight_layout()
plt.show()


# ## 3. Preprocessing
# 
# > (2차 개선) **cycle 단위 train/val/test = 70/10/20** — early stopping은 val로만, test는 최종 평가 전용.

# 센서 정규화
scaler = StandardScaler()
df[SENSOR_COLUMNS] = scaler.fit_transform(df[SENSOR_COLUMNS])

# Cycle-wise train/test split (data leakage 방지)
cycles = df["Cycle_Count_New"].unique()
cycle_has_anomaly = df.groupby("Cycle_Count_New")["label"].apply(
    lambda x: (x != "Normal").any()
).astype(int)

train_cycles, test_cycles = train_test_split(
    cycles, train_size=TRAIN_RATIO, random_state=SEED,
    stratify=[cycle_has_anomaly[c] for c in cycles],
)

# (2차 개선) 검증(val) 사이클 분리: train의 12.5%를 val로 → 최종 70/10/20 (cycle 단위)
# - early stopping·모델 선택은 val로만 수행, test는 "최종 평가 전용" (val/test 분리 엄밀화)
# - test 분할은 기존과 동일(SEED 고정)하므로 이전 결과와 비교 가능
train_cycles, val_cycles = train_test_split(
    train_cycles, test_size=0.125, random_state=SEED,
    stratify=[cycle_has_anomaly[c] for c in train_cycles],
)

train_df = df[df["Cycle_Count_New"].isin(train_cycles)].reset_index(drop=True)
val_df = df[df["Cycle_Count_New"].isin(val_cycles)].reset_index(drop=True)
test_df = df[df["Cycle_Count_New"].isin(test_cycles)].reset_index(drop=True)

print(f"Train: {len(train_df)} samples ({len(train_cycles)} cycles)")
print(f"Val:   {len(val_df)} samples ({len(val_cycles)} cycles)")
print(f"Test:  {len(test_df)} samples ({len(test_cycles)} cycles)")
print(f"\nTrain labels:\n{train_df['label'].value_counts()}")
print(f"\nTest labels:\n{test_df['label'].value_counts()}")

# 시계열 시퀀스 생성 (Sliding Window, cycle 단위)
def create_sequences_by_cycle(data_df, sensor_cols, seq_len):
    """같은 cycle 안에서만 sliding window 시퀀스를 만든다."""
    X_list, y_list = [], []
    for cycle_id, group in data_df.groupby("Cycle_Count_New"):
        values = group[sensor_cols].values.astype(np.float32)
        labels = group["label_encoded"].values
        if len(values) < seq_len:
            continue
        for i in range(len(values) - seq_len):
            X_list.append(values[i:i + seq_len])
            y_list.append(labels[i + seq_len])
    return np.array(X_list), np.array(y_list)

print("Creating sequences...")
X_train_seq, y_train_seq = create_sequences_by_cycle(train_df, SENSOR_COLUMNS, SEQUENCE_LENGTH)
X_val_seq, y_val_seq = create_sequences_by_cycle(val_df, SENSOR_COLUMNS, SEQUENCE_LENGTH)
X_test_seq, y_test_seq = create_sequences_by_cycle(test_df, SENSOR_COLUMNS, SEQUENCE_LENGTH)
print(f"Train: {X_train_seq.shape}  Test: {X_test_seq.shape}")

# 클래스 가중치 (불균형 처리)
counter = Counter(y_train_seq)
total = len(y_train_seq)
class_weights = torch.FloatTensor([
    total / (NUM_CLASSES * counter.get(i, 1)) for i in range(NUM_CLASSES)
])
class_weights = class_weights / class_weights.sum() * NUM_CLASSES
print(f"\nClass weights: {class_weights.tolist()}")


# ## 4. Image Path Resolution

import glob

# 이미지 BATCH 폴더의 부모 디렉토리 자동 탐색
KAGGLE_IMAGE_ROOTS = glob.glob("/kaggle/input/**/BATCH*", recursive=True)
IMAGE_BASE_DIRS = list(set(os.path.dirname(p) for p in KAGGLE_IMAGE_ROOTS))
print(f"BATCH folders found: {len(KAGGLE_IMAGE_ROOTS)}")
print(f"Base directories: {IMAGE_BASE_DIRS}")


def find_image_path(relative_path):
    """
    CSV 경로 'Dataset/BATCH1000/000000_0.png' 를
    Kaggle 절대 경로로 변환
    """
    if not ON_KAGGLE or not IMAGE_BASE_DIRS:
        return None
    if not isinstance(relative_path, str):
        return None

    # 'Dataset/' 접두사 제거
    rel = relative_path
    if rel.startswith("Dataset/"):
        rel = rel[len("Dataset/"):]

    # 각 base dir에서 탐색
    for base_dir in IMAGE_BASE_DIRS:
        candidate = os.path.join(base_dir, rel)
        if os.path.exists(candidate):
            return candidate
    return None


# Cycle state 4, 9만 필터 (카메라가 부품을 촬영하는 상태)
df_image = df[df["CycleState"].isin([4, 9])].copy()
print(f"\nImage-eligible rows (state 4,9): {len(df_image)}")

HAS_IMAGES = False
if ON_KAGGLE:
    # 빠른 테스트: 10개만 매칭 시도 (두 카메라 모두)
    s1 = df_image["Cam1"].head(10).tolist()
    s2 = df_image["Cam2"].head(10).tolist()
    f1 = sum(1 for p in s1 if find_image_path(p) is not None)
    f2 = sum(1 for p in s2 if find_image_path(p) is not None)
    print(f"Sample test: Cam1 {f1}/10, Cam2 {f2}/10 matched")

    if f1 > 0 and f2 > 0:
        print("Resolving all image paths (Cam1 + Cam2)...")
        df_image["cam1_path"] = df_image["Cam1"].apply(find_image_path)
        df_image["cam2_path"] = df_image["Cam2"].apply(find_image_path)
        # 두 카메라 모두 존재하는 행만 사용 (결합 학습 전제)
        df_image = df_image.dropna(subset=["cam1_path", "cam2_path"]).reset_index(drop=True)
        n_found = len(df_image)
        print(f"Both-camera rows: {n_found}")
        HAS_IMAGES = n_found > 100
        if HAS_IMAGES:
            print(f"Image dataset ready (2 cameras): {n_found} samples")
    else:
        print("Path mismatch. Check IMAGE_BASE_DIRS / Cam1 / Cam2.")
else:
    print("Local mode: image training skipped.")

print(f"\nHAS_IMAGES = {HAS_IMAGES}")

# ============================================================
# 데이터 샘플 미리보기 (센서 시계열 + 카메라 이미지) — 직접 실행해 확인
# ============================================================
import matplotlib.pyplot as plt

# --- (0) CycleState 확인: 어떤 상태에서 이미지가 찍히는지 ---
print("=== CycleState 분포 (전체) ===")
print(df["CycleState"].value_counts().sort_index().to_string())
if "Cam1" in df.columns:
    cam_states = df[df["Cam1"].notna() & (df["Cam1"].astype(str).str.len() > 3)]["CycleState"].value_counts().sort_index()
    print(f"\n=== Cam1 이미지 경로가 있는 CycleState ===")
    print(cam_states.to_string())
print()

# --- (1) 센서 시계열 샘플: 클래스별 한 사이클의 주요 채널 (정규화된 값) ---
_cols = [c for c in ["I_R04_Gripper_Load", "M_R01_SJointAngle_Degree", "Q_VFD1_Temperature"] if c in df.columns]
_cls = [c for c in CLASS_NAMES if c in df["label"].unique()]
fig, axes = plt.subplots(1, len(_cols), figsize=(6*len(_cols), 4))
if len(_cols) == 1: axes = [axes]
for ax, col in zip(axes, _cols):
    for lbl in _cls[:4]:
        cyc = df[df["label"] == lbl]["Cycle_Count_New"].iloc[0]
        seg = df[df["Cycle_Count_New"] == cyc][col].values[:200]
        ax.plot(seg, label=lbl, alpha=0.8)
    ax.set_title(f"Sensor: {col}"); ax.set_xlabel("timestep"); ax.legend(fontsize=8)
plt.suptitle("Sensor time-series samples (per class, one cycle, standardized)", fontsize=13)
plt.tight_layout(); plt.show()

# --- (2) 카메라 이미지 샘플: 행 = (CycleState × Camera), 열 = 클래스 ---
#     두 카메라(Cam1=_0, Cam2=_1)를 같은 장면에서 비교해서 봄.
import numpy as np
_has_img = ("cam1_path" in df_image.columns) and df_image["cam1_path"].notna().any()
if _has_img:
    _show = [c for c in CLASS_NAMES if c in df_image["label"].unique()]
    _states = sorted(df_image["CycleState"].unique().tolist())
    _cams = [(c, n) for c, n in [("cam1_path", "Cam1"), ("cam2_path", "Cam2")] if c in df_image.columns]
    # 행 조합: (state, cam) — 예: S4·Cam1, S4·Cam2, S9·Cam1, S9·Cam2
    _rows = [(st, col, nm) for st in _states for (col, nm) in _cams]

    fig, axes = plt.subplots(len(_rows), len(_show), figsize=(4*len(_show), 4*len(_rows)))
    axes = np.array(axes).reshape(len(_rows), len(_show))

    for ri, (state, col, camname) in enumerate(_rows):
        df_state = df_image[df_image["CycleState"] == state]
        for j, lbl in enumerate(_show):
            ax = axes[ri][j]; ax.axis("off")
            if ri == 0:
                ax.set_title(lbl, fontsize=10, fontweight="bold")
            # 행 라벨 (axis off 여도 보이도록 text로 직접 표기)
            if j == 0:
                ax.text(-0.08, 0.5, f"State {state}\n{camname}", transform=ax.transAxes,
                        fontsize=11, fontweight="bold", ha="right", va="center")
            row = df_state[df_state["label"] == lbl][col].dropna().head(1)
            if len(row) > 0:
                try:
                    ax.imshow(Image.open(row.iloc[0]).convert("RGB"))
                except Exception:
                    ax.text(0.5, 0.5, "load error", ha="center", va="center")
            else:
                ax.text(0.5, 0.5, "없음", ha="center", va="center", fontsize=9, color="gray")

    plt.suptitle("Camera samples — 행=(CycleState × Camera 1/2), 열=클래스", fontsize=13)
    plt.tight_layout(); plt.show()

    print("=== CycleState별 이미지 수 ===")
    for st in _states:
        cnt = df_image[df_image["CycleState"] == st]["label"].value_counts()
        print(f"  State {st}: 총 {cnt.sum()}장  →  {cnt.to_dict()}")
else:
    print("[이미지 미리보기] Kaggle 이미지 데이터셋이 연결되면 표시됩니다.")


# ## 5. Dataset & DataLoader Classes

class SensorSequenceDataset(Dataset):
    def __init__(self, sequences, labels):
        self.X = torch.FloatTensor(sequences)
        self.y = torch.LongTensor(labels)
    def __len__(self):
        return len(self.y)
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class ImageAnomalyDataset(Dataset):
    """
    image_paths2 가 주어지면 두 카메라(Cam1, Cam2)를 함께 로드해
    [V=2, 3, H, W] 텐서로 반환 (멀티뷰). 없으면 단일 [3, H, W] (하위호환).
    """
    def __init__(self, image_paths, labels, transform=None, image_paths2=None):
        self.image_paths = image_paths
        self.image_paths2 = image_paths2
        self.labels = torch.LongTensor(labels)
        self.transform = transform
    def __len__(self):
        return len(self.labels)
    def _load(self, p):
        try:
            image = Image.open(p).convert("RGB")
            if self.transform:
                image = self.transform(image)
        except Exception:
            image = torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE)
        return image
    def __getitem__(self, idx):
        im1 = self._load(self.image_paths[idx])
        if self.image_paths2 is not None:
            im2 = self._load(self.image_paths2[idx])
            return torch.stack([im1, im2], dim=0), self.labels[idx]   # [2,3,H,W]
        return im1, self.labels[idx]


class MultimodalDataset(Dataset):
    """
    image_paths2 가 주어지면 두 카메라를 함께 로드해 image 텐서를
    [V=2, 3, H, W] 로 반환 (멀티뷰). has_image 는 Cam1(주 카메라) 존재 기준.
    """
    def __init__(self, sequences, image_paths, labels, transform=None, image_paths2=None):
        self.X_seq = torch.FloatTensor(sequences)
        self.image_paths = image_paths
        self.image_paths2 = image_paths2
        self.labels = torch.LongTensor(labels)
        self.transform = transform
    def __len__(self):
        return len(self.labels)
    def _load(self, path):
        if path and os.path.exists(str(path)):
            try:
                image = Image.open(path).convert("RGB")
                if self.transform:
                    image = self.transform(image)
                return image, True
            except Exception:
                return torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE), False
        return torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE), False
    def __getitem__(self, idx):
        seq = self.X_seq[idx]
        im1, has_image = self._load(self.image_paths[idx])
        if self.image_paths2 is not None:
            im2, _ = self._load(self.image_paths2[idx])
            image = torch.stack([im1, im2], dim=0)               # [2,3,H,W]
        else:
            image = im1
        return seq, image, self.labels[idx], has_image


# Image transforms
train_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
test_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

print("Dataset classes defined.")


# ## 6. Model Definitions

# ============================================================
# Model 1: Sensor-Only (BiLSTM)
# ============================================================
class SensorLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, num_layers=2,
                 num_classes=NUM_CLASSES, dropout=DROPOUT):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=True,
        )
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        hidden = torch.cat([h_n[-2], h_n[-1]], dim=1)
        return self.classifier(hidden)

    def extract_features(self, x):
        _, (h_n, _) = self.lstm(x)
        return torch.cat([h_n[-2], h_n[-1]], dim=1)


# ============================================================
# Model 2: Image-Only (ResNet18 + Transfer Learning)
#   멀티뷰 지원: 입력이 [B, V, 3, H, W] (V=카메라 수) 이면
#   각 뷰를 같은 backbone에 통과시켜 feature를 평균 (해상도 손실 없음).
#   [B, 3, H, W] (단일뷰) 도 그대로 지원 (하위호환).
# ============================================================
class ImageResNet(nn.Module):
    def __init__(self, num_classes=NUM_CLASSES, dropout=DROPOUT):
        super().__init__()
        self.backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        feat_dim = self.backbone.fc.in_features  # 512
        self.backbone.fc = nn.Identity()
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feat_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(128, num_classes),
        )

    def _encode(self, x):
        if x.dim() == 5:                                        # [B, V, 3, H, W]
            B, V = x.shape[:2]
            f = self.backbone(x.reshape(B * V, *x.shape[2:]))  # [B*V, 512]
            return f.view(B, V, -1).mean(dim=1)                # [B, 512] (뷰 평균)
        return self.backbone(x)                                # [B, 512]

    def forward(self, x):
        return self.classifier(self._encode(x))

    def extract_features(self, x):
        return self._encode(x)


# ============================================================
# Model 3: Decision-Level Fusion (Sensor + Image)
# ============================================================
class MultimodalFusion(nn.Module):
    """
    [Image]  -> ResNet18 (frozen) -> f_img   (512)   (멀티뷰면 뷰 평균)
    [Sensor] -> BiLSTM             -> f_sensor (256)
                                       |
                                z = concat (768)
                                       |
                                  FC -> class
    """
    def __init__(self, sensor_input_dim, num_classes=NUM_CLASSES, dropout=DROPOUT):
        super().__init__()
        # Image branch (frozen pretrained)
        resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        img_feat_dim = resnet.fc.in_features  # 512
        resnet.fc = nn.Identity()
        self.image_encoder = resnet
        for p in self.image_encoder.parameters():
            p.requires_grad = False

        # Sensor branch
        self.sensor_lstm = nn.LSTM(
            sensor_input_dim, 128, 2,
            batch_first=True, dropout=dropout, bidirectional=True,
        )
        sensor_feat_dim = 256  # 128*2

        # Fusion head
        self.fusion_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(img_feat_dim + sensor_feat_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_classes),
        )

    def _encode_img(self, images):
        if images.dim() == 5:                                  # [B, V, 3, H, W]
            B, V = images.shape[:2]
            with torch.no_grad():
                f = self.image_encoder(images.reshape(B * V, *images.shape[2:]))
            return f.view(B, V, -1).mean(dim=1)                # [B, 512]
        with torch.no_grad():
            return self.image_encoder(images)

    def forward(self, sensor_seq, images, has_image=None):
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)

        f_image = self._encode_img(images)

        if has_image is not None:
            mask = has_image.float().unsqueeze(1)
            f_image = f_image * mask

        z = torch.cat([f_image, f_sensor], dim=1)
        return self.fusion_head(z)


# ============================================================
# Model 4: Cross-Attention Fusion (개선안 Ⓐ - 최우선)
# ============================================================
class CrossAttentionFusion(nn.Module):
    """
    Cross-Attention Fusion:
      [Image]  -> ResNet18 layer4 (frozen) -> spatial map [B,512,7,7] -> 49 image tokens
                  (멀티뷰 V개면 V*49 토큰: 두 카메라의 위치 토큰을 모두 attention 대상으로)
      [Sensor] -> BiLSTM -> f_sensor (256) -> query
      sensor(Q) 가 image tokens(K,V) 에 attention -> image_context
      z = concat([f_sensor, image_context]) -> FC -> class

    이미지가 없거나(마스킹) 정보량이 낮으면 image_context 기여가 작아져
    f_sensor 경로가 분류를 지배 -> 센서로 자동 폴백 (concat 방식의 노이즈 희석 완화).
    """
    def __init__(self, sensor_input_dim, num_classes=NUM_CLASSES, dropout=DROPOUT,
                 d_model=256, n_heads=4):
        super().__init__()
        # Image branch: avgpool/fc 제거 -> spatial feature map 유지 (frozen)
        resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        self.image_backbone = nn.Sequential(*list(resnet.children())[:-2])  # [B,512,7,7]
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

    def _image_tokens(self, images):
        # 반환: [B, T, 512]  (단일뷰 T=49, 멀티뷰 V개면 T=V*49)
        if images.dim() == 5:                                  # [B, V, 3, H, W]
            B, V = images.shape[:2]
            with torch.no_grad():
                fmap = self.image_backbone(images.reshape(B * V, *images.shape[2:]))  # [B*V,512,h,w]
            c, hh, ww = fmap.shape[1], fmap.shape[2], fmap.shape[3]
            fmap = fmap.view(B, V, c, hh, ww)
            tokens = fmap.flatten(3).permute(0, 1, 3, 2).reshape(B, V * hh * ww, c)   # [B, V*49, 512]
        else:
            with torch.no_grad():
                fmap = self.image_backbone(images)             # [B,512,7,7]
            tokens = fmap.flatten(2).transpose(1, 2)           # [B,49,512]
        return tokens

    def forward(self, sensor_seq, images, has_image=None):
        # Sensor features
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)       # [B,256]
        q = self.sensor_proj(f_sensor).unsqueeze(1)            # [B,1,d]

        tokens = self.img_proj(self._image_tokens(images))     # [B,T,d]

        attn_out, _ = self.cross_attn(q, tokens, tokens)       # [B,1,d]
        attn_out = self.attn_norm(attn_out.squeeze(1))         # [B,d]

        # 이미지 없는 샘플은 image_context=0 -> 센서로 폴백
        if has_image is not None:
            attn_out = attn_out * has_image.float().unsqueeze(1)

        z = torch.cat([f_sensor, attn_out], dim=1)             # [B,256+d]
        return self.fusion_head(z)



print("Models defined.")


# ## 7. Training & Evaluation Functions

def train_epoch(model, loader, criterion, optimizer, model_type):
    model.train()
    total_loss, correct, total = 0, 0, 0
    for batch in loader:
        if model_type == "fusion":
            sensor, images, y, has_img = batch
            sensor, images = sensor.to(DEVICE), images.to(DEVICE)
            y, has_img = y.to(DEVICE), has_img.to(DEVICE)
            logits = model(sensor, images, has_img)
        else:
            X, y = batch
            X, y = X.to(DEVICE), y.to(DEVICE)
            logits = model(X)

        loss = criterion(logits, y)
        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item() * y.size(0)
        correct += (logits.argmax(1) == y).sum().item()
        total += y.size(0)
    return total_loss / total, correct / total


@torch.no_grad()
def evaluate_model(model, loader, criterion, model_type):
    model.eval()
    total_loss, all_preds, all_labels = 0, [], []
    for batch in loader:
        if model_type == "fusion":
            sensor, images, y, has_img = batch
            sensor, images = sensor.to(DEVICE), images.to(DEVICE)
            y, has_img = y.to(DEVICE), has_img.to(DEVICE)
            logits = model(sensor, images, has_img)
        else:
            X, y = batch
            X, y = X.to(DEVICE), y.to(DEVICE)
            logits = model(X)

        total_loss += criterion(logits, y).item() * y.size(0)
        all_preds.extend(logits.argmax(1).cpu().numpy())
        all_labels.extend(y.cpu().numpy())

    preds, labels = np.array(all_preds), np.array(all_labels)
    return {
        "loss": total_loss / len(labels),
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, average="weighted", zero_division=0),
        "precision": precision_score(labels, preds, average="weighted", zero_division=0),
        "recall": recall_score(labels, preds, average="weighted", zero_division=0),
        "preds": preds, "labels": labels,
    }


def run_training(model, train_loader, test_loader, model_type, model_name,
                 epochs=EPOCHS, custom_class_weights=None, lr=LEARNING_RATE,
                 val_loader=None):
    # (2차 개선) val_loader가 주어지면 early stopping·best 모델 선택은 val로만 수행하고
    # test_loader는 학습 종료 후 "최종 평가"에만 사용한다 (val/test 분리 엄밀화).
    eval_loader = val_loader if val_loader is not None else test_loader
    weights = custom_class_weights if custom_class_weights is not None else class_weights
    criterion = nn.CrossEntropyLoss(weight=weights.to(DEVICE))
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr, weight_decay=WEIGHT_DECAY,
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    best_f1, patience_count = 0, 0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_f1": []}

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n{'='*60}")
    print(f" {model_name} | Trainable params: {n_params:,}")
    print(f"{'='*60}")

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, model_type)
        val = evaluate_model(model, eval_loader, criterion, model_type)
        scheduler.step(val["loss"])

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val["loss"])
        history["val_f1"].append(val["f1"])

        print(f"Epoch {epoch:2d}/{epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val['loss']:.4f} F1: {val['f1']:.4f} | "
              f"{time.time()-t0:.1f}s")

        if val["f1"] > best_f1:
            best_f1 = val["f1"]
            patience_count = 0
            torch.save(model.state_dict(), f"{model_name}_best.pt")
        else:
            patience_count += 1
            if patience_count >= 10:
                print(f"Early stopping at epoch {epoch}")
                break

    model.load_state_dict(torch.load(f"{model_name}_best.pt", weights_only=True))
    final = evaluate_model(model, test_loader, criterion, model_type)

    print(f"\n--- {model_name} Final Results ---")
    print(f"Accuracy:  {final['accuracy']:.4f}")
    print(f"Precision: {final['precision']:.4f}")
    print(f"Recall:    {final['recall']:.4f}")
    print(f"F1-Score:  {final['f1']:.4f}")
    print(classification_report(
        final["labels"], final["preds"],
        labels=list(range(NUM_CLASSES)),
        target_names=CLASS_NAMES, zero_division=0,
    ))
    return final, history


print("Training functions ready.")


# ## 8. Model 1: Sensor-Only (BiLSTM)

train_sensor_ds = SensorSequenceDataset(X_train_seq, y_train_seq)
val_sensor_ds = SensorSequenceDataset(X_val_seq, y_val_seq)
test_sensor_ds = SensorSequenceDataset(X_test_seq, y_test_seq)
train_sensor_loader = DataLoader(train_sensor_ds, batch_size=BATCH_SIZE, shuffle=True)
val_sensor_loader = DataLoader(val_sensor_ds, batch_size=BATCH_SIZE)
test_sensor_loader = DataLoader(test_sensor_ds, batch_size=BATCH_SIZE)

sensor_model = SensorLSTM(input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
sensor_result, sensor_history = run_training(
    sensor_model, train_sensor_loader, test_sensor_loader,
    model_type="sensor", model_name="sensor_bilstm",
    val_loader=val_sensor_loader,
)


# ## 9. Model 2: Image-Only (ResNet18)

if HAS_IMAGES:
    df_img_train = df_image[df_image["Cycle_Count_New"].isin(train_cycles)].reset_index(drop=True)
    df_img_val = df_image[df_image["Cycle_Count_New"].isin(val_cycles)].reset_index(drop=True)
    df_img_test = df_image[df_image["Cycle_Count_New"].isin(test_cycles)].reset_index(drop=True)

    train_img_ds = ImageAnomalyDataset(
        df_img_train["cam1_path"].tolist(),
        df_img_train["label_encoded"].values,
        transform=train_transform,
        image_paths2=df_img_train["cam2_path"].tolist(),   # 두 번째 카메라
    )
    test_img_ds = ImageAnomalyDataset(
        df_img_test["cam1_path"].tolist(),
        df_img_test["label_encoded"].values,
        transform=test_transform,
        image_paths2=df_img_test["cam2_path"].tolist(),
    )
    val_img_ds = ImageAnomalyDataset(
        df_img_val["cam1_path"].tolist(),
        df_img_val["label_encoded"].values,
        transform=test_transform,
        image_paths2=df_img_val["cam2_path"].tolist(),
    )
    train_img_loader = DataLoader(train_img_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_img_loader = DataLoader(val_img_ds, batch_size=BATCH_SIZE, num_workers=2)
    test_img_loader = DataLoader(test_img_ds, batch_size=BATCH_SIZE, num_workers=2)

    # 이미지 데이터셋 전용 class weight 계산 (이게 핵심)
    img_train_labels = df_img_train["label_encoded"].values
    img_counter = Counter(img_train_labels)
    img_total = sum(img_counter.values())
    img_class_weights = torch.FloatTensor([
        img_total / (NUM_CLASSES * img_counter.get(i, 1)) for i in range(NUM_CLASSES)
    ])
    img_class_weights = img_class_weights / img_class_weights.sum() * NUM_CLASSES
    print(f"이미지 클래스 분포: {dict(img_counter)}")
    print(f"이미지 전용 class weights: {img_class_weights.tolist()}")

    image_model = ImageResNet().to(DEVICE)
    image_result, image_history = run_training(
        image_model, train_img_loader, test_img_loader,
        model_type="image", model_name="image_resnet18",
        custom_class_weights=img_class_weights,
        val_loader=val_img_loader,
        lr=1e-4,   # iter6: 안정화 fine-tune (ResNet18 전체 FT시 1e-3은 과대 → val F1 출렁)
    )
else:
    print("[SKIP] No image data. Add Kaggle image dataset as input to enable.")
    image_result, image_history = None, None


# ## 10. Model 3: Multimodal Fusion (Sensor + Image)

if HAS_IMAGES:
    # 멀티모달 데이터 생성: cycle state 4,9 시점의 센서 시퀀스 + 두 카메라 이미지
    def create_multimodal_data(data_df, img_df, sensor_cols, seq_len):
        # img_df에서 cam1_path / cam2_path lookup 테이블 생성
        img_lookup, img_lookup2 = {}, {}
        for _, row in img_df.iterrows():
            key = (row["Cycle_Count_New"], row["CycleState"])
            if key not in img_lookup:
                img_lookup[key] = row["cam1_path"]
                img_lookup2[key] = row["cam2_path"]

        X_seq, img_paths, img_paths2, labels = [], [], [], []
        for cycle_id, group in data_df.groupby("Cycle_Count_New"):
            values = group[sensor_cols].values.astype(np.float32)
            lbl = group["label_encoded"].values
            states = group["CycleState"].values
            if len(values) < seq_len:
                continue
            for i in range(len(values) - seq_len):
                t = i + seq_len
                if states[t] in [4, 9]:
                    X_seq.append(values[i:i + seq_len])
                    labels.append(lbl[t])
                    img_paths.append(img_lookup.get((cycle_id, states[t])))
                    img_paths2.append(img_lookup2.get((cycle_id, states[t])))
        return np.array(X_seq), img_paths, img_paths2, np.array(labels)

    print("Creating multimodal dataset...")
    X_train_mm, img_train, img_train2, y_train_mm = create_multimodal_data(
        train_df, df_img_train, SENSOR_COLUMNS, SEQUENCE_LENGTH
    )
    X_val_mm, img_val, img_val2, y_val_mm = create_multimodal_data(
        val_df, df_img_val, SENSOR_COLUMNS, SEQUENCE_LENGTH
    )
    X_test_mm, img_test, img_test2, y_test_mm = create_multimodal_data(
        test_df, df_img_test, SENSOR_COLUMNS, SEQUENCE_LENGTH
    )
    print(f"Train: {X_train_mm.shape}, images(cam1): {sum(1 for p in img_train if p)}, images(cam2): {sum(1 for p in img_train2 if p)}")
    print(f"Test:  {X_test_mm.shape}, images(cam1): {sum(1 for p in img_test if p)}, images(cam2): {sum(1 for p in img_test2 if p)}")

    train_mm_ds = MultimodalDataset(X_train_mm, img_train, y_train_mm, train_transform, image_paths2=img_train2)
    test_mm_ds = MultimodalDataset(X_test_mm, img_test, y_test_mm, test_transform, image_paths2=img_test2)
    val_mm_ds = MultimodalDataset(X_val_mm, img_val, y_val_mm, test_transform, image_paths2=img_val2)
    train_mm_loader = DataLoader(train_mm_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_mm_loader = DataLoader(val_mm_ds, batch_size=BATCH_SIZE, num_workers=2)
    test_mm_loader = DataLoader(test_mm_ds, batch_size=BATCH_SIZE, num_workers=2)

    # Fusion 데이터셋(cycle 4·9 시점) 분포 기반 class weight
    # (센서 전체 분포와 다르므로 fusion 전용으로 재계산해 두 모델에 동일 적용)
    mm_counter = Counter(y_train_mm.tolist())
    mm_total = sum(mm_counter.values())
    mm_class_weights = torch.FloatTensor([
        mm_total / (NUM_CLASSES * mm_counter.get(i, 1)) for i in range(NUM_CLASSES)
    ])
    mm_class_weights = mm_class_weights / mm_class_weights.sum() * NUM_CLASSES
    print(f"Fusion class dist: {dict(mm_counter)}")
    print(f"Fusion class weights: {mm_class_weights.tolist()}")

    # --- (baseline) Decision-Level Concat Fusion ---
    fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    # iter2: 단독 센서(전체 데이터 F1 0.927) LSTM 가중치 warm-start + freeze
    fusion_model.sensor_lstm.load_state_dict(sensor_model.lstm.state_dict())
    for _p in fusion_model.sensor_lstm.parameters():
        _p.requires_grad = False
    # iter3: 이미지 인코더를 학습된 image_model(≈0.99) 가중치로 warm-start (frozen 유지)
    fusion_model.image_encoder.load_state_dict(image_model.backbone.state_dict())
    fusion_result, fusion_history = run_training(
        fusion_model, train_mm_loader, test_mm_loader,
        model_type="fusion", model_name="fusion_dlf",
        custom_class_weights=mm_class_weights,
        val_loader=val_mm_loader,
    )

    # --- (개선 Ⓐ) Cross-Attention Fusion ---
    fusion_attn_model = CrossAttentionFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    # iter2: 센서 LSTM warm-start + freeze
    fusion_attn_model.sensor_lstm.load_state_dict(sensor_model.lstm.state_dict())
    for _p in fusion_attn_model.sensor_lstm.parameters():
        _p.requires_grad = False
    # iter3: 이미지 backbone warm-start (학습된 image_model의 conv 계층, Sequential children[:-2] 매칭)
    fusion_attn_model.image_backbone.load_state_dict(
        nn.Sequential(*list(image_model.backbone.children())[:-2]).state_dict())
    fusion_attn_result, fusion_attn_history = run_training(
        fusion_attn_model, train_mm_loader, test_mm_loader,
        model_type="fusion", model_name="fusion_crossattn",
        custom_class_weights=mm_class_weights,
        val_loader=val_mm_loader,
    )
else:
    print("[SKIP] No image data. Fusion model requires images.")
    fusion_result, fusion_history = None, None
    fusion_attn_result, fusion_attn_history = None, None

# ============================================================
# iter2: 공정 비교(fair eval) — 센서·이미지 단독을 Fusion과 동일한 cycle 4·9 테스트셋에서 재평가
# (기존 sensor_result/image_result는 전체 사이클 셋이라 Fusion과 직접 비교 불가했음)
# ============================================================
if HAS_IMAGES:
    _crit = nn.CrossEntropyLoss()
    sensor_fair_loader = DataLoader(
        SensorSequenceDataset(X_test_mm, y_test_mm), batch_size=BATCH_SIZE)
    sensor_fair = evaluate_model(sensor_model, sensor_fair_loader, _crit, "sensor")

    image_fair_loader = DataLoader(
        ImageAnomalyDataset(img_test, y_test_mm, test_transform, image_paths2=img_test2),
        batch_size=BATCH_SIZE, num_workers=2)
    image_fair = evaluate_model(image_model, image_fair_loader, _crit, "image")

    print("\n" + "=" * 72)
    print(" FAIR COMPARISON  (all models on the SAME cycle 4·9 test set)")
    print("=" * 72)
    print(f"{'Model':<30}{'Accuracy':>10}{'Precision':>10}{'Recall':>10}{'F1':>10}")
    print("-" * 72)
    for _nm, _r in [("Sensor@cyc4_9", sensor_fair), ("Image@cyc4_9", image_fair),
                    ("Fusion-Concat", fusion_result), ("Fusion-CrossAttn", fusion_attn_result)]:
        print(f"{_nm:<30}{_r['accuracy']:>10.4f}{_r['precision']:>10.4f}{_r['recall']:>10.4f}{_r['f1']:>10.4f}")
    print("=" * 72)
    print(f"\n[GOAL] 센서@cyc4_9 F1={sensor_fair['f1']:.4f} | "
          f"best Fusion F1={max(fusion_result['f1'], fusion_attn_result['f1']):.4f} | "
          f"{'DONE: Fusion>=Sensor' if max(fusion_result['f1'], fusion_attn_result['f1']) >= sensor_fair['f1'] else 'not yet'}")
else:
    sensor_fair, image_fair = None, None

# ============================================================
# iter4: Decision-Level(Late) 확률 융합 — 학습된 sensor_model + image_model
# 학습형 fusion head 우회. 이미지 있을 때만 결합, 가중치 w는 validation에서 선택(test 누수 방지, 2차 개선).
# ============================================================
if HAS_IMAGES:
    @torch.no_grad()
    def _softmax_probs(model, loader):
        model.eval(); ps, ys = [], []
        for batch in loader:
            X, y = batch[0], batch[1]
            logits = model(X.to(DEVICE))
            ps.append(torch.softmax(logits, dim=1).cpu().numpy())
            ys.append(y.numpy())
        return np.concatenate(ps), np.concatenate(ys)

    # (2차 개선) w 선택은 validation 멀티모달 셋에서 (test 누수 방지)
    s_va, y_va = _softmax_probs(sensor_model,
        DataLoader(SensorSequenceDataset(X_val_mm, y_val_mm), batch_size=BATCH_SIZE))
    i_va, _ = _softmax_probs(image_model,
        DataLoader(ImageAnomalyDataset(img_val, y_val_mm, test_transform, image_paths2=img_val2), batch_size=BATCH_SIZE, num_workers=2))
    s_te, y_te = _softmax_probs(sensor_model,
        DataLoader(SensorSequenceDataset(X_test_mm, y_test_mm), batch_size=BATCH_SIZE))
    i_te, _ = _softmax_probs(image_model,
        DataLoader(ImageAnomalyDataset(img_test, y_test_mm, test_transform, image_paths2=img_test2), batch_size=BATCH_SIZE, num_workers=2))

    has_tr = np.array([bool(p) for p in img_train])
    has_va = np.array([bool(p) for p in img_val])
    has_te = np.array([bool(p) for p in img_test])

    def _fuse_f1(s_p, i_p, has, y, w):
        p = s_p.copy()
        p[has] = (1 - w) * s_p[has] + w * i_p[has]
        return f1_score(y, p.argmax(1), average="weighted", zero_division=0)

    ws = [k / 20 for k in range(21)]
    best_w = max(ws, key=lambda w: _fuse_f1(s_va, i_va, has_va, y_va, w))

    p_te = s_te.copy()
    p_te[has_te] = (1 - best_w) * s_te[has_te] + best_w * i_te[has_te]
    dlf_pred = p_te.argmax(1)
    decision_fusion_result = {
        "accuracy": accuracy_score(y_te, dlf_pred),
        "precision": precision_score(y_te, dlf_pred, average="weighted", zero_division=0),
        "recall": recall_score(y_te, dlf_pred, average="weighted", zero_division=0),
        "f1": f1_score(y_te, dlf_pred, average="weighted", zero_division=0),
        "preds": dlf_pred, "labels": y_te,
    }
    print("\n" + "=" * 72)
    print(f" DECISION-LEVEL FUSION (late) | best image weight w={best_w:.2f} (tuned on val)")
    print("=" * 72)
    print(f"Sensor@cyc4_9      F1 : {sensor_fair['f1']:.4f}")
    print(f"Fusion-Concat      F1 : {fusion_result['f1']:.4f}")
    print(f"Decision-Fusion    F1 : {decision_fusion_result['f1']:.4f}   "
          f"(img-present {int(has_te.sum())}/{len(has_te)})")
    print("=" * 72)
    print(f"[GOAL-DLF] {'*** ACHIEVED: Decision-Fusion > Sensor ***' if decision_fusion_result['f1'] > sensor_fair['f1'] else 'not yet'}")
    print("=" * 72)
else:
    decision_fusion_result = None

# ============================================================
# [추가분석 ①] 이미지가 실제 존재하는 시점만 비교 (멀티모달 이득 직접 검증)
#   - cycle4·9 테스트 9521 중 ~77%는 이미지 결측 → fusion이 센서로 폴백해 차이가 희석됨.
#   - 이미지가 실제 존재하는 시점에서만 비교해야 "이미지를 더한 효과"가 드러난다.
# ============================================================
if HAS_IMAGES:
    _crit = nn.CrossEntropyLoss()
    m = has_te                       # 이미지 존재 시점 마스크 (cell 위에서 정의됨)
    idx = np.where(m)[0]
    print(f"이미지 존재 시점: {int(m.sum())}/{len(m)} ({100*m.mean():.1f}%)")

    # Sensor 단독
    r_s = evaluate_model(sensor_model,
        DataLoader(SensorSequenceDataset(X_test_mm[m], y_test_mm[m]), batch_size=BATCH_SIZE),
        _crit, "sensor")
    # Image 단독 (두 카메라)
    r_i = evaluate_model(image_model,
        DataLoader(ImageAnomalyDataset([img_test[i] for i in idx], y_test_mm[m], test_transform,
                                       image_paths2=[img_test2[i] for i in idx]),
                   batch_size=BATCH_SIZE, num_workers=2),
        _crit, "image")
    # Fusion (학습형) 두 종 — 이미지 존재 시점만
    mm_sub = DataLoader(MultimodalDataset(X_test_mm[m], [img_test[i] for i in idx], y_test_mm[m],
                                          test_transform, image_paths2=[img_test2[i] for i in idx]),
                        batch_size=BATCH_SIZE, num_workers=2)
    r_fc = evaluate_model(fusion_model, mm_sub, _crit, "fusion")
    r_fa = evaluate_model(fusion_attn_model, mm_sub, _crit, "fusion")
    # Decision-Fusion — 이미 계산된 p_te에서 이미지 존재 시점만 추출
    r_dlf = f1_score(y_test_mm[m], p_te[m].argmax(1), average="weighted", zero_division=0)

    print("=" * 64)
    print(" [이미지 존재 구간만] 멀티모달 이득 검증")
    print("=" * 64)
    print(f"Sensor             F1 : {r_s['f1']:.4f}")
    print(f"Image (2 cameras)  F1 : {r_i['f1']:.4f}")
    print(f"Fusion-Concat      F1 : {r_fc['f1']:.4f}")
    print(f"Fusion-CrossAttn   F1 : {r_fa['f1']:.4f}")
    print(f"Decision-Fusion    F1 : {r_dlf:.4f}")
    best_fusion = max(r_fc["f1"], r_fa["f1"], r_dlf)
    best_single = max(r_s["f1"], r_i["f1"])
    print("=" * 64)
    print(f"best Fusion {best_fusion:.4f}  vs  best Single {best_single:.4f}  ->  "
          f"{'*** 멀티모달 이득 O (Fusion > 둘 다) ***' if best_fusion > best_single else '아직 (단독이 우위)'}")
else:
    print("[SKIP] 이미지 없음")

# ============================================================
# [추가분석 ②] 이미지 약화 통제실험 (modality imbalance ablation)
#   동기: 이미지가 데이터 충분 시 너무 강해(F1~0.93) fusion 이득이 가려진다.
#   이미지 인코더를 의도적으로 적게 학습(저에폭)시켜 "약한 이미지" 시나리오를 만들고,
#   이미지가 실제 존재하는 구간에서 Sensor / Image(weak) / Decision-Fusion 을 비교한다.
#   ※ 의도적 약화임을 명시하는 통제실험 — 주 결과가 아닌 보조 분석.
# ============================================================
if HAS_IMAGES:
    WEAK_EPOCHS = 3
    print(f"\n=== 이미지 약화 학습 ({WEAK_EPOCHS} epochs) ===")
    image_model_weak = ImageResNet().to(DEVICE)
    run_training(image_model_weak, train_img_loader, test_img_loader,
                 model_type="image", model_name="image_weak",
                 epochs=WEAK_EPOCHS, custom_class_weights=img_class_weights)

    @torch.no_grad()
    def _probs_x(model, loader):
        model.eval(); out = []
        for b in loader:
            out.append(torch.softmax(model(b[0].to(DEVICE)), dim=1).cpu().numpy())
        return np.concatenate(out)

    # 이미지가 실제 존재하는 구간 (train: w 튜닝용 / test: 평가용)
    mtr, mte = has_tr, has_te
    itr, ite = np.where(mtr)[0], np.where(mte)[0]
    ytr, yte = y_train_mm[mtr], y_test_mm[mte]

    s_tr2 = _probs_x(sensor_model, DataLoader(SensorSequenceDataset(X_train_mm[mtr], ytr), batch_size=BATCH_SIZE))
    s_te2 = _probs_x(sensor_model, DataLoader(SensorSequenceDataset(X_test_mm[mte], yte), batch_size=BATCH_SIZE))
    iw_tr = _probs_x(image_model_weak, DataLoader(
        ImageAnomalyDataset([img_train[i] for i in itr], ytr, test_transform,
                            image_paths2=[img_train2[i] for i in itr]), batch_size=BATCH_SIZE, num_workers=2))
    iw_te = _probs_x(image_model_weak, DataLoader(
        ImageAnomalyDataset([img_test[i] for i in ite], yte, test_transform,
                            image_paths2=[img_test2[i] for i in ite]), batch_size=BATCH_SIZE, num_workers=2))

    def _f1w(s, i, y, w):
        return f1_score(y, ((1 - w) * s + w * i).argmax(1), average="weighted", zero_division=0)
    bw = max([k / 20 for k in range(21)], key=lambda w: _f1w(s_tr2, iw_tr, ytr, w))

    f_s  = f1_score(yte, s_te2.argmax(1), average="weighted", zero_division=0)
    f_iw = f1_score(yte, iw_te.argmax(1), average="weighted", zero_division=0)
    f_fz = _f1w(s_te2, iw_te, yte, bw)

    print("=" * 64)
    print(f" [통제실험] 이미지 약화({WEAK_EPOCHS}ep) · 이미지 존재 구간 · DLF w={bw:.2f}")
    print("=" * 64)
    print(f"Sensor              F1 : {f_s:.4f}")
    print(f"Image (weak, 2cam)  F1 : {f_iw:.4f}")
    print(f"Decision-Fusion     F1 : {f_fz:.4f}")
    print("=" * 64)
    print(f"{'*** 멀티모달 이득 O: Fusion > 두 단독 ***' if f_fz > max(f_s, f_iw) else '아직 (단독 우위)'}")
else:
    print("[SKIP] 이미지 없음")

# [추가실험 ③] 균형 통제 — 센서도 약화시켜 두 모달리티 비등 상태에서 융합 검증
if HAS_IMAGES:
    SWEAK = 3
    sensor_weak = SensorLSTM(input_dim=NUM_SENSOR_FEATURES, hidden_dim=32).to(DEVICE)
    run_training(sensor_weak, train_sensor_loader, test_sensor_loader,
                 model_type="sensor", model_name="sensor_weak", epochs=SWEAK)

    @torch.no_grad()
    def _pb(model, loader):
        model.eval(); out = []
        for b in loader:
            out.append(torch.softmax(model(b[0].to(DEVICE)), 1).cpu().numpy())
        return np.concatenate(out)

    mtr, mte = has_tr, has_te
    itr, ite = np.where(mtr)[0], np.where(mte)[0]
    ytr, yte = y_train_mm[mtr], y_test_mm[mte]

    sw_tr = _pb(sensor_weak, DataLoader(SensorSequenceDataset(X_train_mm[mtr], ytr), batch_size=BATCH_SIZE))
    sw_te = _pb(sensor_weak, DataLoader(SensorSequenceDataset(X_test_mm[mte], yte), batch_size=BATCH_SIZE))
    iw_tr = _pb(image_model_weak, DataLoader(ImageAnomalyDataset(
        [img_train[i] for i in itr], ytr, test_transform,
        image_paths2=[img_train2[i] for i in itr]), batch_size=BATCH_SIZE, num_workers=2))
    iw_te = _pb(image_model_weak, DataLoader(ImageAnomalyDataset(
        [img_test[i] for i in ite], yte, test_transform,
        image_paths2=[img_test2[i] for i in ite]), batch_size=BATCH_SIZE, num_workers=2))

    def _f1w(s, i, y, w):
        return f1_score(y, ((1 - w) * s + w * i).argmax(1), average="weighted", zero_division=0)
    bw = max([k / 20 for k in range(21)], key=lambda w: _f1w(sw_tr, iw_tr, ytr, w))
    fsw = f1_score(yte, sw_te.argmax(1), average="weighted", zero_division=0)
    fiw = f1_score(yte, iw_te.argmax(1), average="weighted", zero_division=0)
    ffz = _f1w(sw_te, iw_te, yte, bw)

    print("=" * 64)
    print(f" [균형 통제] 센서 약화(h32,{SWEAK}ep) + 이미지 약화 · 이미지 존재 구간 (w={bw:.2f})")
    print("=" * 64)
    print(f"Sensor (weak)    F1 : {fsw:.4f}")
    print(f"Image  (weak)    F1 : {fiw:.4f}")
    print(f"Decision-Fusion  F1 : {ffz:.4f}")
    print("=" * 64)
    print("*** 균형 상태에서 멀티모달 이득 O ***" if ffz > max(fsw, fiw) else "균형에서도 이득 미미 (정직 보고)")

# [추가실험 ④] 부트스트랩 — Fusion > Sensor 차이가 우연인지 95% 신뢰구간으로 판정
if HAS_IMAGES:
    rng = np.random.default_rng(42)
    yb = y_test_mm[has_te]
    s_pred = s_te[has_te].argmax(1)      # 센서 예측 (이미지 존재 구간)
    f_pred = p_te[has_te].argmax(1)      # decision-fusion 예측
    n = len(yb); diffs = []
    for _ in range(1000):
        idx = rng.integers(0, n, n)
        fs = f1_score(yb[idx], f_pred[idx], average="weighted", zero_division=0)
        ss = f1_score(yb[idx], s_pred[idx], average="weighted", zero_division=0)
        diffs.append(fs - ss)
    diffs = np.array(diffs); lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"Fusion - Sensor F1 차이: 평균 {diffs.mean():+.4f}, 95% CI [{lo:+.4f}, {hi:+.4f}]")
    print("→ " + ("유의함 (CI가 0보다 큼)" if lo > 0 else "통계적으로 유의하지 않음 (CI가 0 포함)"))

# [추가실험 ⑤] 균형 통제 v2 — 센서를 강하게 약화하여 진짜 "0.8 vs 0.8" 균형 검증
# 동기: 이전 균형통제(③)는 센서 hidden=32, 3ep으로 약화해도 F1 0.95에 머물렀음.
#       hidden=16, 2ep으로 더 강하게 약화하여 사용자가 원한 ~0.8 수준 달성 목표.
# 평가: 주 평가는 FAIR 전체 9,521 시점 (현실적), 보조로 이미지 존재 구간(2,161)도 출력.
if HAS_IMAGES:
    SHIDDEN = 16
    SEPOCH = 2
    print(f"\n=== 강한 센서 약화 학습: hidden={SHIDDEN}, {SEPOCH} epochs ===")
    sensor_vw = SensorLSTM(input_dim=NUM_SENSOR_FEATURES, hidden_dim=SHIDDEN).to(DEVICE)
    run_training(sensor_vw, train_sensor_loader, test_sensor_loader,
                 model_type="sensor", model_name="sensor_very_weak", epochs=SEPOCH)

    @torch.no_grad()
    def _pb(model, loader):
        model.eval(); out = []
        for b in loader:
            out.append(torch.softmax(model(b[0].to(DEVICE)), 1).cpu().numpy())
        return np.concatenate(out)

    # === 확률 계산 (cycle 4·9 train/test 9,521 전체 시점) ===
    s_tr = _pb(sensor_vw, DataLoader(SensorSequenceDataset(X_train_mm, y_train_mm), batch_size=BATCH_SIZE))
    s_te = _pb(sensor_vw, DataLoader(SensorSequenceDataset(X_test_mm, y_test_mm), batch_size=BATCH_SIZE))
    i_tr = _pb(image_model_weak, DataLoader(
        ImageAnomalyDataset(img_train, y_train_mm, test_transform, image_paths2=img_train2),
        batch_size=BATCH_SIZE, num_workers=2))
    i_te = _pb(image_model_weak, DataLoader(
        ImageAnomalyDataset(img_test, y_test_mm, test_transform, image_paths2=img_test2),
        batch_size=BATCH_SIZE, num_workers=2))

    # === Decision-Fusion 가중치 w 탐색 (train, 이미지 있을 때만 결합) ===
    def _fuse(s, i, has, y, w):
        p = s.copy()
        p[has] = (1 - w) * s[has] + w * i[has]
        return f1_score(y, p.argmax(1), average="weighted", zero_division=0)
    bw = max([k / 20 for k in range(21)], key=lambda w: _fuse(s_tr, i_tr, has_tr, y_train_mm, w))

    # === 평가 1: FAIR 전체 9,521 시점 (주 평가) ===
    f_s = f1_score(y_test_mm, s_te.argmax(1), average="weighted", zero_division=0)
    f_i = f1_score(y_test_mm, i_te.argmax(1), average="weighted", zero_division=0)
    f_fz = _fuse(s_te, i_te, has_te, y_test_mm, bw)

    print("\n" + "=" * 72)
    print(f" [균형 통제 v2] 센서 h{SHIDDEN}/{SEPOCH}ep + 이미지 약화 3ep · FAIR 전체 9,521 시점")
    print("=" * 72)
    print(f"Sensor (very weak)  F1 : {f_s:.4f}   ← ~0.8 목표")
    print(f"Image  (weak)       F1 : {f_i:.4f}   ← 결측 77% 포함 (낮음 정상)")
    print(f"Decision-Fusion     F1 : {f_fz:.4f}   (w={bw:.2f})")
    print("=" * 72)
    if f_fz > max(f_s, f_i):
        print(f"*** FAIR 전체 멀티모달 이득 O ({f_fz:.4f} > Sensor {f_s:.4f}, Image {f_i:.4f}) ***")
    else:
        print(f"FAIR 전체 이득 미미 (정직 보고)")

    # === 평가 2: 이미지 존재 구간 2,161 시점 (보조, "두 모달 비등" 그림) ===
    m = has_te
    f_s_p = f1_score(y_test_mm[m], s_te[m].argmax(1), average="weighted", zero_division=0)
    f_i_p = f1_score(y_test_mm[m], i_te[m].argmax(1), average="weighted", zero_division=0)
    p_pres = (1 - bw) * s_te[m] + bw * i_te[m]
    f_fz_p = f1_score(y_test_mm[m], p_pres.argmax(1), average="weighted", zero_division=0)

    print(f"\n[보조] 같은 모델, 이미지 존재 구간 2,161 시점만:")
    print(f"  Sensor F1            : {f_s_p:.4f}   ← 약화된 센서가 쉬운 구간에서 얼마나 나오나")
    print(f"  Image  F1            : {f_i_p:.4f}   ← 약화된 이미지")
    print(f"  Decision-Fusion F1   : {f_fz_p:.4f}")
    print(f"  → 두 단독 차이: {abs(f_s_p - f_i_p):.4f} (0에 가까울수록 균형)")
    if f_fz_p > max(f_s_p, f_i_p):
        print(f"  *** 균형 구간 멀티모달 이득 O ***")
    print("=" * 72)


# ## 11. Results Comparison

# 결과 수집
all_results = {"Sensor (BiLSTM)": sensor_result}
all_histories = {"Sensor (BiLSTM)": sensor_history}
if image_result:
    all_results["Image (ResNet18)"] = image_result
    all_histories["Image (ResNet18)"] = image_history
if fusion_result:
    all_results["Fusion-Concat"] = fusion_result
    all_histories["Fusion-Concat"] = fusion_history
if fusion_attn_result:
    all_results["Fusion-CrossAttn"] = fusion_attn_result
    all_histories["Fusion-CrossAttn"] = fusion_attn_history

# 성능 비교 바 차트
fig, ax = plt.subplots(figsize=(10, 6))
metrics = ["accuracy", "precision", "recall", "f1"]
metric_labels = ["Accuracy", "Precision", "Recall", "F1-Score"]
x = np.arange(len(metrics))
width = 0.25
colors = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63", "#9C27B0"]

for i, (name, res) in enumerate(all_results.items()):
    vals = [res[m] for m in metrics]
    bars = ax.bar(x + i * width, vals, width, label=name, color=colors[i % len(colors)])
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()+0.01,
                f"{v:.3f}", ha="center", fontsize=9)

ax.set_ylabel("Score")
ax.set_title("Model Performance Comparison (per-model default eval set / fair comparison: see FAIR cells)")
ax.set_xticks(x + width * (len(all_results)-1)/2)
ax.set_xticklabels(metric_labels)
ax.legend()
ax.set_ylim(0, 1.15)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.show()

# Confusion Matrix
fig, axes = plt.subplots(1, len(all_results), figsize=(7*len(all_results), 6))
if len(all_results) == 1:
    axes = [axes]

for ax, (name, res) in zip(axes, all_results.items()):
    cm = confusion_matrix(res["labels"], res["preds"])
    cm_norm = cm.astype("float") / cm.sum(axis=1, keepdims=True)
    sns.heatmap(cm_norm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, ax=ax)
    ax.set_title(name)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")

plt.tight_layout()
plt.show()

# 학습 곡선
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for name, hist in all_histories.items():
    ep = range(1, len(hist["train_loss"])+1)
    axes[0].plot(ep, hist["train_loss"], label=f"{name} (train)")
    axes[0].plot(ep, hist["val_loss"], "--", label=f"{name} (val)")
    axes[1].plot(ep, hist["val_f1"], label=name)

axes[0].set_title("Loss"); axes[0].set_xlabel("Epoch"); axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)
axes[1].set_title("Validation F1"); axes[1].set_xlabel("Epoch"); axes[1].legend(fontsize=8); axes[1].grid(alpha=0.3)
plt.tight_layout()
plt.show()

# 최종 요약
print("\n" + "="*70)
print(" FINAL RESULTS SUMMARY")
print("="*70)
print(f"{'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
print("-"*70)
for name, res in all_results.items():
    print(f"{name:<25} {res['accuracy']:>10.4f} {res['precision']:>10.4f} "
          f"{res['recall']:>10.4f} {res['f1']:>10.4f}")
print("="*70)
print("\nDone!")


# ## 12. 이미지 열화 견고성 실험 (Robustness to Image Degradation)
# 
# 실제 공장은 조명·가려짐·노이즈로 이미지가 자주 나빠진다. 학습된 모델을 그대로 두고 **테스트 이미지만 점점 열화**(블러+조명변화+가림)시켜, 이미지 존재 구간(3,912 시점)에서 각 모델의 견고성을 추론만으로 비교한다. (재학습 없음)

# === 이미지 열화 견고성 실험 (학습된 모델로 추론만, 깨끗/중간열화/강열화) ===
from torchvision import transforms as _T
from sklearn.metrics import f1_score as _f1
import numpy as _np, torch as _torch
from torch.utils.data import DataLoader as _DL

if HAS_IMAGES:
    _MEAN=[0.485,0.456,0.406]; _STD=[0.229,0.224,0.225]
    clean_tf  = test_transform
    mild_tf   = _T.Compose([_T.Resize((IMAGE_SIZE,IMAGE_SIZE)), _T.ColorJitter(0.3,0.3),
                            _T.GaussianBlur(5,(0.6,1.2)), _T.ToTensor(), _T.Normalize(_MEAN,_STD),
                            _T.RandomErasing(p=0.5,scale=(0.04,0.10))])
    strong_tf = _T.Compose([_T.Resize((IMAGE_SIZE,IMAGE_SIZE)), _T.ColorJitter(0.6,0.6),
                            _T.GaussianBlur(9,(2.0,4.0)), _T.ToTensor(), _T.Normalize(_MEAN,_STD),
                            _T.RandomErasing(p=1.0,scale=(0.15,0.30))])

    @_torch.no_grad()
    def _pi(model,p1,p2,y,tf):
        dl=_DL(ImageAnomalyDataset(p1,y,tf,image_paths2=p2),batch_size=BATCH_SIZE,num_workers=2)
        return _np.concatenate([_torch.softmax(model(b[0].to(DEVICE)),1).cpu().numpy() for b in dl])
    @_torch.no_grad()
    def _ps(model,X,y):
        dl=_DL(SensorSequenceDataset(X,y),batch_size=BATCH_SIZE)
        return _np.concatenate([_torch.softmax(model(b[0].to(DEVICE)),1).cpu().numpy() for b in dl])
    @_torch.no_grad()
    def _ff(model,X,p1,p2,y,tf):
        dl=_DL(MultimodalDataset(X,p1,y,tf,image_paths2=p2),batch_size=BATCH_SIZE,num_workers=2)
        P=[]
        for s,im,_,hi in dl: P.append(model(s.to(DEVICE),im.to(DEVICE),hi.to(DEVICE)).argmax(1).cpu().numpy())
        return _f1(y,_np.concatenate(P),average="weighted",zero_division=0)

    _m=has_te; _idx=_np.where(_m)[0]
    _Xm,_ym=X_test_mm[_m],y_test_mm[_m]
    _p1=[img_test[i] for i in _idx]; _p2=[img_test2[i] for i in _idx]
    _ste=_ps(sensor_model,_Xm,_ym); _fsen=_f1(_ym,_ste.argmax(1),average="weighted",zero_division=0)
    _itr=_np.where(has_va)[0]
    _str=_ps(sensor_model,X_val_mm[has_va],y_val_mm[has_va])
    _itrp=_pi(image_model,[img_val[i] for i in _itr],[img_val2[i] for i in _itr],y_val_mm[has_va],clean_tf)
    def _fz(s,i,y,w): return _f1(y,((1-w)*s+w*i).argmax(1),average="weighted",zero_division=0)
    _bw=max([k/20 for k in range(21)],key=lambda w:_fz(_str,_itrp,y_val_mm[has_va],w))

    def run_deg(tf,tag):
        _ite=_pi(image_model,_p1,_p2,_ym,tf)
        print(f"\n[{tag}]  (이미지 존재 {int(_m.sum())} 시점, w={_bw:.2f})")
        print(f"  Sensor           F1 : {_fsen:.4f}")
        print(f"  Image            F1 : {_f1(_ym,_ite.argmax(1),average='weighted',zero_division=0):.4f}")
        print(f"  Fusion-Concat    F1 : {_ff(fusion_model,_Xm,_p1,_p2,_ym,tf):.4f}")
        print(f"  Fusion-CrossAttn F1 : {_ff(fusion_attn_model,_Xm,_p1,_p2,_ym,tf):.4f}")
        print(f"  Decision-Fusion  F1 : {_fz(_ste,_ite,_ym,_bw):.4f}")

    print("="*64); print(" [이미지 열화 견고성] 깨끗 / 중간열화 / 강열화")
    run_deg(clean_tf,  "깨끗한 이미지")
    run_deg(mild_tf,   "중간 열화 (약한 블러+조명+가림 절반)")
    run_deg(strong_tf, "강한 열화 (강한 블러+조명+가림 전체)")
    print("="*64)
else:
    print("[SKIP] 이미지 없음")


# ## 13. 분류 예시 시각화 — 이미지 + 센서 + 모달리티별 예측 (정답/오답)
# 
# 테스트셋(이미지 존재 구간)에서 **정답 사례(정상 Normal 포함, 각 클래스 고루)와 오답 사례**를 뽑아,
# 한 예시를 **2×2 레이아웃**(위: Cam1·Cam2 이미지 / 아래: 같은 시점 센서 윈도우·융합 클래스별 확률)으로 표시한다.
# 정답 중 일부는 단독 모델(센서 또는 이미지)이 틀렸으나 융합이 바로잡은 사례이며, 각 패널 제목에 센서·이미지·융합의 예측을 병기한다.
# 정답/오답을 각각 `classification_correct.png` / `classification_wrong.png`로 저장한다. (★ = 실제 클래스)

# ============================================================
# [13] 분류 예시 시각화 — 이미지 + 센서 + 모달리티별 예측 (정답/오답, 2x2 레이아웃)
#   - 각 클래스(Normal 포함) 정답을 1개씩 보장 + 일부는 '융합이 단독오류 보정' 사례
#   - 한 예시 = 2x2 (위: Cam1/Cam2, 아래: 센서 윈도우/융합 확률), 정답·오답 2장 저장
# ============================================================
if HAS_IMAGES:
    import torch.nn.functional as _F
    import matplotlib.gridspec as _gridspec
    from PIL import Image as _PILImage

    _m = np.array([bool(p) for p in img_test]); _idx = np.where(_m)[0]
    _Xv = X_test_mm[_m]; _yv = y_test_mm[_m]
    _p1 = [img_test[i] for i in _idx]; _p2 = [img_test2[i] for i in _idx]

    _dl = DataLoader(MultimodalDataset(_Xv, _p1, _yv, test_transform, image_paths2=_p2),
                     batch_size=BATCH_SIZE, num_workers=2)
    for _mdl in (sensor_model, image_model, fusion_model): _mdl.eval()
    _Ps, _Pi, _Pf = [], [], []
    with torch.no_grad():
        for _s, _im, _, _hi in _dl:
            _s, _im, _hi = _s.to(DEVICE), _im.to(DEVICE), _hi.to(DEVICE)
            _Ps.append(_F.softmax(sensor_model(_s), 1).cpu().numpy())
            _Pi.append(_F.softmax(image_model(_im), 1).cpu().numpy())
            _Pf.append(_F.softmax(fusion_model(_s, _im, _hi), 1).cpu().numpy())
    _Ps, _Pi, _Pf = map(np.concatenate, (_Ps, _Pi, _Pf))
    _ps, _pi, _pf = _Ps.argmax(1), _Pi.argmax(1), _Pf.argmax(1)

    # 정답: 각 클래스(Normal 포함)에서 1개씩(융합 보정 사례 우선) + 보정 사례로 6개 채움
    _rng = np.random.default_rng(SEED)
    _cor = np.where(_pf == _yv)[0]; _wr = np.where(_pf != _yv)[0]
    _saved = set(i for i in _cor if _ps[i] != _yv[i] or _pi[i] != _yv[i])
    _sel_c = []
    for _cls in range(NUM_CLASSES):
        _cands = [i for i in _cor if _yv[i] == _cls]
        if not _cands: continue
        _pool = [i for i in _cands if i in _saved] or _cands
        _sel_c.append(int(_rng.choice(_pool)))
    _extra = [i for i in _cor if i in _saved and i not in _sel_c]; _rng.shuffle(_extra)
    _sel_c = (_sel_c + _extra)[:6]
    _sel_w = list(_rng.permutation(_wr))[:4]

    _chs = [SENSOR_COLUMNS.index(c) for c in
            ["I_R04_Gripper_Load", "M_R01_SJointAngle_Degree", "Q_VFD1_Temperature"] if c in SENSOR_COLUMNS]

    def _draw(sel, tag, fname):
        n = len(sel)
        if n == 0: return
        fig = plt.figure(figsize=(11, 5.6 * n))
        outer = _gridspec.GridSpec(n, 1, hspace=0.5)
        col = "green" if tag == "CORRECT" else "red"
        for s, i in enumerate(sel):
            inr = _gridspec.GridSpecFromSubplotSpec(2, 2, subplot_spec=outer[s], hspace=0.3, wspace=0.18)
            a = fig.add_subplot(inr[0, 0])
            try: a.imshow(_PILImage.open(_p1[i]).convert("RGB"))
            except Exception: pass
            a.set_title(f"Example {s+1}  [{tag}]   |   Cam1", color=col, fontsize=12, fontweight="bold"); a.axis("off")
            a = fig.add_subplot(inr[0, 1])
            try: a.imshow(_PILImage.open(_p2[i]).convert("RGB"))
            except Exception: pass
            a.set_title("Cam2", fontsize=12); a.axis("off")
            a = fig.add_subplot(inr[1, 0])
            for ci in _chs: a.plot(_Xv[i][:, ci], lw=1.2, label=SENSOR_COLUMNS[ci][:16])
            a.set_title("Sensor window (50 steps, standardized)", fontsize=10); a.legend(fontsize=8, loc="upper right")
            a = fig.add_subplot(inr[1, 1])
            bc = ["#cccccc"] * NUM_CLASSES; bc[_pf[i]] = col
            a.barh(range(NUM_CLASSES), _Pf[i] * 100, color=bc)
            a.set_yticks(range(NUM_CLASSES)); a.set_yticklabels(CLASS_NAMES, fontsize=9)
            a.invert_yaxis(); a.set_xlim(0, 100); a.set_xlabel("Fusion probability (%)", fontsize=10)
            a.plot(2, _yv[i], marker="*", color="blue", markersize=15)
            a.set_title(f"Fusion: {CLASS_NAMES[_pf[i]]} {_Pf[i][_pf[i]]*100:.0f}%  (True: {CLASS_NAMES[_yv[i]]})\n"
                        f"Sensor->{CLASS_NAMES[_ps[i]][:12]} | Image->{CLASS_NAMES[_pi[i]][:12]}", fontsize=9.5, color=col)
        fig.suptitle(f"{tag} examples   |   bars: green=correct / red=wrong / gray=other,   * (blue) = true class",
                     fontsize=12, y=1.0)
        plt.savefig(fname, dpi=140, bbox_inches="tight"); plt.show(); print("saved", fname)

    _draw(_sel_c, "CORRECT", "classification_correct.png")
    _draw(_sel_w, "WRONG", "classification_wrong.png")
    print(f"분류 예시 저장 | 정답 {len(_sel_c)}(클래스 커버리지 포함) / 오답 {len(_sel_w)}")
else:
    print("[SKIP] No image data.")
