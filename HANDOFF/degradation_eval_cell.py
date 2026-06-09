# ============================================================================
# [열화 견고성 실험] 학습된 모델을 '깨끗한' vs '열화된' 테스트 이미지로 추론만 비교
#   - 재학습 없음. 위쪽 "7. Training & Evaluation Functions"까지 실행한 뒤 이 셀 실행.
#   - 사전: iter6(v2) 출력(.pt 4개)을 Add Input(Notebook 탭)으로 마운트해 둘 것.
# ============================================================================
import glob, numpy as np, torch
from torch.utils.data import DataLoader
from torchvision import transforms
from sklearn.metrics import f1_score

def W(name):
    hits = glob.glob(f"/kaggle/input/**/{name}", recursive=True)
    assert hits, f"가중치 못 찾음: {name}  (iter6 출력을 Add Input 했는지 확인)"
    return hits[0]

# --- 1) 테스트 멀티모달 데이터(이미지 존재 구간) 재구성 (학습 안 함) ---
df_img_test  = df_image[df_image["Cycle_Count_New"].isin(test_cycles)].reset_index(drop=True)
df_img_train = df_image[df_image["Cycle_Count_New"].isin(train_cycles)].reset_index(drop=True)

def create_mm(data_df, img_df, cols, seq_len):
    lut, lut2 = {}, {}
    for _, r in img_df.iterrows():
        k = (r["Cycle_Count_New"], r["CycleState"])
        if k not in lut:
            lut[k] = r["cam1_path"]; lut2[k] = r["cam2_path"]
    Xs, p1, p2, ys = [], [], [], []
    for cid, g in data_df.groupby("Cycle_Count_New"):
        v = g[cols].values.astype(np.float32); lbl = g["label_encoded"].values; st = g["CycleState"].values
        if len(v) < seq_len: continue
        for i in range(len(v) - seq_len):
            t = i + seq_len
            if st[t] in [4, 9]:
                Xs.append(v[i:i+seq_len]); ys.append(lbl[t])
                p1.append(lut.get((cid, st[t]))); p2.append(lut2.get((cid, st[t])))
    return np.array(Xs), p1, p2, np.array(ys)

X_tr, img_tr, img_tr2, y_tr = create_mm(train_df, df_img_train, SENSOR_COLUMNS, SEQUENCE_LENGTH)
X_te, img_te, img_te2, y_te = create_mm(test_df,  df_img_test,  SENSOR_COLUMNS, SEQUENCE_LENGTH)
has_tr = np.array([bool(p) for p in img_tr]); has_te = np.array([bool(p) for p in img_te])
print(f"이미지 존재 시점: train {has_tr.sum()}, test {has_te.sum()}")

# --- 2) 학습된 모델 로드 (추론 전용) ---
sensor_model = SensorLSTM(input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
sensor_model.load_state_dict(torch.load(W("sensor_bilstm_best.pt"), weights_only=True)); sensor_model.eval()
image_model  = ImageResNet().to(DEVICE)
image_model.load_state_dict(torch.load(W("image_resnet18_best.pt"), weights_only=True)); image_model.eval()
fusion_model = MultimodalFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
fusion_model.load_state_dict(torch.load(W("fusion_dlf_best.pt"), weights_only=True)); fusion_model.eval()
attn_model   = CrossAttentionFusion(sensor_input_dim=NUM_SENSOR_FEATURES).to(DEVICE)
attn_model.load_state_dict(torch.load(W("fusion_crossattn_best.pt"), weights_only=True)); attn_model.eval()

# --- 3) 깨끗한 / 열화된 이미지 transform (현실적 악조건 모사) ---
MEAN=[0.485,0.456,0.406]; STD=[0.229,0.224,0.225]
clean_tf = test_transform                       # 기존(깨끗) transform 재사용
degrade_tf = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ColorJitter(brightness=0.6, contrast=0.6),     # 조명 변화
    transforms.GaussianBlur(kernel_size=9, sigma=(2.0, 4.0)), # 흐림
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
    transforms.RandomErasing(p=1.0, scale=(0.15, 0.30)),      # 가림(occlusion)
])

# --- 4) 추론 헬퍼 ---
@torch.no_grad()
def p_img(model, p1, p2, y, tf):
    dl = DataLoader(ImageAnomalyDataset(p1, y, tf, image_paths2=p2), batch_size=BATCH_SIZE, num_workers=2)
    return np.concatenate([torch.softmax(model(b[0].to(DEVICE)),1).cpu().numpy() for b in dl])

@torch.no_grad()
def p_sensor(model, X, y):
    dl = DataLoader(SensorSequenceDataset(X, y), batch_size=BATCH_SIZE)
    return np.concatenate([torch.softmax(model(b[0].to(DEVICE)),1).cpu().numpy() for b in dl])

@torch.no_grad()
def f1_fuse_model(model, X, p1, p2, y, tf):     # concat / crossattn
    dl = DataLoader(MultimodalDataset(X, p1, y, tf, image_paths2=p2), batch_size=BATCH_SIZE, num_workers=2)
    P = []
    for s, im, _, hi in dl:
        P.append(model(s.to(DEVICE), im.to(DEVICE), hi.to(DEVICE)).argmax(1).cpu().numpy())
    return f1_score(y, np.concatenate(P), average="weighted", zero_division=0)

# 이미지 존재 구간만
m = has_te; idx = np.where(m)[0]
Xm, ym = X_te[m], y_te[m]
p1m = [img_te[i] for i in idx]; p2m = [img_te2[i] for i in idx]

# 센서 (이미지와 무관 → 깨끗/열화 동일)
s_te = p_sensor(sensor_model, Xm, ym)
f_sensor = f1_score(ym, s_te.argmax(1), average="weighted", zero_division=0)

# Decision-Fusion 가중치 w: train(깨끗)에서 튜닝 → test에 적용 (누수 방지)
itr = np.where(has_tr)[0]
s_tr = p_sensor(sensor_model, X_tr[has_tr], y_tr[has_tr])
i_tr = p_img(image_model, [img_tr[i] for i in itr], [img_tr2[i] for i in itr], y_tr[has_tr], clean_tf)
def fuse_f1(s, i, y, w): return f1_score(y, ((1-w)*s + w*i).argmax(1), average="weighted", zero_division=0)
bw = max([k/20 for k in range(21)], key=lambda w: fuse_f1(s_tr, i_tr, y_tr[has_tr], w))

def run(tf, tag):
    i_te = p_img(image_model, p1m, p2m, ym, tf)
    f_img = f1_score(ym, i_te.argmax(1), average="weighted", zero_division=0)
    f_dec = fuse_f1(s_te, i_te, ym, bw)
    f_cc  = f1_fuse_model(fusion_model, Xm, p1m, p2m, ym, tf)
    f_ca  = f1_fuse_model(attn_model,  Xm, p1m, p2m, ym, tf)
    print(f"\n[{tag}]  (이미지 존재 {int(m.sum())} 시점, w={bw:.2f})")
    print(f"  Sensor            F1 : {f_sensor:.4f}")
    print(f"  Image             F1 : {f_img:.4f}")
    print(f"  Fusion-Concat     F1 : {f_cc:.4f}")
    print(f"  Fusion-CrossAttn  F1 : {f_ca:.4f}")
    print(f"  Decision-Fusion   F1 : {f_dec:.4f}")

print("="*64)
run(clean_tf,   "깨끗한 이미지")
run(degrade_tf, "열화된 이미지 (블러+조명변화+가림)")
print("="*64)
print("해석 가이드:")
print(" - 열화 시 Image가 급락하는데 Decision/Concat이 버티면 → 견고성 입증")
print(" - 같이 끌려가면 → 결측엔 견고하나 열화엔 취약(고정 w 한계) → 적응형 융합(Cross-Attn) 필요")
print(" - Cross-Attn이 열화에 가장 덜 떨어지면 → 적응형 주의의 강건성 입증")
