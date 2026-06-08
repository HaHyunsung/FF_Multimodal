# 01. 프로젝트 전체 맥락

## 과제

- **수업**: 아주대학교 딥러닝응용 (4학년)
- **팀**: 3조 — 김주헌, 하현성
- **주제**: 멀티모달 딥러닝 기반 제조 공정 이상 탐지 (시계열 센서 + 카메라 이미지)
- **제출물**: 최종 발표 PPT (9~10분) + 보고서

## 데이터셋

**Future Factories (FF) Dataset** — University of South Carolina (USC) AI Institute

- 실제 조립 라인(로봇 4대 + 컨베이어)에서 30시간 가동 수집
- **166,001 레코드** (1.95Hz 측정)
- **285개 사이클** (= 285개 로켓 모형 조립, 한 사이클 ≈ 582 타임스텝)
- **CycleState 1~21** (사이클 내 단계 번호)
- **22채널 센서** (모든 타임스텝에 기록): 그리퍼 부하, 관절 각도, 컨베이어 온도/속도, VFD 온도 등
- **카메라 2대** (Cam1, Cam2) — 전 단계에 기록되어 있으나 **부품이 명확히 보이는 단계는 4번·9번**. 우리는 NSF-MAP 논문을 따라 cycle 4·9 시점만 사용.
- **이미지 Part 1·2 (6파트 중 2개) 사용**: 각 104GB, 카메라 2장씩
- **5클래스 라벨** (병합 후):
  - Normal (54.7%)
  - NoNose (11.6%)
  - NoNose_NoBody2 (15.2%)
  - NoNose_NoBody2_NoBody1 (16.0%)
  - NoBody1 + 기타 (~2.4%, 소수)
- **E_STOPPED**(공정 중단) 제거

### ⭐ 라벨 구조 (중요)
**"제품 단위 양/불"이 아님.** 매 타임스텝마다 그 순간의 상태(어떤 부품 빠짐)가 기록됨. 부품 누적 제거 가능 (예: 1~3단계 정상 → 4단계 NoBody1 → 8단계 NoNose,NoBody2,NoBody1).

→ 과제는 **"지금 이 순간 어떤 상태인가"를 매 타임스텝 분류**.

## 모델 (3가지)

| 모델 | 입력 | 구조 | 평가 가능 범위 |
|------|------|------|---------------|
| **Sensor (BiLSTM)** | 22채널 시계열 (sliding window 50) | 양방향 LSTM 2-layer, hidden 128 | 전체 1~21단계 |
| **Image (ResNet18)** | 카메라 2대 동기 입력 | ImageNet 전이학습, 두 카메라 feature 평균 | cycle 4·9 시점 |
| **Fusion (Decision-level)** | 위 두 모델 출력 확률 | 가중 결합 (w는 train에서 grid search), 이미지 결측 시 센서 폴백 | cycle 4·9 + 결측 폴백 |

추가로 **Fusion-Concat**, **Fusion-CrossAttn**도 구현됨 (비교용).

## 평가 방법론

- **Cycle-wise train/test split** (data leakage 방지): 같은 사이클 내 데이터가 train/test에 섞이지 않도록
- **80% train / 20% test** (228 cycles / 57 cycles)
- **Weighted F1** (클래스 불균형 보정)
- 모든 모델 동일한 학습/테스트 분할 사용

## 환경

- **Kaggle Notebook + GPU T4 x2** (다운로드 없이 데이터 직접 마운트)
- 주 30시간 GPU 무료 할당량
- 노트북 계정: 두 개 사용
  - `hyunsungha` (Kaggle API 키 있음, Version 1~12)
  - `kimjoohoen` (Version 13 학습 — 사용자가 GPU 쿼터 절약하려고 새로 만든 계정. **이 계정 노트북은 private, API 접근 불가**)

## 참고 논문

- **NSF-MAP** (IJCAI 2025): "Neurosymbolic Multimodal Fusion for Robust and Interpretable Anomaly Prediction in Assembly Pipelines" by Shyalika et al., USC
- 같은 FF Dataset 사용
- 우리 cycle 4·9 필터링은 이 논문 근거 (`Filter cycle state 4 & 9 → Object Detection(YOLO) → Crop`)
- 우리는 YOLO ROI 크롭은 생략, raw 이미지 사용

## 디자인 템플릿

- **중간발표 PPT**: `TEMPLATE_중간발표.pptx`
- 표지: 흰 배경 + 상하단 그라데이션 바(파랑→틸→코랄)
- 헤더: 네이비 밴드 + 틸 원형 번호 + 흰 제목
- 본문: 연회색 둥근 카드 + 컬러 번호원
- → 이 디자인 그대로 유지하면서 내용만 우리 최종 결과로
