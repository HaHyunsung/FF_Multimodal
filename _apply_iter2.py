"""iter2: Fusion 센서 LSTM warm-start+freeze + 공정평가 셀 + cell30 제거 + EPOCHS 20.
_kaggle_push/ 노트북을 in-place 수정."""
import json

P = "_kaggle_push/multimodal-anomaly-detection.ipynb"
nb = json.load(open(P, encoding="utf-8"))
cells = nb["cells"]

def src(i): return "".join(cells[i]["source"])

# ---- 1) EPOCHS 30 -> 20 (config 셀 탐색) ----
done_epochs = False
for c in cells:
    if c["cell_type"] == "code":
        s = "".join(c["source"])
        if "EPOCHS = 30" in s:
            c["source"] = s.replace("EPOCHS = 30", "EPOCHS = 20  # iter2: 런타임 바운드(early stopping 보유)").splitlines(keepends=True)
            done_epochs = True
            break
assert done_epochs, "EPOCHS=30 not found"

# ---- 2) cell24: warm-start + freeze 삽입 ----
ci24 = next(i for i,c in enumerate(cells)
            if c["cell_type"]=="code" and "fusion_attn_model = CrossAttentionFusion" in "".join(c["source"]))
c24 = src(ci24)

old_concat = '''    fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
'''
new_concat = '''    fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    # iter2: 단독 센서(전체 데이터 F1 0.927) LSTM 가중치 warm-start + freeze
    fusion_model.sensor_lstm.load_state_dict(sensor_model.lstm.state_dict())
    for _p in fusion_model.sensor_lstm.parameters():
        _p.requires_grad = False
'''
assert old_concat in c24
c24 = c24.replace(old_concat, new_concat)

old_attn = '''    fusion_attn_model = CrossAttentionFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
'''
new_attn = '''    fusion_attn_model = CrossAttentionFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
    # iter2: 센서 LSTM warm-start + freeze
    fusion_attn_model.sensor_lstm.load_state_dict(sensor_model.lstm.state_dict())
    for _p in fusion_attn_model.sensor_lstm.parameters():
        _p.requires_grad = False
'''
assert old_attn in c24
c24 = c24.replace(old_attn, new_attn)
cells[ci24]["source"] = c24.splitlines(keepends=True)

# ---- 3) 공정평가 셀 신규 삽입 (Results Comparison 마크다운 앞) ----
FAIR = '''# ============================================================
# iter2: 공정 비교(fair eval) — 센서·이미지 단독을 Fusion과 동일한 cycle 4·9 테스트셋에서 재평가
# (기존 sensor_result/image_result는 전체 사이클 셋이라 Fusion과 직접 비교 불가했음)
# ============================================================
if HAS_IMAGES:
    _crit = nn.CrossEntropyLoss()
    sensor_fair_loader = DataLoader(
        SensorSequenceDataset(X_test_mm, y_test_mm), batch_size=BATCH_SIZE)
    sensor_fair = evaluate_model(sensor_model, sensor_fair_loader, _crit, "sensor")

    image_fair_loader = DataLoader(
        ImageAnomalyDataset(img_test, y_test_mm, test_transform),
        batch_size=BATCH_SIZE, num_workers=2)
    image_fair = evaluate_model(image_model, image_fair_loader, _crit, "image")

    print("\\n" + "=" * 72)
    print(" FAIR COMPARISON  (all models on the SAME cycle 4·9 test set)")
    print("=" * 72)
    print(f"{'Model':<30}{'Accuracy':>10}{'Precision':>10}{'Recall':>10}{'F1':>10}")
    print("-" * 72)
    for _nm, _r in [("Sensor@cyc4_9", sensor_fair), ("Image@cyc4_9", image_fair),
                    ("Fusion-Concat", fusion_result), ("Fusion-CrossAttn", fusion_attn_result)]:
        print(f"{_nm:<30}{_r['accuracy']:>10.4f}{_r['precision']:>10.4f}{_r['recall']:>10.4f}{_r['f1']:>10.4f}")
    print("=" * 72)
    print(f"\\n[GOAL] 센서@cyc4_9 F1={sensor_fair['f1']:.4f} | "
          f"best Fusion F1={max(fusion_result['f1'], fusion_attn_result['f1']):.4f} | "
          f"{'DONE: Fusion>=Sensor' if max(fusion_result['f1'], fusion_attn_result['f1']) >= sensor_fair['f1'] else 'not yet'}")
else:
    sensor_fair, image_fair = None, None
'''
fair_cell = {"cell_type":"code","metadata":{},"execution_count":None,"outputs":[],
             "source":FAIR.splitlines(keepends=True)}
# Results Comparison 마크다운 위치 찾기
ci_results_md = next(i for i,c in enumerate(cells)
                     if c["cell_type"]=="markdown" and "Results Comparison" in "".join(c["source"]))
cells.insert(ci_results_md, fair_cell)

# ---- 4) 진단 glob 셀(cell30) 제거 ----
before = len(cells)
cells[:] = [c for c in cells if not (
    c["cell_type"]=="code" and ("=== 폴더 구조 ===" in "".join(c["source"])
                                 or 'glob.glob(f"{base}/**/*.png"' in "".join(c["source"])))]
removed = before - len(cells)

# ---- 저장 ----
for c in cells:
    if c["cell_type"]=="code":
        c["outputs"]=[]; c["execution_count"]=None
json.dump(nb, open(P,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("EPOCHS->20 OK | warm-start+freeze in cell", ci24, "| fair cell inserted at", ci_results_md, "| diagnostic cells removed:", removed, "| total cells", len(cells))
