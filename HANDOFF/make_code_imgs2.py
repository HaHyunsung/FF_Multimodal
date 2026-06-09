# -*- coding: utf-8 -*-
"""추가 코드-셀 이미지(BiLSTM·ResNet·Concat·Decision) — crossattn과 동일 스타일."""
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

bilstm = '''class SensorLSTM(nn.Module):                 # 센서 단독 (BiLSTM)
    def __init__(self, input_dim, hidden_dim=128, num_layers=2, ...):
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers,
                            batch_first=True, bidirectional=True, dropout=dropout)
        self.classifier = nn.Sequential(            # 256 -> 64 -> 5클래스
            nn.Dropout(dropout), nn.Linear(hidden_dim*2, 64),
            nn.ReLU(), nn.Linear(64, NUM_CLASSES))
    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        hidden = torch.cat([h_n[-2], h_n[-1]], dim=1)   # 양방향 마지막 은닉 결합
        return self.classifier(hidden)'''

resnet = '''class ImageResNet(nn.Module):                # 이미지 단독 (ResNet18 전이학습)
    def __init__(self, ...):
        self.backbone = models.resnet18(weights=ResNet18_Weights.DEFAULT)  # ImageNet
        self.backbone.fc = nn.Identity()                       # 512차원 특징
        self.classifier = nn.Sequential(nn.Dropout(d), nn.Linear(512, 128),
                                        nn.ReLU(), nn.Linear(128, NUM_CLASSES))
    def _encode(self, x):                        # 멀티뷰: 카메라 2장 특징 평균
        if x.dim() == 5:
            B, V = x.shape[:2]
            f = self.backbone(x.reshape(B*V, *x.shape[2:]))
            return f.view(B, V, -1).mean(dim=1)                # 두 카메라 평균
        return self.backbone(x)
    def forward(self, x): return self.classifier(self._encode(x))'''

concat = '''class MultimodalFusion(nn.Module):           # Concat 융합 (특징 결합)
    def forward(self, sensor_seq, images, has_image=None):
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)   # 센서 특징 256
        f_image  = self._encode_img(images)               # 이미지 특징 512
        if has_image is not None:                          # 이미지 없으면 0 마스킹
            f_image = f_image * has_image.float().unsqueeze(1)
        z = torch.cat([f_image, f_sensor], dim=1)          # 768로 이어붙임
        return self.fusion_head(z)                         # FC -> 5클래스'''

decision = '''# Decision-Level 융합: 두 단독 모델의 softmax 확률을 가중 평균
# 가중치 w는 train에서 grid search로 선택 (test 누수 방지)
p = sensor_prob.copy()                                 # 이미지 없으면 센서로 폴백
p[has_image] = (1 - w) * sensor_prob[has_image] + w * image_prob[has_image]
pred = p.argmax(1)                                     # 최종 예측'''

render(bilstm, "code_bilstm.png", 7)
render(resnet, "code_resnet.png", 8)
render(concat, "code_concat.png", 19)
render(decision, "code_decision.png", 17)
