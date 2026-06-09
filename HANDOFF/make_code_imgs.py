# -*- coding: utf-8 -*-
"""보고서용 코드-셀 이미지(Kaggle 셀 스타일) 렌더링."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

OUT = "_ppt_assets_iter6"

def render(code, fname, n):
    lines = code.strip("\n").split("\n")
    h = 0.30 * len(lines) + 0.55
    fig = plt.figure(figsize=(9.2, h), dpi=170)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                 facecolor="#FBFBFB", edgecolor="#D0D0D0", lw=1.0))
    # In [n]: 거터
    ax.add_patch(plt.Rectangle((0, 0), 0.072, 1, transform=ax.transAxes,
                 facecolor="#F0F0F0", edgecolor="#D0D0D0", lw=0.5))
    ax.text(0.064, 0.94, f"In [{n}]:", transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color="#3572A5", family="monospace")
    y = 0.93
    for ln in lines:
        # 주석은 회색, 키워드 강조
        if ln.strip().startswith("#"):
            color = "#7A8B99"
        elif any(ln.lstrip().startswith(k) for k in ("from ", "import ", "class ", "def ", "return ", "if ", "for ")):
            color = "#0B3D91"
        else:
            color = "#1A1A1A"
        ax.text(0.085, y, ln if ln else " ", transform=ax.transAxes, ha="left", va="top",
                fontsize=9.2, color=color, family="monospace")
        y -= 0.30 / h * 1.0 * (1.0)
        y = max(y, 0.02)
    # 균등 줄간격 재계산
    plt.close(fig)
    # 다시 정확히 그리기 (균등 간격)
    fig = plt.figure(figsize=(9.2, h), dpi=170)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                 facecolor="#FBFBFB", edgecolor="#D0D0D0", lw=1.0))
    ax.add_patch(plt.Rectangle((0, 0), 0.072, 1, transform=ax.transAxes,
                 facecolor="#F0F0F0", edgecolor="#D0D0D0", lw=0.5))
    ax.text(0.064, 0.93, f"In [{n}]:", transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color="#3572A5", family="monospace")
    top, bot = 0.92, 0.06
    step = (top - bot) / max(len(lines) - 1, 1)
    for i, ln in enumerate(lines):
        if ln.strip().startswith("#"):
            color = "#7A8B99"
        elif any(ln.lstrip().startswith(k) for k in ("from ", "import ", "class ", "def ", "return ", "if ", "for ", "with ")):
            color = "#0B3D91"
        else:
            color = "#1A1A1A"
        ax.text(0.085, top - i * step, ln if ln else " ", transform=ax.transAxes,
                ha="left", va="top", fontsize=9.0, color=color, family="Malgun Gothic")
    fig.savefig(f"{OUT}/{fname}", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print("saved", fname)


split_code = '''# 사이클 단위 8:2 분할 — 같은 사이클이 train/test에 섞이지 않게 (데이터 누수 방지)
from sklearn.model_selection import train_test_split

train_cycles, test_cycles = train_test_split(
    cycles, train_size=TRAIN_RATIO, random_state=SEED,
    stratify=[cycle_has_anomaly[c] for c in cycles],   # 결함 유무로 층화
)
train_df = df[df["Cycle_Count_New"].isin(train_cycles)].reset_index(drop=True)
test_df  = df[df["Cycle_Count_New"].isin(test_cycles)].reset_index(drop=True)'''

attn_code = '''class CrossAttentionFusion(nn.Module):           # 적응형 융합 (핵심 기여)
    def forward(self, sensor_seq, images, has_image=None):
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)       # [B,256]
        q = self.sensor_proj(f_sensor).unsqueeze(1)           # query = 센서
        tokens = self.img_proj(self._image_tokens(images))    # key/value = 이미지 토큰
        attn_out, _ = self.cross_attn(q, tokens, tokens)      # 센서가 이미지에 주의
        if has_image is not None:                             # 이미지 없으면 센서 폴백
            attn_out = attn_out * has_image.float().unsqueeze(1)
        z = torch.cat([f_sensor, attn_out.squeeze(1)], dim=1)
        return self.fusion_head(z)'''

render(split_code, "code_split.png", 9)
render(attn_code, "code_crossattn.png", 21)
