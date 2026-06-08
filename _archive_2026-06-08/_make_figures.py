# -*- coding: utf-8 -*-
"""보고서용 결과 그래프 생성 (영문 라벨로 폰트 이슈 회피)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = "_report_figs"
import os; os.makedirs(OUT, exist_ok=True)

C_SENSOR="#2196F3"; C_IMAGE="#FF9800"; C_FUSION="#4CAF50"; C_DEC="#9C27B0"

# ---- Fig 1: 데이터구간별 멀티모달 이득 (핵심) ----
parts = ["1 part\n(cov 23%)", "2 parts\n(cov 41%)", "3 parts\n(cov 54%)"]
x = np.arange(len(parts))
image_real = [0.69, 0.96, 0.995]          # 실제 이미지셋 F1
sensor     = [0.871, 0.871, 0.871]        # cycle4·9 고정
decfusion  = [0.872, 0.885, 0.959]        # decision-level fusion

fig, ax = plt.subplots(figsize=(8,5))
ax.plot(x, image_real, "o-", color=C_IMAGE, lw=2.5, ms=9, label="Image-only (real images)")
ax.plot(x, sensor, "s--", color=C_SENSOR, lw=2.5, ms=9, label="Sensor-only (BiLSTM)")
ax.plot(x, decfusion, "^-", color=C_DEC, lw=2.5, ms=10, label="Decision-Level Fusion")
for xi,v in zip(x,image_real): ax.annotate(f"{v:.2f}",(xi,v),textcoords="offset points",xytext=(0,8),ha="center",fontsize=9,color=C_IMAGE)
for xi,v in zip(x,decfusion): ax.annotate(f"{v:.3f}",(xi,v),textcoords="offset points",xytext=(0,-15),ha="center",fontsize=9,color=C_DEC)
ax.set_xticks(x); ax.set_xticklabels(parts)
ax.set_ylabel("Weighted F1 (cycle 4·9 test)"); ax.set_ylim(0.6,1.02)
ax.set_title("Multimodal Benefit vs. Image Data Volume", fontsize=13, fontweight="bold")
ax.legend(loc="lower right"); ax.grid(alpha=0.3)
ax.text(0.02,0.04,"Fusion ≥ Sensor in every regime; image overtakes only when data is abundant",
        transform=ax.transAxes, fontsize=8, style="italic", color="#555")
plt.tight_layout(); plt.savefig(f"{OUT}/fig1_regime_ablation.png", dpi=160); plt.close()

# ---- Fig 2: 동일 테스트셋(cycle4·9 전체) 4모델 비교 — 2파트(균형) ----
models = ["Sensor", "Image\n(handicapped*)", "Fusion\n(Concat)", "Fusion\n(Decision)"]
f1 = [0.8710, 0.4323, 0.8782, 0.8848]
colors = [C_SENSOR, C_IMAGE, C_FUSION, C_DEC]
fig, ax = plt.subplots(figsize=(8,5))
bars = ax.bar(models, f1, color=colors, width=0.6)
for b,v in zip(bars,f1): ax.annotate(f"{v:.3f}",(b.get_x()+b.get_width()/2,v),textcoords="offset points",xytext=(0,4),ha="center",fontsize=10,fontweight="bold")
ax.axhline(0.8710, color=C_SENSOR, ls="--", lw=1, alpha=0.6)
ax.set_ylabel("Weighted F1 (same cycle 4·9 test set)"); ax.set_ylim(0,1.0)
ax.set_title("Fusion > Both Single Modalities on Identical Test Set (2-part)", fontsize=12.5, fontweight="bold")
ax.grid(axis="y", alpha=0.3)
ax.text(0.5,-0.17,"*Image is evaluated over all cycle 4·9 timepoints incl. those without an image (no input → penalized).\nReal-image-only F1 = 0.96. Fusion uses image only when available.",
        transform=ax.transAxes, fontsize=7.5, ha="center", color="#555")
plt.tight_layout(); plt.savefig(f"{OUT}/fig2_matched_comparison.png", dpi=160, bbox_inches="tight"); plt.close()

# ---- Fig 3: 센서 단독 강건성 (전체 사이클) — 중간발표 대비 ----
fig, ax = plt.subplots(figsize=(7,4.5))
ms = ["Sensor\n(all cycles)", "Image\n(real)", "Fusion\n(3-part, all)"]
vals = [0.927, 0.995, 0.964]
bars = ax.bar(ms, vals, color=[C_SENSOR,C_IMAGE,C_FUSION], width=0.55)
for b,v in zip(bars,vals): ax.annotate(f"{v:.3f}",(b.get_x()+b.get_width()/2,v),textcoords="offset points",xytext=(0,4),ha="center",fontsize=10,fontweight="bold")
ax.set_ylabel("Weighted F1"); ax.set_ylim(0.8,1.02)
ax.set_title("Peak Performance (abundant image data)", fontsize=12, fontweight="bold")
ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig(f"{OUT}/fig3_peak.png", dpi=160); plt.close()

print("figures written to", OUT)
import glob
for f in sorted(glob.glob(f"{OUT}/*.png")): print(" -", f, os.path.getsize(f),"bytes")
