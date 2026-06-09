# -*- coding: utf-8 -*-
"""iter6(이미지 LR 1e-4 안정화) 결과 그래프 — res_present / res_story / res_byclass."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

OUT = "_ppt_assets_iter6"
os.makedirs(OUT, exist_ok=True)

C_SENSOR = "#2E78B7"; C_IMAGE = "#E15554"; C_FUSION = "#2A9D8F"; C_DEC = "#F4A024"; NAVY = "#1E2A4A"

def style(ax):
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25)

def barlabel(ax, bars, vals, fmt="{:.3f}"):
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.006, fmt.format(v),
                ha="center", fontsize=9.5, fontweight="bold")

# ---- res_present: 이미지 존재 구간 3,912 (iter6) ----
fig, ax = plt.subplots(figsize=(8, 4.6))
models = ["Sensor", "Image\n(2 cam)", "Fusion\n(Concat)", "Fusion\n(CrossAttn)", "Decision\nFusion"]
f1 = [0.9074, 0.9572, 0.9770, 0.9057, 0.9572]
colors = [C_SENSOR, C_IMAGE, C_FUSION, C_FUSION, C_DEC]
bars = ax.bar(models, f1, color=colors, width=0.62)
barlabel(ax, bars, f1)
ax.set_ylim(0.85, 1.0); ax.set_ylabel("Weighted F1")
ax.axhline(0.9572, color=C_IMAGE, ls="--", lw=1, alpha=0.6)
ax.set_title("Image-present timesteps only (3,912 pts)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.20, "이미지가 강해도(0.957) 최적 융합(Concat 0.977)이 두 단독을 근소하게 앞섬 · 배포형 Decision-Fusion은 이미지와 동등",
        transform=ax.transAxes, ha="center", fontsize=8, style="italic", color=C_FUSION, fontweight="bold")
style(ax); plt.tight_layout()
plt.savefig(f"{OUT}/res_present.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- res_story: 이미지 강/약 vs 융합 (iter6, Decision-Fusion) ----
fig, ax = plt.subplots(figsize=(7.6, 4.8))
scenarios = ["Image weak\n(under-trained)", "Image strong\n(fully trained)"]
x = np.arange(len(scenarios))
sensor_v = [0.9074, 0.9074]
image_v  = [0.7726, 0.9572]
fusion_v = [0.9615, 0.9572]   # Decision-Fusion
w = 0.25
b1 = ax.bar(x-w, sensor_v, w, label="Sensor", color=C_SENSOR)
b2 = ax.bar(x,   image_v,  w, label="Image", color=C_IMAGE)
b3 = ax.bar(x+w, fusion_v, w, label="Decision-Fusion", color=C_DEC)
for bars, vals in [(b1, sensor_v), (b2, image_v), (b3, fusion_v)]:
    for bb, v in zip(bars, vals):
        ax.text(bb.get_x()+bb.get_width()/2, v+0.012, f"{v:.2f}", ha="center", fontsize=8, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(scenarios, fontsize=10)
ax.set_ylim(0.0, 1.13); ax.set_ylabel("Weighted F1")
ax.set_title("Fusion matches the best modality — recovers when image degrades",
             fontsize=12.5, fontweight="bold", color=NAVY)
ax.legend(loc="upper left", fontsize=8.5, frameon=False, ncol=1)
ax.text(0.5, -0.20, "이미지가 약하면 융합이 0.96으로 회복(이미지 0.77) · 이미지가 강하면 융합=이미지 → 융합은 최고 모달리티 밑으로 안 떨어짐",
        transform=ax.transAxes, ha="center", fontsize=8, style="italic", color=C_DEC, fontweight="bold")
style(ax); plt.tight_layout()
plt.savefig(f"{OUT}/res_story.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- res_byclass: 클래스별 (Fusion-Concat, iter6, cycle 4·9) ----
fig, ax = plt.subplots(figsize=(8.2, 4.6))
labels = ["NoNose", "NoNose\n_NoBody2", "NoNose_NoBody2\n_NoBody1", "Normal"]
f1c = [0.97, 0.94, 0.71, 0.92]
colors2 = [C_FUSION, C_FUSION, C_IMAGE, C_SENSOR]
bars = ax.bar(labels, f1c, color=colors2, width=0.6)
barlabel(ax, bars, f1c, fmt="{:.2f}")
ax.set_ylim(0, 1.1); ax.set_ylabel("F1-Score (Fusion-Concat)")
ax.set_title("Per-class Performance (cycle 4·9)", fontsize=13, fontweight="bold", color=NAVY)
ax.text(0.5, -0.22, "단순 결함(NoNose)은 0.97로 정확하나, 3중 복합 결함은 0.71로 여전히 가장 어려움",
        transform=ax.transAxes, ha="center", fontsize=8.5, style="italic", color="#555")
style(ax); plt.tight_layout()
plt.savefig(f"{OUT}/res_byclass.png", dpi=160, bbox_inches="tight"); plt.close()

import glob
print("iter6 그래프 생성:")
for f in sorted(glob.glob(f"{OUT}/res_*.png")):
    print(" -", f, os.path.getsize(f), "bytes")
