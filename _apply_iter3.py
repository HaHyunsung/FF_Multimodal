"""iter3: fusion 두 모델의 이미지 인코더를 학습된 image_model 가중치로 warm-start (frozen 유지)."""
import json
P = "_kaggle_push/multimodal-anomaly-detection.ipynb"
nb = json.load(open(P, encoding="utf-8"))
cells = nb["cells"]

ci = next(i for i,c in enumerate(cells)
          if c["cell_type"]=="code" and "fusion_attn_model = CrossAttentionFusion" in "".join(c["source"]))
s = "".join(cells[ci]["source"])

# concat: 센서 freeze 직후 이미지 인코더 warm-start 삽입
concat_anchor = '''    fusion_model.sensor_lstm.load_state_dict(sensor_model.lstm.state_dict())
    for _p in fusion_model.sensor_lstm.parameters():
        _p.requires_grad = False
'''
concat_new = concat_anchor + '''    # iter3: 이미지 인코더를 학습된 image_model(≈0.99) 가중치로 warm-start (frozen 유지)
    fusion_model.image_encoder.load_state_dict(image_model.backbone.state_dict())
'''
assert concat_anchor in s, "concat sensor-freeze anchor not found"
s = s.replace(concat_anchor, concat_new)

# cross-attn: 센서 freeze 직후 이미지 backbone warm-start 삽입
attn_anchor = '''    fusion_attn_model.sensor_lstm.load_state_dict(sensor_model.lstm.state_dict())
    for _p in fusion_attn_model.sensor_lstm.parameters():
        _p.requires_grad = False
'''
attn_new = attn_anchor + '''    # iter3: 이미지 backbone warm-start (학습된 image_model의 conv 계층, Sequential children[:-2] 매칭)
    fusion_attn_model.image_backbone.load_state_dict(
        nn.Sequential(*list(image_model.backbone.children())[:-2]).state_dict())
'''
assert attn_anchor in s, "attn sensor-freeze anchor not found"
s = s.replace(attn_anchor, attn_new)

cells[ci]["source"] = s.splitlines(keepends=True)

for c in cells:
    if c["cell_type"]=="code":
        c["outputs"]=[]; c["execution_count"]=None
json.dump(nb, open(P,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("iter3 applied to cell", ci)
