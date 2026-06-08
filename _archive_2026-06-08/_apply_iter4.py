"""iter4: Decision-Level(Late) 확률 융합 셀을 fair-eval 셀 직후에 삽입."""
import json
P = "_kaggle_push/multimodal-anomaly-detection.ipynb"
nb = json.load(open(P, encoding="utf-8"))
cells = nb["cells"]

DLF = r'''# ============================================================
# iter4: Decision-Level(Late) 확률 융합 — 학습된 sensor_model + image_model
# 학습형 fusion head 우회. 이미지 있을 때만 결합, 가중치 w는 train에서 선택(test 누수 방지).
# ============================================================
if HAS_IMAGES:
    @torch.no_grad()
    def _softmax_probs(model, loader):
        model.eval(); ps, ys = [], []
        for batch in loader:
            X, y = batch[0], batch[1]
            logits = model(X.to(DEVICE))
            ps.append(torch.softmax(logits, dim=1).cpu().numpy())
            ys.append(y.numpy())
        return np.concatenate(ps), np.concatenate(ys)

    # 멀티모달 train/test 에서 두 단독 모델의 확률 (loader shuffle=False로 정렬 유지)
    s_tr, y_tr = _softmax_probs(sensor_model,
        DataLoader(SensorSequenceDataset(X_train_mm, y_train_mm), batch_size=BATCH_SIZE))
    i_tr, _ = _softmax_probs(image_model,
        DataLoader(ImageAnomalyDataset(img_train, y_train_mm, test_transform), batch_size=BATCH_SIZE, num_workers=2))
    s_te, y_te = _softmax_probs(sensor_model,
        DataLoader(SensorSequenceDataset(X_test_mm, y_test_mm), batch_size=BATCH_SIZE))
    i_te, _ = _softmax_probs(image_model,
        DataLoader(ImageAnomalyDataset(img_test, y_test_mm, test_transform), batch_size=BATCH_SIZE, num_workers=2))

    has_tr = np.array([bool(p) for p in img_train])
    has_te = np.array([bool(p) for p in img_test])

    def _fuse_f1(s_p, i_p, has, y, w):
        p = s_p.copy()
        p[has] = (1 - w) * s_p[has] + w * i_p[has]
        return f1_score(y, p.argmax(1), average="weighted", zero_division=0)

    ws = [k / 20 for k in range(21)]
    best_w = max(ws, key=lambda w: _fuse_f1(s_tr, i_tr, has_tr, y_tr, w))

    p_te = s_te.copy()
    p_te[has_te] = (1 - best_w) * s_te[has_te] + best_w * i_te[has_te]
    dlf_pred = p_te.argmax(1)
    decision_fusion_result = {
        "accuracy": accuracy_score(y_te, dlf_pred),
        "precision": precision_score(y_te, dlf_pred, average="weighted", zero_division=0),
        "recall": recall_score(y_te, dlf_pred, average="weighted", zero_division=0),
        "f1": f1_score(y_te, dlf_pred, average="weighted", zero_division=0),
        "preds": dlf_pred, "labels": y_te,
    }
    print("\n" + "=" * 72)
    print(f" DECISION-LEVEL FUSION (late) | best image weight w={best_w:.2f} (tuned on train)")
    print("=" * 72)
    print(f"Sensor@cyc4_9      F1 : {sensor_fair['f1']:.4f}")
    print(f"Fusion-Concat      F1 : {fusion_result['f1']:.4f}")
    print(f"Decision-Fusion    F1 : {decision_fusion_result['f1']:.4f}   "
          f"(img-present {int(has_te.sum())}/{len(has_te)})")
    print("=" * 72)
    print(f"[GOAL-DLF] {'*** ACHIEVED: Decision-Fusion > Sensor ***' if decision_fusion_result['f1'] > sensor_fair['f1'] else 'not yet'}")
    print("=" * 72)
else:
    decision_fusion_result = None
'''

fair_i = next(i for i,c in enumerate(cells)
              if c["cell_type"]=="code" and "FAIR COMPARISON" in "".join(c["source"]))
cell = {"cell_type":"code","metadata":{},"execution_count":None,"outputs":[],
        "source":DLF.splitlines(keepends=True)}
cells.insert(fair_i + 1, cell)

for c in cells:
    if c["cell_type"]=="code":
        c["outputs"]=[]; c["execution_count"]=None
json.dump(nb, open(P,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("iter4 DLF cell inserted after fair-eval cell idx", fair_i, "| total cells", len(cells))
