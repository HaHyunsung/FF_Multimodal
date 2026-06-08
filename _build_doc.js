// 발표용 스크립트 + 모델 구조 Q&A 대응 문서 생성
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak
} = require('docx');

// ── 색상/스타일 헬퍼 ──────────────────────────────────────────
const NAVY = "1B2A4A";
const TEAL = "16A295";
const CORAL = "E85850";
const GRAY = "666666";
const LIGHT_BG = "F0F4F8";

const border = { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 100, bottom: 100, left: 140, right: 140 };

// 텍스트 헬퍼
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { before: opts.before || 0, after: opts.after || 80, line: 320 },
    alignment: opts.align || AlignmentType.LEFT,
    children: [new TextRun({
      text,
      bold: opts.bold || false,
      italics: opts.italics || false,
      size: opts.size || 22,
      color: opts.color || "222222",
      font: "맑은 고딕",
    })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 280, after: 160 },
    children: [new TextRun({ text, bold: true, size: 32, color: NAVY, font: "맑은 고딕" })],
  });
}

function h2(text, color = NAVY) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, size: 26, color, font: "맑은 고딕" })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 180, after: 100 },
    children: [new TextRun({ text, bold: true, size: 23, color: TEAL, font: "맑은 고딕" })],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60, line: 300 },
    children: [new TextRun({ text, size: 21, font: "맑은 고딕" })],
  });
}

function script(text) {
  // 발표 스크립트 (들여쓰기 + 부드러운 회색 박스 느낌)
  return new Paragraph({
    spacing: { before: 60, after: 120, line: 360 },
    indent: { left: 360 },
    children: [new TextRun({ text, size: 22, font: "맑은 고딕", color: "222222" })],
  });
}

function quote(text) {
  return new Paragraph({
    spacing: { before: 100, after: 100, line: 320 },
    indent: { left: 360, right: 360 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: TEAL, space: 8 } },
    children: [new TextRun({ text, italics: true, size: 21, color: GRAY, font: "맑은 고딕" })],
  });
}

function cell(text, opts = {}) {
  return new TableCell({
    borders,
    margins: cellMargins,
    width: { size: opts.width || 3120, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: [new TextRun({
        text,
        bold: opts.bold || false,
        size: opts.size || 20,
        color: opts.color || "222222",
        font: "맑은 고딕",
      })],
    })],
  });
}

function divider() {
  return new Paragraph({
    spacing: { before: 60, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC", space: 1 } },
    children: [new TextRun("")],
  });
}

// ── 문서 본문 구성 ────────────────────────────────────────────
const children = [];

// ╔═══════════════════════════════════════════════════════════════╗
// 표지
// ╚═══════════════════════════════════════════════════════════════╝
children.push(new Paragraph({
  spacing: { before: 1200, after: 240 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: "멀티모달 딥러닝 기반 제조 공정 이상 탐지",
    bold: true, size: 40, color: NAVY, font: "맑은 고딕",
  })],
}));
children.push(new Paragraph({
  spacing: { after: 600 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: "중간 발표 스크립트 & 질의 대응 자료",
    size: 26, color: TEAL, font: "맑은 고딕",
  })],
}));
children.push(new Paragraph({
  spacing: { after: 120 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: "아주대학교 · 딥러닝응용 · 기말 프로젝트",
    size: 22, color: GRAY, font: "맑은 고딕",
  })],
}));
children.push(new Paragraph({
  spacing: { after: 120 },
  alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: "3조 · 김주헌 · 하현성",
    size: 22, color: GRAY, font: "맑은 고딕",
  })],
}));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ╔═══════════════════════════════════════════════════════════════╗
// PART 1. 발표 스크립트
// ╚═══════════════════════════════════════════════════════════════╝
children.push(h1("PART 1. 발표 스크립트"));
children.push(p("각 슬라이드별 발표용 스크립트입니다. ( ) 표기는 영문 기술 용어의 한글 발음 가이드입니다.", { color: GRAY, italics: true, after: 240 }));
children.push(divider());

// Slide 1
children.push(h2("Slide 1 — 표지"));
children.push(script("안녕하세요. 3조 김주헌, 하현성입니다. 저희가 진행 중인 멀티모달 딥러닝 기반 제조 공정 이상 탐지 프로젝트의 중간 진행 상황을 발표드리겠습니다."));

// Slide 2
children.push(h2("Slide 2 — 프로젝트 동기"));
children.push(script("프로젝트의 출발점은 저희 팀의 현장 경험입니다. 팀원 전원이 자동화 장비 업계에서 근무하면서 제조 공정에서 딥러닝이 어떻게 활용되는지 직접 접하고 있습니다."));
children.push(script("현재 산업 현장의 불량 판정은 대부분 비전 카메라 단독 방식입니다. 그러나 실제로는 조명, 각도, 가려짐 때문에 비전만으로 판단이 어려운 경우가 자주 발생합니다. 반대로 센서 데이터도 노이즈나 고장 때문에 단독으로는 신뢰하기 어려운 경우가 존재합니다."));
children.push(script("두 모달리티의 약점이 서로 보완 가능하다는 점에 주목해서, 이미지와 센서를 함께 활용하는 멀티모달 접근이 실제로 어떤 성능 차이를 만드는지 정량적으로 확인하는 것이 본 프로젝트의 핵심 동기입니다."));

// Slide 3
children.push(h2("Slide 3 — 프로젝트 목표"));
children.push(script("구체적인 목표는 세 가지 모델을 동일한 데이터와 평가 지표로 비교하는 것입니다."));
children.push(script("첫 번째는 BiLSTM(바이 엘에스티엠) 기반 센서 단독 모델로, 22채널 시계열 센서를 입력으로 사용하며 전체 사이클에 적용 가능합니다."));
children.push(script("두 번째는 ResNet18(레즈넷 에이틴) 기반 이미지 단독 모델로, Transfer Learning을 적용하며 카메라에 부품이 보이는 Cycle 4·9 구간만 학습합니다."));
children.push(script("세 번째는 앞의 두 브랜치를 Decision-Level Fusion으로 결합한 멀티모달 모델입니다."));
children.push(script("단일 모달리티 대비 융합 모델이 어떤 보완 효과를 보이는지가 가장 중요한 관찰 포인트입니다."));

// Slide 4
children.push(h2("Slide 4 — 관련 연구 (NSF-MAP)"));
children.push(script("주요 참고 논문은 IJCAI 2025의 NSF-MAP입니다. 동일한 Future Factories 데이터셋을 사용했고, 단계적 발전 방식이 핵심입니다."));
children.push(script("P1 기본 Decision-Level Fusion이 72%, P2에서 Transfer Learning을 더해 88%, P3에서 Process Ontology 기반 Knowledge Infusion으로 93%를 달성합니다."));
children.push(script("본 프로젝트는 강의에서 학습한 LSTM·ResNet으로 모델을 재구성하고, 모달리티별 효과 비교 자체에 집중합니다. Knowledge Infusion은 향후 확장 과제로 둡니다."));

// Slide 5
children.push(h2("Slide 5 — 데이터셋"));
children.push(script("데이터셋은 사우스캐롤라이나 대학교에서 공개한 Future Factories Lab Dataset입니다. 로봇 4대와 컨베이어로 구성된 실제 조립 라인을 30시간 가동하면서 수집한 데이터로, 16만 개 레코드와 285 사이클이 있습니다."));
children.push(script("센서는 40채널 이상이고, 카메라 2대가 동기화 촬영합니다."));
children.push(script("라벨 분포를 보시면 Normal이 약 55%로 다수를 차지하고, 소수 클래스가 여러 개 있어서 클래스 불균형이 큰 문제입니다. 저희는 소수 클래스 일부를 병합해 5클래스로 단순화하고, Cycle-wise 분할로 데이터 누출을 방지했습니다."));

// Slide 6
children.push(h2("Slide 6 — 전체 아키텍처"));
children.push(script("전체 아키텍처를 흐름도로 정리하면 이렇습니다."));
children.push(script("센서 데이터는 22채널 50 스텝 시퀀스로 만들어 BiLSTM에 입력하고, 양방향 hidden state를 합쳐 256차원의 센서 특징 벡터를 얻습니다."));
children.push(script("이미지 데이터는 224×224 RGB 이미지로 변환해서 ImageNet 사전학습 ResNet18에 통과시키고 512차원 특징 벡터를 추출합니다. 이때 ResNet18은 사전학습 가중치를 그대로 사용하기 위해 backbone을 동결했습니다."));
children.push(script("마지막으로 두 특징을 Concatenate해서 768차원으로 만든 뒤 FC와 Dropout 레이어를 거쳐 5클래스 분류를 수행합니다. 이미지가 없는 시점에는 센서 정보만 활용하도록 마스킹 처리도 적용했습니다."));

// Slide 7
children.push(h2("Slide 7 — 모델별 학습 전략"));
children.push(script("각 모델의 학습 전략은 슬라이드의 카드에 정리했습니다. 세 모델 모두 동일한 5클래스, Cycle-wise 80대 20 분할, 동일한 평가 지표를 사용해서 오로지 모달리티 차이만 비교할 수 있도록 통제했습니다."));
children.push(script("이미지와 Fusion 모델은 데이터가 Cycle 4와 9 구간으로 한정되어 더 작은 학습셋을 가진다는 점이 한계입니다."));

// Slide 8
children.push(h2("Slide 8 — 실행 환경 및 데이터 제약"));
children.push(script("실행 환경에서 가장 큰 제약은 데이터 용량이었습니다. 이미지 원본이 6 파트 580GB로 로컬 PC 다운로드가 사실상 불가능했습니다."));
children.push(script("또한 3개 모델을 반복적으로 학습·실험해야 하는 상황에서 로컬 자원을 장시간 점유하는 부담이 컸기 때문에, 빠른 프로토타이핑이 필요했습니다."));
children.push(script("이 문제를 Kaggle Notebook으로 해결했습니다. Kaggle 서버에 마운트된 원본 데이터를 다운로드 없이 직접 읽고, 무료로 제공되는 Tesla T4 GPU로 실험 사이클을 단축했습니다. 검증된 모델은 추후 로컬에서도 재현 가능합니다."));
children.push(script("다만 이미지는 6 파트 중 1 파트만 사용해서 약 9,500장이 매칭됐는데, 이는 NSF-MAP에서 사용한 약 1.5만 장과 비교해도 학술적으로 유의미한 규모입니다."));
children.push(script("추가로 Kaggle 세션이 idle 시 자동 종료되는 점을 고려해서 Random Seed를 42로 고정하고, 학습된 가중치와 결과를 Kaggle Output에 별도 저장해 재현성을 확보했습니다."));

// Slide 9
children.push(h2("Slide 9 — 최종 실험 결과"));
children.push(script("3개 모델 학습이 모두 완료되었습니다. 결과를 보시면 센서 단독 BiLSTM(바이 엘에스티엠)이 Weighted F1 0.927로 가장 높은 성능을 기록했습니다."));
children.push(script("이미지 단독 ResNet18(레즈넷 에이틴)은 F1 0.611로 가장 낮고, Fusion은 F1 0.882로 중간에 위치합니다. 직관적으로는 Fusion이 가장 좋아야 하는데, 결과가 반대로 나온 이유가 있습니다."));
children.push(script("이미지 데이터는 Cycle 4와 9 구간, 파트 1만 사용해서 약 9,500장에 불과합니다. 반면 센서 데이터는 전체 사이클 12만여 시퀀스로 훨씬 풍부합니다. 이 불균형 때문에 Fusion에서 이미지 브랜치가 정보를 더하기보다 노이즈로 작용한 것으로 분석됩니다."));
children.push(script("NSF-MAP 논문도 P1 기본 Fusion이 72%로 가장 낮았다가 Transfer Learning과 Knowledge Infusion을 추가하면서 93%까지 올라간 것과 같은 맥락입니다. 즉, 이번 결과 자체가 멀티모달 융합에서 데이터 균형이 얼마나 중요한지를 잘 보여주는 사례입니다."));

// Slide 10
children.push(h2("Slide 10 — 한계와 향후 개선 방향"));
children.push(script("한계의 핵심은 데이터 불균형입니다. 이미지 9,500장 대비 센서 12만 시퀀스로 Fusion에서 이미지 브랜치가 노이즈로 작용했습니다."));
children.push(script("개선은 두 축입니다. 데이터 측면에서는 이미지 파트를 1개에서 2~6개까지 확장하고, MixUp(믹스업)·CutMix(컷믹스) 등 강한 Augmentation, 그리고 Fusion 학습 시 두 모달리티 샘플링 비율을 맞추는 전략을 적용할 계획입니다."));
children.push(script("모델 측면에서 가장 우선순위가 높은 건 단순 Concat을 Cross-Attention으로 바꾸는 것입니다. 이미지 신뢰도가 낮을 때 센서에 자동으로 가중치가 실립니다. 추가로 ResNet18 일부 unfreeze는 NSF-MAP P2가 72%를 88%로 끌어올린 방식이고, Knowledge Infusion은 P3가 93% 달성한 핵심 기법입니다."));
children.push(script("이 개선들을 적용하면 Fusion이 센서 단독을 상회할 것으로 기대합니다."));

// Slide 11
children.push(h2("Slide 11 — 스케줄 및 역할 분담"));
children.push(script("스케줄은 1-3주차 데이터 확보와 모델 구현, 4-5주차에 3개 모델 학습과 비교 분석까지 완료했습니다. 남은 6주차는 추가 개선 실험과 최종 보고서 작성입니다."));
children.push(script("역할은 하현성이 멀티모달 융합 아키텍처와 센서 브랜치, Kaggle 환경 구축을, 김주헌이 이미지 브랜치와 데이터 탐색 및 라벨 정리, 평가 시각화를 담당했습니다. Fusion 통합과 비교 분석, 보고서 작성은 공동 수행입니다."));

// Slide 12
children.push(h2("Slide 12 — Q&A"));
children.push(script("이상입니다. 질문 받겠습니다. 감사합니다."));

children.push(new Paragraph({ children: [new PageBreak()] }));

// ╔═══════════════════════════════════════════════════════════════╗
// PART 2. 모델 구조 & 질의 대응
// ╚═══════════════════════════════════════════════════════════════╝
children.push(h1("PART 2. 모델 구조 & 질의 대응 자료"));
children.push(p("발표 중 질문에 빠르게 답변할 수 있도록 모델 아키텍처, 입력/클래스, 평가 조건, 예상 질문을 정리했습니다.", { color: GRAY, italics: true, after: 240 }));
children.push(divider());

// 2-1. 분류 클래스 구성
children.push(h2("1. 분류 클래스 구성"));
children.push(p("Future Factories는 4개 부품 로켓 모형 조립 라인입니다. 결함은 부품 누락 조합으로 정의됩니다.", { after: 120 }));

children.push(h3("원본 라벨 → 최종 5클래스 매핑"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [4680, 4680],
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("원본 라벨 (label_map key)", { width: 4680, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("최종 클래스 (value)", { width: 4680, bold: true, fill: NAVY, color: "FFFFFF" }),
    ]}),
    new TableRow({ children: [
      cell("Normal", { width: 4680 }),
      cell("Normal", { width: 4680, bold: true, color: TEAL }),
    ]}),
    new TableRow({ children: [
      cell("NoBody1", { width: 4680, fill: LIGHT_BG }),
      cell("NoBody1", { width: 4680, fill: LIGHT_BG, bold: true, color: TEAL }),
    ]}),
    new TableRow({ children: [
      cell("NoBody2", { width: 4680 }),
      cell("NoBody1 ← 병합", { width: 4680, bold: true, color: CORAL }),
    ]}),
    new TableRow({ children: [
      cell("NoBody2,NoBody1", { width: 4680, fill: LIGHT_BG }),
      cell("NoBody1 ← 병합", { width: 4680, fill: LIGHT_BG, bold: true, color: CORAL }),
    ]}),
    new TableRow({ children: [
      cell("NoNose", { width: 4680 }),
      cell("NoNose", { width: 4680, bold: true, color: TEAL }),
    ]}),
    new TableRow({ children: [
      cell("NoNose,NoBody2", { width: 4680, fill: LIGHT_BG }),
      cell("NoNose_NoBody2", { width: 4680, fill: LIGHT_BG, bold: true, color: TEAL }),
    ]}),
    new TableRow({ children: [
      cell("NoNose,NoBody2,NoBody1", { width: 4680 }),
      cell("NoNose_NoBody2_NoBody1", { width: 4680, bold: true, color: TEAL }),
    ]}),
  ]
}));
children.push(p("→ 원본 7가지 결함 조합 중 'Body 계열만 누락'인 3개를 NoBody1로 통합 → 최종 5클래스.", { color: GRAY, italics: true, before: 100 }));

children.push(h3("최종 5클래스 분포"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [4280, 1880, 1600, 1600],
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("클래스", { width: 4280, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("의미", { width: 1880, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("개수", { width: 1600, bold: true, fill: NAVY, color: "FFFFFF", align: AlignmentType.RIGHT }),
      cell("비율", { width: 1600, bold: true, fill: NAVY, color: "FFFFFF", align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("Normal", { width: 4280, bold: true }),
      cell("정상", { width: 1880 }),
      cell("90,775", { width: 1600, align: AlignmentType.RIGHT }),
      cell("54.7%", { width: 1600, align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("NoBody1 (병합)", { width: 4280, bold: true, fill: LIGHT_BG }),
      cell("Body 계열 결함", { width: 1880, fill: LIGHT_BG }),
      cell("4,016", { width: 1600, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
      cell("2.4%", { width: 1600, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("NoNose", { width: 4280, bold: true }),
      cell("Nose 누락", { width: 1880 }),
      cell("19,307", { width: 1600, align: AlignmentType.RIGHT }),
      cell("11.7%", { width: 1600, align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("NoNose_NoBody2", { width: 4280, bold: true, fill: LIGHT_BG }),
      cell("Nose+Body2 누락", { width: 1880, fill: LIGHT_BG }),
      cell("25,206", { width: 1600, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
      cell("15.2%", { width: 1600, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("NoNose_NoBody2_NoBody1", { width: 4280, bold: true }),
      cell("3개 모두 누락", { width: 1880 }),
      cell("26,628", { width: 1600, align: AlignmentType.RIGHT }),
      cell("16.0%", { width: 1600, align: AlignmentType.RIGHT }),
    ]}),
  ]
}));

children.push(divider());

// 2-2. Model 1
children.push(h2("2. Model 1 — BiLSTM (센서 단독)"));
children.push(h3("아키텍처"));
children.push(p("입력 (batch, 50, 22)", { color: GRAY }));
children.push(p("  ↓ BiLSTM (hidden=128, num_layers=2, bidirectional=True, dropout=0.2)", { color: GRAY }));
children.push(p("  ↓ forward h_n[-1] + backward h_n[-1] concat", { color: GRAY }));
children.push(p("센서 특징 벡터 (batch, 256)   # 128 × 2 (양방향)", { color: GRAY }));
children.push(p("  ↓ FC(256→128) → ReLU → Dropout(0.3) → FC(128→5)", { color: GRAY }));

children.push(h3("핵심 하이퍼파라미터"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2400, 1800, 5160],
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("항목", { width: 2400, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("값", { width: 1800, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("근거", { width: 5160, bold: true, fill: NAVY, color: "FFFFFF" }),
    ]}),
    new TableRow({ children: [
      cell("seq_len (T)", { width: 2400 }), cell("50 step", { width: 1800, bold: true }),
      cell("~10Hz 샘플링 기준 5초 윈도우. 사이클 내 패턴 포착에 충분", { width: 5160 }),
    ]}),
    new TableRow({ children: [
      cell("hidden_dim", { width: 2400, fill: LIGHT_BG }), cell("128", { width: 1800, fill: LIGHT_BG, bold: true }),
      cell("NSF-MAP 및 강의 노트 표준 설정", { width: 5160, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("num_layers", { width: 2400 }), cell("2", { width: 1800, bold: true }),
      cell("1층은 표현력 부족, 3층은 gradient 불안정", { width: 5160 }),
    ]}),
    new TableRow({ children: [
      cell("dropout", { width: 2400, fill: LIGHT_BG }), cell("0.2 + 0.3", { width: 1800, fill: LIGHT_BG, bold: true }),
      cell("LSTM 내부 0.2 + FC 직전 0.3, 과적합 방지", { width: 5160, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("optimizer", { width: 2400 }), cell("Adam", { width: 1800, bold: true }),
      cell("lr=1e-3, ReduceLROnPlateau, Early Stopping", { width: 5160 }),
    ]}),
    new TableRow({ children: [
      cell("학습 샘플", { width: 2400, fill: LIGHT_BG }), cell("121,550", { width: 1800, fill: LIGHT_BG, bold: true }),
      cell("Sliding Window 적용 후 시퀀스 수", { width: 5160, fill: LIGHT_BG }),
    ]}),
  ]
}));

children.push(h3("예상 질문 & 답변"));
children.push(p("Q. 왜 단방향 LSTM 아닌 BiLSTM?", { bold: true, color: NAVY }));
children.push(quote("제조 공정 사이클은 사후 분석이 가능한 task라 미래 정보 활용 가능합니다. 양방향 구조가 anomaly의 전조와 잔여 패턴을 모두 포착할 수 있고, 강의 10-2 자료 p13에 양방향 모델이 명시되어 있어 강의 범위 내 선택입니다."));
children.push(p("Q. 왜 Transformer 아닌 LSTM?", { bold: true, color: NAVY }));
children.push(quote("데이터가 12만 시퀀스로 Transformer 학습에는 비효율적이고, 시퀀스 길이 50으로 짧아 LSTM이 충분합니다. 또한 강의 범위 내 모델을 사용한다는 원칙도 있습니다."));
children.push(p("Q. 22채널 어떻게 선정?", { bold: true, color: NAVY }));
children.push(quote("원본 40+ 채널 중 결측이 많거나 분산이 0인 채널을 제외하고, 핵심 로봇 관절각도·그리퍼 로드셀·컨베이어 신호를 중심으로 22개를 선정했습니다."));

children.push(divider());

// 2-3. Model 2
children.push(h2("3. Model 2 — ResNet18 (이미지 단독)"));
children.push(h3("아키텍처"));
children.push(p("입력 (batch, 3, 224, 224)", { color: GRAY }));
children.push(p("  ↓ ResNet18 backbone (ImageNet pretrained, frozen)", { color: GRAY }));
children.push(p("이미지 특징 벡터 (batch, 512)   # avgpool 출력", { color: GRAY }));
children.push(p("  ↓ FC(512→128) → ReLU → Dropout(0.5) → FC(128→5)", { color: GRAY }));

children.push(h3("핵심 하이퍼파라미터"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2400, 1800, 5160],
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("항목", { width: 2400, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("값", { width: 1800, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("근거", { width: 5160, bold: true, fill: NAVY, color: "FFFFFF" }),
    ]}),
    new TableRow({ children: [
      cell("backbone", { width: 2400 }), cell("ResNet18", { width: 1800, bold: true }),
      cell("강의 7-2 p16 ResNet 다룸, 9,500장에 적합한 가벼운 모델", { width: 5160 }),
    ]}),
    new TableRow({ children: [
      cell("Pretrained", { width: 2400, fill: LIGHT_BG }), cell("ImageNet", { width: 1800, fill: LIGHT_BG, bold: true }),
      cell("Transfer Learning 적용 (일반 시각 특징 활용)", { width: 5160, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("Backbone freeze", { width: 2400 }), cell("True", { width: 1800, bold: true }),
      cell("9,500장으로는 fine-tune 시 과적합 위험", { width: 5160 }),
    ]}),
    new TableRow({ children: [
      cell("Augmentation", { width: 2400, fill: LIGHT_BG }), cell("Flip/Rot/Color", { width: 1800, fill: LIGHT_BG, bold: true }),
      cell("HorizontalFlip + Rotation(10°) + ColorJitter(0.2)", { width: 5160, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("Dropout", { width: 2400 }), cell("0.5", { width: 1800, bold: true }),
      cell("센서 모델보다 강한 dropout (데이터 부족 보완)", { width: 5160 }),
    ]}),
    new TableRow({ children: [
      cell("학습 샘플", { width: 2400, fill: LIGHT_BG }), cell("9,542장", { width: 1800, fill: LIGHT_BG, bold: true }),
      cell("Cycle 4·9 한정, Part 1만 사용", { width: 5160, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("Class Weight", { width: 2400 }), cell("별도 계산", { width: 1800, bold: true }),
      cell("이미지 분포 기반 (센서 분포와 다름, 디버깅 로그 3.2 참고)", { width: 5160 }),
    ]}),
  ]
}));

children.push(h3("예상 질문 & 답변"));
children.push(p("Q. 왜 ResNet50 / EfficientNet 아닌 ResNet18?", { bold: true, color: NAVY }));
children.push(quote("학습 데이터 9,500장은 deeper model에는 부족하여 작은 모델이 유리합니다. 강의 7-2에서 ResNet 계열을 다뤘기 때문에 강의 범위 내 선택이며, NSF-MAP의 EfficientNet-B0를 단순화한 것입니다."));
children.push(p("Q. Backbone 동결 이유?", { bold: true, color: NAVY }));
children.push(quote("ImageNet의 일반 시각 특징(엣지, 텍스처)이 산업 이미지에도 유효하고, 9,500장으로 전체 fine-tune 시 과적합 위험이 큽니다. 향후 개선 방향에 일부 unfreeze가 포함되어 있습니다."));
children.push(p("Q. 왜 Cycle 4·9만 사용?", { bold: true, color: NAVY }));
children.push(quote("그 외 사이클은 카메라에 부품이 보이지 않습니다(컨베이어 이동 중). 결함 판별에 의미 있는 시각 정보가 Cycle 4·9에만 존재하기 때문입니다."));
children.push(p("Q. F1 0.611이 낮은 이유?", { bold: true, color: NAVY }));
children.push(quote("9,500장에 5클래스 불균형이 가장 큰 원인입니다. Precision 0.53이 Recall 0.73보다 현저히 낮은데, 이는 모델이 다수 클래스 편향 학습을 했다는 신호입니다. 클래스 가중치를 이미지 분포 기반으로 재계산해서 일부 개선했지만, 절대 데이터 양이 부족해 한계가 있었습니다."));

children.push(divider());

// 2-4. Model 3
children.push(h2("4. Model 3 — Decision-Level Fusion (멀티모달)"));
children.push(h3("아키텍처"));
children.push(p("센서 입력           이미지 입력", { color: GRAY }));
children.push(p("   ↓                   ↓", { color: GRAY }));
children.push(p("BiLSTM            ResNet18 (frozen)", { color: GRAY }));
children.push(p("   ↓                   ↓", { color: GRAY }));
children.push(p("f_sensor (256)    f_image (512)", { color: GRAY }));
children.push(p("   └─────── Concat ─────┘", { color: GRAY }));
children.push(p("              ↓", { color: GRAY }));
children.push(p("       Fusion 벡터 (768)", { color: GRAY }));
children.push(p("              ↓", { color: GRAY }));
children.push(p("   FC(768→256) → ReLU → Dropout(0.4) → FC(256→5)", { color: GRAY }));

children.push(h3("핵심 설계"));
children.push(bullet("융합 방식: Decision-Level Fusion (Late Fusion) — 각 모달리티 특징 추출 후 concat"));
children.push(bullet("마스킹: 이미지 없는 시점은 zero 벡터 → 사실상 센서 정보만으로 분류"));
children.push(bullet("학습: BiLSTM은 learnable, ResNet18은 frozen (계산 효율)"));
children.push(bullet("Loss: CrossEntropyLoss + 이미지 분포 기반 Class Weight"));

children.push(h3("예상 질문 & 답변"));
children.push(p("Q. Early / Feature-level Fusion은 안 했나?", { bold: true, color: NAVY }));
children.push(quote("Early Fusion은 raw 데이터 차원이 너무 달라(시퀀스 vs 이미지) 결합이 어렵습니다. Decision-Level은 NSF-MAP P1 baseline과 동일하여 직접 비교가 용이합니다."));
children.push(p("Q. Concat 외에 다른 융합 방식은?", { bold: true, color: NAVY }));
children.push(quote("본 발표는 baseline 비교가 목적입니다. 슬라이드 10의 개선안에 Cross-Attention 방식을 명시했습니다. Attention 적용 시 이미지 신뢰도가 낮으면 자동으로 센서에 가중치가 부여됩니다."));
children.push(p("Q. Fusion이 센서 단독보다 낮은 이유?", { bold: true, color: NAVY }));
children.push(quote("이미지 9,500장 vs 센서 12만 시퀀스의 데이터 불균형이 원인입니다. ResNet18 출력이 불안정하여 768차원 concat에서 이미지 정보가 노이즈로 작용했습니다. NSF-MAP P1이 72%로 가장 낮았던 것과 동일한 현상입니다."));
children.push(p("Q. 멀티모달 시도가 실패한 것 아닌가?", { bold: true, color: NAVY }));
children.push(quote("아닙니다. 데이터 균형이 멀티모달 성공의 핵심임을 입증한 baseline 결과입니다. 개선 방향 6가지(데이터 3, 모델 3)는 모두 NSF-MAP 등 선행 연구로 검증된 방법이며, 적용 시 Fusion이 센서 단독을 상회할 가능성이 충분합니다."));

children.push(divider());

// 2-5. 공통 평가 조건
children.push(h2("5. 공통 평가 조건"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3000, 6360],
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("항목", { width: 3000, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("값 / 설명", { width: 6360, bold: true, fill: NAVY, color: "FFFFFF" }),
    ]}),
    new TableRow({ children: [
      cell("Train/Test 분할", { width: 3000, bold: true }),
      cell("Cycle-wise 80:20 (228 사이클 학습 / 57 사이클 평가, 데이터 누출 방지)", { width: 6360 }),
    ]}),
    new TableRow({ children: [
      cell("평가 지표", { width: 3000, bold: true, fill: LIGHT_BG }),
      cell("Accuracy, Weighted F1 (메인), Precision, Recall", { width: 6360, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("클래스", { width: 3000, bold: true }),
      cell("5개 (Normal + 4 결함 유형, 소수 클래스 일부 병합)", { width: 6360 }),
    ]}),
    new TableRow({ children: [
      cell("Random Seed", { width: 3000, bold: true, fill: LIGHT_BG }),
      cell("42 (numpy, torch, random 모두 동일하게 고정)", { width: 6360, fill: LIGHT_BG }),
    ]}),
    new TableRow({ children: [
      cell("학습 환경", { width: 3000, bold: true }),
      cell("Kaggle Notebook + Tesla T4 GPU + PyTorch", { width: 6360 }),
    ]}),
  ]
}));

children.push(h3("왜 Weighted F1이 메인 지표?"));
children.push(quote("Accuracy는 다수 클래스(Normal 55%) 편향이 있어 불균형 데이터 평가에 부적절합니다. Weighted F1은 클래스 빈도로 가중 평균하여 불균형 데이터에 더 적합한 지표입니다."));

children.push(h3("Cycle-wise 분할의 중요성"));
children.push(quote("시점별 무작위 분할 시 같은 사이클의 인접 시점이 Train과 Test에 모두 들어가 정보 누출이 발생합니다. Cycle 단위 분할이 실전 일반화 성능을 정확히 측정할 수 있게 합니다."));

children.push(divider());

// 2-6. 최종 결과 비교 & NSF-MAP 비교
children.push(h2("6. 최종 결과 & NSF-MAP 비교"));
children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [3360, 1500, 1500, 1500, 1500],
  rows: [
    new TableRow({ tableHeader: true, children: [
      cell("모델", { width: 3360, bold: true, fill: NAVY, color: "FFFFFF" }),
      cell("Accuracy", { width: 1500, bold: true, fill: NAVY, color: "FFFFFF", align: AlignmentType.RIGHT }),
      cell("Precision", { width: 1500, bold: true, fill: NAVY, color: "FFFFFF", align: AlignmentType.RIGHT }),
      cell("Recall", { width: 1500, bold: true, fill: NAVY, color: "FFFFFF", align: AlignmentType.RIGHT }),
      cell("F1", { width: 1500, bold: true, fill: NAVY, color: "FFFFFF", align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("M1 · Sensor (BiLSTM)", { width: 3360, bold: true, color: TEAL }),
      cell("0.9276", { width: 1500, bold: true, align: AlignmentType.RIGHT }),
      cell("0.9276", { width: 1500, align: AlignmentType.RIGHT }),
      cell("0.9276", { width: 1500, align: AlignmentType.RIGHT }),
      cell("0.9267", { width: 1500, bold: true, color: TEAL, align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("M2 · Image (ResNet18)", { width: 3360, bold: true, fill: LIGHT_BG, color: CORAL }),
      cell("0.7263", { width: 1500, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
      cell("0.5276", { width: 1500, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
      cell("0.7263", { width: 1500, fill: LIGHT_BG, align: AlignmentType.RIGHT }),
      cell("0.6112", { width: 1500, fill: LIGHT_BG, bold: true, color: CORAL, align: AlignmentType.RIGHT }),
    ]}),
    new TableRow({ children: [
      cell("M3 · Fusion", { width: 3360, bold: true }),
      cell("0.8941", { width: 1500, align: AlignmentType.RIGHT }),
      cell("0.8891", { width: 1500, align: AlignmentType.RIGHT }),
      cell("0.8941", { width: 1500, align: AlignmentType.RIGHT }),
      cell("0.8824", { width: 1500, bold: true, align: AlignmentType.RIGHT }),
    ]}),
  ]
}));

children.push(h3("Q. NSF-MAP P1 Fusion이 72%인데 우리는 0.88이다 — 우리가 더 잘한 것?"));
children.push(quote("단순 1:1 비교는 어렵습니다. 첫째, 평가 데이터 구성이 다릅니다 — 저희는 이미지가 있는 Cycle 4·9 시점만 평가한 반면 NSF-MAP은 전체 사이클을 평가했을 가능성이 큽니다. 둘째, 저희 센서 브랜치가 F1 0.927로 매우 강해서 Fusion에서도 그 정보가 그대로 활용된 영향이 큽니다. 셋째, NSF-MAP P1은 baseline 성격이라 ImageNet 사전학습 같은 강화 기법을 제외한 반면 저희는 P1부터 적용했습니다. 즉, '다른 조건에서 측정한 다른 baseline'으로 보는 것이 정확합니다."));

children.push(divider());

// 2-7. 개선 방향
children.push(h2("7. 향후 개선 방향 (Slide 10 상세)"));

children.push(h3("데이터 측면 (3가지)"));
children.push(p("① 이미지 파트 확장 (1 → 2~6)", { bold: true, color: NAVY }));
children.push(bullet("현재 Part 1만 9,542장 → Part 6 전체 시 약 53,000장 (~5.5배)"));
children.push(bullet("ResNet 특징 벡터 안정성 향상 → 노이즈에서 신호로 전환"));

children.push(p("② MixUp / CutMix Augmentation", { bold: true, color: NAVY }));
children.push(bullet("MixUp: 두 이미지 픽셀 단위 선형 합성 + 라벨 soft target 합성"));
children.push(bullet("CutMix: 한 이미지 영역을 잘라 다른 이미지에 붙임 (가림 학습)"));
children.push(bullet("산업 이미지의 부품 가림에 강건성 + 가상 샘플 생성 효과"));

children.push(p("③ 모달리티 비율 맞춤 샘플링", { bold: true, color: NAVY }));
children.push(bullet("현재 13:1 불균형 → 센서 다운샘플링 또는 이미지 업샘플링으로 균형"));
children.push(bullet("두 단계 학습: 각자 학습 → Fusion FC만 학습 방식도 검토"));

children.push(h3("모델 측면 (3가지)"));
children.push(p("Ⓐ Cross-Attention Fusion (최우선)", { bold: true, color: CORAL }));
children.push(bullet("Concat 무조건 동등 가중치 → Attention 기반 동적 가중치"));
children.push(bullet("Q=f_sensor, K=V=f_image → 이미지 신뢰도 낮을 때 자동으로 센서 우회"));
children.push(bullet("Cross-Attention은 데이터가 충분해야 효과 → ① 데이터 확장과 함께 적용"));

children.push(p("Ⓑ ResNet18 일부 Unfreeze (NSF-MAP P2 전략)", { bold: true, color: CORAL }));
children.push(bullet("현재 backbone 전체 동결 → layer4 + FC만 unfreeze"));
children.push(bullet("ImageNet 일반 특징 + 산업 도메인 특화 fine-tune"));
children.push(bullet("NSF-MAP P2 사례: 72% → 88% (+16%p)"));

children.push(p("Ⓒ Knowledge Infusion (NSF-MAP P3 전략)", { bold: true, color: CORAL }));
children.push(bullet("도메인 지식(센서 정상 범위)을 손실 함수에 명시적으로 주입"));
children.push(bullet("예: 그리퍼 로드셀 > 50N인데 'Normal' 예측 시 추가 페널티"));
children.push(bullet("NSF-MAP P3 사례: 88% → 93% (+5%p)"));

children.push(divider());

// 2-8. 기타 핵심 질문
children.push(h2("8. 기타 자주 묻는 질문"));

children.push(p("Q. 우선순위는?", { bold: true, color: NAVY }));
children.push(quote("Cross-Attention(Ⓐ) > 데이터 확장(①) > Transfer Learning 강화(Ⓑ) 순입니다. Cross-Attention은 코드 수정만으로 즉시 검증 가능하고, 데이터 확장은 환경 작업이 더 필요해 시간이 듭니다."));

children.push(p("Q. 정말 Fusion이 센서 단독을 넘을 수 있을까?", { bold: true, color: NAVY }));
children.push(quote("NSF-MAP이 동일 데이터셋에서 72% → 88% → 93%까지 단계적으로 끌어올린 선례가 있어 가능성은 충분합니다. 다만 저희는 P1부터 강화된 baseline이라 향상폭은 작을 수 있고, '더 작은 향상이지만 단독 모달리티 초월'이 현실적 목표입니다."));

children.push(p("Q. 이 프로젝트의 학술적 의의는?", { bold: true, color: NAVY }));
children.push(quote("멀티모달 융합이 단일 모달리티를 항상 이긴다는 막연한 직관에 반해, 데이터 균형이 핵심 조건임을 정량적으로 입증한 사례입니다. NSF-MAP의 단계적 개선 전략을 우리 환경에서 재현 가능함을 확인했고, 실제 산업 현장에 적용 시 데이터 수집 전략의 중요성을 시사합니다."));

children.push(p("Q. 강의에서 배운 내용을 어디에 적용했는가?", { bold: true, color: NAVY }));
children.push(quote("강의 10-2에서 RNN/LSTM/GRU와 양방향 모델을 다뤘고, 이를 BiLSTM 센서 모델에 적용했습니다. 강의 7-2에서 ResNet의 Residual Connection과 ImageNet 사전학습을 다뤘고, 이를 ResNet18 이미지 모델에 적용했습니다. 강의 9-1의 멀티모달 프로젝트 안내에서 다룬 CNN+RNN 융합 구조를 본 프로젝트 Fusion 모델에 적용했습니다."));

children.push(divider());
children.push(p("문서 끝.", { color: GRAY, italics: true, align: AlignmentType.CENTER, before: 200 }));

// ── 문서 생성 ───────────────────────────────────────────────
const doc = new Document({
  creator: "3조",
  title: "멀티모달 딥러닝 중간 발표 — 스크립트 & 질의 대응",
  styles: {
    default: { document: { run: { font: "맑은 고딕", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "맑은 고딕", color: NAVY },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "맑은 고딕", color: NAVY },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, font: "맑은 고딕", color: TEAL },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]
    }]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },  // US Letter
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "딥러닝응용 3조 · 멀티모달 중간발표 · ", size: 18, color: GRAY, font: "맑은 고딕" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: GRAY, font: "맑은 고딕" }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  const out = "C:\\Users\\Hyunsung Ha\\Desktop\\아주대학교\\4학년\\딥러닝응용\\기말 멀티모달 프로젝트\\딥러닝응용_3조_중간발표_스크립트.docx";
  fs.writeFileSync(out, buffer);
  console.log("Written:", out);
});
