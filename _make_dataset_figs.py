# -*- coding: utf-8 -*-
"""데이터셋 슬라이드용 센서 샘플 시각화 (영문 라벨로 폰트 이슈 회피)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os

OUT = "_ppt_assets"
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv("data/Multi-modal Dataset/FF_Multimodal.csv", low_memory=False)
lm = {"Normal": "Normal", "NoBody1": "NoBody1", "NoNose": "NoNose",
      "NoNose,NoBody2": "NoNose_NoBody2", "NoNose,NoBody2,NoBody1": "NoNose_NoBody2_NoBody1",
      "NoBody2": "NoBody1", "NoBody2,NoBody1": "NoBody1"}
df = df[df["actual_state"] != "E_STOPPED"].copy()
df["label"] = df["actual_state"].map(lm)

# 주요 센서 3채널, 클래스별 한 사이클 비교
cols = [("I_R04_Gripper_Load", "Gripper Load (R04)"),
        ("M_R01_SJointAngle_Degree", "Joint Angle (R01 S)"),
        ("Q_VFD1_Temperature", "Conveyor Temp (VFD1)")]
classes = ["Normal", "NoNose", "NoNose_NoBody2"]
colors = {"Normal": "#2E78B7", "NoNose": "#E15554", "NoNose_NoBody2": "#F4A024"}

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for ax, (col, title) in zip(axes, cols):
    for lbl in classes:
        sub = df[df["label"] == lbl]
        if len(sub) == 0:
            continue
        cyc = sub["Cycle_Count_New"].iloc[0]
        seg = df[df["Cycle_Count_New"] == cyc][col].values[:200]
        ax.plot(seg, label=lbl, color=colors[lbl], alpha=0.85, linewidth=1.6)
    ax.set_title(title, fontsize=13, fontweight="bold", color="#1E2A4A")
    ax.set_xlabel("timestep", fontsize=10)
    ax.legend(fontsize=9, frameon=False)
    ax.grid(alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
plt.suptitle("22-channel Sensor Time-Series (per anomaly class, one cycle)",
             fontsize=14, fontweight="bold", color="#1E2A4A")
plt.tight_layout()
plt.savefig(f"{OUT}/sensor_sample.png", dpi=160, bbox_inches="tight")
plt.close()
print("saved:", f"{OUT}/sensor_sample.png")

# 클래스 분포 (데이터셋 설명용)
fig, ax = plt.subplots(figsize=(7, 4))
vc = df["label"].value_counts()
bars = ax.bar(range(len(vc)), vc.values, color="#2E78B7")
ax.set_xticks(range(len(vc)))
ax.set_xticklabels(vc.index, rotation=20, ha="right", fontsize=9)
ax.set_ylabel("records", fontsize=10)
ax.set_title("Class Distribution (after merge, E_STOPPED removed)",
             fontsize=12, fontweight="bold", color="#1E2A4A")
ax.grid(axis="y", alpha=0.25)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
for b, v in zip(bars, vc.values):
    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
plt.tight_layout()
plt.savefig(f"{OUT}/class_dist.png", dpi=160, bbox_inches="tight")
plt.close()
print("saved:", f"{OUT}/class_dist.png")
print("label counts:", df["label"].value_counts().to_dict())
