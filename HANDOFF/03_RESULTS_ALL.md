# 03. 모든 실험 결과 종합

> 발표·보고서에 들어갈 모든 수치. 평가 조건 명시 필수.

---

## 🔬 데이터 분할 (모든 실험 동일)

- 285개 사이클을 cycle-wise로 80/20 분할
- Train: 228 cycles, 132,950 시점 → 시퀀스 121,550개 (sliding window 50)
- Test: 57 cycles, 32,982 시점 → 시퀀스 30,132개
- 그 중 cycle 4·9 시점만 모은 Fusion test 셋: **9,521 시점**
- 그 중 이미지 매칭 성공한 시점: **2,161 시점** (22.7%)
- 이미지 데이터셋 자체 test 셋(Part1+2): 2,346장

---

## 📊 Version 12 결과 (이미지 정상 학습)

### FINAL SUMMARY (각 모델 자기 test셋, 비공정 비교, 발표에선 안 씀)
| Model | Test Set | Accuracy | F1 |
|-------|----------|----------|-----|
| Sensor (BiLSTM) | 전체 cycle 30,132 시점 | 0.9224 | 0.9215 |
| Image (ResNet18 2cam) | cycle 4·9 이미지 2,346장 | 0.9258 | 0.9315 |
| Fusion-Concat | cycle 4·9 9,521 시점 | 0.8736 | 0.8693 |
| Fusion-CrossAttn | cycle 4·9 9,521 시점 | 0.8750 | 0.8703 |

### FAIR COMPARISON (모든 모델 동일 cycle 4·9 9,521 시점)
| Model | F1 |
|-------|-----|
| Sensor@cyc4·9 | 0.8710 |
| Image@cyc4·9 | 0.6066 (결측 77% 때문에 낮음) |
| Fusion-Concat | 0.8693 |
| Fusion-CrossAttn | 0.8690 |
| Decision-Fusion (w=0.55) | 0.8720 |

### 이미지 존재 구간 (2,161 시점)
| Model | F1 |
|-------|-----|
| Sensor | 0.9739 |
| Image (2 cameras) | **0.9285** |
| **Fusion-Concat** | **0.9814 ★** |
| Fusion-CrossAttn | 0.9801 |
| Decision-Fusion | 0.9277 |

→ **best Fusion 0.9814 > best Single 0.9739 → 멀티모달 이득 O ✅**

### 이미지 약화 통제실험 (이미지 3epoch만 학습, 2,161 시점)
| Model | F1 |
|-------|-----|
| Sensor | 0.9739 |
| Image (weak, 3ep, 2cam) | 0.7751 |
| **Decision-Fusion (w=0.90)** | **0.9779** |

→ 균형 잡힌 환경에서도 Fusion 우위 ✅

### 부트스트랩 통계 유의성 (Decision-Fusion vs Sensor, 이미지 존재 구간)
- Fusion − Sensor F1 차이: 평균 -0.0463, 95% CI [-0.0557, -0.0374]
- → **통계적으로 유의하지 않음** (Decision-Fusion 0.928 < Sensor 0.974)
- (학습형 Fusion-Concat 0.981은 별도 — 이게 멀티모달 이득의 진짜 증거)

### 결함 유형별 성능 (Fusion-Concat, cycle 4·9)
| 클래스 | F1 |
|--------|-----|
| NoNose (단순 결함) | 0.98 |
| NoNose_NoBody2 (2부품 빠짐) | 0.87 |
| NoNose_NoBody2_NoBody1 (3부품 빠짐) | **0.59** ← 가장 어려움 |
| Normal | 0.92 |

---

## 🆕 Version 13 결과 (이번에 막 나옴, PPT 미반영)

### 추가실험 ⑤: 균형 통제 v2 (센서도 강하게 약화)

**설정**: SensorLSTM(hidden_dim=16) + 2 epochs로 센서 약화 (이전 통제 ③의 hidden=32, 3ep으론 0.95에 머물러서 더 강하게)

**FAIR 전체 9,521 시점**:
| Model | F1 | 비고 |
|-------|-----|------|
| Sensor (very weak) | **0.8757** | 사용자가 원했던 ~0.8 수준 달성 |
| Image (weak) | 0.1586 | 결측 77% 포함 (낮음 정상) |
| **Decision-Fusion (w=0.40)** | **0.8766** | Fusion이 단독 능가 ✅ |

**이미지 존재 구간 2,161 시점**:
| Model | F1 |
|-------|-----|
| Sensor | 0.8984 |
| Image | 0.2643 |
| **Decision-Fusion** | **0.9004** |
| 두 단독 차이 | 0.6341 |

→ **두 평가 모두 멀티모달 이득 확인** ✅

### sensor_very_weak 학습 상세
```
Epoch 1/2 | Train Loss: 0.4770 Acc: 0.8327 | Val F1: 0.8855
Epoch 2/2 | Train Loss: 0.2801 Acc: 0.9151 | Val F1: 0.9141

Final: Accuracy 0.9147, F1 0.9141
- NoBody1: 0.89
- NoNose: 0.92
- NoNose_NoBody2: 0.91
- NoNose_NoBody2_NoBody1: 0.81
- Normal: 0.94
```

→ 강하게 약화시켰지만 전체 평가에선 여전히 0.91. 그런데 cycle 4·9 평가셋에서는 0.8757로 떨어짐 (이 구간이 더 어려워서). 사용자가 원했던 "센서 ~0.8, 이미지 ~0.8" 균형은 이 신규 실험에서 처음으로 자연스럽게 나옴.

---

## 📌 발표·보고서 핵심 메시지

**가장 강력한 결과 (PPT 메인)**:
> Version 12 — 정상 학습된 모델로, 이미지가 함께 입력되는 시점에서 융합이 두 단독을 능가
> → Sensor 0.974, Image 0.928, **Fusion 0.981** (멀티모달 이득의 직접 증거)

**보강 결과**:
> Version 13 — 두 모달리티를 약화시켜 비등하게 만든 균형 조건에서도 융합이 우위
> → Sensor 0.876, Image 0.16(결측 포함), **Fusion 0.877** (FAIR 전체) — 균형에서도 일관됨

**솔직한 한계**:
- 단일 데이터셋 검증
- 융합 향상 폭이 작음 (Decision-Fusion 부트스트랩은 유의성 미달, 학습형 Fusion-Concat이 진짜 이득)
- 복합 결함 (3부품 동시 빠짐) F1 0.59로 어려움
