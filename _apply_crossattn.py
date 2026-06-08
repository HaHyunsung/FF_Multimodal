"""Kaggle 노트북에 Cross-Attention Fusion 개선을 통합한다.
_kaggle_pull/multimodal-anomaly-detection.ipynb 를 수정 → _kaggle_push/ 에 저장."""
import json, os, shutil, copy

SRC = "_kaggle_pull/multimodal-anomaly-detection.ipynb"
PUSH_DIR = "_kaggle_push"
nb = json.load(open(SRC, encoding="utf-8"))
cells = nb["cells"]

def src(i): return "".join(cells[i]["source"])

# ---------------------------------------------------------------
# 1) Cell 16: CrossAttentionFusion 클래스 추가 (맨 끝 print 앞에 삽입)
# ---------------------------------------------------------------
CROSS_ATTN_CLASS = '''

# ============================================================
# Model 4: Cross-Attention Fusion (개선안 Ⓐ - 최우선)
# ============================================================
class CrossAttentionFusion(nn.Module):
    """
    Cross-Attention Fusion:
      [Image]  -> ResNet18 layer4 (frozen) -> spatial map [B,512,7,7] -> 49 image tokens
      [Sensor] -> BiLSTM -> f_sensor (256) -> query
      sensor(Q) 가 image tokens(K,V) 에 attention -> image_context
      z = concat([f_sensor, image_context]) -> FC -> class

    이미지가 없거나(마스킹) 정보량이 낮으면 image_context 기여가 작아져
    f_sensor 경로가 분류를 지배 -> 센서로 자동 폴백 (concat 방식의 노이즈 희석 완화).
    """
    def __init__(self, sensor_input_dim, num_classes=NUM_CLASSES, dropout=DROPOUT,
                 d_model=256, n_heads=4):
        super().__init__()
        # Image branch: avgpool/fc 제거 -> spatial feature map 유지 (frozen)
        resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        self.image_backbone = nn.Sequential(*list(resnet.children())[:-2])  # [B,512,7,7]
        for p in self.image_backbone.parameters():
            p.requires_grad = False
        self.img_proj = nn.Linear(512, d_model)

        # Sensor branch
        self.sensor_lstm = nn.LSTM(
            sensor_input_dim, 128, 2,
            batch_first=True, dropout=dropout, bidirectional=True,
        )
        self.sensor_proj = nn.Linear(256, d_model)

        # Cross-attention: query=sensor, key/value=image tokens
        self.cross_attn = nn.MultiheadAttention(
            d_model, n_heads, dropout=dropout, batch_first=True
        )
        self.attn_norm = nn.LayerNorm(d_model)

        # Fusion head: [f_sensor(256) ; image_context(d_model)]
        self.fusion_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(256 + d_model, 256),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, sensor_seq, images, has_image=None):
        # Sensor features
        _, (h_n, _) = self.sensor_lstm(sensor_seq)
        f_sensor = torch.cat([h_n[-2], h_n[-1]], dim=1)       # [B,256]
        q = self.sensor_proj(f_sensor).unsqueeze(1)            # [B,1,d]

        # Image tokens (frozen backbone)
        with torch.no_grad():
            fmap = self.image_backbone(images)                 # [B,512,7,7]
        tokens = fmap.flatten(2).transpose(1, 2)               # [B,49,512]
        tokens = self.img_proj(tokens)                         # [B,49,d]

        attn_out, _ = self.cross_attn(q, tokens, tokens)       # [B,1,d]
        attn_out = self.attn_norm(attn_out.squeeze(1))         # [B,d]

        # 이미지 없는 샘플은 image_context=0 -> 센서로 폴백
        if has_image is not None:
            attn_out = attn_out * has_image.float().unsqueeze(1)

        z = torch.cat([f_sensor, attn_out], dim=1)             # [B,256+d]
        return self.fusion_head(z)

'''
c16 = src(16)
marker = 'print("Models defined.")'
assert marker in c16, "cell16 marker not found"
c16_new = c16.replace(marker, CROSS_ATTN_CLASS.lstrip("\n") + "\n\n" + marker)
cells[16]["source"] = c16_new.splitlines(keepends=True)

# ---------------------------------------------------------------
# 2) Cell 24: mm_class_weights + cross-attn 학습 추가
# ---------------------------------------------------------------
c24 = src(24)
old_tail = '''    fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    fusion_result, fusion_history = run_training(
        fusion_model, train_mm_loader, test_mm_loader,
        model_type="fusion", model_name="fusion_dlf"
    )
else:
    print("[SKIP] No image data. Fusion model requires images.")
    fusion_result, fusion_history = None, None'''
assert old_tail in c24, "cell24 tail not found"
new_tail = '''    # Fusion 데이터셋(cycle 4·9 시점) 분포 기반 class weight
    # (센서 전체 분포와 다르므로 fusion 전용으로 재계산해 두 모델에 동일 적용)
    mm_counter = Counter(y_train_mm.tolist())
    mm_total = sum(mm_counter.values())
    mm_class_weights = torch.FloatTensor([
        mm_total / (NUM_CLASSES * mm_counter.get(i, 1)) for i in range(NUM_CLASSES)
    ])
    mm_class_weights = mm_class_weights / mm_class_weights.sum() * NUM_CLASSES
    print(f"Fusion class dist: {dict(mm_counter)}")
    print(f"Fusion class weights: {mm_class_weights.tolist()}")

    # --- (baseline) Decision-Level Concat Fusion ---
    fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    fusion_result, fusion_history = run_training(
        fusion_model, train_mm_loader, test_mm_loader,
        model_type="fusion", model_name="fusion_dlf",
        custom_class_weights=mm_class_weights,
    )

    # --- (개선 Ⓐ) Cross-Attention Fusion ---
    fusion_attn_model = CrossAttentionFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    fusion_attn_result, fusion_attn_history = run_training(
        fusion_attn_model, train_mm_loader, test_mm_loader,
        model_type="fusion", model_name="fusion_crossattn",
        custom_class_weights=mm_class_weights,
    )
else:
    print("[SKIP] No image data. Fusion model requires images.")
    fusion_result, fusion_history = None, None
    fusion_attn_result, fusion_attn_history = None, None'''
cells[24]["source"] = c24.replace(old_tail, new_tail).splitlines(keepends=True)

# ---------------------------------------------------------------
# 3) Cell 26: Fusion-CrossAttn 결과 추가 + 색상 4개 대응
# ---------------------------------------------------------------
c26 = src(26)
old_collect = '''if fusion_result:
    all_results["Fusion (Sensor+Image)"] = fusion_result
    all_histories["Fusion (Sensor+Image)"] = fusion_history'''
assert old_collect in c26, "cell26 collect not found"
new_collect = '''if fusion_result:
    all_results["Fusion-Concat"] = fusion_result
    all_histories["Fusion-Concat"] = fusion_history
if fusion_attn_result:
    all_results["Fusion-CrossAttn"] = fusion_attn_result
    all_histories["Fusion-CrossAttn"] = fusion_attn_history'''
c26 = c26.replace(old_collect, new_collect)
# 색상: 3 -> 5개, 인덱싱 안전하게 modulo
c26 = c26.replace(
    'colors = ["#2196F3", "#FF9800", "#4CAF50"]',
    'colors = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63", "#9C27B0"]')
c26 = c26.replace("label=name, color=colors[i])", "label=name, color=colors[i % len(colors)])")
cells[26]["source"] = c26.splitlines(keepends=True)

# ---------------------------------------------------------------
# outputs/execution_count 정리 (push용)
# ---------------------------------------------------------------
for c in cells:
    if c.get("cell_type") == "code":
        c["outputs"] = []
        c["execution_count"] = None

# ---------------------------------------------------------------
# 저장 + 메타데이터 복사
# ---------------------------------------------------------------
os.makedirs(PUSH_DIR, exist_ok=True)
json.dump(nb, open(f"{PUSH_DIR}/multimodal-anomaly-detection.ipynb", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
shutil.copy("_kaggle_pull/kernel-metadata.json", f"{PUSH_DIR}/kernel-metadata.json")
print("written:", PUSH_DIR)
print("cell16 lines:", len(cells[16]["source"]))
print("cell24 lines:", len(cells[24]["source"]))
print("cell26 lines:", len(cells[26]["source"]))
