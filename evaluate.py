"""
평가 및 시각화: Confusion Matrix, 학습 곡선, 모델 비교 차트

실행:
    python evaluate.py
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    confusion_matrix, classification_report,
    precision_recall_fscore_support, roc_curve, auc,
)
from sklearn.preprocessing import label_binarize

import config

# 한글 폰트 설정 (Windows)
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def plot_confusion_matrix(y_true, y_pred, class_names, title="Confusion Matrix",
                          save_path=None):
    """Confusion Matrix 히트맵"""
    cm = confusion_matrix(y_true, y_pred)
    cm_normalized = cm.astype("float") / cm.sum(axis=1, keepdims=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # 절대값
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=class_names, yticklabels=class_names, ax=axes[0])
    axes[0].set_title(f"{title} (Count)")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")

    # 정규화
    sns.heatmap(cm_normalized, annot=True, fmt=".2f", cmap="Blues",
                xticklabels=class_names, yticklabels=class_names, ax=axes[1])
    axes[1].set_title(f"{title} (Normalized)")
    axes[1].set_xlabel("Predicted")
    axes[1].set_ylabel("Actual")

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()


def plot_training_history(history, title="Training History", save_path=None):
    """학습 곡선: Loss, Accuracy, F1"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    epochs = range(1, len(history["train_loss"]) + 1)

    # Loss
    axes[0].plot(epochs, history["train_loss"], "b-", label="Train")
    axes[0].plot(epochs, history["val_loss"], "r-", label="Validation")
    axes[0].set_title("Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Accuracy
    axes[1].plot(epochs, history["train_acc"], "b-", label="Train")
    axes[1].plot(epochs, history["val_acc"], "r-", label="Validation")
    axes[1].set_title("Accuracy")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # F1
    axes[2].plot(epochs, history["train_f1"], "b-", label="Train")
    axes[2].plot(epochs, history["val_f1"], "r-", label="Validation")
    axes[2].set_title("F1-Score")
    axes[2].set_xlabel("Epoch")
    axes[2].set_ylabel("F1")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.suptitle(title, fontsize=14)
    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()


def plot_model_comparison(results_dict, save_path=None):
    """
    3가지 모델 성능 비교 바 차트.

    Args:
        results_dict: {"sensor": {...}, "image": {...}, "fusion": {...}}
    """
    models = list(results_dict.keys())
    metrics = ["accuracy", "precision", "recall", "f1"]
    metric_labels = ["Accuracy", "Precision", "Recall", "F1-Score"]

    x = np.arange(len(metrics))
    width = 0.25
    colors = ["#2196F3", "#FF9800", "#4CAF50"]

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, model_name in enumerate(models):
        values = [results_dict[model_name][m] for m in metrics]
        bars = ax.bar(x + i * width, values, width, label=model_name, color=colors[i])
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Score")
    ax.set_title("Model Performance Comparison")
    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_labels)
    ax.legend()
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()


def plot_per_class_f1(results_dict, class_names, save_path=None):
    """클래스별 F1-Score 비교 (논문 Figure 2 스타일)"""
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(class_names))
    width = 0.25
    colors = ["#2196F3", "#FF9800", "#4CAF50"]

    for i, (model_name, result) in enumerate(results_dict.items()):
        _, _, f1_per_class, _ = precision_recall_fscore_support(
            result["labels"], result["predictions"],
            labels=range(len(class_names)), zero_division=0
        )
        ax.bar(x + i * width, f1_per_class, width,
               label=model_name, color=colors[i])

    ax.set_ylabel("F1-Score")
    ax.set_title("Per-Class F1-Score Comparison")
    ax.set_xticks(x + width)
    ax.set_xticklabels(class_names, rotation=30, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.show()


def generate_full_report(results_dict, class_names, output_dir=None):
    """전체 평가 리포트 생성"""
    output_dir = output_dir or config.RESULT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # 1. 모델별 Confusion Matrix
    for name, result in results_dict.items():
        plot_confusion_matrix(
            result["labels"], result["predictions"],
            class_names, title=f"{name} Confusion Matrix",
            save_path=os.path.join(output_dir, f"cm_{name}.png"),
        )

    # 2. 모델 성능 비교
    plot_model_comparison(
        results_dict,
        save_path=os.path.join(output_dir, "model_comparison.png"),
    )

    # 3. 클래스별 F1 비교
    plot_per_class_f1(
        results_dict, class_names,
        save_path=os.path.join(output_dir, "per_class_f1.png"),
    )

    # 4. 텍스트 리포트
    report_path = os.path.join(output_dir, "evaluation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("멀티모달 이상 탐지 평가 리포트\n")
        f.write("=" * 60 + "\n\n")

        for name, result in results_dict.items():
            f.write(f"\n{'─'*40}\n")
            f.write(f"Model: {name}\n")
            f.write(f"{'─'*40}\n")
            f.write(f"Accuracy:  {result['accuracy']:.4f}\n")
            f.write(f"Precision: {result['precision']:.4f}\n")
            f.write(f"Recall:    {result['recall']:.4f}\n")
            f.write(f"F1-Score:  {result['f1']:.4f}\n\n")
            f.write(classification_report(
                result["labels"], result["predictions"],
                target_names=class_names, zero_division=0,
            ))
            f.write("\n")

    print(f"\n[INFO] 평가 리포트 저장: {output_dir}")


if __name__ == "__main__":
    # 데모 데이터로 시각화 테스트
    np.random.seed(42)
    n = 200
    demo_results = {}
    for name in ["sensor", "image", "fusion"]:
        labels = np.random.randint(0, config.NUM_CLASSES, n)
        preds = labels.copy()
        noise_idx = np.random.choice(n, size=int(n * 0.2), replace=False)
        preds[noise_idx] = np.random.randint(0, config.NUM_CLASSES, len(noise_idx))
        demo_results[name] = {
            "labels": labels,
            "predictions": preds,
            "accuracy": np.mean(labels == preds),
            "precision": 0.8 + np.random.random() * 0.1,
            "recall": 0.75 + np.random.random() * 0.1,
            "f1": 0.77 + np.random.random() * 0.1,
        }

    generate_full_report(demo_results, config.ANOMALY_CLASSES)
