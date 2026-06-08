# 04. PPT 현재 상태 + 갱신 할 일

## 현재 PPT (`PPT_current_v2.pptx`) 구성

**12슬라이드, ~9분 35초 분량** (사용자 요구: 9~10분, 10분 넘지 않게)

| # | 슬라이드 | 주요 내용 | 그래프/시각자료 | 노트 길이 |
|---|---------|-----------|---------------|---------|
| 01 | 표지 | 멀티모달 딥러닝 기반 제조 공정 이상 탐지 | - | 15초 |
| 02 | 왜 멀티모달인가 | 3카드 (센서만/이미지만/함께) | - | 50초 |
| 03 | 프로젝트 목표 | 3가지 질문 (결합·언제·결측) | - | 40초 |
| 04 | 데이터셋 | FF Lab + 표 + 라벨 구조 | sensor_sample.png | 60초 |
| 05 | 3개 모델 | 3컬럼 (Sensor·Image·Fusion) | - | 60초 |
| 06 | 시스템 전체 구조 | 다이어그램 | - | 40초 |
| 07 | 핵심 결과 | 이미지 존재 구간 비교 | res_present.png | 75초 |
| 08 | 추가 검증 | 모달리티 균형 3시나리오 | res_story.png ⚠️ | 75초 |
| 09 | 결함 유형별 분석 | 클래스별 F1 | res_byclass.png | 50초 |
| 10 | 결론 | 확인한 것 + 의의 | - | 60초 |
| 11 | 한계와 향후 | 3카드 | - | 40초 |
| 12 | Thank you | - | - | 10초 |

## ⚠️ 갱신 필요한 부분 (Version 13 결과 반영)

### 슬라이드 8 (추가 검증) — `res_story.png`
현재 그래프 데이터 (`make_result_figs.py`의 Fig D):
```python
scenarios = ["Image weakened\n(3ep, 0.78)", "Both weakened\n(balanced)", "Image moderate\n(0.93)"]
sensor_v = [0.9739, 0.9555, 0.9739]   # Both weakened은 추가실험 ③ 결과
image_v = [0.7751, 0.7751, 0.9285]
fusion_v = [0.9784, 0.9675, 0.9814]
```

**Version 13 신규 결과로 갱신**:
- "Both weakened (balanced)" 시나리오의 수치를 **추가실험 ⑤** (h16/2ep)으로 교체:
  - Sensor: 0.9555 → **0.8984** (이미지 존재 구간)
  - Image: 0.7751 → **0.2643** (이미지 존재 구간)
  - Fusion: 0.9675 → **0.9004** (이미지 존재 구간)
- 또는 FAIR 전체 (9,521)로 한 시나리오 추가도 고려

### 슬라이드 8 발표 노트 (`build_ppt.py`의 notes 9번)
현재:
> "그런데 한 가지 의문이 들 수 있습니다... 이미지가 약한 경우, 두 모달이 비등한 경우, 이미지가 강한 경우 모두에서 융합 모델이 두 단독 모델을 능가했습니다."

**갱신**: 새 균형 통제 v2 결과 (sensor h16/2ep, image weak)에서도 융합 우위였음을 추가로 명시.

### 슬라이드 10 (결론)
현재 수치 그대로 OK. 단, 한계 슬라이드(11)에 "균형 통제 v2로 추가 확인" 한 줄 추가 가능.

---

## 빌드 방법

### 그래프 갱신
1. `make_result_figs.py` 열기 → `# ---- Fig D` 부분의 `scenarios`, `sensor_v`, `image_v`, `fusion_v` 수정
2. 실행: `python make_result_figs.py` → `ppt_assets/res_story.png` 갱신됨

### PPT 재빌드
```bash
python build_ppt.py
# 출력: 딥러닝응용_3조_최종발표.pptx (12 slides)
```

### 시각 QA (Windows PowerShell COM 사용)
```powershell
$base = "프로젝트 폴더 절대경로"
$out = "$base\_qa"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
$pp = New-Object -ComObject PowerPoint.Application
$p = $pp.Presentations.Open("$base\딥러닝응용_3조_최종발표.pptx", $true, $false, $false)
$p.SaveAs($out, 17)  # 17 = ppSaveAsJPG
$p.Close(); $pp.Quit()
# 각 슬라이드가 _qa/슬라이드1.JPG, ... 로 저장됨. Read 도구로 직접 확인.
```

---

## ⚠️ 알아둘 함정

### `build_ppt.py` 인덱스 관리 주의
- 원본 슬라이드 인덱스(0-base): T0~T11
- 복제 슬라이드: `i_s9` (T8 복제), `i_s11` (T1 복제)
- 텍스트 교체 → 도형 제거 순서 중요 (제거 먼저 하면 인덱스 밀림)
- 슬라이드 순서 재배치 후 번호원은 자동 재설정됨

### 파일 잠김 (PermissionError)
사용자가 PowerPoint로 PPT 열어둔 채로 빌드하면 `PermissionError`. 빌드 스크립트에 이미 `_NEW` fallback 추가됨.

### 한글 PPTX + Windows
- `python -m markitdown` 등 일부 도구가 콘솔 인코딩 깨짐 → `PYTHONUTF8=1` 환경변수
- `_dump_shapes.py`처럼 UTF-8 파일로 저장 후 읽는 방식 권장

---

## 보고서 (`REPORT_초안_하현성.docx`)

- 별도 작업 필요 (현재는 구버전 결과 반영)
- 우선순위: PPT 우선, 보고서는 그 다음
- 보고서엔 "불공정 비교", 모든 평가 셋 설명 등 디테일 다 들어가도 OK (청중 아님)
