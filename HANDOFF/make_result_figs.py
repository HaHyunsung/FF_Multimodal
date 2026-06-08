# -*- coding: utf-8 -*-
"""최종발표용 결과 그래프 (신규 커밋: 두 카메라 + 추가분석 ①②). 영문 라벨."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

OUT = "_ppt_assets"
os.makedirs(OUT, exist_ok=True)

# 템플릿 색상
C_SENSOR = "#2E78B7"   # 파랑
C_IMAGE = "#E15554"    # 빨강
C_FUSION = "#2A9D8F"   # 틸
C_DEC = "#F4A024"      # 노랑
NAVY = "#1E2A4A"

def style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25)

def barlabel(ax, bars, vals, fmt="{:.3f}"):
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.008, fmt.format(v),
                ha="center", fontsize=9.5, fontweight="bold")

# ---- Fig A: 공정 비교 (cycle 4·9 동일 테스트셋) ----
fig, ax = plt.subplots(figsize=(8, 4.6))
models = ["Sensor", "Image\n(2 cam)", "Fusion\n(Concat)", "Fusion\n(CrossAttn)", "Decision\nFusion"]
f1 = [0.8710, 0.5929, 0.8693, 0.8703, 0.8602]
colors = [C_SENSOR, C_IMAGE, C_FUSION, C_FUSION, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.62)
barlabel(ax, bars, f1)
ax.axhline(0.8710, color=C_SENSOR, ls="--", lw=1, alpha=0.6)
ax.set_ylim(0, 1.0); ax.set_ylabel("Weighted F1")
ax.set_title("Fair Comparison — same cycle 4·9 test set", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "Image suffers from missing-image timesteps (77%); Fusion falls back to sensor → stays ≥ Sensor",
        transform=ax.transAxes, ha="center", fontsize=8, style="italic", color="#555")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_fair.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig B: 이미지 존재 구간 (Fusion이 두 단독 초과) ----
fig, ax = plt.subplots(figsize=(8, 4.6))
models = ["Sensor", "Image\n(2 cam)", "Fusion\n(Concat)", "Fusion\n(CrossAttn)", "Decision\nFusion"]
f1 = [0.9739, 0.9285, 0.9814, 0.9801, 0.9277]
colors = [C_SENSOR, C_IMAGE, C_FUSION, C_FUSION, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.62)
barlabel(ax, bars, f1)
ax.set_ylim(0.88, 1.0); ax.set_ylabel("Weighted F1")
ax.axhline(0.9739, color=C_SENSOR, ls="--", lw=1, alpha=0.6)
ax.set_title("Image-present timesteps only (2,161 pts)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "When Image is moderate (0.93), trained Fusion-Concat (0.981) EXCEEDS both Sensor and Image → multimodal gain",
        transform=ax.transAxes, ha="center", fontsize=8, style="italic", color=C_FUSION, fontweight="bold")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_present.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig C: 이미지 약화 통제실험 (Fusion > 둘 다) ----
fig, ax = plt.subplots(figsize=(7, 4.6))
models = ["Sensor", "Image\n(weakened)", "Decision\nFusion"]
f1 = [0.9739, 0.7751, 0.9779]
colors = [C_SENSOR, C_IMAGE, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.55)
barlabel(ax, bars, f1)
ax.set_ylim(0.7, 1.02); ax.set_ylabel("Weighted F1")
ax.set_title("Controlled ablation — image weakened (3 epochs)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "With balanced modalities, Fusion (0.978) EXCEEDS both Sensor (0.974) and Image (0.775)",
        transform=ax.transAxes, ha="center", fontsize=8.5, style="italic", color=C_FUSION, fontweight="bold")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_weak.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig D: 핵심 스토리 — 이미지 강도 vs 융합 이득 ----
fig, ax = plt.subplots(figsize=(8.5, 4.8))
scenarios = ["Image weakened\n(3ep, 0.78)", "Both weakened\n(balanced)", "Image moderate\n(0.93)"]
x = np.arange(len(scenarios))
image_v = [0.7751, 0.7751, 0.9285]
sensor_v = [0.9739, 0.9555, 0.9739]
fusion_v = [0.9784, 0.9675, 0.9814]
w = 0.25
b1 = ax.bar(x-w, sensor_v, w, label="Sensor", color=C_SENSOR)
b2 = ax.bar(x, image_v, w, label="Image", color=C_IMAGE)
b3 = ax.bar(x+w, fusion_v, w, label="Fusion (best)", color=C_FUSION)
ax.set_xticks(x); ax.set_xticklabels(scenarios, fontsize=9.5)
ax.set_ylim(0.6, 1.05); ax.set_ylabel("Weighted F1")
ax.set_title("Fusion exceeds both single modalities across regimes", fontsize=13, fontweight="bold", color=NAVY)
ax.legend(loc="upper left", fontsize=9, frameon=False, ncol=3)
# 이득 표시
for i in range(len(scenarios)):
    best_single = max(sensor_v[i], image_v[i])
    if fusion_v[i] > best_single:
        ax.annotate("Fusion wins", (x[i]+w, fusion_v[i]+0.02), ha="center", fontsize=8, color=C_FUSION, fontweight="bold")
    else:
        ax.annotate("Image wins", (x[i], image_v[i]+0.02), ha="center", fontsize=8, color=C_IMAGE, fontweight="bold")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_story.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig E: 클래스별 성능 (Fusion-Concat, cycle 4·9) ----
fig, ax = plt.subplots(figsize=(8.2, 4.6))
labels = ["NoNose", "NoNose\n_NoBody2", "NoNose_NoBody2\n_NoBody1", "Normal"]
f1c = [0.98, 0.87, 0.59, 0.92]
colors2 = [C_FUSION, C_FUSION, C_IMAGE, C_SENSOR]
bars = ax.bar(labels, f1c, color=colors2, width=0.6)
barlabel(ax, bars, f1c, fmt="{:.2f}")
ax.set_ylim(0, 1.1); ax.set_ylabel("F1-Score (Fusion-Concat)")
ax.set_title("Per-class Performance (cycle 4·9)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.22, "단순 결함(NoNose)은 0.98로 정확하나, 3중 복합 결함은 0.59로 가장 어려움",
        transform=ax.transAxes, ha="center", fontsize=8.5, style="italic", color="#555")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_byclass.png", dpi=160, bbox_inches="tight"); plt.close()

import glob
print("생성된 결과 그래프:")
for f in sorted(glob.glob(f"{OUT}/res_*.png")):
    print(" -", f, os.path.getsize(f), "bytes")
