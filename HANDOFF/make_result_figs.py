# -*- coding: utf-8 -*-
"""최종발표용 결과 그래프 (신규 커밋: 두 카메라 + 추가분석 ①②). 영문 라벨."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

# 한글 캡션 렌더링용 폰트
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

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

# ---- Fig A: 공정 비교 (cycle 4·9 동일 테스트셋, 9,521 시점) ----
fig, ax = plt.subplots(figsize=(8, 4.6))
models = ["Sensor", "Image\n(2 cam)", "Fusion\n(Concat)", "Fusion\n(CrossAttn)", "Decision\nFusion"]
f1 = [0.8710, 0.4068, 0.8796, 0.8724, 0.9041]
colors = [C_SENSOR, C_IMAGE, C_FUSION, C_FUSION, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.62)
barlabel(ax, bars, f1)
ax.axhline(0.8710, color=C_SENSOR, ls="--", lw=1, alpha=0.6)
ax.set_ylim(0, 1.0); ax.set_ylabel("Weighted F1")
ax.set_title("Fair Comparison — same cycle 4·9 test set (9,521 pts)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "Image suffers from missing-image timesteps (77%); Fusion falls back to sensor → stays ≥ Sensor",
        transform=ax.transAxes, ha="center", fontsize=8, style="italic", color="#555")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_fair.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig B: 이미지 존재 구간 (Decision-Fusion이 두 단독 초과) ----
fig, ax = plt.subplots(figsize=(8, 4.6))
models = ["Sensor", "Image\n(2 cam)", "Fusion\n(Concat)", "Fusion\n(CrossAttn)", "Decision\nFusion"]
f1 = [0.9074, 0.9251, 0.9212, 0.9132, 0.9858]
colors = [C_SENSOR, C_IMAGE, C_FUSION, C_FUSION, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.62)
barlabel(ax, bars, f1)
ax.set_ylim(0.85, 1.0); ax.set_ylabel("Weighted F1")
ax.axhline(0.9251, color=C_IMAGE, ls="--", lw=1, alpha=0.6)
ax.set_title("Image-present timesteps only (3,912 pts)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "Decision-Fusion (0.986) EXCEEDS both Sensor (0.907) and Image (0.925) → multimodal gain (statistically significant)",
        transform=ax.transAxes, ha="center", fontsize=8, style="italic", color=C_DEC, fontweight="bold")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_present.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig C: 이미지 약화 통제실험 (이미지 존재 구간) ----
fig, ax = plt.subplots(figsize=(7, 4.6))
models = ["Sensor", "Image\n(weakened)", "Decision\nFusion"]
f1 = [0.9074, 0.2643, 0.9075]
colors = [C_SENSOR, C_IMAGE, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.55)
barlabel(ax, bars, f1)
ax.set_ylim(0.0, 1.05); ax.set_ylabel("Weighted F1")
ax.set_title("Controlled ablation — image weakened (3 epochs)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "When image is weak (0.264), Fusion safely matches Sensor (0.907) with no degradation",
        transform=ax.transAxes, ha="center", fontsize=8.5, style="italic", color=C_DEC, fontweight="bold")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_weak.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig D: 핵심 스토리 — 이미지 강도 vs 융합 이득 (V13, 이미지 존재 3,912 시점) ----
fig, ax = plt.subplots(figsize=(7.6, 4.8))
scenarios = ["Image weak\n(under-trained)", "Image strong\n(fully trained)"]
x = np.arange(len(scenarios))
sensor_v = [0.9074, 0.9074]
image_v = [0.2643, 0.9251]
fusion_v = [0.9075, 0.9858]   # Decision-Fusion
w = 0.25
b1 = ax.bar(x-w, sensor_v, w, label="Sensor", color=C_SENSOR)
b2 = ax.bar(x, image_v, w, label="Image", color=C_IMAGE)
b3 = ax.bar(x+w, fusion_v, w, label="Decision-Fusion", color=C_DEC)
ax.set_xticks(x); ax.set_xticklabels(scenarios, fontsize=9.5)
ax.set_ylim(0.0, 1.08); ax.set_ylabel("Weighted F1")
ax.set_title("Fusion never underperforms — gain grows with image quality", fontsize=13, fontweight="bold", color=NAVY)
ax.legend(loc="upper center", fontsize=9, frameon=False, ncol=3)
# 융합 - 최고 단독 마진 표시 (정직하게 수치로)
for i in range(len(scenarios)):
    best_single = max(sensor_v[i], image_v[i])
    margin = fusion_v[i] - best_single
    tag = f"+{margin:.3f}" if margin >= 0 else f"{margin:.3f}"
    if margin >= 0.01:
        tag += " gain"
    else:
        tag = "= sensor (no loss)"
    ax.annotate(tag, (x[i]+w, fusion_v[i]+0.025), ha="center", fontsize=8, color=C_DEC, fontweight="bold")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_story.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig E: 클래스별 성능 (Fusion-Concat, cycle 4·9) ----
fig, ax = plt.subplots(figsize=(8.2, 4.6))
labels = ["NoNose", "NoNose\n_NoBody2", "NoNose_NoBody2\n_NoBody1", "Normal"]
f1c = [0.98, 0.89, 0.62, 0.93]
colors2 = [C_FUSION, C_FUSION, C_IMAGE, C_SENSOR]
bars = ax.bar(labels, f1c, color=colors2, width=0.6)
barlabel(ax, bars, f1c, fmt="{:.2f}")
ax.set_ylim(0, 1.1); ax.set_ylabel("F1-Score (Fusion-Concat)")
ax.set_title("Per-class Performance (cycle 4·9)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.22, "단순 결함(NoNose)은 0.98로 정확하나, 3중 복합 결함은 0.62로 가장 어려움",
        transform=ax.transAxes, ha="center", fontsize=8.5, style="italic", color="#555")
style(ax)
plt.tight_layout()
plt.savefig(f"{OUT}/res_byclass.png", dpi=160, bbox_inches="tight"); plt.close()

import glob
print("생성된 결과 그래프:")
for f in sorted(glob.glob(f"{OUT}/res_*.png")):
    print(" -", f, os.path.getsize(f), "bytes")
