"""
=============================================================================
 멀티모달 딥러닝 기반 제조 공정 이상 탐지
 (이미지 + 시계열 센서 데이터)

 - Kaggle Notebook용 전체 파이프라인
 - Future Factories Dataset 사용
 - 3가지 모델 비교: 센서 단독 / 이미지 단독 / 멀티모달 융합
=============================================================================

Kaggle에서 실행 시 필요한 Input Datasets:
  1. "ff-2023-12-12-multi-modal-dataset-16" (이미지 원본, Kaggle 공개 데이터)
  2. "ff-multimodal-csv" (직접 업로드한 전처리 CSV)
     → FF_Multimodal.csv를 Kaggle에 Dataset으로 업로드

GPU Accelerator를 켜고 실행하세요 (Settings > Accelerator > GPU T4 x2)
"""

# %%  [1] Setup
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
from torch.utils.data import Dataset, DataLoader, random_split
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

# %%  [2] Configuration
# ──────────────────────────────────────────────
# Kaggle 경로 설정
# ──────────────────────────────────────────────

# 방법 1: Kaggle Notebook에서 실행
KAGGLE_BASE = "/kaggle/input"
CSV_PATH_KAGGLE = os.path.join(KAGGLE_BASE, "ff-multimodal-csv", "FF_Multimodal.csv")

# Kaggle 이미지 데이터셋 (여러 파트 자동 탐색)
KAGGLE_IMAGE_PARTS = [
    "ff-2023-12-12-multi-modal-dataset-16",
    "ff-2023-12-12-multi-modal-dataset-26",
    "ff-2023-12-12-multi-modal-dataset-36",
    "ff-2023-12-12-multi-modal-dataset-46",
    "ff-2023-12-12-multi-modal-dataset-56",
    "ff-2023-12-12-multi-modal-dataset-66",
]

# 방법 2: 로컬에서 실행 (경로 수정)
CSV_PATH_LOCAL = "data/Multi-modal Dataset/FF_Multimodal.csv"
LOCAL_IMAGE_ROOT = "data/raw"

# 자동 경로 선택
if os.path.exists(CSV_PATH_KAGGLE):
    CSV_PATH = CSV_PATH_KAGGLE
    ON_KAGGLE = True
    print("Running on Kaggle")
elif os.path.exists(CSV_PATH_LOCAL):
    CSV_PATH = CSV_PATH_LOCAL
    ON_KAGGLE = False
    print("Running locally")
else:
    raise FileNotFoundError("CSV 파일을 찾을 수 없습니다. 경로를 확인하세요.")

# 하이퍼파라미터
BATCH_SIZE = 32
EPOCHS = 30
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
DROPOUT = 0.5
SEQUENCE_LENGTH = 50     # LSTM 입력 시퀀스 길이
IMAGE_SIZE = 224
NUM_CLASSES = 5           # 5개 이상 유형 (소수 클래스 병합)
TRAIN_RATIO = 0.8

# 센서 컬럼 정의 (40개 중 핵심 센서만 선택)
SENSOR_COLUMNS = [
    # 그리퍼 로드셀 (4개 로봇)
    "I_R01_Gripper_Load", "I_R02_Gripper_Load",
    "I_R03_Gripper_Load", "I_R04_Gripper_Load",
    # 그리퍼 포텐셔미터
    "I_R01_Gripper_Pot", "I_R02_Gripper_Pot",
    "I_R03_Gripper_Pot", "I_R04_Gripper_Pot",
    # VFD 온도
    "Q_VFD1_Temperature", "Q_VFD2_Temperature",
    "Q_VFD3_Temperature", "Q_VFD4_Temperature",
    # 컨베이어 속도
    "M_Conv1_Speed_mmps", "M_Conv2_Speed_mmps",
    "M_Conv3_Speed_mmps", "M_Conv4_Speed_mmps",
    # Robot 1 관절 각도 (이상에 민감)
    "M_R01_SJointAngle_Degree", "M_R01_LJointAngle_Degree",
    "M_R01_UJointAngle_Degree",
    # Robot 4 관절 각도
    "M_R04_SJointAngle_Degree", "M_R04_LJointAngle_Degree",
    "M_R04_UJointAngle_Degree",
]
NUM_SENSOR_FEATURES = len(SENSOR_COLUMNS)
print(f"Using {NUM_SENSOR_FEATURES} sensor features")

# %%  [3] Data Loading & EDA
print("Loading CSV...")
df = pd.read_csv(CSV_PATH, low_memory=False)
print(f"Shape: {df.shape}")

# ── 라벨 정리 ──
# 소수 클래스 병합: NoBody2, NoBody2+NoBody1 → NoBody1에 포함
# E_STOPPED → 제거 (69건, 센서 오류)
label_map = {
    "Normal": "Normal",
    "NoBody1": "NoBody1",
    "NoNose": "NoNose",
    "NoNose,NoBody2": "NoNose_NoBody2",
    "NoNose,NoBody2,NoBody1": "NoNose_NoBody2_NoBody1",
    "NoBody2": "NoBody1",            # 소수 → NoBody1에 병합
    "NoBody2,NoBody1": "NoBody1",    # 소수 → NoBody1에 병합
}

df = df[df["actual_state"] != "E_STOPPED"].copy()
df["label"] = df["actual_state"].map(label_map)
df = df.dropna(subset=["label"]).reset_index(drop=True)

print(f"\nFiltered shape: {df.shape}")
print(f"\nLabel distribution:")
print(df["label"].value_counts())

# 라벨 인코딩
le = LabelEncoder()
df["label_encoded"] = le.fit_transform(df["label"])
CLASS_NAMES = list(le.classes_)
NUM_CLASSES = len(CLASS_NAMES)
print(f"\nClasses ({NUM_CLASSES}): {CLASS_NAMES}")
print(f"Encoding: {dict(zip(CLASS_NAMES, le.transform(CLASS_NAMES)))}")

# %%  [4] EDA - 데이터 분포 시각화
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# 4-1. 클래스 분포
df["label"].value_counts().plot(kind="bar", ax=axes[0], color="steelblue")
axes[0].set_title("Anomaly Type Distribution")
axes[0].set_ylabel("Count")
axes[0].tick_params(axis="x", rotation=30)

# 4-2. Cycle State 분포
df["CycleState"].value_counts().sort_index().plot(kind="bar", ax=axes[1], color="coral")
axes[1].set_title("Cycle State Distribution")
axes[1].set_ylabel("Count")

# 4-3. 핵심 센서 분포 (정상 vs 이상)
normal = df[df["label"] == "Normal"]["I_R04_Gripper_Load"]
anomaly = df[df["label"] != "Normal"]["I_R04_Gripper_Load"]
axes[2].hist(normal, bins=50, alpha=0.6, label="Normal", density=True)
axes[2].hist(anomaly, bins=50, alpha=0.6, label="Anomaly", density=True)
axes[2].set_title("R04 Gripper Load: Normal vs Anomaly")
axes[2].legend()

plt.tight_layout()
plt.savefig("eda_overview.png", dpi=150, bbox_inches="tight")
plt.show()

# %%  [5] Image Path Resolution (Kaggle)
def find_image_path(relative_path):
    """
    CSV의 상대 경로(예: Dataset/BATCH1000/000000_0.png)를
    Kaggle 절대 경로로 변환한다.
    여러 파트에서 탐색하여 실제 존재하는 경로를 반환한다.
    """
    if not ON_KAGGLE:
        full = os.path.join(LOCAL_IMAGE_ROOT, relative_path)
        return full if os.path.exists(full) else None

    for part in KAGGLE_IMAGE_PARTS:
        full = os.path.join(KAGGLE_BASE, part, relative_path)
        if os.path.exists(full):
            return full
    return None


# Cycle state 4, 9만 필터 (로켓 부품이 카메라에 보이는 상태)
df_image = df[df["CycleState"].isin([4, 9])].copy()
print(f"Image-eligible rows (state 4,9): {len(df_image)}")

# 실제 존재하는 이미지 탐색 (Kaggle에서만 의미 있음)
print("Resolving image paths...")
if ON_KAGGLE:
    # 일부만 샘플링하여 경로 테스트
    sample_paths = df_image["Cam1"].head(100).tolist()
    found = sum(1 for p in sample_paths if find_image_path(p) is not None)
    print(f"Sample test: {found}/100 images found")

    # 전체 경로 매핑
    df_image["cam1_path"] = df_image["Cam1"].apply(find_image_path)
    df_image["cam2_path"] = df_image["Cam2"].apply(find_image_path)
    df_image = df_image.dropna(subset=["cam1_path"]).reset_index(drop=True)
    print(f"Images with valid paths: {len(df_image)}")
else:
    print("Local mode: image paths will be resolved at load time")
    df_image["cam1_path"] = df_image["Cam1"]
    df_image["cam2_path"] = df_image["Cam2"]

# %%  [6] Preprocessing - Sensor Data
print("Preprocessing sensor data...")

# 센서 정규화
scaler = StandardScaler()
df[SENSOR_COLUMNS] = scaler.fit_transform(df[SENSOR_COLUMNS])

# ── Cycle-wise split ──
# 같은 사이클의 데이터가 train/test에 섞이면 data leakage
cycles = df["Cycle_Count_New"].unique()
cycle_has_anomaly = df.groupby("Cycle_Count_New")["label"].apply(
    lambda x: (x != "Normal").any()
).astype(int)

train_cycles, test_cycles = train_test_split(
    cycles,
    train_size=TRAIN_RATIO,
    random_state=SEED,
    stratify=[cycle_has_anomaly[c] for c in cycles],
)
print(f"Train cycles: {len(train_cycles)}, Test cycles: {len(test_cycles)}")

train_df = df[df["Cycle_Count_New"].isin(train_cycles)].reset_index(drop=True)
test_df = df[df["Cycle_Count_New"].isin(test_cycles)].reset_index(drop=True)

print(f"Train: {len(train_df)} samples")
print(f"Test:  {len(test_df)} samples")
print(f"\nTrain label dist:\n{train_df['label'].value_counts()}")
print(f"\nTest label dist:\n{test_df['label'].value_counts()}")

# ── 시계열 시퀀스 생성 (Sliding Window) ──
def create_sequences_by_cycle(data_df, sensor_cols, seq_len, label_col="label_encoded"):
    """사이클 단위로 sliding window 시퀀스를 생성한다."""
    X_list, y_list = [], []
    for cycle_id, group in data_df.groupby("Cycle_Count_New"):
        values = group[sensor_cols].values.astype(np.float32)
        labels = group[label_col].values

        if len(values) < seq_len:
            continue

        for i in range(len(values) - seq_len):
            X_list.append(values[i:i + seq_len])
            y_list.append(labels[i + seq_len])

    return np.array(X_list), np.array(y_list)

print("\nCreating sequences...")
X_train_seq, y_train_seq = create_sequences_by_cycle(
    train_df, SENSOR_COLUMNS, SEQUENCE_LENGTH
)
X_test_seq, y_test_seq = create_sequences_by_cycle(
    test_df, SENSOR_COLUMNS, SEQUENCE_LENGTH
)
print(f"Train sequences: {X_train_seq.shape}")
print(f"Test sequences:  {X_test_seq.shape}")

# ── 클래스 가중치 계산 ──
counter = Counter(y_train_seq)
total = len(y_train_seq)
class_weights = torch.FloatTensor([
    total / (NUM_CLASSES * counter.get(i, 1)) for i in range(NUM_CLASSES)
])
class_weights = class_weights / class_weights.sum() * NUM_CLASSES
print(f"\nClass weights: {class_weights.tolist()}")

# %%  [7] Dataset Classes
class SensorSequenceDataset(Dataset):
    """시계열 센서 시퀀스 Dataset"""
    def __init__(self, sequences, labels):
        self.X = torch.FloatTensor(sequences)
        self.y = torch.LongTensor(labels)
    def __len__(self):
        return len(self.y)
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class ImageAnomalyDataset(Dataset):
    """이미지 Dataset (Cycle state 4, 9 전용)"""
    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = torch.LongTensor(labels)
        self.transform = transform

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        path = self.image_paths[idx]
        try:
            image = Image.open(path).convert("RGB")
            if self.transform:
                image = self.transform(image)
        except Exception:
            image = torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE)
        return image, self.labels[idx]


class MultimodalDataset(Dataset):
    """센서 시퀀스 + 이미지 동시 로드"""
    def __init__(self, sequences, image_paths, labels, transform=None):
        self.X_seq = torch.FloatTensor(sequences)
        self.image_paths = image_paths
        self.labels = torch.LongTensor(labels)
        self.transform = transform

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        seq = self.X_seq[idx]
        path = self.image_paths[idx]
        has_image = False

        if path and os.path.exists(str(path)):
            try:
                image = Image.open(path).convert("RGB")
                if self.transform:
                    image = self.transform(image)
                has_image = True
            except Exception:
                image = torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE)
        else:
            image = torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE)

        return seq, image, self.labels[idx], has_image


# Image transforms
train_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])
test_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# %%  [8] Model Definitions

# ── Model 1: Sensor-Only (BiLSTM) ──
class SensorLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, num_layers=2,
                 num_classes=NUM_CLASSES, dropout=DROPOUT):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0,
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


# ── Model 2: Image-Only (ResNet18) ──
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

    def forward(self, x):
        features = self.backbone(x)
        return self.classifier(features)

    def extract_features(self, x):
        return self.backbone(x)


# ── Model 3: Multimodal Fusion (Sensor + Image) ──
class MultimodalFusion(nn.Module):
    """
    Decision-Level Fusion:
      [Image] -> ResNet18(frozen) -> f_img (512)
      [Sensor] -> BiLSTM -> f_sensor (256)
                                |
                         z = [f_img ; f_sensor]  (768)
                                |
                         FC -> Classification
    """
    def __init__(self, sensor_input_dim, num_classes=NUM_CLASSES, dropout=DROPOUT):
        super().__init__()
        # Image branch (frozen)
        resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        img_feat_dim = resnet.fc.in_features  # 512
        resnet.fc = nn.Identity()
        self.image_encoder = resnet
        for param in self.image_encoder.parameters():
            param.requires_grad = False

        # Sensor branch
        self.sensor_lstm = nn.LSTM(
            sensor_input_dim, 128, 2,
            batch_first=True, dropout=dropout, bidirectional=True,
        )
        sensor_feat_dim = 256  # 128 * 2 (bidirectional)

        # Fusion head
        fusion_dim = img_feat_dim + sensor_feat_dim  # 768
        self.fusion_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(fusion_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, sensor_seq, images, has_image=None):
        # Sensor features
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)

        # Image features
        with torch.no_grad():
            f_image = self.image_encoder(images)

        # 이미지 없는 샘플 마스킹
        if has_image is not None:
            mask = has_image.float().unsqueeze(1)
            f_image = f_image * mask

        z = torch.cat([f_image, f_sensor], dim=1)
        return self.fusion_head(z)


# %%  [9] Training & Evaluation Functions

def train_epoch(model, loader, criterion, optimizer, model_type="sensor"):
    model.train()
    total_loss, correct, total = 0, 0, 0

    for batch in loader:
        if model_type == "sensor":
            X, y = batch
            X, y = X.to(DEVICE), y.to(DEVICE)
            logits = model(X)
        elif model_type == "image":
            X, y = batch
            X, y = X.to(DEVICE), y.to(DEVICE)
            logits = model(X)
        elif model_type == "fusion":
            sensor, images, y, has_img = batch
            sensor = sensor.to(DEVICE)
            images = images.to(DEVICE)
            y = y.to(DEVICE)
            has_img = has_img.to(DEVICE)
            logits = model(sensor, images, has_img)

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
def evaluate_model(model, loader, criterion, model_type="sensor"):
    model.eval()
    total_loss, all_preds, all_labels = 0, [], []

    for batch in loader:
        if model_type == "sensor":
            X, y = batch
            X, y = X.to(DEVICE), y.to(DEVICE)
            logits = model(X)
        elif model_type == "image":
            X, y = batch
            X, y = X.to(DEVICE), y.to(DEVICE)
            logits = model(X)
        elif model_type == "fusion":
            sensor, images, y, has_img = batch
            sensor = sensor.to(DEVICE)
            images = images.to(DEVICE)
            y = y.to(DEVICE)
            has_img = has_img.to(DEVICE)
            logits = model(sensor, images, has_img)

        loss = criterion(logits, y)
        total_loss += loss.item() * y.size(0)
        all_preds.extend(logits.argmax(1).cpu().numpy())
        all_labels.extend(y.cpu().numpy())

    preds = np.array(all_preds)
    labels = np.array(all_labels)
    return {
        "loss": total_loss / len(labels),
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, average="weighted", zero_division=0),
        "precision": precision_score(labels, preds, average="weighted", zero_division=0),
        "recall": recall_score(labels, preds, average="weighted", zero_division=0),
        "preds": preds,
        "labels": labels,
    }


def run_training(model, train_loader, test_loader, model_type, model_name,
                 epochs=EPOCHS):
    """Full training pipeline with LR scheduler and early stopping."""
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(DEVICE))
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY,
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=5, factor=0.5
    )

    best_f1, patience_count = 0, 0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_f1": []}

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n{'='*60}")
    print(f" {model_name} | Trainable params: {n_params:,}")
    print(f"{'='*60}")

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, model_type
        )
        val = evaluate_model(model, test_loader, criterion, model_type)
        scheduler.step(val["loss"])

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val["loss"])
        history["val_f1"].append(val["f1"])

        elapsed = time.time() - t0
        print(
            f"Epoch {epoch:2d}/{epochs} | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
            f"Val Loss: {val['loss']:.4f} F1: {val['f1']:.4f} | "
            f"{elapsed:.1f}s"
        )

        if val["f1"] > best_f1:
            best_f1 = val["f1"]
            patience_count = 0
            torch.save(model.state_dict(), f"{model_name}_best.pt")
        else:
            patience_count += 1
            if patience_count >= 10:
                print(f"Early stopping at epoch {epoch}")
                break

    # Best model reload & final eval
    model.load_state_dict(torch.load(f"{model_name}_best.pt", weights_only=True))
    final = evaluate_model(model, test_loader, criterion, model_type)

    print(f"\n--- {model_name} Final Results ---")
    print(f"Accuracy:  {final['accuracy']:.4f}")
    print(f"Precision: {final['precision']:.4f}")
    print(f"Recall:    {final['recall']:.4f}")
    print(f"F1-Score:  {final['f1']:.4f}")
    print(classification_report(
        final["labels"], final["preds"],
        target_names=CLASS_NAMES, zero_division=0
    ))

    return final, history


# %%  [10] === MODEL 1: Sensor-Only (BiLSTM) ===
print("\n" + "#" * 60)
print("  MODEL 1: Sensor-Only (BiLSTM)")
print("#" * 60)

train_sensor_ds = SensorSequenceDataset(X_train_seq, y_train_seq)
test_sensor_ds = SensorSequenceDataset(X_test_seq, y_test_seq)

train_sensor_loader = DataLoader(train_sensor_ds, batch_size=BATCH_SIZE, shuffle=True)
test_sensor_loader = DataLoader(test_sensor_ds, batch_size=BATCH_SIZE, shuffle=False)

sensor_model = SensorLSTM(input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
sensor_result, sensor_history = run_training(
    sensor_model, train_sensor_loader, test_sensor_loader,
    model_type="sensor", model_name="sensor_bilstm"
)

# %%  [11] === MODEL 2: Image-Only (ResNet18) ===
# 이미지가 있을 때만 실행
print("\n" + "#" * 60)
print("  MODEL 2: Image-Only (ResNet18)")
print("#" * 60)

# 이미지용 train/test 분할 (cycle-wise)
df_img_train = df_image[df_image["Cycle_Count_New"].isin(train_cycles)].reset_index(drop=True)
df_img_test = df_image[df_image["Cycle_Count_New"].isin(test_cycles)].reset_index(drop=True)

HAS_IMAGES = ON_KAGGLE and len(df_image) > 0

if HAS_IMAGES:
    train_img_ds = ImageAnomalyDataset(
        df_img_train["cam1_path"].tolist(),
        df_img_train["label_encoded"].values,
        transform=train_transform,
    )
    test_img_ds = ImageAnomalyDataset(
        df_img_test["cam1_path"].tolist(),
        df_img_test["label_encoded"].values,
        transform=test_transform,
    )
    train_img_loader = DataLoader(train_img_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    test_img_loader = DataLoader(test_img_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    image_model = ImageResNet().to(DEVICE)
    image_result, image_history = run_training(
        image_model, train_img_loader, test_img_loader,
        model_type="image", model_name="image_resnet18"
    )
else:
    print("[SKIP] No image data available. Image model training skipped.")
    print("       To enable: add Kaggle image dataset parts as input.")
    image_result = None
    image_history = None

# %%  [12] === MODEL 3: Multimodal Fusion ===
print("\n" + "#" * 60)
print("  MODEL 3: Multimodal Fusion (Sensor + Image)")
print("#" * 60)

if HAS_IMAGES:
    # 멀티모달 데이터 준비: 이미지 시점에 맞는 센서 시퀀스 생성
    def create_multimodal_data(data_df, img_df, sensor_cols, seq_len):
        """이미지가 있는 시점의 센서 시퀀스 + 이미지 경로를 매칭"""
        X_seq, img_paths, labels = [], [], []

        for cycle_id, group in data_df.groupby("Cycle_Count_New"):
            values = group[sensor_cols].values.astype(np.float32)
            lbl = group["label_encoded"].values
            cam_paths = group.get("cam1_path", pd.Series([None] * len(group)))
            cycle_states = group["CycleState"].values

            if len(values) < seq_len:
                continue

            for i in range(len(values) - seq_len):
                target_idx = i + seq_len
                if cycle_states[target_idx] in [4, 9]:
                    X_seq.append(values[i:i + seq_len])
                    labels.append(lbl[target_idx])
                    # 이미지 경로 (있으면 사용, 없으면 None)
                    path_val = cam_paths.iloc[target_idx] if target_idx < len(cam_paths) else None
                    img_paths.append(path_val if pd.notna(path_val) else None)

        return np.array(X_seq), img_paths, np.array(labels)

    # 이미지 경로를 원본 df에 merge
    train_df_merged = train_df.merge(
        df_image[["Cycle_Count_New", "CycleState", "cam1_path"]].drop_duplicates(),
        on=["Cycle_Count_New", "CycleState"], how="left"
    )
    test_df_merged = test_df.merge(
        df_image[["Cycle_Count_New", "CycleState", "cam1_path"]].drop_duplicates(),
        on=["Cycle_Count_New", "CycleState"], how="left"
    )

    X_train_mm, img_train, y_train_mm = create_multimodal_data(
        train_df_merged, df_img_train, SENSOR_COLUMNS, SEQUENCE_LENGTH
    )
    X_test_mm, img_test, y_test_mm = create_multimodal_data(
        test_df_merged, df_img_test, SENSOR_COLUMNS, SEQUENCE_LENGTH
    )
    print(f"Multimodal train: {X_train_mm.shape}, images: {sum(1 for p in img_train if p)}")
    print(f"Multimodal test:  {X_test_mm.shape}, images: {sum(1 for p in img_test if p)}")

    train_mm_ds = MultimodalDataset(X_train_mm, img_train, y_train_mm, train_transform)
    test_mm_ds = MultimodalDataset(X_test_mm, img_test, y_test_mm, test_transform)

    train_mm_loader = DataLoader(train_mm_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    test_mm_loader = DataLoader(test_mm_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    fusion_result, fusion_history = run_training(
        fusion_model, train_mm_loader, test_mm_loader,
        model_type="fusion", model_name="fusion_dlf"
    )
else:
    print("[SKIP] No image data. Fusion model skipped.")
    fusion_result = None
    fusion_history = None

# %%  [13] Results Comparison & Visualization

# ── 결과 수집 ──
all_results = {"Sensor (BiLSTM)": sensor_result}
all_histories = {"Sensor (BiLSTM)": sensor_history}
if image_result:
    all_results["Image (ResNet18)"] = image_result
    all_histories["Image (ResNet18)"] = image_history
if fusion_result:
    all_results["Fusion (Sensor+Image)"] = fusion_result
    all_histories["Fusion (Sensor+Image)"] = fusion_history

# ── 13-1. 성능 비교 바 차트 ──
fig, ax = plt.subplots(figsize=(10, 6))
metrics = ["accuracy", "precision", "recall", "f1"]
metric_labels = ["Accuracy", "Precision", "Recall", "F1-Score"]
x = np.arange(len(metrics))
width = 0.25
colors = ["#2196F3", "#FF9800", "#4CAF50"]

for i, (name, res) in enumerate(all_results.items()):
    vals = [res[m] for m in metrics]
    bars = ax.bar(x + i * width, vals, width, label=name, color=colors[i])
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{v:.3f}", ha="center", fontsize=9)

ax.set_ylabel("Score")
ax.set_title("Model Performance Comparison")
ax.set_xticks(x + width * (len(all_results) - 1) / 2)
ax.set_xticklabels(metric_labels)
ax.legend()
ax.set_ylim(0, 1.15)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("model_comparison.png", dpi=150, bbox_inches="tight")
plt.show()

# ── 13-2. Confusion Matrix ──
fig, axes = plt.subplots(1, len(all_results), figsize=(7 * len(all_results), 6))
if len(all_results) == 1:
    axes = [axes]

for ax, (name, res) in zip(axes, all_results.items()):
    cm = confusion_matrix(res["labels"], res["preds"])
    cm_norm = cm.astype("float") / cm.sum(axis=1, keepdims=True)
    sns.heatmap(cm_norm, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, ax=ax)
    ax.set_title(f"{name}")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")

plt.tight_layout()
plt.savefig("confusion_matrices.png", dpi=150, bbox_inches="tight")
plt.show()

# ── 13-3. 학습 곡선 ──
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for name, hist in all_histories.items():
    epochs_range = range(1, len(hist["train_loss"]) + 1)
    axes[0].plot(epochs_range, hist["train_loss"], label=f"{name} (train)")
    axes[0].plot(epochs_range, hist["val_loss"], "--", label=f"{name} (val)")
    axes[1].plot(epochs_range, hist["val_f1"], label=name)

axes[0].set_title("Loss Curves")
axes[0].set_xlabel("Epoch")
axes[0].set_ylabel("Loss")
axes[0].legend(fontsize=8)
axes[0].grid(alpha=0.3)

axes[1].set_title("Validation F1-Score")
axes[1].set_xlabel("Epoch")
axes[1].set_ylabel("F1")
axes[1].legend(fontsize=8)
axes[1].grid(alpha=0.3)

plt.tight_layout()
plt.savefig("training_curves.png", dpi=150, bbox_inches="tight")
plt.show()

# ── 13-4. 최종 요약 테이블 ──
print("\n" + "=" * 70)
print(" FINAL RESULTS SUMMARY")
print("=" * 70)
print(f"{'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
print("-" * 70)
for name, res in all_results.items():
    print(f"{name:<25} {res['accuracy']:>10.4f} {res['precision']:>10.4f} "
          f"{res['recall']:>10.4f} {res['f1']:>10.4f}")
print("=" * 70)

print("\nDone!")
