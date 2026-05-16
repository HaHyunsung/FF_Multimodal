"""
Future Factories Dataset 로더
- 시계열 센서 데이터 + 이미지 데이터를 동기화하여 로드
- Cycle-wise 분할로 train/test 데이터 누출 방지
"""
import os
import json
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from collections import Counter
import torch

import config


# ──────────────────────────────────────────────
# 1. 데이터 전처리 함수
# ──────────────────────────────────────────────

def load_and_preprocess_raw_data(raw_dir: str, output_dir: str):
    """
    FF Dataset 원본 JSON 파일들을 읽어 통합 CSV로 변환한다.
    NSF-MAP 논문의 전처리 파이프라인을 따른다.

    raw_dir 구조 예시:
        raw/
          batch_0001/
            data.json        (센서 값 + 이미지 경로)
            images/
              cam1_0001.jpg
              cam2_0001.jpg
          batch_0002/
          ...

    이미 전처리된 CSV가 있으면 이 함수를 건너뛴다.
    NSF-MAP GitHub에서 전처리된 데이터를 제공하므로 그것을 사용해도 된다.
    """
    csv_path = os.path.join(output_dir, "multimodal_dataset.csv")
    if os.path.exists(csv_path):
        print(f"[INFO] 전처리 완료 CSV 발견: {csv_path}")
        return pd.read_csv(csv_path)

    print("[INFO] 원본 JSON에서 데이터 변환 시작...")
    os.makedirs(output_dir, exist_ok=True)

    all_records = []
    batch_dirs = sorted(
        [d for d in os.listdir(raw_dir) if os.path.isdir(os.path.join(raw_dir, d))]
    )

    for batch_name in batch_dirs:
        json_path = os.path.join(raw_dir, batch_name, "data.json")
        if not os.path.exists(json_path):
            continue

        with open(json_path, "r") as f:
            batch_data = json.load(f)

        for record in batch_data:
            all_records.append(record)

    df = pd.DataFrame(all_records)
    df.to_csv(csv_path, index=False)
    print(f"[INFO] 전처리 완료: {len(df)} 레코드 → {csv_path}")
    return df


def load_preprocessed_data(csv_path: str) -> pd.DataFrame:
    """NSF-MAP GitHub에서 받은 전처리 완료 CSV를 로드한다."""
    df = pd.read_csv(csv_path)
    print(f"[INFO] 데이터 로드 완료: {df.shape}")
    print(f"[INFO] 컬럼: {list(df.columns[:10])}...")
    print(f"[INFO] 이상 유형 분포:\n{df['anomaly_type'].value_counts()}")
    return df


def prepare_sensor_features(df: pd.DataFrame, sensor_columns: list) -> np.ndarray:
    """센서 컬럼을 선택하고 StandardScaler로 정규화한다."""
    scaler = StandardScaler()
    sensor_data = scaler.fit_transform(df[sensor_columns].values)
    return sensor_data, scaler


def create_sequences(sensor_data: np.ndarray, labels: np.ndarray,
                     seq_length: int) -> tuple:
    """
    시계열 데이터를 sliding window 방식으로 시퀀스로 변환한다.
    같은 사이클 내에서만 시퀀스를 생성한다.
    """
    X_seq, y_seq, idx_seq = [], [], []
    for i in range(len(sensor_data) - seq_length):
        X_seq.append(sensor_data[i:i + seq_length])
        y_seq.append(labels[i + seq_length])
        idx_seq.append(i + seq_length)

    return np.array(X_seq), np.array(y_seq), np.array(idx_seq)


def cycle_wise_split(df: pd.DataFrame, train_ratio: float = 0.8,
                     seed: int = 42) -> tuple:
    """
    Cycle-wise 분할: 같은 사이클의 데이터가 train/test에 걸쳐 섞이지 않도록 한다.
    논문과 동일하게 정상/이상 비율을 유지하는 stratified split을 수행한다.
    """
    cycles = df["cycle_id"].unique()

    cycle_labels = []
    for c in cycles:
        cycle_df = df[df["cycle_id"] == c]
        has_anomaly = (cycle_df["anomaly_type"] != "NoAnomaly").any()
        cycle_labels.append(1 if has_anomaly else 0)

    train_cycles, test_cycles = train_test_split(
        cycles, train_size=train_ratio,
        random_state=seed, stratify=cycle_labels
    )

    train_df = df[df["cycle_id"].isin(train_cycles)].reset_index(drop=True)
    test_df = df[df["cycle_id"].isin(test_cycles)].reset_index(drop=True)

    print(f"[INFO] Train: {len(train_df)} samples ({len(train_cycles)} cycles)")
    print(f"[INFO] Test:  {len(test_df)} samples ({len(test_cycles)} cycles)")
    return train_df, test_df


# ──────────────────────────────────────────────
# 2. PyTorch Dataset 클래스
# ──────────────────────────────────────────────

class SensorDataset(Dataset):
    """시계열 센서 데이터 전용 Dataset"""

    def __init__(self, sequences: np.ndarray, labels: np.ndarray):
        self.sequences = torch.FloatTensor(sequences)
        self.labels = torch.LongTensor(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.sequences[idx], self.labels[idx]


class ImageDataset(Dataset):
    """이미지 데이터 전용 Dataset"""

    def __init__(self, image_paths: list, labels: np.ndarray,
                 transform=None):
        self.image_paths = image_paths
        self.labels = torch.LongTensor(labels)
        self.transform = transform or get_image_transforms(is_train=False)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = Image.open(img_path).convert("RGB")
        image = self.transform(image)
        return image, self.labels[idx]


class MultimodalDataset(Dataset):
    """
    멀티모달 Dataset: 시계열 시퀀스 + 동기화된 이미지를 함께 반환한다.
    각 시계열 시퀀스의 마지막 시점에 해당하는 이미지를 매칭한다.
    """

    def __init__(self, sequences: np.ndarray, image_paths: list,
                 labels: np.ndarray, transform=None):
        self.sequences = torch.FloatTensor(sequences)
        self.image_paths = image_paths
        self.labels = torch.LongTensor(labels)
        self.transform = transform or get_image_transforms(is_train=False)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        sensor_seq = self.sequences[idx]

        img_path = self.image_paths[idx]
        if img_path and os.path.exists(img_path):
            image = Image.open(img_path).convert("RGB")
            image = self.transform(image)
            has_image = True
        else:
            image = torch.zeros(3, config.IMAGE_SIZE, config.IMAGE_SIZE)
            has_image = False

        return sensor_seq, image, self.labels[idx], has_image


# ──────────────────────────────────────────────
# 3. 이미지 Transform
# ──────────────────────────────────────────────

def get_image_transforms(is_train: bool = True) -> transforms.Compose:
    """학습/평가용 이미지 변환 파이프라인"""
    if is_train:
        return transforms.Compose([
            transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(10),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize(mean=config.IMAGE_MEAN, std=config.IMAGE_STD),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=config.IMAGE_MEAN, std=config.IMAGE_STD),
        ])


# ──────────────────────────────────────────────
# 4. 클래스 가중치 계산
# ──────────────────────────────────────────────

def compute_class_weights(labels: np.ndarray) -> torch.Tensor:
    """
    클래스 불균형 처리를 위한 역빈도(inverse frequency) 가중치 계산.
    정상 샘플이 압도적으로 많으므로 소수 클래스에 높은 가중치를 부여한다.
    """
    counter = Counter(labels)
    total = len(labels)
    num_classes = len(counter)
    weights = []
    for c in range(num_classes):
        count = counter.get(c, 1)
        weights.append(total / (num_classes * count))

    weights = torch.FloatTensor(weights)
    weights = weights / weights.sum() * num_classes  # 정규화
    print(f"[INFO] 클래스 가중치: {weights.tolist()}")
    return weights


# ──────────────────────────────────────────────
# 5. DataLoader 생성 헬퍼
# ──────────────────────────────────────────────

def get_dataloaders(train_dataset, test_dataset, batch_size=None):
    """Train/Test DataLoader를 생성한다."""
    bs = batch_size or config.BATCH_SIZE
    use_pin = torch.cuda.is_available()
    train_loader = DataLoader(
        train_dataset, batch_size=bs, shuffle=True,
        num_workers=0, pin_memory=use_pin
    )
    test_loader = DataLoader(
        test_dataset, batch_size=bs, shuffle=False,
        num_workers=0, pin_memory=use_pin
    )
    return train_loader, test_loader
