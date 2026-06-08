# -*- coding: utf-8 -*-
"""마지막 추가실험 셀 ⑤ — 강한 센서 약화로 진짜 균형 통제."""
import json

CODE = r'''# [추가실험 ⑤] 균형 통제 v2 — 센서를 강하게 약화하여 진짜 "0.8 vs 0.8" 균형 검증
# 동기: 이전 균형통제(③)는 센서 hidden=32, 3ep으로 약화해도 F1 0.95에 머물렀음.
#       hidden=16, 2ep으로 더 강하게 약화하여 사용자가 원한 ~0.8 수준 달성 목표.
# 평가: 주 평가는 FAIR 전체 9,521 시점 (현실적), 보조로 이미지 존재 구간(2,161)도 출력.
if HAS_IMAGES:
    SHIDDEN = 16
    SEPOCH = 2
    print(f"\n=== 강한 센서 약화 학습: hidden={SHIDDEN}, {SEPOCH} epochs ===")
    sensor_vw = SensorLSTM(input_dim=NUM_SENSOR_FEATURES, hidden_dim=SHIDDEN).to(DEVICE)
    run_training(sensor_vw, train_sensor_loader, test_sensor_loader,
                 model_type="sensor", model_name="sensor_very_weak", epochs=SEPOCH)

    @torch.no_grad()
    def _pb(model, loader):
        model.eval(); out = []
        for b in loader:
            out.append(torch.softmax(model(b[0].to(DEVICE)), 1).cpu().numpy())
        return np.concatenate(out)

    # === 확률 계산 (cycle 4·9 train/test 9,521 전체 시점) ===
    s_tr = _pb(sensor_vw, DataLoader(SensorSequenceDataset(X_train_mm, y_train_mm), batch_size=BATCH_SIZE))
    s_te = _pb(sensor_vw, DataLoader(SensorSequenceDataset(X_test_mm, y_test_mm), batch_size=BATCH_SIZE))
    i_tr = _pb(image_model_weak, DataLoader(
        ImageAnomalyDataset(img_train, y_train_mm, test_transform, image_paths2=img_train2),
        batch_size=BATCH_SIZE, num_workers=2))
    i_te = _pb(image_model_weak, DataLoader(
        ImageAnomalyDataset(img_test, y_test_mm, test_transform, image_paths2=img_test2),
        batch_size=BATCH_SIZE, num_workers=2))

    # === Decision-Fusion 가중치 w 탐색 (train, 이미지 있을 때만 결합) ===
    def _fuse(s, i, has, y, w):
        p = s.copy()
        p[has] = (1 - w) * s[has] + w * i[has]
        return f1_score(y, p.argmax(1), average="weighted", zero_division=0)
    bw = max([k / 20 for k in range(21)], key=lambda w: _fuse(s_tr, i_tr, has_tr, y_train_mm, w))

    # === 평가 1: FAIR 전체 9,521 시점 (주 평가) ===
    f_s = f1_score(y_test_mm, s_te.argmax(1), average="weighted", zero_division=0)
    f_i = f1_score(y_test_mm, i_te.argmax(1), average="weighted", zero_division=0)
    f_fz = _fuse(s_te, i_te, has_te, y_test_mm, bw)

    print("\n" + "=" * 72)
    print(f" [균형 통제 v2] 센서 h{SHIDDEN}/{SEPOCH}ep + 이미지 약화 3ep · FAIR 전체 9,521 시점")
    print("=" * 72)
    print(f"Sensor (very weak)  F1 : {f_s:.4f}   ← ~0.8 목표")
    print(f"Image  (weak)       F1 : {f_i:.4f}   ← 결측 77% 포함 (낮음 정상)")
    print(f"Decision-Fusion     F1 : {f_fz:.4f}   (w={bw:.2f})")
    print("=" * 72)
    if f_fz > max(f_s, f_i):
        print(f"*** FAIR 전체 멀티모달 이득 O ({f_fz:.4f} > Sensor {f_s:.4f}, Image {f_i:.4f}) ***")
    else:
        print(f"FAIR 전체 이득 미미 (정직 보고)")

    # === 평가 2: 이미지 존재 구간 2,161 시점 (보조, "두 모달 비등" 그림) ===
    m = has_te
    f_s_p = f1_score(y_test_mm[m], s_te[m].argmax(1), average="weighted", zero_division=0)
    f_i_p = f1_score(y_test_mm[m], i_te[m].argmax(1), average="weighted", zero_division=0)
    p_pres = (1 - bw) * s_te[m] + bw * i_te[m]
    f_fz_p = f1_score(y_test_mm[m], p_pres.argmax(1), average="weighted", zero_division=0)

    print(f"\n[보조] 같은 모델, 이미지 존재 구간 2,161 시점만:")
    print(f"  Sensor F1            : {f_s_p:.4f}   ← 약화된 센서가 쉬운 구간에서 얼마나 나오나")
    print(f"  Image  F1            : {f_i_p:.4f}   ← 약화된 이미지")
    print(f"  Decision-Fusion F1   : {f_fz_p:.4f}")
    print(f"  → 두 단독 차이: {abs(f_s_p - f_i_p):.4f} (0에 가까울수록 균형)")
    if f_fz_p > max(f_s_p, f_i_p):
        print(f"  *** 균형 구간 멀티모달 이득 O ***")
    print("=" * 72)
'''

def mkcell(code):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": code.splitlines(keepends=True)}

for path in ["multimodal_anomaly_detection_최신본.ipynb",
             "_kaggle_push/multimodal-anomaly-detection.ipynb"]:
    nb = json.load(open(path, encoding="utf-8"))
    cells = nb["cells"]
    joined = "".join("".join(c["source"]) for c in cells)
    if "추가실험 ⑤" in joined:
        print(path, "- already has cell ⑤, skip")
        continue
    # 추가실험 ④(부트스트랩) 다음에 삽입
    idx = None
    for i, c in enumerate(cells):
        src = "".join(c["source"])
        if "추가실험 ④" in src or "부트스트랩" in src:
            idx = i
    if idx is None:
        idx = len(cells) - 1
    cells.insert(idx + 1, mkcell(CODE))
    json.dump(nb, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(path, f"- inserted at {idx+1}, total {len(cells)} cells")
