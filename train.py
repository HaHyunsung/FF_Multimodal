"""
학습 파이프라인: 3가지 모델(이미지, 센서, 융합)을 학습하고 비교한다.

실행 예시:
    python train.py --model image       # 이미지 단독
    python train.py --model sensor      # 센서 단독
    python train.py --model fusion      # 멀티모달 융합
    python train.py --model all         # 3가지 모두
"""
import os
import argparse
import time
import numpy as np
import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    classification_report, confusion_matrix,
)

import config
from dataset import (
    SensorDataset, ImageDataset, MultimodalDataset,
    get_dataloaders, compute_class_weights, get_image_transforms,
)
from models.image_model import ImageClassifier
from models.sensor_model import SensorLSTM, SensorAutoencoderClassifier
from models.fusion_model import MultimodalFusionNet
from losses import CombinedLoss


# ──────────────────────────────────────────────
# 학습 루프
# ──────────────────────────────────────────────

def train_one_epoch(model, dataloader, criterion, optimizer, device,
                    model_type="sensor"):
    """1 에폭 학습"""
    model.train()
    total_loss = 0
    all_preds, all_labels = [], []

    for batch in dataloader:
        if model_type == "sensor":
            inputs, labels = batch
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)

            if isinstance(outputs, tuple):
                logits, reconstructed = outputs
                loss_dict = criterion(logits, labels, reconstructed, inputs[:, -1, :])
            else:
                logits = outputs
                loss_dict = criterion(logits, labels)

        elif model_type == "image":
            inputs, labels = batch
            inputs, labels = inputs.to(device), labels.to(device)
            logits = model(inputs)
            loss_dict = criterion(logits, labels)

        elif model_type == "fusion":
            sensor_data, images, labels, has_image = batch
            sensor_data = sensor_data.to(device)
            images = images.to(device)
            labels = labels.to(device)
            has_image = has_image.to(device)

            result = model(sensor_data, images, has_image)
            logits = result["logits"]
            reconstructed = result.get("sensor_reconstructed")
            loss_dict = criterion(
                logits, labels,
                reconstructed=reconstructed,
                original=sensor_data[:, -1, :] if reconstructed is not None else None,
            )

        if isinstance(loss_dict, dict):
            loss = loss_dict["total"]
        else:
            loss = loss_dict

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item() * labels.size(0)
        preds = logits.argmax(dim=1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(all_labels)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
    return avg_loss, acc, f1


@torch.no_grad()
def evaluate(model, dataloader, criterion, device, model_type="sensor"):
    """검증/테스트 평가"""
    model.eval()
    total_loss = 0
    all_preds, all_labels = [], []

    for batch in dataloader:
        if model_type == "sensor":
            inputs, labels = batch
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            if isinstance(outputs, tuple):
                logits, reconstructed = outputs
                loss_dict = criterion(logits, labels, reconstructed, inputs[:, -1, :])
            else:
                logits = outputs
                loss_dict = criterion(logits, labels)

        elif model_type == "image":
            inputs, labels = batch
            inputs, labels = inputs.to(device), labels.to(device)
            logits = model(inputs)
            loss_dict = criterion(logits, labels)

        elif model_type == "fusion":
            sensor_data, images, labels, has_image = batch
            sensor_data = sensor_data.to(device)
            images = images.to(device)
            labels = labels.to(device)
            has_image = has_image.to(device)

            result = model(sensor_data, images, has_image)
            logits = result["logits"]
            reconstructed = result.get("sensor_reconstructed")
            loss_dict = criterion(
                logits, labels,
                reconstructed=reconstructed,
                original=sensor_data[:, -1, :] if reconstructed is not None else None,
            )

        if isinstance(loss_dict, dict):
            loss = loss_dict["total"]
        else:
            loss = loss_dict

        total_loss += loss.item() * labels.size(0)
        preds = logits.argmax(dim=1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(all_labels)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
    precision = precision_score(all_labels, all_preds, average="weighted", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="weighted", zero_division=0)

    return {
        "loss": avg_loss,
        "accuracy": acc,
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "predictions": np.array(all_preds),
        "labels": np.array(all_labels),
    }


# ──────────────────────────────────────────────
# 학습 전체 파이프라인
# ──────────────────────────────────────────────

def train_model(model, train_loader, test_loader, criterion, device,
                model_type="sensor", model_name="model"):
    """전체 학습 루프 (Early Stopping + LR Scheduling)"""
    optimizer = Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=config.LEARNING_RATE,
        weight_decay=config.WEIGHT_DECAY,
    )
    scheduler = ReduceLROnPlateau(
        optimizer, mode="min", patience=config.LR_PATIENCE, factor=0.5
    )

    best_f1 = 0
    patience_counter = 0
    history = {"train_loss": [], "train_acc": [], "train_f1": [],
               "val_loss": [], "val_acc": [], "val_f1": []}

    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    checkpoint_path = os.path.join(config.CHECKPOINT_DIR, f"{model_name}_best.pt")

    print("\n" + "=" * 60)
    print(f" Training: {model_name}")
    print(f" Device: {device}")
    print(f" Trainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")
    print("=" * 60)

    for epoch in range(1, config.EPOCHS + 1):
        t0 = time.time()

        train_loss, train_acc, train_f1 = train_one_epoch(
            model, train_loader, criterion, optimizer, device, model_type
        )
        val_result = evaluate(model, test_loader, criterion, device, model_type)

        scheduler.step(val_result["loss"])

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["train_f1"].append(train_f1)
        history["val_loss"].append(val_result["loss"])
        history["val_acc"].append(val_result["accuracy"])
        history["val_f1"].append(val_result["f1"])

        elapsed = time.time() - t0
        print(
            f"Epoch {epoch:3d}/{config.EPOCHS} | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} F1: {train_f1:.4f} | "
            f"Val Loss: {val_result['loss']:.4f} Acc: {val_result['accuracy']:.4f} "
            f"F1: {val_result['f1']:.4f} | {elapsed:.1f}s"
        )

        if val_result["f1"] > best_f1:
            best_f1 = val_result["f1"]
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "best_f1": best_f1,
            }, checkpoint_path)
            print(f"  -> Best model saved (F1: {best_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= config.EARLY_STOP_PATIENCE:
                print(f"  -> Early stopping at epoch {epoch}")
                break

    # Best 모델 로드
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    print(f"\nBest model loaded from epoch {ckpt['epoch']} (F1: {ckpt['best_f1']:.4f})")

    # 최종 테스트 평가
    final_result = evaluate(model, test_loader, criterion, device, model_type)
    print(f"\n{'='*60}")
    print(f" Final Test Results: {model_name}")
    print(f"{'='*60}")
    print(f"  Accuracy:  {final_result['accuracy']:.4f}")
    print(f"  Precision: {final_result['precision']:.4f}")
    print(f"  Recall:    {final_result['recall']:.4f}")
    print(f"  F1-Score:  {final_result['f1']:.4f}")
    print(f"\n{classification_report(final_result['labels'], final_result['predictions'], target_names=config.ANOMALY_CLASSES, zero_division=0)}")

    return model, history, final_result


# ──────────────────────────────────────────────
# 데모용 합성 데이터 생성 (실제 데이터 없이 코드 검증용)
# ──────────────────────────────────────────────

def create_demo_data():
    """코드 구조 검증을 위한 소규모 합성 데이터"""
    np.random.seed(config.RANDOM_SEED)
    n_samples = 500
    seq_len = config.SEQUENCE_LENGTH
    n_features = config.NUM_SENSOR_FEATURES
    n_classes = config.NUM_CLASSES

    # 합성 시계열 데이터
    X_sensor = np.random.randn(n_samples, seq_len, n_features).astype(np.float32)
    y = np.random.randint(0, n_classes, size=n_samples)

    # 클래스 불균형 시뮬레이션 (정상 60%, 이상 각 10%)
    y[:300] = 0
    np.random.shuffle(y)

    # 합성 이미지 경로 (실제 파일 없이 검증)
    dummy_images = [None] * n_samples

    split = int(n_samples * config.TRAIN_RATIO)
    train_sensor = X_sensor[:split]
    test_sensor = X_sensor[split:]
    train_labels = y[:split]
    test_labels = y[split:]
    train_images = dummy_images[:split]
    test_images = dummy_images[split:]

    return {
        "train_sensor": train_sensor,
        "test_sensor": test_sensor,
        "train_labels": train_labels,
        "test_labels": test_labels,
        "train_images": train_images,
        "test_images": test_images,
    }


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="멀티모달 이상 탐지 학습")
    parser.add_argument("--model", type=str, default="all",
                        choices=["image", "sensor", "fusion", "all"])
    parser.add_argument("--sensor_branch", type=str, default="lstm",
                        choices=["lstm", "autoencoder"])
    parser.add_argument("--image_backbone", type=str, default="resnet18",
                        choices=["resnet18", "efficientnet_b0"])
    parser.add_argument("--fusion_strategy", type=str, default="concat",
                        choices=["concat", "attention"])
    parser.add_argument("--demo", action="store_true",
                        help="합성 데이터로 코드 검증")
    parser.add_argument("--data_csv", type=str, default=None,
                        help="전처리 완료 CSV 경로")
    args = parser.parse_args()

    device = config.DEVICE
    print(f"[INFO] Device: {device}")

    # ── 데이터 로드 ──
    if args.demo:
        print("[INFO] 데모 모드: 합성 데이터 사용")
        data = create_demo_data()
    else:
        # TODO: 실제 데이터 로드 로직
        # df = load_preprocessed_data(args.data_csv)
        # train_df, test_df = cycle_wise_split(df)
        # ... 전처리 ...
        print("[INFO] --demo 플래그 없이 실행하려면 데이터 경로를 지정하세요.")
        print("[INFO] 데모 모드로 전환합니다.")
        data = create_demo_data()

    class_weights = compute_class_weights(data["train_labels"])
    class_weights = class_weights.to(device)

    results = {}

    # ═══════════════════════════════════════════
    # 1. 센서 단독 모델
    # ═══════════════════════════════════════════
    if args.model in ("sensor", "all"):
        print("\n" + "#" * 60)
        print(" [1/3] Sensor-Only Model (LSTM)")
        print("#" * 60)

        train_ds = SensorDataset(data["train_sensor"], data["train_labels"])
        test_ds = SensorDataset(data["test_sensor"], data["test_labels"])
        train_loader, test_loader = get_dataloaders(train_ds, test_ds)

        if args.sensor_branch == "lstm":
            model = SensorLSTM().to(device)
        else:
            model = SensorAutoencoderClassifier().to(device)

        criterion = CombinedLoss(
            class_weights=class_weights,
            use_knowledge_penalty=False,
        )

        model, history, result = train_model(
            model, train_loader, test_loader, criterion,
            device, model_type="sensor", model_name="sensor_only"
        )
        results["sensor"] = result

    # ═══════════════════════════════════════════
    # 2. 이미지 단독 모델
    # ═══════════════════════════════════════════
    if args.model in ("image", "all"):
        print("\n" + "#" * 60)
        print(" [2/3] Image-Only Model (ResNet18)")
        print("#" * 60)

        if data["train_images"][0] is None:
            print("[WARN] 이미지 데이터 없음 → 랜덤 텐서로 대체 (데모)")
            n_train = len(data["train_labels"])
            n_test = len(data["test_labels"])
            train_imgs = torch.randn(n_train, 3, config.IMAGE_SIZE, config.IMAGE_SIZE)
            test_imgs = torch.randn(n_test, 3, config.IMAGE_SIZE, config.IMAGE_SIZE)

            class DemoImageDataset(torch.utils.data.Dataset):
                def __init__(self, imgs, labels):
                    self.imgs = imgs
                    self.labels = torch.LongTensor(labels)
                def __len__(self):
                    return len(self.labels)
                def __getitem__(self, idx):
                    return self.imgs[idx], self.labels[idx]

            train_ds = DemoImageDataset(train_imgs, data["train_labels"])
            test_ds = DemoImageDataset(test_imgs, data["test_labels"])
        else:
            train_ds = ImageDataset(
                data["train_images"], data["train_labels"],
                transform=get_image_transforms(is_train=True)
            )
            test_ds = ImageDataset(
                data["test_images"], data["test_labels"],
                transform=get_image_transforms(is_train=False)
            )

        train_loader, test_loader = get_dataloaders(train_ds, test_ds)

        model = ImageClassifier(
            backbone=args.image_backbone,
            freeze_backbone=False,
        ).to(device)

        criterion = CombinedLoss(
            class_weights=class_weights,
            use_knowledge_penalty=False,
        )

        model, history, result = train_model(
            model, train_loader, test_loader, criterion,
            device, model_type="image", model_name="image_only"
        )
        results["image"] = result

    # ═══════════════════════════════════════════
    # 3. 멀티모달 융합 모델
    # ═══════════════════════════════════════════
    if args.model in ("fusion", "all"):
        print("\n" + "#" * 60)
        print(" [3/3] Multimodal Fusion (Decision-Level Fusion)")
        print("#" * 60)

        if data["train_images"][0] is None:
            print("[WARN] 이미지 데이터 없음 → 랜덤 텐서로 대체 (데모)")
            n_train = len(data["train_labels"])
            n_test = len(data["test_labels"])

            class DemoMultimodalDataset(torch.utils.data.Dataset):
                def __init__(self, sensor, labels, n):
                    self.sensor = torch.FloatTensor(sensor)
                    self.labels = torch.LongTensor(labels)
                    self.images = torch.randn(n, 3, config.IMAGE_SIZE, config.IMAGE_SIZE)
                def __len__(self):
                    return len(self.labels)
                def __getitem__(self, idx):
                    return (self.sensor[idx], self.images[idx],
                            self.labels[idx], True)

            train_ds = DemoMultimodalDataset(
                data["train_sensor"], data["train_labels"], n_train
            )
            test_ds = DemoMultimodalDataset(
                data["test_sensor"], data["test_labels"], n_test
            )
        else:
            train_ds = MultimodalDataset(
                data["train_sensor"], data["train_images"],
                data["train_labels"],
                transform=get_image_transforms(is_train=True)
            )
            test_ds = MultimodalDataset(
                data["test_sensor"], data["test_images"],
                data["test_labels"],
                transform=get_image_transforms(is_train=False)
            )

        train_loader, test_loader = get_dataloaders(train_ds, test_ds)

        model = MultimodalFusionNet(
            sensor_branch=args.sensor_branch,
            image_backbone=args.image_backbone,
            fusion_strategy=args.fusion_strategy,
        ).to(device)

        criterion = CombinedLoss(
            class_weights=class_weights,
            use_knowledge_penalty=config.USE_KNOWLEDGE_PENALTY,
            sensor_ranges={},  # 실제 데이터에서 온톨로지 범위 지정
        )

        model, history, result = train_model(
            model, train_loader, test_loader, criterion,
            device, model_type="fusion", model_name="fusion_dlf"
        )
        results["fusion"] = result

    # ═══════════════════════════════════════════
    # 결과 비교 요약
    # ═══════════════════════════════════════════
    if len(results) > 1:
        print("\n" + "=" * 60)
        print(" 모델 성능 비교 요약")
        print("=" * 60)
        print(f"{'Model':<20} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        print("-" * 60)
        for name, res in results.items():
            print(
                f"{name:<20} {res['accuracy']:>10.4f} {res['precision']:>10.4f} "
                f"{res['recall']:>10.4f} {res['f1']:>10.4f}"
            )


if __name__ == "__main__":
    main()
