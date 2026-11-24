// deck.js — "암호화 LLM 트래픽 추론 깊이 식별" 3차 정리 발표자료를 만든다.
//
// 무엇을 하는가
//   2026-11-12 발표(심규상_20261112_개인연구.pptx) 이후 11-24 까지의 연구 흐름을
//   테마·레이아웃·섹션을 갖춘 구조화 덱으로 출력한다. 모든 슬라이드에 발표자 메모를
//   붙이는데, 메모에는 (1) 그 장에 나오는 용어의 뜻과 (2) 그 결과가 왜 의미가 있는지를
//   전공자가 아닌 사람도 읽을 수 있게 풀어 쓴다.
//
// 입력  : 없음 (내용이 이 파일 안에 상수로 들어 있다)
// 출력  : C:\Users\GyuSang\OneDrive - 고려대학교\02_PPT\심규상_261124_암호화트래픽_연구흐름정리.pptx
//
// 주의  : 색상 hex 에 '#' 을 붙이면 파일이 깨진다. 옵션 객체는 addText 호출마다 새로
//         만든다(pptxgenjs 가 제자리에서 EMU 로 바꿔치기 때문). 테마 색은 writeFile
//         이후 apply_theme.js 로 주입해야 실제로 반영된다.
//
// 작성일: 2026-11-24

const path = require('path');
const pptxgen = require('pptxgenjs');
const { applyTheme } = require('C:/Users/GyuSang/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/2de1d7bf-7449-4dfa-9ffd-00c6248b1a4e/a5d2ee58-683e-43ae-9b35-62f5c3acdc59/skills/pptx/scripts/apply_theme.js');

const OUT = 'C:/Users/GyuSang/OneDrive - 고려대학교/02_PPT/심규상_261124_암호화트래픽_연구흐름정리.pptx';

// ── 테마 ────────────────────────────────────────────────────────────────
// 주제가 '암호문 속에서 새어 나오는 신호'라 어두운 남색을 바탕으로 깔고,
// 누출·신호를 민트(accent3)로, 정정·사고를 테라코타(accent4)로 고정해서 쓴다.
// 폰트는 QA 에서 폭이 변하지 않는 안전 폰트로만 고른다(Cambria 제목 / Calibri 본문).
const THEME = {
  name: 'Encrypted Traffic Probe',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '161A1F', lt1: 'FFFFFF',
    dk2: '1B2A41', lt2: 'EEF2F7',
    accent1: '0B5A82', accent2: '1C7293', accent3: '00A896',
    accent4: 'B85042', accent5: '6B7A8F', accent6: 'D98C3F',
    hlink: '1C7293', folHlink: '6B7A8F',
  },
};

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';            // 13.3" x 7.5". 슬라이드 추가 전에 반드시 설정한다.
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = '심규상';
pres.company = 'Korea University Sejong NMLAB';
pres.subject = '암호화 LLM 트래픽 추론 깊이 식별';
pres.title = '암호화 LLM 트래픽 추론 깊이 식별 — 3차 정리';

const C = pres.SchemeColor;
const M = 0.62;                          // 좌우 여백
const W = 13.33 - M * 2;                 // 본문 폭

// ── 레이아웃 ────────────────────────────────────────────────────────────
// 네 종류만 둔다. 표지 / 섹션 구분 / 본문 / 마무리.
// 본문 레이아웃의 아래쪽 띠는 장식이 아니라 '이 장의 결론' 한 줄을 담는 자리다.

pres.defineSlideMaster({
  title: 'TITLE_DARK',
  background: { color: THEME.colors.dk2 },
  objects: [
    { rect: { x: 0, y: 0, w: 13.33, h: 0.16, fill: { color: THEME.colors.accent3 }, objectName: 'topEdge' } },
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 2.35, w: W, h: 1.5, fontSize: 40, bold: true, color: C.background1, valign: 'bottom' } } },
    { placeholder: { options: { name: 'subtitle', type: 'body', x: M, y: 3.95, w: W, h: 0.75, fontSize: 18, color: THEME.colors.accent3 } } },
    { placeholder: { options: { name: 'meta', type: 'body', x: M, y: 5.6, w: W, h: 1.2, fontSize: 13, color: THEME.colors.accent5 } } },
  ],
});

pres.defineSlideMaster({
  title: 'SECTION',
  background: { color: THEME.colors.dk2 },
  objects: [
    { placeholder: { options: { name: 'num', type: 'body', x: M, y: 2.0, w: 3.0, h: 1.5, fontSize: 66, bold: true, color: THEME.colors.accent3 } } },
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 3.4, w: W, h: 1.0, fontSize: 32, bold: true, color: C.background1 } } },
    { placeholder: { options: { name: 'subtitle', type: 'body', x: M, y: 4.4, w: W, h: 1.4, fontSize: 15, color: THEME.colors.accent5 } } },
  ],
});

pres.defineSlideMaster({
  title: 'CONTENT',
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: 'kicker', type: 'body', x: M, y: 0.34, w: W, h: 0.34, fontSize: 11, bold: true, color: THEME.colors.accent2, charSpacing: 1 } } },
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 0.68, w: W, h: 0.72, fontSize: 25, bold: true, color: C.text1, valign: 'top' } } },
    { placeholder: { options: { name: 'body', type: 'body', x: M, y: 1.52, w: W, h: 4.85, fontSize: 14, color: C.text1, valign: 'top' } } },
    { rect: { x: 0, y: 6.62, w: 13.33, h: 0.88, fill: { color: THEME.colors.dk2 }, objectName: 'takeawayBand' } },
    { placeholder: { options: { name: 'takeaway', type: 'body', x: M, y: 6.72, w: W, h: 0.68, fontSize: 13, bold: true, color: C.background1, valign: 'middle' } } },
  ],
  slideNumber: { x: 12.75, y: 6.95, w: 0.45, h: 0.3, fontSize: 10, color: THEME.colors.accent5, align: 'right' },
});

pres.defineSlideMaster({
  title: 'CLOSING',
  background: { color: THEME.colors.dk2 },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: M, y: 1.0, w: W, h: 0.9, fontSize: 28, bold: true, color: C.background1 } } },
    { placeholder: { options: { name: 'body', type: 'body', x: M, y: 2.0, w: W, h: 4.6, fontSize: 14, color: THEME.colors.lt2, valign: 'top' } } },
  ],
});

// ── 도우미 ──────────────────────────────────────────────────────────────

/** 본문 슬라이드 하나를 만든다. kicker/title/takeaway 를 채우고 slide 를 돌려준다. */
function content(section, kicker, title, takeaway) {
  const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: section });
  s.addText(kicker, { placeholder: 'kicker' });
  s.addText(title, { placeholder: 'title' });
  if (takeaway) s.addText(takeaway, { placeholder: 'takeaway' });
  return s;
}

/** 불릿 목록. 마지막 항목만 breakLine 을 끈다(끄지 않으면 빈 줄이 하나 더 생긴다). */
function bullets(items) {
  return items.map((t, i) => {
    const o = { bullet: true, breakLine: i !== items.length - 1, paraSpaceAfter: 7 };
    if (typeof t === 'string') return { text: t, options: o };
    return { text: t.text, options: Object.assign(o, t.opt || {}) };
  });
}

/** 표. 머리행은 짙은 남색, 본문은 흰 바탕. 강조 행은 rows 쪽에서 직접 색을 준다. */
function table(slide, rows, opt) {
  const o = Object.assign({
    x: M, y: 1.55, w: W,
    fontSize: 11.5, fontFace: 'Calibri', color: THEME.colors.dk1,
    border: { type: 'solid', pt: 0.5, color: 'D5DCE4' },
    align: 'left', valign: 'middle',
    rowH: 0.3, margin: 0.06,
  }, opt || {});
  slide.addTable(rows, o);
}

/** 표 머리행 셀 묶음. */
function head(cells) {
  return cells.map(t => ({ text: t, options: { bold: true, color: 'FFFFFF', fill: { color: THEME.colors.dk2 }, fontSize: 11 } }));
}

/** 숫자 하나를 크게 보여주는 통계 타일. */
function stat(slide, x, y, w, value, label, sub, col) {
  slide.addText(value, { x, y, w, h: 0.78, fontSize: 36, bold: true, color: col || THEME.colors.accent1, isTextBox: true, margin: 0, align: 'left' });
  slide.addText(label, { x, y: y + 0.76, w, h: 0.3, fontSize: 12, bold: true, color: THEME.colors.dk1, isTextBox: true, margin: 0 });
  if (sub) slide.addText(sub, { x, y: y + 1.04, w, h: 0.5, fontSize: 10.5, color: THEME.colors.accent5, isTextBox: true, margin: 0 });
}

// ═══════════════════════════════════════════════════════════════════════
// 1. 표지
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '표지' });
{
  const s = pres.addSlide({ masterName: 'TITLE_DARK', sectionTitle: '표지' });
  s.addText('암호화 LLM 트래픽 추론 깊이 식별', { placeholder: 'title' });
  s.addText('3차 정리 — 2차 발표(2026-11-12) 이후 12일 동안 무엇이 밝혀지고 무엇이 뒤집혔나', { placeholder: 'subtitle' });
  s.addText([
    { text: '고려대학교 세종캠퍼스 · 네트워크 관리 연구실', options: { breakLine: true } },
    { text: '심규상  학부 연구생   cole0213@korea.ac.kr', options: { breakLine: true } },
    { text: '2026-11-24', options: {} },
  ], { placeholder: 'meta' });
  s.addNotes([
    '[이 발표가 무엇인가]',
    '지난 11월 12일 2차 진행 보고 이후 12일 동안의 연구 기록을 시간순으로 정리한 자료다.',
    '새로운 주장을 펴는 자리가 아니라, 그 사이에 (1) 무엇이 추가로 측정됐고 (2) 어떤 기존 전제가',
    '틀린 것으로 드러났는지를 분명히 하는 데 목적이 있다.',
    '',
    '[연구를 한 문장으로]',
    'TLS로 암호화돼서 내용을 전혀 볼 수 없는 LLM API 트래픽을 바깥에서 구경만 해도,',
    '그 모델이 "얼마나 깊이 생각했는가"를 알아낼 수 있다는 것을 보이는 연구다.',
    '내용은 못 읽는데 사고의 양은 샌다 — 이것이 보안 연구가 되는 지점이다.',
    '',
    '[핵심 용어]',
    '· TLS : 웹에서 쓰는 암호화 규약. 내용은 가려지지만 "언제 몇 바이트가 오갔는가"는 그대로 보인다.',
    '· reasoning effort(추론 설정) : 요청할 때 "얼마나 깊이 생각해라"를 low~max 로 지정하는 값.',
    '· reasoning token(추론 토큰) : 모델이 실제로 혼잣말처럼 소비한 사고의 양. 답변 글자와는 별개로 과금된다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 2. 한 장 요약
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '요약' });
{
  const s = content('요약', '한 장 요약', '12일 동안 바뀐 것', '측정 규모가 10배 늘었고, 그 과정에서 연구의 주 타깃과 핵심 전제가 둘 다 바뀌었다.');
  table(s, [
    head(['', '2026-11-12 발표', '지금 (11-24)']),
    ['provider', 'Google 1곳', { text: '3곳 (Google · Anthropic · OpenAI)', options: { bold: true, color: THEME.colors.accent1 } }],
    ['모델', '1개', { text: '8개', options: { bold: true, color: THEME.colors.accent1 } }],
    ['추론 단계', '3단계 (low/medium/high)', { text: '5단계 (low~max)', options: { bold: true } }],
    ['누적 콜', '1,020', { text: '약 14,000', options: { bold: true, color: THEME.colors.accent1 } }],
    ['누출 기전', '미규명', { text: '세 제조사 전부 "암호화 사고 서명". 검산까지 일치', options: { bold: true, color: THEME.colors.accent3 } }],
    ['주 타깃', 'Task A (설정 탐지)', { text: 'Task B (실제 추론량) — R² 0.88~0.98', options: { bold: true, color: THEME.colors.accent3 } }],
    ['답 길이 통제', '반드시 필요한 교란 통제라고 믿음', { text: '핸디캡이었음. 풀면 +14~17%p', options: { bold: true, color: THEME.colors.accent4 } }],
    ['방어 검토', '없음', { text: '패딩 단독은 무력. 바이트+타이밍 동시 필요', options: { bold: true } }],
  ], { y: 1.55, colW: [2.1, 4.3, 5.69], rowH: 0.42 });
  s.addNotes([
    '[이 표를 읽는 법]',
    '왼쪽이 지난 발표 시점, 오른쪽이 지금이다. 위 네 줄은 "규모가 커졌다"는 이야기고,',
    '아래 네 줄이 더 중요하다 — 규모가 커지면서 연구의 방향 자체가 바뀐 부분이다.',
    '',
    '[용어]',
    '· provider : LLM을 파는 회사. Google, Anthropic(Claude), OpenAI(GPT) 셋을 다뤘다.',
    '· 콜(call) : API 호출 한 번. 질문 1개를 5단계 설정으로 던지면 콜 5번이다.',
    '· Task A / Task B : 뒤에서 자세히 나온다. A는 "설정값 맞히기", B는 "실제 사고량 맞히기".',
    '· R² : 회귀가 얼마나 잘 맞는지를 0~1로 나타낸 값. 1에 가까울수록 정확하다.',
    '· %p(퍼센트 포인트) : 40%에서 54%로 오른 것은 "14%p 상승"이다. "35% 상승"과 구별해서 쓴다.',
    '',
    '[왜 중요한가]',
    '아래 세 줄은 전부 "지난 발표에서 내가 믿었던 것이 틀렸다"는 내용이다.',
    '연구에서 이런 정정은 약점이 아니라 오히려 데이터가 쌓였다는 증거다. 숨기지 말고 먼저 말한다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 0 — 출발점
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '00 출발점' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '00 출발점' });
  s.addText('00', { placeholder: 'num' });
  s.addText('출발점 — 11-12 발표가 서 있던 자리', { placeholder: 'title' });
  s.addText('Gemini 한 모델, 3단계, 1,020콜. 여기서 시작했다.', { placeholder: 'subtitle' });
  s.addNotes([
    '[이 섹션의 목적]',
    '지난 발표를 되짚는 이유는 복습이 아니라, 그때 "다음에 하겠다"고 적어둔 항목들이',
    '지금 어떻게 됐는지를 대조하기 위해서다. 연구 보고는 약속과 결과를 맞춰 보이는 자리다.',
  ].join('\n'));
}

{
  const s = content('00 출발점', '2026-11-12 2차 진행 보고', '그때의 측정 범위와 네 가지 주장',
    '한 모델·한 경로에서 나온 결과였다. 그 경로(게이트웨이)는 이후 연구 범위에서 제외했다 — 다음 장.');
  s.addText([
    { text: '측정 범위', options: { bold: true, fontSize: 15, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 6 } },
    ...bullets([
      'gemini-3.5-flash-lite 한 모델 · 3단계(low / medium / high)',
      { text: '340문항 / 222템플릿 / 1,020콜 — 학교 LLM 게이트웨이(BAZE) 경유', opt: { color: THEME.colors.accent4 } },
    ]),
  ], { x: M, y: 1.55, w: 6.1, h: 1.6, fontSize: 13, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText([
    { text: '그때 내세운 네 가지', options: { bold: true, fontSize: 15, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 6 } },
    ...bullets([
      '용도를 7개에서 1개로 잘랐다 — "토큰 남용 탐지"만 남김',
      '조기 식별을 재정의: 침묵이 끝난 뒤가 아니라 침묵 중간에 판정 → 정확도 0.972',
      'AUC 0.930. 이전 0.994에서 내려간 것이 오히려 올바른 방향(표본 12 → 222)',
      '피처 하나에 의존하면 못 잡는다 — 게이트웨이가 바뀌자 pkt_gap이 0.496으로 붕괴',
    ]),
  ], { x: 6.95, y: 1.55, w: 5.76, h: 4.6, fontSize: 13, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText('→ 발표 23장에 적어둔 "다음 할 일" 4개: 다른 provider 캡처 · medium↔high 혼동 규명 · Realized 라벨 결합 · 불응률 전수',
    { x: M, y: 5.5, w: W, h: 0.7, fontSize: 12.5, italic: true, color: THEME.colors.accent2, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[용어]',
    '· 문항 / 템플릿 : 같은 틀에서 숫자만 바꾼 문제 25개는 서로 닮아서 독립 표본이 아니다.',
    '  그래서 "문항 340개"가 아니라 "템플릿 222개"로 말해야 신뢰구간이 정직해진다.',
    '· AUC : 두 집단을 얼마나 잘 가르는지를 0.5~1.0으로 나타낸 값. 0.5는 동전 던지기, 1.0은 완벽.',
    '· pkt_gap : 요청을 보낸 뒤 첫 응답 패킷이 올 때까지의 침묵 길이. 모델이 생각하는 동안 생긴다.',
    '· 게이트웨이 : 학교가 운영하는 LLM 중계 서버. 여러 회사 모델을 한 주소로 모아서 중계한다.',
    '',
    '[왜 pkt_gap이 무너졌나 — 중요한 교훈]',
    '게이트웨이가 응답 통로(SSE 스트림)를 미리 열어버리기 때문에 헤더가 6ms 만에 도착한다.',
    '침묵이 사라진 게 아니라 "스트림 바깥"에서 "스트림 안쪽"으로 자리를 옮긴 것이다.',
    '중계 구조가 바뀌면 신호를 읽어야 할 자리도 바뀐다 — 피처 하나에 의존하면 안 되는 이유다.',
    '',
    '[이 장의 의의]',
    '지난 발표의 결과는 전부 "한 모델, 한 경로"에서 나왔다. 일반화 가능성이 전혀 검증되지 않은 상태였다.',
    '이후 12일은 바로 그 구멍을 메우는 기간이었다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 1 — 동기와 OpenAI
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '01 동기·OpenAI' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '01 동기·OpenAI' });
  s.addText('01', { placeholder: 'num' });
  s.addText('11-16~17 — 동기를 서열화하고 OpenAI로 들어가다', { placeholder: 'title' });
  s.addText('"왜 필요한지 와닿지 않는다"는 피드백의 진짜 답을 여기서 찾았다.', { placeholder: 'subtitle' });
  s.addNotes('이 섹션은 두 갈래다. 앞쪽은 "이 연구가 왜 필요한가"를 정리한 것이고, 뒤쪽은 OpenAI 모델을 새로 재면서 예상 밖의 발견이 나온 부분이다.');
}

{
  const s = content('01 동기·OpenAI', '연구 동기', '동기 넷의 강도를 줄 세웠다',
    '넷 다 맞는 말이지만 논문의 척추가 되는 것은 (A) 하나뿐이다. 순서를 틀리면 FinOps 블로그가 된다.');
  table(s, [
    head(['', '동기', '강도', '성립 조건 / 함정']),
    [{ text: 'A', options: { bold: true, color: THEME.colors.accent3 } }, { text: '제3자 부채널', options: { bold: true } },
      { text: '척추', options: { bold: true, fill: { color: 'DFF5F0' } } },
      '관측자는 API 사용자가 아니다. 암호문만 보는데 "얼마나 깊이 생각했나"가 샌다. 추론 깊이는 질문의 난도·민감도와 상관하므로 내용을 못 읽어도 질문의 성격이 샌다'],
    [{ text: 'B', options: { bold: true, color: THEME.colors.accent2 } }, { text: '자기보고 숫자의 외부 감사', options: { bold: true } }, '두 번째',
      'usage는 과금 주체가 스스로 적은 숫자다. 외부 교차검증 수단이 없다. (※ 범위 축소 — 아래)'],
    ['C', '깊이에 따라 트래픽이 어떻게 변하나', '—', '이건 동기가 아니라 연구 질문 그 자체(RQ1·RQ2)'],
    [{ text: 'D', options: { color: THEME.colors.accent5 } }, { text: '토큰 비용', options: { color: THEME.colors.accent5 } },
      { text: '배경', options: { color: THEME.colors.accent5 } },
      { text: '설정 하나로 비용이 7배가 되는 건 사실이다. 그러나 "비용 문제면 usage 읽으면 끝"이라는 반문을 (B) 없이는 못 막는다', options: { color: THEME.colors.accent5 } }],
  ], { y: 1.6, colW: [0.45, 2.7, 0.9, 7.95], rowH: 0.52 });

  s.addText('발표 순서는 A → B → D. 비용을 앞세우면 보안 논문이 아니라 비용 절감 블로그가 된다.',
    { x: M, y: 4.6, w: W, h: 0.5, fontSize: 13, bold: true, color: THEME.colors.accent4, isTextBox: true });

  s.addNotes([
    '[용어]',
    '· 부채널(side channel) : 정상적인 통로가 아니라 "옆에서 새는" 정보로 비밀을 알아내는 공격.',
    '  내용은 암호화돼 있어도 크기·시간·전력 같은 부수적 흔적이 남으면 그것으로 추측할 수 있다.',
    '· 제3자 관측자 : 통신의 당사자가 아닌 사람. 여기서는 기관의 네트워크 관리자.',
    '· usage : API가 응답에 같이 돌려주는 사용량 정보. 추론 토큰 수가 여기 적혀 온다.',
    '· 직결 vs 게이트웨이 : 모델 회사 서버에 바로 접속하느냐, 중계 서버를 거치느냐.',
    '',
    '[왜 이 순서가 중요한가]',
    '"추론 깊이를 알면 뭐가 좋은데?"라는 질문에 비용부터 답하면 반드시 이렇게 반박당한다 —',
    '"비용이 궁금하면 API가 알려주는 usage를 읽으면 되지 왜 패킷을 보나?"',
    '맞는 반박이다. 그래서 A(관측자가 당사자가 아니라서 usage를 애초에 볼 수 없다)를 먼저 세운다.',
    '',
    '[A가 왜 보안 문제인가]',
    '"얼마나 깊이 생각했는가"는 "얼마나 어렵거나 민감한 질문이었는가"와 상관이 있다.',
    '즉 질문 내용을 한 글자도 못 읽어도 질문의 성격이 새어 나간다. 이게 프라이버시 침해가 되는 지점이다.',
  ].join('\n'));
}

{
  const s = content('01 동기·OpenAI', '범위 결정 (2026-11-24)', '학교 게이트웨이(BAZE)를 연구 범위에서 뺀다',
    '성립 조건이 스스로 배제하고 있었다. 11-12 자료의 게이트웨이 측정 네 장은 범위 밖이 된다.');
  s.addText([
    { text: '① 척추 동기 (A)의 성립 조건과 정면 충돌한다', options: { bold: true, fontSize: 13.5, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 4 } },
    { text: '     11-12 자료 5장이 "기관이 API 프록시를 운영한다 → 평문으로 다 본다"를 불성립 조건으로 적어놨다. BAZE가 그 API 프록시다.', options: { fontSize: 12, color: THEME.colors.accent5, breakLine: true, paraSpaceAfter: 11 } },
    { text: '② 주 타깃 Task B의 정답을 못 만든다', options: { bold: true, fontSize: 13.5, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 4 } },
    { text: '     thoughts_tokens 가 1,020/1,020 전부 null 이다. ground truth 를 못 내는 경로는 측정 경로가 될 수 없다.', options: { fontSize: 12, color: THEME.colors.accent5, breakLine: true, paraSpaceAfter: 11 } },
    { text: '③ 재는 대상이 모델이 아니라 중계 방식이 된다', options: { bold: true, fontSize: 13.5, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 4 } },
    { text: '     게이트웨이가 SSE 를 즉시 열어 pkt_gap 이 6ms 로 죽었다(AUC 0.496). 침묵이 사라진 게 아니라 중계기가 자리를 옮긴 것이다.', options: { fontSize: 12, color: THEME.colors.accent5, breakLine: true, paraSpaceAfter: 11 } },
    { text: '④ n = 1 이고 운영 주체도 미확인이다', options: { bold: true, fontSize: 13.5, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 4 } },
    { text: '     한 곳으로 "게이트웨이는 이렇다"를 쓸 수 없다. 일반화하려면 2~3곳을 더 봐야 하는데 본 연구의 길이 아니다.', options: { fontSize: 12, color: THEME.colors.accent5 } },
  ], { x: M, y: 1.55, w: 7.5, h: 3.9, color: C.text1, isTextBox: true, valign: 'top' });

  table(s, [
    head(['thoughts_tokens 없음', '']),
    ['직결 (Gemini 네이티브)', '71 / 1,020 (15.3%)'],
    [{ text: '게이트웨이 (BAZE)', options: { bold: true } }, { text: '1,020 / 1,020 (100%)', options: { bold: true, color: THEME.colors.accent4 } }],
  ], { x: 8.4, y: 1.62, w: 4.3, colW: [2.6, 1.7], rowH: 0.34, fontSize: 10.5 });

  s.addText([
    { text: '잃는 것 / 지키는 것', options: { bold: true, fontSize: 12.5, color: THEME.colors.accent3, breakLine: true, paraSpaceAfter: 6 } },
    { text: '11-12 자료 14~17장(AUC 0.930 · 등간격 아님 · 0.994→0.930 하락 논증)이 범위 밖이 된다. 다만 전부 직결 250문항에서 재측정됐다 — 실질 손실 없다.', options: { fontSize: 11.5, breakLine: true, paraSpaceAfter: 8 } },
    { text: '조기 탐지 0.972 / 533ms 는 gem_strict, 즉 Gemini 직결이라 그대로 살아남는다.', options: { fontSize: 11.5 } },
  ], { x: 8.4, y: 3.0, w: 4.3, h: 2.45, color: C.text1, isTextBox: true, valign: 'top', fill: { color: THEME.colors.lt2 }, margin: 9 });

  s.addText('동기 (B)는 게이트웨이 없이 서는 형태로 좁힌다 — "usage는 과금 주체가 스스로 적은 숫자이고, 외부 교차검증 수단이 없다." 자기보고 감사 논거는 프록시 없이도 성립한다. 약해지지만 0은 아니다.',
    { x: M, y: 5.6, w: 7.5, h: 0.8, fontSize: 12, bold: true, color: THEME.colors.accent1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[이 결정의 배경]',
    '11-12 발표의 주요 측정은 학교 LLM 게이트웨이(BAZE)를 거쳐서 이뤄졌다.',
    '"학생이 실제로 쓰는 경로에서 쟀다"는 것이 당시의 장점이었다. 그런데 연구가 진행되면서',
    '이 경로가 네 가지 이유로 연구 범위와 맞지 않는다는 것이 분명해졌다.',
    '',
    '[용어]',
    '· API 프록시 / 게이트웨이 : 여러 회사의 LLM을 한 주소로 모아 중계해 주는 서버.',
    '  기관이 이걸 운영하면 기관은 오가는 내용을 평문으로 다 볼 수 있다.',
    '· 성립 조건 : 이 연구의 위협모델이 말이 되려면 반드시 참이어야 하는 전제.',
    '  "관측자에게 암호문만 보인다"가 그것인데, 프록시를 운영하면 이 전제가 깨진다.',
    '· ground truth(정답) : 학습과 평가에 쓰는 참값. Task B에서는 실제 추론 토큰 수다.',
    '· null : 값이 없다는 뜻. "0이라서 없다"와 "안 알려줘서 없다"가 로그에서 똑같이 보인다.',
    '· SSE : 서버가 응답을 조금씩 나눠 보내는 방식.',
    '· pkt_gap : 요청 후 첫 응답 패킷까지의 침묵. 게이트웨이가 통로를 미리 열어버리면 6ms로 줄어든다.',
    '',
    '[①이 가장 결정적이다]',
    '11-12 자료 5장에서 "기관이 API 프록시를 운영하면 평문으로 다 보므로 이 연구가 성립하지 않는다"고',
    '직접 적었다. 그런데 바로 그 프록시에서 측정을 하고 있었다. 내부 모순이다.',
    '관측자가 게이트웨이에 앉아 있다면 패킷을 분석할 이유가 없다 — 그냥 읽으면 된다.',
    '',
    '[잃는 것을 정확히 말하면]',
    '11-12 자료 14~17장이 BAZE 기반이다. 그런데 그 네 장의 결론(단계가 등간격이 아니다,',
    '인접 단계는 잘 안 갈린다, 표본을 늘리면 성능이 내려간다)은 전부 직결 250문항 측정에서',
    '더 큰 표본으로 다시 확인됐다. 즉 결론은 살아 있고 근거만 교체된 것이다.',
    '',
    '[동기 (B)를 어떻게 살리나]',
    '원래 (B)의 유일한 증거가 "게이트웨이 고객은 추론 토큰을 못 본다"였다. 이게 빠지면',
    '"usage는 과금하는 쪽이 스스로 적은 숫자다"로 좁혀야 한다. 청구서를 발행하는 주체가',
    '청구 근거도 함께 제출하는 구조이고, 이를 독립적으로 검증할 외부 수단이 없다는 논거다.',
    '프록시가 없어도 성립하지만, 게이트웨이 사례만큼 구체적이지는 않다.',
  ].join('\n'));
}

{
  const s = content('01 동기·OpenAI', '예상 밖의 발견 ①', '싼 모델이 더 많이 생각한다',
    '가설 둘을 세우고 대조군으로 갈랐다. "능력 차이" 확정, "예산 매핑" 기각.');
  stat(s, M, 1.6, 3.1, '631', 'gpt-6-luna  ($0.5/1M)', '콜당 평균 추론 토큰', THEME.colors.accent3);
  stat(s, M + 3.5, 1.6, 3.1, '246', 'gpt-6.1-terra  ($5/1M)', '', THEME.colors.accent2);
  stat(s, M + 7.0, 1.6, 3.1, '135', 'gpt-6.1-sol  ($10/1M)', '', THEME.colors.accent1);
  s.addText('짝지은 문항별 비교로도 luna > sol이 57/60 (95%)',
    { x: M, y: 3.2, w: W, h: 0.35, fontSize: 12.5, bold: true, color: THEME.colors.dk1, isTextBox: true });

  table(s, [
    head(['', '원래 문항(v2) 콜당', 'trivial 문항 콜당', '감소']),
    ['luna', '631', { text: '19.1', options: { bold: true } }, '33배'],
    ['terra', '246', { text: '5.3', options: { bold: true } }, '46배'],
    ['sol', '135', { text: '13.7', options: { bold: true } }, '10배'],
  ], { y: 3.7, colW: [2.0, 3.4, 3.4, 3.29], rowH: 0.34 });

  s.addText('→ 고정 예산을 태우는 모델이 하나도 없다. 쉬운 문항에서는 전부 급감한다. (나) 예산 매핑 기각, (가) 능력 차이 확정.',
    { x: M, y: 5.25, w: W, h: 0.6, fontSize: 13, bold: true, color: THEME.colors.accent1, isTextBox: true });

  s.addNotes([
    '[무엇을 한 실험인가]',
    '세 모델에 똑같은 60문항을 던져서 각자 추론 토큰을 얼마나 쓰는지 셌다.',
    '놀랍게도 제일 싼 모델이 제일 많이 썼다. 비싼 모델이 더 열심히 생각할 거라는 직관과 반대다.',
    '',
    '[가설 두 개와 어떻게 갈랐나]',
    '(가) 능력 차이 : 약한 모델이라 같은 결론에 도달하는 데 더 많은 단계가 필요하다.',
    '(나) 예산 매핑 : 같은 "high"라는 글자가 모델마다 다른 세기로 번역돼 있다(= 고정 예산을 태운다).',
    '',
    '가르는 방법 : "추론할 것이 없는" 문제만 모은 대조군(trivial, 암산 한 번짜리 12문항)을 만들었다.',
    '만약 (나)가 맞다면 쉬운 문제에서도 예산만큼은 태울 테니 숫자가 안 줄어야 한다.',
    '결과는 전부 10~46배 급감. 따라서 (나)는 기각, (가)가 맞다.',
    '',
    '[왜 중요한가]',
    'OpenAI 공식 문서에 "모델은 적응적으로 추론한다"고 적혀 있는데, 그걸 외부에서 실측으로 확인한 셈이다.',
    '그리고 뒤에 나올 "탐지 난이도는 모델이 단계를 얼마나 벌려 쓰느냐가 정한다"는 결론의 출발점이 된다.',
    '',
    '[대조군(control group)이란]',
    '비교 기준이 되는 집단. 여기서는 "추론이 필요 없는 문제"가 대조군이고,',
    '이걸 둬야 "모델이 문제에 반응한 것"과 "모델이 원래 그런 것"을 구별할 수 있다.',
  ].join('\n'));
}

{
  const s = content('01 동기·OpenAI', '예상 밖의 발견 ②', '세대 가설도 기각됐다 — 0 토큰은 포기가 아니라 생략',
    '같은 세대가 정반대로 갈렸다. "비쌀수록 끈다"가 아니라 "가장 싼 하나만 못 끈다"에 가깝다.');
  table(s, [
    head(['모델', '$/1M 출력', 'low', 'medium', 'high', 'xhigh', 'max', '정답률']),
    [{ text: 'gpt-6-luna', options: { bold: true } }, '0.50',
      { text: '16.0', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '18.2', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '19.5', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '18.6', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '20.8', options: { bold: true, color: THEME.colors.accent3 } }, '100%'],
    ['gpt-6.1-terra', '5', '0.0', '0.0', '0.0', '0.0', '32.9', '100%'],
    ['gpt-6.1-sol', '10', '0.0', '0.0', '5.1', '20.1', '42.8', '100%'],
    [{ text: 'gpt-6-astra', options: { bold: true } }, '50',
      { text: '0.0', options: { bold: true, color: THEME.colors.accent4 } },
      { text: '0.0', options: { bold: true, color: THEME.colors.accent4 } }, '7.4', '23.8', '53.2', '100%'],
  ], { y: 1.7, colW: [2.3, 1.3, 1.2, 1.4, 1.2, 1.2, 1.2, 2.29], rowH: 0.38 });

  s.addText([
    ...bullets([
      { text: 'astra는 luna와 같은 gpt-6 세대인데 low·medium이 전부 0이다 (12/12 콜) → 세대별 게이팅 정책이 아니다', opt: { bold: true } },
      '단가 순서도 아니다. 가장 적극적으로 끄는 것은 terra($5)로 sol·astra보다 더 끈다',
      { text: 'terra는 추론 토큰 0으로 12문항을 다 맞혔다 → 0 토큰은 "포기"가 아니라 "생략"이다', opt: { bold: true, color: THEME.colors.accent1 } },
      'luna가 쓴 16~21 토큰은 이 문항들에서 순수 낭비다. 0 토큰 모델과 똑같은 답을 낸다',
    ]),
  ], { x: M, y: 3.78, w: W, h: 2.45, fontSize: 13, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[표를 읽는 법]',
    '칸의 숫자는 그 설정에서 쓴 평균 추론 토큰 수다. 0이면 아예 생각을 안 했다는 뜻이다.',
    '',
    '[세대 가설이란]',
    '"gpt-6 세대는 추론을 항상 조금은 하고, gpt-6.1 세대는 끌 수 있다" 같은',
    '세대별 정책이 있을 거라는 추측이었다. astra가 luna와 같은 gpt-6인데 정반대로 행동하므로 기각된다.',
    '',
    '[게이팅(gating)이란]',
    '조건에 따라 기능을 켜고 끄는 것. 여기서는 "쉬운 문제면 추론을 끈다"는 내부 판단을 말한다.',
    '',
    '[왜 중요한가 — 두 가지]',
    '(1) 연구 방법상 : 모델마다 설정값의 의미가 다르다. "low"라는 같은 글자가 어떤 모델에서는',
    '    추론 16토큰, 다른 모델에서는 0토큰이다. 따라서 설정값(Configured)을 정답으로 삼는',
    '    Task A는 근본적으로 흔들리는 땅 위에 서 있다. 이것이 Task B로 무게를 옮긴 이유다.',
    '(2) 결과 해석상 : 0 토큰인데 12문항을 다 맞혔다는 건 "포기해서 0"이 아니라',
    '    "필요 없어서 생략"이라는 뜻이다. 모델이 똑똑해서 아끼는 것이지 고장난 게 아니다.',
  ].join('\n'));
}

{
  const s = content('01 동기·OpenAI', '예상 밖의 발견 ③', '추론은 정확도를 산다 — 단, medium까지만',
    'medium 위로는 토큰만 더 쓰고 정확도는 안 오른다. 설정값이 성능과 선형 관계가 아니다.');
  const chartData = [{
    name: '정답률 (%)',
    labels: ['none', 'low', 'medium', 'high', 'xhigh', 'max'],
    values: [42.0, 88.0, 96.0, 92.0, 95.9, 95.8],
  }];
  s.addChart(pres.ChartType.bar, chartData, {
    x: M, y: 1.65, w: 6.3, h: 3.5,
    barDir: 'col',
    showTitle: true, title: 'gpt-6-luna · 정답 있는 50문항',
    titleFontFace: '+mn-lt', titleFontSize: 12, titleColor: THEME.colors.dk1,
    chartColors: [THEME.colors.accent2],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 10,
    dataLabelFontFace: '+mn-lt', dataLabelColor: THEME.colors.dk1,
    catAxisLabelColor: THEME.colors.accent5, valAxisLabelColor: THEME.colors.accent5,
    catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
    catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
    valGridLine: { color: 'E3E9EF', size: 1 },
    catGridLine: { style: 'none' },
    valAxisMaxVal: 100, valAxisMinVal: 0,
    showLegend: false,
  });

  table(s, [
    head(['짝지은 비교 (같은 문항)', '둘 다 맞음', '앞만', '뒤만', '둘 다 틀림']),
    ['none vs low', '20', '1', { text: '24', options: { bold: true, color: THEME.colors.accent3 } }, '5'],
    ['low vs medium', '44', '0', { text: '4', options: { bold: true, color: THEME.colors.accent3 } }, '2'],
    ['medium vs high', '45', { text: '3', options: { bold: true, color: THEME.colors.accent4 } }, '1', '1'],
  ], { x: 7.2, y: 1.95, w: 5.5, colW: [1.9, 1.0, 0.8, 0.8, 1.0], rowH: 0.4, fontSize: 10.5 });

  s.addText('medium → high 에서는 오히려 뒤집히는 쪽이 더 많다 (medium만 맞음 3 vs high만 맞음 1).',
    { x: 7.2, y: 3.75, w: 5.5, h: 0.8, fontSize: 12, bold: true, color: THEME.colors.accent4, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[무엇을 보여주는 그림인가]',
    '왼쪽 막대는 설정을 올릴수록 정답률이 어떻게 변하는지다. none(42%) → low(88%)에서 크게 뛰고,',
    'medium(96%)에서 꼭대기를 찍은 뒤로는 평평하거나 살짝 내려간다.',
    '',
    '[짝지은 비교(paired comparison)란]',
    '전체 평균만 보면 "우연히 쉬운 문제가 걸렸나"를 구분할 수 없다. 그래서 같은 문항을 두 설정으로',
    '각각 풀린 뒤 그 문항 안에서 승부를 센다. 표의 "앞만/뒤만"이 누가 이겼는지다.',
    '',
    '[왜 중요한가]',
    '· 실용적으로 : medium 위로 올리는 것은 돈만 더 쓰는 일이다.',
    '· 연구적으로 : 설정 라벨(low~max)이 실제 성능과 선형으로 대응하지 않는다는 증거가 하나 더 쌓인다.',
    '  이것도 Task A(설정 맞히기)가 아니라 Task B(실제 추론량 맞히기)로 무게를 옮긴 근거가 된다.',
    '',
    '[주의]',
    '이 실험은 luna 한 모델, 정답이 있는 50문항 기준이다. 다른 모델에서 같은 꺾임이 나오는지는 아직 안 쟀다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 2 — Anthropic과 기전
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '02 기전' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '02 기전' });
  s.addText('02', { placeholder: 'num' });
  s.addText('11-18~19 — Anthropic 진입, 그리고 누출의 기전', { placeholder: 'title' });
  s.addText('"샌다"에서 "이렇게 샌다"로. 그리고 단계 해상도의 진짜 한계가 드러났다.', { placeholder: 'subtitle' });
  s.addNotes('기전(mechanism)이란 "왜 그런 일이 일어나는가"의 물리적 경로를 말한다. 현상만 보이면 우연일 수 있지만, 기전을 밝히면 주장이 단단해진다.');
}

{
  const s = content('02 기전', '누출 기전', '암호화된 "사고 서명"이 전선 바이트까지 그대로 통과한다',
    '애플리케이션이 만든 서명 길이와 전선에서 센 바이트가 거의 1:1이다. 상관 0.9986.');
  table(s, [
    head(['상관 관계 (claude-haiku-5-5, 깨끗한 1,166행)', 'Pearson r', '기울기']),
    [{ text: 'sig_chars → down_bytes  (사고 서명 길이 → 내려온 바이트)', options: { bold: true } },
      { text: '0.9986', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '1.008 바이트/글자', options: { bold: true, color: THEME.colors.accent3 } }],
    ['thoughts_tokens → down_bytes  (추론 토큰 → 바이트)', '0.9765', '3.214 바이트/토큰'],
    ['thoughts_tokens → app_ttft_ms  (추론 토큰 → 첫 응답까지 시간)', '0.9934', '4.541 ms/토큰'],
  ], { y: 1.6, colW: [7.3, 2.2, 2.59], rowH: 0.44 });

  s.addText([
    { text: '길이 통제도 성립을 확인했다', options: { bold: true, fontSize: 14, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 6 } },
    ...bullets([
      '조건별 요청 바이트(up_bytes) 중앙값 1178 / 1177.5 / 1177.5 / 1177.5 / 1177.5 — 0.5바이트 차',
      '요청 쪽은 설정을 전혀 흘리지 않는다. 따라서 하향(내려오는) 신호가 진짜다',
      'Gemini(r=0.9977)와 같은 수준 → 발표 자료에 "미확인"으로 남아 있던 Claude 전선 검증이 닫혔다',
    ]),
  ], { x: M, y: 3.5, w: W, h: 2.6, fontSize: 13, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[핵심 용어 — 사고 서명(thought signature)]',
    '모델이 생각한 내용을 모델 회사가 암호화해서 응답에 같이 실어 보내는 덩어리다.',
    '사용자는 못 읽는다(암호화돼 있으니까). 그런데 많이 생각할수록 이 덩어리가 길어진다.',
    '즉 "읽을 수는 없지만 길이는 보이는" 것이고, 그 길이가 곧 사고의 양을 알려준다.',
    '',
    '[용어]',
    '· Pearson r : 두 값이 같이 움직이는 정도. 1에 가까울수록 한쪽을 알면 다른 쪽을 거의 안다.',
    '· 기울기 1.008 바이트/글자 : 서명이 1글자 늘면 전선 바이트도 정확히 1바이트 늘었다는 뜻.',
    '  암호화·압축·분할 같은 중간 과정이 있는데도 거의 손실 없이 통과했다는 의미다.',
    '· down_bytes / up_bytes : 서버에서 내려온 바이트 / 내가 올려보낸 바이트.',
    '· app_ttft_ms : 요청 후 첫 응답 글자가 도착할 때까지 걸린 시간(밀리초).',
    '· 중앙값 : 값을 줄 세웠을 때 한가운데 값. 평균과 달리 극단값에 안 흔들린다.',
    '',
    '[길이 통제가 왜 필요한가]',
    '만약 깊이 생각할수록 답도 길어진다면, 우리가 본 것은 "사고의 양"이 아니라 "답의 길이"일 수 있다.',
    '그래서 답을 한 글자로 강제했다. 그리고 올려보내는 요청 크기도 패딩으로 똑같이 맞췄다.',
    '위 1178 vs 1177.5는 "요청 쪽에서는 설정이 전혀 새지 않았다"는 확인이다.',
    '(※ 뒤에서 이 길이 통제가 사실은 필요 없었다는 것이 밝혀진다 — 05번 섹션 참조)',
    '',
    '[왜 중요한가]',
    '이전까지는 "암호문에서 뭔가 새는 것 같다"는 현상 관찰이었다. 이제 "무엇이 어떤 경로로 새는가"를',
    '숫자로 말할 수 있다. 심사자가 "다른 이유 때문 아니냐"고 물을 때 방어할 수 있는 근거가 생긴 것이다.',
  ].join('\n'));
}

{
  const s = content('02 기전', '해상도의 한계', '극단은 결정적, 인접 단계는 동전 던지기에 가깝다',
    '"5단계를 식별한다"고 쓰면 과장이다. "추론량이 샌다, 극단 대비는 결정적이다"가 정확하다.');
  table(s, [
    head(['지표 (claude-haiku, 5조건 완비 201문항)', 'low < max', '5단계 완전단조', '인접단계 증가율']),
    ['down_bytes', { text: '201/201 (100%)', options: { bold: true, color: THEME.colors.accent3 } }, '67/201 (33.3%)', '76 / 76 / 73 / 98%'],
    ['app_ttft_ms', { text: '201/201 (100%)', options: { bold: true, color: THEME.colors.accent3 } }, '52/201 (25.9%)', '67 / 74 / 70 / 97%'],
    ['thoughts_tokens', { text: '201/201 (100%)', options: { bold: true, color: THEME.colors.accent3 } }, '59/201 (29.4%)', '68 / 76 / 76 / 98%'],
  ], { y: 1.6, colW: [4.9, 2.4, 2.3, 2.49], rowH: 0.42 });

  s.addText([
    { text: '읽는 법이 둘이고, 둘 다 말해야 한다', options: { bold: true, fontSize: 15, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 7 } },
    { text: '① low vs max는 암호문 바이트만으로 201문항 전부 맞는다. 예외가 0건이다.', options: { bold: true, breakLine: true, paraSpaceAfter: 5 } },
    { text: '     모델도 필요 없고 문항 난이도로는 설명되지 않는다. 위협모델의 존재증명으로 충분하다.', options: { breakLine: true, paraSpaceAfter: 9, color: THEME.colors.accent5 } },
    { text: '② 중간 네 단계는 단계당 73~76%. 넷 중 하나가 뒤집힌다.', options: { bold: true, breakLine: true, paraSpaceAfter: 5, color: THEME.colors.accent4 } },
    { text: '     5단계가 전부 순서대로 나오는 문항은 33%뿐. 우연(0.83%)의 40배지만 절대 수준은 낮다.', options: { color: THEME.colors.accent5 } },
  ], { x: M, y: 3.5, w: W, h: 2.6, fontSize: 13, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[표를 읽는 법]',
    '· "low < max" : 한 문항 안에서 low 설정의 값이 max 설정의 값보다 작았던 비율.',
    '  201문항 전부가 그랬다 = 예외가 하나도 없다.',
    '· "5단계 완전단조" : low < medium < high < xhigh < max 가 순서대로 다 지켜진 비율.',
    '  단조(monotone)란 중간에 뒤집히지 않고 쭉 커지는 것을 말한다.',
    '· "인접단계 증가율" : 바로 옆 단계끼리 비교했을 때 순서가 맞은 비율.',
    '',
    '[왜 같은 문항 안에서 비교하나]',
    '문항을 섞어서 재면 "어려운 문제라서 추론도 많고 응답도 길다"와 구별이 안 된다.',
    '같은 문항에서 설정만 바꾸면 문항 난이도가 상수가 되므로 설정의 효과만 남는다.',
    '',
    '[왜 이 장이 중요한가 — 연구 윤리의 문제이기도 하다]',
    '"암호문만 보고 5단계를 구분한다"고 쓰면 멋있지만 과장이다. 실제로는 양 끝은 완벽한데',
    '가운데는 거의 못 가른다. 이걸 먼저 밝히고 들어가면 심사자가 발견했을 때 받을 타격이 없다.',
    '',
    '[여기서 연구 방향이 바뀌었다]',
    '주장을 "effort 단계를 식별한다"가 아니라 "추론량 자체가 바이트·시간으로 새고, 극단 대비는',
    '결정적이다"로 다시 잡았다. 설정 라벨(Configured)이 아니라 실제 추론량(Realized)을',
    '타깃으로 삼는 쪽이 훨씬 방어하기 쉽다는 판단이다.',
    '',
    '[참고] opus는 더 나쁘다. low 154 → medium 213 → high 222 → xhigh 337 → max 1,780 으로,',
    'medium과 high가 사실상 같다. 단계 라벨이 추론량으로 번역되지 않는 구간이 모델마다 다르다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 3 — 전수와 정정
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '03 전수·정정' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '03 전수·정정' });
  s.addText('03', { placeholder: 'num' });
  s.addText('11-20 — 3 provider 전수, 기전 확정, 그리고 자기 정정', { placeholder: 'title' });
  s.addText('하룻밤에 7모델 9,812콜. 그리고 그날 저녁, 아침에 쓴 제목이 틀렸다는 것을 발견했다.', { placeholder: 'subtitle' });
  s.addNotes('이 섹션이 이번 연구의 분수령이다. 세 회사 데이터가 같은 축 위에 올라오면서 비로소 비교가 가능해졌다.');
}

{
  const s = content('03 전수·정정', '전수 캡처', '7모델이 동일한 250문항을 공유한다',
    '같은 문항 축에 올려야 provider 간 수치를 나란히 놓을 수 있다. 여기서 비교가 처음 가능해졌다.');
  table(s, [
    head(['모델', 'provider', '단계', '콜', '완전·깨끗 문항', '불응', '비용']),
    ['gemini-3.5-flash-lite', 'Google', '3', '2,312', '731 / 770', '2%', '무료등급'],
    ['gpt-6.1-sol', 'OpenAI', '5', '1,250', { text: '250 / 250', options: { bold: true, color: THEME.colors.accent3 } }, { text: '0%', options: { bold: true, color: THEME.colors.accent3 } }, '$2.04'],
    ['gpt-6.1-terra', 'OpenAI', '5', '1,250', '248 / 250', { text: '0%', options: { bold: true, color: THEME.colors.accent3 } }, '$1.57'],
    ['gpt-6-luna', 'OpenAI', '5', '1,250', '245 / 250', { text: '0%', options: { bold: true, color: THEME.colors.accent3 } }, '$0.20'],
    ['claude-haiku-5-5', 'Anthropic', '5', '1,250', '201 / 250', '7%', '—'],
    ['claude-opus-5-5', 'Anthropic', '5', '1,250', '178 / 250', '21%', '$14.01'],
    ['claude-sonnet-5-5', 'Anthropic', '5', '1,250', { text: '101 / 250', options: { bold: true, color: THEME.colors.accent4 } }, { text: '28%', options: { bold: true, color: THEME.colors.accent4 } }, '$8.17'],
  ], { y: 1.6, colW: [2.9, 1.5, 0.7, 1.0, 2.0, 1.0, 2.99], rowH: 0.33 });

  s.addText([
    ...bullets([
      '통제는 전 모델에서 성립 — 요청 바이트 폭 0~2B, 순응 행의 answer_chars 전부 정확히 1, pcap 매칭 실패 5,205행 중 0건',
      { text: 'Claude만 dilemma 갈래에서 한 글자 규칙을 어긴다. OpenAI 3모델은 3,750콜 중 산문 불응 0건', opt: { bold: true } },
      { text: 'sonnet은 250문항 중 149개(60%)를 불응으로 잃었다. 사전선별 20~30콜($0.3)로 가를 수 있었다', opt: { bold: true, color: THEME.colors.accent4 } },
    ]),
  ], { x: M, y: 4.25, w: W, h: 2.0, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[용어]',
    '· 불응 : 답을 한 글자로 쓰라고 했는데 모델이 설명을 늘어놓은 경우. 길이 통제가 깨지므로 버려야 한다.',
    '· dilemma 갈래 : 트롤리 문제처럼 윤리적 선택을 묻는 문항. Claude가 여기서 "한 글자로는',
    '  답할 수 없습니다" 같은 해명을 쓰는 경향이 있다.',
    '· 완전·깨끗 문항 : 5개 설정 전부가 불응·잘림 없이 정상적으로 측정된 문항. 짝지은 비교에 쓸 수 있는 것.',
    '· pcap : 네트워크 패킷을 그대로 저장한 파일. 전선에서 실제로 무엇이 오갔는지의 원본 기록이다.',
    '· 사전선별(screening) : 본 측정 전에 소수 문항으로 미리 돌려보고 쓸 수 있는지 거르는 절차.',
    '',
    '[왜 "같은 250문항"이 중요한가]',
    '모델마다 다른 문항으로 쟀다면 "A모델이 더 잘 샌다"가 "A모델 문항이 더 쉬웠다"와 구별되지 않는다.',
    '7모델 전부를 같은 문항 위에 올렸기 때문에 비로소 공정한 비교가 가능해졌다.',
    '',
    '[반성할 점]',
    'sonnet에서 60%를 날린 것은 사전선별을 건너뛴 대가다. $0.3로 막을 수 있었던 손실이다.',
    '유료 API는 기회가 한 번뿐이라 미리 작게 확인하는 절차를 생략하면 안 된다.',
  ].join('\n'));
}

{
  const s = content('03 전수·정정', '자기 정정', 'OpenAI도 암호화 서명을 보낸다 — 그것도 2~3번',
    '"필드가 0"을 "provider가 안 보낸다"로 읽으면 안 된다. 우리 코드가 못 본 것이었다.');
  s.addText([
    { text: '아침에 쓴 제목: ', options: { color: THEME.colors.accent5 } },
    { text: '"서명 없는 OpenAI가 Claude보다 10배 많이 샌다"', options: { strike: true, color: THEME.colors.accent5, breakLine: true } },
    { text: '저녁에 정정: OpenAI도 Claude·Gemini와 똑같은 자리에 서명을 보낸다. 우리 러너가 delta 문자열만 검사해서 못 봤다.', options: { bold: true, color: THEME.colors.accent4 } },
  ], { x: M, y: 1.58, w: W, h: 0.9, fontSize: 13.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText('"item":{"type":"reasoning","summary":[],"content":[],\n        "encrypted_content":"gAAAAABq_9h1xnODKi-0YtW4vOanv5Cw_5qDpiXLTv4j9F8M…"}',
    { x: M, y: 2.5, w: W, h: 0.72, fontSize: 10.5, fontFace: 'Courier New', color: THEME.colors.dk1, fill: { color: THEME.colors.lt2 }, isTextBox: true, margin: 8, valign: 'middle' });

  table(s, [
    head(['SSE 이벤트', 'sol  추론토큰당 B', 'terra']),
    ['response.output_item.added', '1.59', '15.26'],
    ['response.output_item.done', '16.31', '14.60'],
    ['response.completed  (output 전체 재전송)', '16.19', '14.50'],
    [{ text: '합', options: { bold: true } }, { text: '34.10', options: { bold: true } }, { text: '44.36', options: { bold: true } }],
    [{ text: 'pcap 실측 (1,250콜)', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '35.99', options: { bold: true, color: THEME.colors.accent3 } }, '36.18'],
  ], { x: M, y: 3.42, w: 7.2, colW: [3.9, 1.7, 1.6], rowH: 0.33, fontSize: 10.5 });

  s.addText([
    { text: '기전 확정', options: { bold: true, fontSize: 16, color: THEME.colors.accent3, breakLine: true, paraSpaceAfter: 8 } },
    { text: 'sol의 계산 합계 34.10이 pcap 실측 35.99와 거의 일치한다. 이론과 전선이 맞았다.', options: { breakLine: true, paraSpaceAfter: 10 } },
    { text: '10배 차이의 내역: 서명 자체가 추론토큰당 약 15자로 Claude(3.1자)의 5배이고, 같은 blob을 2~3번 내려보낸다.', options: {} },
  ], { x: 8.1, y: 3.42, w: 4.6, h: 2.6, fontSize: 12, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[무슨 일이 있었나]',
    '아침에는 "Claude는 서명을 보내고 OpenAI는 안 보낸다"고 결론 내렸다. 로그의 sig_chars 칸이 0이었기 때문이다.',
    '저녁에 원시 통신 내용을 직접 떠보니 OpenAI도 보내고 있었다. 우리 측정 코드가 보는 위치가 틀렸던 것이다.',
    '',
    '[용어]',
    '· SSE(Server-Sent Events) : 서버가 응답을 조금씩 나눠 보내는 방식. ChatGPT에서 글자가',
    '  하나씩 나타나는 그 방식이다. 이벤트 종류마다 이름이 있다.',
    '· delta : SSE에서 "방금 새로 생긴 조각"을 담는 칸. 우리 코드는 여기만 봤는데,',
    '  서명은 item이라는 다른 칸에 실려 왔다.',
    '· encrypted_content : 암호화된 사고 내용. gAAAAAB로 시작하는 것은 Fernet이라는 암호 형식의 표식이다.',
    '· blob : 의미를 알 수 없는 덩어리 데이터.',
    '',
    '[왜 2~3번 보내나]',
    '같은 서명이 세 이벤트(added / done / completed)에 중복해서 실린다. 마지막 completed는',
    '지금까지의 출력 전체를 한 번 더 통째로 보낸다. 구현상의 선택이지 내용 때문이 아니다.',
    '',
    '[기전 확정이란 무슨 뜻인가]',
    'SSE 이벤트에서 센 바이트를 더한 값(34.10)과 실제 네트워크 패킷에서 잰 값(35.99)이 거의 같다.',
    '"이 누출이 바로 이 경로로 일어난다"를 숫자로 닫은 것이다. 다른 설명이 끼어들 여지가 없어진다.',
    '',
    '[교훈]',
    '"필드가 0으로 보인다"를 "회사가 그걸 안 보낸다"로 읽으면 안 된다. 내 코드가 못 봤을 수도 있다.',
    '세 제조사가 전부 같은 누출 경로를 가지고 있다는 쪽이 오히려 더 강한 결과다.',
  ].join('\n'));
}

{
  const s = content('03 전수·정정', '공통축 성적', 'Task B가 Task A보다 훨씬 잘 된다',
    '전선만 보고 추론 토큰 수를 상대오차 9~25%로 맞힌다. 라벨 붕괴의 영향을 안 받기 때문이다.');
  table(s, [
    head(['모델', 'Task A1  3분류 (우연 33%)', 'Task B  R²(log)', '중앙 절대오차', '상대오차']),
    ['gemini-3.5-flash-lite', { text: '64.7%', options: { bold: true } }, '0.936', '104 tok', '14%'],
    ['claude-sonnet-5-5', '62.6%', '0.964', '31 tok', '11%'],
    ['claude-haiku-5-5', '47.5%', { text: '0.977', options: { bold: true, color: THEME.colors.accent3 } }, '27 tok', { text: '9%', options: { bold: true, color: THEME.colors.accent3 } }],
    ['gpt-6.1-terra', '43.3%', '0.928', '16 tok', '21%'],
    ['gpt-6.1-sol', '40.7%', '0.887', '13 tok', '25%'],
    ['claude-opus-5-5', '36.5%', '0.878', '23 tok', '13%'],
    ['gpt-6-luna', { text: '35.6%', options: { color: THEME.colors.accent4 } }, '0.917', '17 tok', '19%'],
  ], { y: 1.6, colW: [3.2, 2.9, 2.0, 1.8, 2.19], rowH: 0.34 });

  s.addText([
    ...bullets([
      'Task A1 순위가 추론토큰 격차 순위와 거의 같다 → 탐지 난이도는 탐지기가 아니라 모델이 단계를 얼마나 벌려 쓰느냐가 정한다',
      'Gemini가 압도적인 이유: low→high가 13배(93→1,221)로 벌어진다. opus가 꼴찌인 이유: medium 215 vs high 221로 두 단계를 사실상 같게 쓴다',
      { text: 'Task B는 라벨 붕괴(sonnet low≡medium, opus medium≡high)의 영향을 안 받는다 → "Realized를 타깃으로" 방침이 수치로 확인됐다', opt: { bold: true, color: THEME.colors.accent1 } },
    ]),
  ], { x: M, y: 4.42, w: W, h: 1.9, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[Task A와 Task B의 차이 — 이 연구에서 가장 중요한 구분]',
    '· Task A (Configured, "설정") : 내가 보낸 설정값이 low였는지 max였는지 맞히기.',
    '· Task B (Realized, "실현") : 모델이 실제로 추론 토큰을 몇 개 썼는지 맞히기.',
    '',
    '[왜 Task B가 더 잘 되나]',
    '설정값과 실제 사고량이 일대일로 대응하지 않기 때문이다. sonnet은 low와 medium에서 둘 다',
    '추론을 0개 쓴다. 즉 설정은 다른데 실제 행동이 똑같다. 이걸 맞히라고 하면 원리적으로 불가능하다.',
    '반면 실제 추론 토큰 수는 전선 신호와 직접 연결돼 있으므로 잘 맞는다.',
    '이것을 "라벨 붕괴"라고 부른다 — 정답표 자체가 구분 불가능한 항목을 담고 있는 상태.',
    '',
    '[용어]',
    '· A1 / A2 / A3 : A1은 콜 하나만 보고 문항도 모르는 상태(가장 현실적이고 가장 어렵다).',
    '  A2는 같은 문항의 인접한 두 조건 비교, A3는 전 단계 순서 맞히기.',
    '· R²(log) : 로그 공간에서 잰 회귀 설명력. 추론 토큰은 10~1000 범위로 널리 퍼져 있어서',
    '  로그를 취해야 작은 값과 큰 값을 공평하게 다룬다.',
    '· 중앙 절대오차 : 예측이 실제에서 평균적으로 몇 토큰 빗나갔는가.',
    '· 상대오차 : 그 오차가 실제값 대비 몇 %인가.',
    '· 우연 33% : 3개 중 하나를 찍으면 평균 33%를 맞힌다. 이보다 높아야 의미가 있다.',
    '',
    '[피처 선정의 원칙]',
    '여기서 쓴 피처는 전부 "전선에서 관측 가능한 것"뿐이다 — 내려온 바이트, 첫 응답까지 시간 등.',
    'sig_chars나 thoughts_tokens는 API 응답에 적혀 오는 값이라 바깥 관측자는 못 본다. 그래서 제외했다.',
    '이 원칙을 안 지키면 "공격자가 알 수 없는 정보로 공격에 성공했다"는 말이 되어 버린다.',
  ].join('\n'));
}

{
  const s = content('03 전수·정정', 'Task C', 'provider는 거의 완벽히, 같은 회사 안 모델은 거의 못 가른다',
    '이 비대칭이 오히려 Task A와 Task C의 분리 논증을 강화한다.');
  table(s, [
    head(['과제', '정확도', '우연', '해석']),
    [{ text: '3 provider 식별', options: { bold: true } }, { text: '99.2%', options: { bold: true, color: THEME.colors.accent3 } }, '33.3%', 'Google은 725/725 완전 분리. Anthropic↔OpenAI 오분류 40건(0.9%)'],
    ['7 모델 식별', '51.8%', '14.3%', ''],
    ['OpenAI 내부 3모델', '46.8%', '33.3%', '우연보다 조금 나은 수준'],
    ['Anthropic 내부 3모델', { text: '38.3%', options: { bold: true, color: THEME.colors.accent4 } }, '33.3%', '거의 못 가른다'],
  ], { y: 1.6, colW: [3.0, 1.5, 1.2, 6.39], rowH: 0.46 });

  s.addText([
    { text: '해석에 주의 — 99.2%의 대부분은 추론 신호가 아니다', options: { bold: true, fontSize: 14, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      'down_bytes 절편이 Claude 약 3,000B vs OpenAI 약 11,500B. 추론량이 0이어도 4배 차이가 난다',
      '즉 "응답을 어떻게 포장하느냐"가 갈리는 것이지 "얼마나 생각했느냐"가 갈리는 게 아니다',
      { text: '그런데 이것이 오히려 논증을 강화한다 — provider 지문은 쉽게 읽히는데 같은 provider 안 모델은 38~47%에 그친다. 따라서 Task A의 성능이 "모델 지문을 베껴 쓴 것"이라고 말할 수 없다', opt: { bold: true, color: THEME.colors.accent1 } },
    ]),
  ], { x: M, y: 4.02, w: W, h: 1.95, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText('배제 못 한 교란 : 모델마다 캡처 시각이 다르다(11-18 아침 ~ 11-20 새벽). 한 pcap 안에서 모델을 교차로 찍는 캡처가 필요하다.',
    { x: M, y: 6.05, w: W, h: 0.45, fontSize: 11.5, italic: true, color: THEME.colors.accent5, isTextBox: true });

  s.addNotes([
    '[Task C란]',
    '트래픽만 보고 "이게 어느 회사, 어느 모델인가"를 맞히는 과제다.',
    '이걸 왜 하냐면 — Task A(추론 깊이 탐지)가 혹시 "추론 깊이"가 아니라 "모델 종류"를',
    '읽고 있는 것 아니냐는 반박을 막기 위해서다.',
    '',
    '[결과가 왜 다행인가]',
    '만약 같은 회사 안 모델들도 잘 구분됐다면 "네 탐지기는 모델 지문을 보는 것"이라는 의심이 생긴다.',
    '그런데 실제로는 38~47%(우연 33%)로 거의 못 가른다. 모델 지문이 그렇게 강하지 않다는 뜻이고,',
    '따라서 Task A가 잘 되는 것은 모델 지문 때문이 아니라 진짜 추론 신호 때문이라고 말할 수 있다.',
    '',
    '[용어]',
    '· 절편(intercept) : 추론량이 0일 때의 기본 바이트 수. 응답 포장에 드는 고정 비용이다.',
    '· 교란(confounding) : 진짜 원인이 아닌 다른 요인이 결과를 만들어냈을 가능성.',
    '  여기서는 "모델이 달라서"가 아니라 "측정한 시각이 달라서" 망 상태가 달랐을 수 있다는 것.',
    '',
    '[왜 교차 캡처가 필요한가]',
    '모델 A를 월요일 아침에, 모델 B를 수요일 새벽에 쟀다면, 둘의 차이가 모델 차이인지',
    '그날 망 상태 차이인지 알 수 없다. 네 모델을 같은 시간대에 번갈아 찍으면 이 문제가 사라진다.',
    '이것이 11월 22일 마지막 캡처에서 실제로 수행한 작업이다.',
  ].join('\n'));
}

{
  const s = content('03 전수·정정', '방어', '패딩만으로는 못 막는다 — 단일 채널 방어는 전부 무력',
    '패딩은 크기를 바꾸지 시간을 안 바꾼다. 바이트와 타이밍을 동시에 막아야 한다.');
  table(s, [
    head(['모델', '패딩 없음', '4KB 패딩 후', '그래도 남는 app_ttft', 'stall_total']),
    ['gemini-3.5-flash-lite', '90.6%', '56.0%', { text: '81.4%', options: { bold: true, color: THEME.colors.accent4 } }, '5.3%'],
    ['claude-sonnet-5-5', '81.4%', '21.3%', { text: '79.7%', options: { bold: true, color: THEME.colors.accent4 } }, '74.3%'],
    ['claude-haiku-5-5', '80.5%', '26.1%', { text: '76.9%', options: { bold: true, color: THEME.colors.accent4 } }, '76.4%'],
    ['claude-opus-5-5', '77.9%', '19.5%', { text: '75.6%', options: { bold: true, color: THEME.colors.accent4 } }, '77.0%'],
    ['gpt-6.1-terra', '80.0%', '34.8%', { text: '77.9%', options: { bold: true, color: THEME.colors.accent4 } }, '77.8%'],
    ['gpt-6.1-sol', '84.2%', '37.8%', { text: '73.2%', options: { bold: true, color: THEME.colors.accent4 } }, '75.0%'],
    ['gpt-6-luna', '63.3%', '24.0%', '58.3%', '57.7%'],
  ], { y: 1.6, colW: [3.2, 2.0, 2.2, 2.6, 2.09], rowH: 0.34 });

  s.addText('패딩을 걸면 바이트 채널은 실제로 죽는다(80% → 20~37%). 그런데 타이밍은 73~81%로 거의 그대로 남는다. 방어 비용이 둘의 합이라는 뜻이다 — 논문의 방어 절에서 중요한 주장이 된다.',
    { x: M, y: 4.48, w: W, h: 1.0, fontSize: 13, bold: true, color: THEME.colors.accent1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[용어]',
    '· 패딩(padding) : 실제 데이터 뒤에 의미 없는 바이트를 덧붙여 크기를 일정하게 만드는 방어.',
    '  여기서는 4KB 단위로 올림했다 — 3,100바이트도 7,900바이트도 각각 4KB, 8KB로 보이게 만든다.',
    '· app_ttft : 요청 후 첫 응답까지의 시간.',
    '· stall_total : 응답이 오는 도중에 멈칫한 시간의 합. 모델이 중간에 더 생각하면 여기가 늘어난다.',
    '· 인접단계 판별 : 바로 옆 단계 두 개를 구분하는 과제. 우연은 50%다.',
    '  같은 패딩 버킷에 들어가면 공격자가 못 가르므로 "동률"을 실패로 셌다.',
    '',
    '[왜 이것이 중요한 주장인가]',
    '방어를 제안하는 쪽에서는 보통 "패딩하면 된다"고 말한다. 간단하고 비용이 적기 때문이다.',
    '이 실험은 그것만으로는 안 된다는 것을 숫자로 보여준다. 크기를 가려도 시간이 그대로 새기 때문이다.',
    '제대로 막으려면 패딩 + 지터 주입(일부러 시간을 흐트러뜨리기) 또는 응답 일괄 방출을 같이 해야 하고,',
    '그러면 응답 속도가 느려진다. 즉 방어에 실제 비용이 든다.',
    '',
    '[주의 — 오늘 논의한 한계]',
    '이 표의 타이밍 수치는 조용한 네트워크에서 쟀다. "망이 붐비면 타이밍 신호도 묻히는 것 아니냐"는',
    '반박이 가능하다. 바이트 쪽은 망과 무관하므로 안전하지만, 타이밍 쪽은 동시 트래픽 조건에서',
    '다시 확인할 필요가 있다. 이것이 다음 실험 항목이다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 4 — 전제가 뒤집힌 날
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '04 전제 역전' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '04 전제 역전' });
  s.addText('04', { placeholder: 'num' });
  s.addText('11-21 — 연구 시작부터 믿어온 전제가 뒤집혔다', { placeholder: 'title' });
  s.addText('"답을 한 글자로 강제하는 것"은 교란 통제가 아니라 핸디캡이었다.', { placeholder: 'subtitle' });
  s.addNotes('이 섹션이 이번 12일 중 가장 중요한 발견이다. 지금까지 보고한 모든 OpenAI 수치가 하한이었다는 뜻이기 때문이다.');
}

{
  const s = content('04 전제 역전', '길이 arm 실험', '답 길이를 풀어주면 탐지가 더 쉬워진다',
    '지금까지 보고한 OpenAI 수치는 전부 하한이었다. 실제 사용 조건에서는 더 잘 잡힌다.');
  table(s, [
    head(['모델', 'arm (답변 길이 지시)', 'A1  (우연 20%)', 'A2  (50%)', 'A3  (0.8%)']),
    ['gpt-6-luna', '답만 (한 글자)', '23.3%', '61.1%', '5.7%'],
    ['gpt-6-luna', '짧은 설명', '24.1%', '63.6%', '11.8%'],
    ['gpt-6-luna', '자유 설명', '24.1%', '70.4%', '20.0%'],
    ['gpt-6.1-terra', '답만 (한 글자)', '25.0%', '75.0%', '23.4%'],
    ['gpt-6.1-terra', '짧은 설명', '31.6%', { text: '88.3%', options: { bold: true } }, { text: '57.8%', options: { bold: true } }],
    ['gpt-6.1-terra', '자유 설명', '30.9%', '88.3%', '55.0%'],
    ['gpt-6.1-sol', '답만 (한 글자)', '25.6%', '76.2%', '21.5%'],
    ['gpt-6.1-sol', '짧은 설명', '33.6%', '86.7%', '56.1%'],
    [{ text: 'gpt-6.1-sol', options: { bold: true } }, { text: '자유 설명', options: { bold: true } },
      { text: '34.8%', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '91.5%', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '66.2%', options: { bold: true, color: THEME.colors.accent3 } }],
  ], { y: 1.58, colW: [2.6, 3.0, 2.2, 2.2, 2.09], rowH: 0.3 });

  s.addText('sol 기준 A3가 21.5% → 66.2%. 세 배가 됐다. 72문항 × 5단계 × 3모델 × 3 arm = 3,239행.',
    { x: M, y: 5.0, w: W, h: 0.5, fontSize: 13, bold: true, color: THEME.colors.accent1, isTextBox: true });

  s.addNotes([
    '[arm이란]',
    '실험 조건의 갈래를 말한다. 여기서는 모델에게 주는 "답변 길이 지시"를 세 가지로 바꿨다.',
    '· 답만 : "A, B, C, D 중 한 글자만 쓰라" — 지금까지의 모든 본 측정이 이 조건이었다.',
    '· 짧은 설명 : 간단히 이유를 덧붙이게 함.',
    '· 자유 설명 : 길이 제한 없이 설명하게 함. 실제 사용자가 쓰는 방식에 가장 가깝다.',
    '',
    '[왜 9개 캡처를 따로 찍었나]',
    '한 캡처 안에 arm을 섞으면 앞 콜의 거대한 응답이 다음 콜의 측정 창을 오염시킨다.',
    '그래서 조건마다 별도로 측정했다.',
    '',
    '[A1 / A2 / A3 다시]',
    '· A1 : 콜 하나만 보고, 문항이 무엇인지도 모르는 상태에서 설정 맞히기. 가장 현실적이고 가장 어렵다.',
    '· A2 : 같은 문항의 인접한 두 조건 중 어느 쪽이 더 깊은지 고르기. 우연 50%.',
    '· A3 : 5단계 전부의 순서 맞히기. 우연은 1/120 = 0.8%.',
    '',
    '[왜 이것이 연구의 전환점인가]',
    '길이를 한 글자로 묶은 것은 "답이 길어져서 생기는 교란을 막기 위한 통제"라고 믿어왔다.',
    '그런데 실제로는 그 통제가 신호 자체를 죽이고 있었다. 즉 우리는 스스로 손을 묶고 측정해 온 것이다.',
    '',
    '[좋은 소식이자 나쁜 소식]',
    '좋은 소식 : 실제 사용 조건에서는 공격이 더 잘 통한다. 위협이 더 현실적이라는 뜻이다.',
    '나쁜 소식 : 지금까지 쌓은 측정값이 전부 하한이라 다시 재야 하는 항목이 생겼다.',
  ].join('\n'));
}

{
  const s = content('04 전제 역전', '기전', '답 길이 때문이 아니다 — 모델이 단계를 더 벌려 쓴다',
    '답변 토큰은 완전히 평평하다. 바뀐 것은 추론 토큰의 확산 폭이다.');
  table(s, [
    head(['모델', 'arm', '추론토큰 중앙 low→max', 'max/low', '답변토큰 max/low']),
    ['gpt-6.1-sol', '답만', '45 / 48 / 69 / 95 / 151', '3.4배', '1.00배'],
    ['gpt-6.1-sol', '짧은 설명', '65 / 99 / 269 / 425 / 668', { text: '10.3배', options: { bold: true, color: THEME.colors.accent3 } }, '0.99배'],
    [{ text: 'gpt-6.1-sol', options: { bold: true } }, { text: '자유 설명', options: { bold: true } }, '91 / 141 / 371 / 709 / 1,244',
      { text: '13.7배', options: { bold: true, color: THEME.colors.accent3 } }, { text: '0.92배', options: { bold: true } }],
    ['gpt-6.1-terra', '답만', '47 / 72 / 84 / 100 / 163', '3.5배', '1.00배'],
    ['gpt-6.1-terra', '자유 설명', '102 / 254 / 354 / 516 / 1,034', { text: '10.1배', options: { bold: true, color: THEME.colors.accent3 } }, '1.18배'],
  ], { y: 1.6, colW: [2.5, 2.0, 3.9, 1.8, 1.89], rowH: 0.36 });

  s.addText([
    { text: '해석', options: { bold: true, fontSize: 15, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      { text: '설명을 시키면 모델이 단계 간 추론량을 훨씬 더 벌려 쓴다. 답을 한 글자로 강제한 것이 모델의 단계 사용을 압축하고 있었다', opt: { bold: true } },
      '"탐지 난이도는 모델이 단계를 얼마나 벌려 쓰느냐가 정한다"는 기존 관찰과 정확히 맞아떨어진다. 그 폭은 질문의 형식에 따라 달라진다',
      '덤으로, 조건별 답변 토큰이 평평하다는 것은 길이 통제가 애초에 필요 없었음을 직접 보여준다',
    ]),
  ], { x: M, y: 3.6, w: 7.4, h: 2.6, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText([
    { text: 'down_bytes 분해', options: { bold: true, fontSize: 13, color: THEME.colors.accent3, breakLine: true, paraSpaceAfter: 6 } },
    { text: '≈ a + (35~40)·추론토큰\n        + (257~288)·답변토큰', options: { fontFace: 'Courier New', fontSize: 11, breakLine: true, paraSpaceAfter: 6 } },
    { text: 'R² 0.96~0.99', options: { fontSize: 11, color: THEME.colors.accent5, breakLine: true, paraSpaceAfter: 9 } },
    { text: '답변 1토큰이 전선에서 7배 무겁다. 평문 delta가 TLS 레코드 오버헤드를 매번 짊어지는 반면 추론은 암호 blob 덩어리로 나가기 때문이다.', options: { fontSize: 11.5 } },
  ], { x: 8.2, y: 3.6, w: 4.5, h: 2.6, color: C.text1, isTextBox: true, valign: 'top', fill: { color: THEME.colors.lt2 }, margin: 10 });

  s.addNotes([
    '[이 장이 하는 일]',
    '앞 장에서 "길이를 풀면 더 잘 잡힌다"를 보였다. 여기서는 "왜 그런가"를 답한다.',
    '',
    '[처음 세운 설명과 왜 틀렸나]',
    '처음엔 "답이 길어지니까 길이 자체가 단서가 된 것"이라고 생각했다. 그런데 표의 마지막 열을 보면',
    '답변 토큰 수는 설정을 바꿔도 거의 안 변한다(0.92~1.18배). 즉 답 길이는 단서가 아니다.',
    '진짜로 변한 것은 추론 토큰의 퍼짐이다 — sol 기준 3.4배에서 13.7배로 네 배 넓어졌다.',
    '',
    '[용어]',
    '· 추론토큰 중앙 low→max : 다섯 설정 각각의 추론 토큰 중앙값을 순서대로 나열한 것.',
    '· max/low 배수 : 가장 깊은 설정이 가장 얕은 설정의 몇 배인가. 이 값이 클수록 탐지가 쉽다.',
    '· delta : 응답이 조금씩 나뉘어 올 때의 각 조각.',
    '· TLS 레코드 오버헤드 : 암호화 규약이 조각마다 붙이는 고정 비용. 조각이 많을수록 손해다.',
    '',
    '[down_bytes 분해식이 말하는 것]',
    '내려온 바이트는 "추론 토큰 수 × 35~40" + "답변 토큰 수 × 257~288"로 거의 완벽히 설명된다.',
    '답변 1토큰이 추론 1토큰보다 7배 무겁다는 뜻이다. 답변은 조각조각 나눠 오느라 포장 비용을',
    '매번 내지만, 추론 서명은 큰 덩어리로 한 번에 나가기 때문이다.',
    '',
    '[방어 설계에 주는 함의]',
    '바이트를 줄이려면 답변 쪽을 패딩하는 게 효율적이다. 그런데 신호는 추론 쪽에 있다.',
    '즉 효율적인 패딩과 효과적인 패딩이 서로 다른 곳에 있다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 5 — 이번 주
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '05 이번 주' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '05 이번 주' });
  s.addText('05', { placeholder: 'num' });
  s.addText('11-22~24 — 정본 분류기로 다시 재고, 사고를 하나 냈다', { placeholder: 'title' });
  s.addText('아직 연구 노트에 반영하지 않은 최신 결과다.', { placeholder: 'subtitle' });
  s.addNotes('"정본"이란 임시로 급히 만든 것이 아니라 제대로 된 방법으로 다시 잰 공식 수치를 말한다.');
}

{
  const s = content('05 이번 주', '정본 재측정', '분류기를 바꾸자 순위가 흔들렸다',
    '이전 수치는 상관 0.97 이상인 피처에 조건부 독립을 가정한 임시 분류기였다. 참고치로만 썼어야 한다.');
  table(s, [
    head(['모델', 'RF 5클래스 (우연 20%)', '우연 대비', '이전 가우시안 3클래스 우연 대비']),
    [{ text: 'sonnet250', options: { bold: true } }, { text: '43.3%', options: { bold: true, color: THEME.colors.accent3 } }, '2.17배', '1.90배'],
    [{ text: 'sol250', options: { bold: true } }, { text: '40.3%', options: { bold: true, color: THEME.colors.accent3 } }, '2.02배', { text: '1.23배  (이전 5위)', options: { color: THEME.colors.accent4 } }],
    ['haiku250', '38.2%', '1.91배', '1.44배'],
    ['terra250', '34.4%', '1.72배', '1.31배'],
    ['opus250', '31.8%', '1.59배', '1.11배'],
    ['luna250', '26.2%', '1.31배', '1.08배'],
  ], { y: 1.6, colW: [2.5, 3.2, 2.1, 4.29], rowH: 0.36 });

  s.addText([
    ...bullets([
      { text: 'sol이 5위에서 2위로 올라갔다 → 노트의 "A1 순위가 추론토큰 격차 순위와 거의 같다"는 관찰을 다시 검증해야 한다', opt: { bold: true, color: THEME.colors.accent4 } },
      '다만 이 비교는 통제된 대조가 아니다. 클래스 수(5 vs 3) · 분할 방식 · 피처 집합이 전부 다르다',
      '공정하게 비교하려면 이전 가우시안을 동일 조건에서 다시 돌려야 한다 — 아직 안 했다',
    ]),
  ], { x: M, y: 4.28, w: W, h: 2.0, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[무엇을 바꿨나]',
    '이전 수치는 급히 만든 "대각 공분산 가우시안 분류기"로 잰 것이다. 이 방법은 피처들이',
    '서로 독립이라고 가정하는데, 실제로는 피처끼리 상관이 0.97 이상이라 가정이 크게 깨져 있었다.',
    '이번에는 RandomForest로 다시 쟀다. RandomForest는 피처 간 상관을 가정하지 않는다.',
    '',
    '[용어]',
    '· RandomForest : 결정 트리 수백 개를 만들어 투표시키는 분류기. 피처 사이 관계를 가정하지 않아',
    '  이런 상황에서 안전하다. 여기서는 300그루를 썼다.',
    '· 가우시안 분류기 : 각 조건의 피처 분포를 정규분포로 가정하고 확률을 계산하는 방법.',
    '  "대각 공분산"은 피처끼리 서로 무관하다고 보는 단순화다.',
    '· 조건부 독립 : "클래스를 알면 피처들은 서로 무관하다"는 가정. 깨지면 결과가 왜곡된다.',
    '· family 단위 GroupKFold : 같은 틀에서 나온 변형 문항들을 통째로 묶어서, 학습과 시험에',
    '  절대 같이 들어가지 않게 나누는 방법. 이걸 안 하면 분류기가 문항을 외워버려 점수가 부풀려진다.',
    '· 우연 대비 : 찍었을 때 나오는 점수의 몇 배인가. 5클래스면 우연이 20%이므로 40%는 2.0배다.',
    '',
    '[왜 이 표를 조심해서 읽어야 하나]',
    '왼쪽과 오른쪽은 클래스 개수부터 다르다(5개 vs 3개). 클래스가 많으면 우연 확률이 낮아지므로',
    '"우연 대비"로 환산해도 완전히 같은 조건이 아니다. 그래서 "순위가 바뀌었다"는 사실만 받아들이고,',
    '"RF가 더 좋다"는 결론은 아직 내리면 안 된다.',
    '',
    '[해야 할 일]',
    '이전 가우시안을 지금과 똑같은 조건(5클래스, 같은 분할, 같은 피처)에서 다시 돌려야',
    '둘을 공정하게 비교할 수 있다.',
  ].join('\n'));
}

{
  const s = content('05 이번 주', '길이 효과 재현', '72문항 결과가 250문항에서 그대로 재현됐다',
    '그리고 혼동행렬이 순서형이다 — "5중 택1"이 아니라 "연속량 추정"에 가깝다.');
  table(s, [
    head(['모델', 'arm 0 (한 글자)', 'free_brief (짧은 설명)', '차이']),
    ['luna', '26.2%', '29.0%', '+2.8%p'],
    [{ text: 'terra', options: { bold: true } }, '34.4%', { text: '50.9%', options: { bold: true, color: THEME.colors.accent3 } }, { text: '+16.5%p', options: { bold: true, color: THEME.colors.accent3 } }],
    [{ text: 'sol', options: { bold: true } }, '40.3%', { text: '54.2%', options: { bold: true, color: THEME.colors.accent3 } }, { text: '+13.9%p', options: { bold: true, color: THEME.colors.accent3 } }],
  ], { x: M, y: 1.6, w: 6.3, colW: [1.4, 1.8, 2.0, 1.1], rowH: 0.38 });

  s.addText([
    { text: 'terra 혼동행렬 (free_brief, 행=실제)', options: { bold: true, fontSize: 12, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 6 } },
    { text: 'low    186  47  11   3   3\nmedium  69  88  57  29   7\nhigh    20  58  79  71  22\nxhigh    2  22  64 105  57\nmax      1   4  21  46 178', options: { fontFace: 'Courier New', fontSize: 11.5 } },
  ], { x: 7.3, y: 1.6, w: 5.4, h: 2.1, color: C.text1, isTextBox: true, valign: 'top', fill: { color: THEME.colors.lt2 }, margin: 10 });

  s.addText([
    ...bullets([
      { text: '오분류가 무작위가 아니라 순서형이다 — 틀릴 때도 인접 등급으로만 틀린다 (low를 max로 본 것은 3건뿐)', opt: { bold: true, color: THEME.colors.accent1 } },
      'low 186/250 · max 178/250이 맞는다. 양 끝은 잘 잡고 가운데가 흐리다 — 02번 섹션의 해상도 한계와 같은 구조',
      '"5중 택1"보다 "연속량 추정"에 가깝다는 직접 증거 → Task B(실제 추론량 회귀) 쪽 근거가 된다',
      { text: 'luna만 1.45배로 여전히 우연 근처다. 길이를 풀어줘도 안 샌다 — 피처 중요도가 0.079~0.085로 평평하다', opt: { color: THEME.colors.accent4 } },
    ]),
  ], { x: M, y: 3.95, w: W, h: 2.3, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[혼동행렬(confusion matrix)이란]',
    '세로줄이 실제 정답, 가로줄이 분류기의 예측이다. 왼쪽 위에서 오른쪽 아래로 내려가는 대각선이',
    '"맞힌 것"이고, 대각선에서 멀어질수록 크게 틀린 것이다.',
    '',
    '[이 행렬에서 무엇을 봐야 하나]',
    '첫 줄(실제 low)을 보면 186 / 47 / 11 / 3 / 3 이다. 맞힌 게 186이고, 틀려도 대부분',
    '바로 옆인 medium(47)으로 틀린다. 제일 먼 max로 틀린 것은 3건뿐이다.',
    '즉 분류기가 "헷갈려서 아무거나 찍는" 게 아니라 "대충은 아는데 미세 조정을 못 하는" 상태다.',
    '',
    '[순서형(ordinal)이란]',
    '카테고리에 순서가 있는 것. low < medium < high < xhigh < max 처럼.',
    '순서가 없는 분류(고양이/개/새)와 달리, 순서형에서는 "한 칸 틀린 것"과 "네 칸 틀린 것"이',
    '전혀 다른 의미를 갖는다. 이 결과는 전자가 압도적이라는 뜻이다.',
    '',
    '[왜 Task B의 근거가 되나]',
    '오분류가 순서를 따라 퍼진다는 것은 모델이 본질적으로 "연속적인 양"을 보고 있다는 뜻이다.',
    '그렇다면 억지로 5개 칸에 밀어넣는 분류보다, 그 양 자체를 추정하는 회귀(Task B)가 더 맞는 틀이다.',
    '',
    '[luna가 왜 안 새나 — 아직 모른다]',
    '피처 중요도가 평평하다는 건 "어느 신호도 특별히 도움이 안 된다"는 뜻이다.',
    'luna는 앞 섹션에서 봤듯 단계 간 추론량 차이가 작다(max/low 3.1배). 그래서 벌어질 신호 자체가 적다.',
  ].join('\n'));
}

{
  const s = content('05 이번 주', '사고와 대응', '$7.47을 날렸다 — 그리고 그것이 다음 실험의 근거가 됐다',
    '관측지점에 동시 플로가 있으면 타이밍 피처가 무너진다는 것을 $7.47짜리로 증명한 셈이다.');
  s.addText([
    { text: '무슨 일이 있었나', options: { bold: true, fontSize: 15, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      '11-22 07:16, 런처를 A안·B안으로 18초 간격으로 두 번 띄웠다',
      "B의 종료 패턴 'run_openai_next\\.sh' 가 'run_openai_next_b.sh' 를 못 잡아서 A의 러너가 살아남았다",
      { text: 'OpenAI는 Cloudflare 뒤라 모델이 달라도 IP가 같다 → 두 tcpdump 필터가 글자 그대로 동일했다', opt: { bold: true } },
      '두 캡처가 1시간 반 동안 서로의 패킷을 같이 잡았다. pcap 2개의 타이밍 피처 전손',
    ]),
  ], { x: M, y: 1.58, w: 6.3, h: 3.0, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText([
    { text: '두 겹으로 막았다', options: { bold: true, fontSize: 15, color: THEME.colors.accent3, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      '런처에 flock — 두 번째 런처는 락을 못 잡고 즉시 종료한다',
      '캡처를 띄우기 직전 pgrep 검사 — 다른 캡처가 있으면 다음 단계로 넘어가지 않고 전체를 멈춘다',
      '이 가드 아래 마지막 캡처는 $11.537로 계획대로 완주했다',
    ]),
  ], { x: 7.2, y: 1.58, w: 5.5, h: 3.0, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText([
    { text: '그런데 이 사고에는 연구적 의미가 있다', options: { bold: true, fontSize: 14, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 7 } },
    { text: '실험실에서는 한 번에 한 콜만 돌기 때문에 패킷을 콜에 대응시키는 일이 공짜다. 그런데 실제 관측자(기관 네트워크 관리자)는 수천 개 플로가 섞인 지점에 앉아 있고, 플로를 먼저 갈라야 한다. 이 사고는 바로 그 상황에서 타이밍 피처가 어떻게 되는지를 우연히 실증한 것이다. 바이트 피처는 망과 무관해서 안전하지만, 타이밍은 아니다.', options: {} },
  ], { x: M, y: 4.75, w: W, h: 1.6, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top', fill: { color: THEME.colors.lt2 }, margin: 10 });

  s.addNotes([
    '[용어]',
    '· 런처 : 여러 캡처를 순서대로 돌려주는 실행 스크립트.',
    '· tcpdump : 네트워크 패킷을 잡아 파일로 저장하는 도구.',
    '· BPF 필터 : "이 IP와 이 포트의 패킷만 잡아라"라는 조건식. 두 캡처의 조건이 똑같으면',
    '  둘 다 서로의 패킷을 잡게 된다.',
    '· Cloudflare : 전 세계에 분산된 중계 서비스. OpenAI가 이걸 쓰기 때문에 모델이 달라도',
    '  접속하는 IP 주소가 같다. 그래서 IP로는 모델을 구분할 수 없다.',
    '· flock : 파일에 자물쇠를 걸어 같은 프로그램이 두 번 뜨지 못하게 하는 리눅스 기능.',
    '· pgrep : 특정 이름의 프로그램이 지금 돌고 있는지 확인하는 명령.',
    '· 플로(flow) : 하나의 연결. 출발지·목적지·포트로 식별되는 통신 한 줄기.',
    '',
    '[왜 이 슬라이드를 넣었나]',
    '실패를 기록으로 남기는 것이 연구 기록의 기본이다. 그리고 이 실패는 단순한 운영 실수가 아니라',
    '연구 질문 하나를 건드린다 — "관측지점에 다른 트래픽이 섞이면 어떻게 되는가".',
    '',
    '[다음 실험으로 이어지는 논리]',
    '지금까지 모든 측정은 조용한 선에서 이뤄졌다. 이것은 부채널 연구의 표준 관행이고,',
    '"공격자에게 최선인 조건에서 잰 누출의 상한"이라는 정당한 프레이밍이 있다.',
    '하지만 이 연구가 선언한 관측자는 기관 네트워크 관리자이고, 그 사람은 붐비는 지점에 앉아 있다.',
    '그래서 "동시 플로" 조건을 arm 하나로 추가할 필요가 있다. 4모델 50문항으로 약 $3이면 된다.',
    '바이트 피처는 어차피 망과 무관하므로, 이 실험이 실제로 시험하는 것은 타이밍 절반뿐이다.',
  ].join('\n'));
}

{
  const s = content('05 이번 주', '오늘 발견', 'sonnet은 설정이 둘인데 실제 행동이 같다',
    'Configured(설정)와 Realized(실제)를 분리해야 하는 이유의 가장 깨끗한 사례다.');
  table(s, [
    head(['모델', 'low', 'medium', 'high', 'xhigh', 'max', '사다리 모양']),
    [{ text: 'claude-sonnet-5-5', options: { bold: true } },
      { text: '0', options: { bold: true, color: THEME.colors.accent4 } },
      { text: '0', options: { bold: true, color: THEME.colors.accent4 } }, '212', '266', '866',
      { text: '아래 두 칸이 붙어 있다', options: { color: THEME.colors.accent4 } }],
    ['claude-opus-5-5', '121', '149', '170', '246', '975', 'medium~high가 거의 같다'],
    [{ text: 'claude-haiku-5-5', options: { bold: true } }, '88', '204', '283', '373', '1058',
      { text: '가장 깨끗한 사다리', options: { bold: true, color: THEME.colors.accent3 } }],
  ], { y: 1.6, colW: [3.0, 1.1, 1.3, 1.1, 1.1, 1.1, 3.39], rowH: 0.42 });

  s.addText([
    ...bullets([
      { text: 'sonnet은 Task A 1위(43.3%)인데, low/medium 구분은 추론량이 아닌 다른 것에서 나온 것이다 — 실제 추론량이 둘 다 0이기 때문', opt: { bold: true } },
      '설정값(Configured)을 정답으로 삼는 Task A는 이런 구간에서 원리적으로 맞힐 수 없다',
      { text: 'haiku는 88 → 1058로 사다리가 가장 깨끗하다. 길이 arm 실험을 Anthropic에서 재현할 때 첫 후보가 될 수 있다', opt: { color: THEME.colors.accent1 } },
    ]),
  ], { x: M, y: 3.5, w: W, h: 2.3, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText('Anthropic 실측 비용 — sonnet $8.17 / 1,250콜 · opus $16.72 환산. haiku는 요금을 확인하지 못했다.',
    { x: M, y: 5.95, w: W, h: 0.45, fontSize: 11.5, italic: true, color: THEME.colors.accent5, isTextBox: true });

  s.addNotes([
    '[Configured와 Realized]',
    '· Configured(설정) : 내가 요청할 때 적어 보낸 값. "low로 해줘" 같은 것.',
    '· Realized(실현) : 모델이 실제로 한 행동. 추론 토큰을 몇 개 썼는가.',
    '이 둘이 일치할 거라고 생각하기 쉽지만, 표에서 보듯 sonnet은 low와 medium에서 둘 다 0을 쓴다.',
    '',
    '[왜 이것이 연구 전략의 핵심인가]',
    '만약 Task A(설정 맞히기)만 한다면, sonnet의 low/medium은 아무리 좋은 분류기를 써도',
    '맞힐 수 없다. 전선에 나타날 차이가 애초에 없기 때문이다. 즉 성능 상한이 데이터가 아니라',
    '정답표 자체에 박혀 있다. 이것을 "라벨 붕괴"라고 부른다.',
    '',
    '그래서 연구의 주 타깃을 Realized(Task B)로 옮겼다. Realized는 전선 신호와 직접 연결돼 있어서',
    '라벨 붕괴가 없다. Configured는 "이 설정이 실제로 지켜지는가"를 검증하는 보조 축으로 쓴다.',
    '',
    '[실용적 함의]',
    '사용자 입장에서는 이것도 문제다. "low로 설정했는데 실제로 얼마나 생각했는지"를 확인할 길이',
    '게이트웨이에서는 없고, 반대로 "medium으로 올렸는데 모델이 무시하고 0을 쓸" 수도 있다.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 섹션 6 — 지금과 다음
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '06 다음' });
{
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: '06 다음' });
  s.addText('06', { placeholder: 'num' });
  s.addText('남은 것 — 무엇이 안 됐고 무엇이 다음인가', { placeholder: 'title' });
  s.addText('발표 자료의 "다음 할 일" 4개 중 3개가 닫혔다. 그리고 새 항목이 생겼다.', { placeholder: 'subtitle' });
  s.addNotes('연구 보고에서 가장 신뢰를 얻는 부분은 "안 한 것"을 정확히 말하는 대목이다.');
}

{
  const s = content('06 다음', '약속 대조', '발표 자료가 적어둔 "다음 할 일" 4개의 결산',
    '3개가 닫혔다. 닫는 과정에서 전제 하나가 뒤집혔고, 새 항목이 둘 생겼다.');
  table(s, [
    head(['11-12 발표의 약속', 'Task', '결과']),
    ['같은 게이트웨이로 다른 provider 캡처', 'C', { text: '완료 — 단, 게이트웨이가 아니라 직결로. 게이트웨이는 범위에서 뺐다(01 섹션). 망 조건 통제를 잃은 대신 모델 교차 캡처로 메웠다', options: { color: THEME.colors.accent3 } }],
    ['medium ↔ high 혼동 구조 규명', 'A · B', { text: '완료 — 모델마다 뭉개는 구간이 다르다. sonnet은 아래쪽(low≡medium), opus는 가운데(medium≡high)', options: { color: THEME.colors.accent3 } }],
    ['Realized 라벨을 직결에서 받아 결합', 'B', { text: '완료 — Task B 회귀 R² 0.878~0.977. 오히려 Task A보다 잘 된다', options: { color: THEME.colors.accent3 } }],
    ['정답 없는 갈래 불응률 150문항 전수', 'A', { text: '미완 — 250문항 본 캡처에서 provider별 불응률은 얻었으나(OpenAI 0%, Claude 7~28%) 갈래별 전수는 안 했다', options: { color: THEME.colors.accent4 } }],
  ], { y: 1.6, colW: [4.0, 0.9, 7.19], rowH: 0.62 });

  s.addText([
    { text: '그 과정에서 새로 생긴 항목', options: { bold: true, fontSize: 14, color: THEME.colors.accent1, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      '길이 arm — 길이 통제가 핸디캡이었다는 발견. OpenAI 3모델에서만 확인됐고 Anthropic 재현이 필요하다',
      '동시 플로 arm — 타이밍 피처가 붐비는 관측지점에서도 살아남는지. 11-22 사고가 필요성을 보여줬다',
    ]),
  ], { x: M, y: 4.8, w: W, h: 1.5, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addNotes([
    '[이 장의 의의]',
    '지난 발표에서 "다음에 하겠다"고 말한 것을 하나씩 대조한다. 연구 보고에서 가장 기본적인 예의이고,',
    '동시에 진행이 실제로 있었는지를 보이는 가장 확실한 방법이다.',
    '',
    '[바뀐 점 하나 — 게이트웨이 대신 직결]',
    '원래는 학교 게이트웨이로 여러 provider를 재려 했다. 같은 IP·같은 경로라 망 조건이 통제되기 때문이다.',
    '그런데 게이트웨이는 추론 토큰을 안 알려주므로 Task B의 정답을 만들 수 없다.',
    'Task B가 주 타깃이 되면서 직결로 방향을 바꿨다. 대신 망 조건 통제를 잃었고,',
    '그래서 "모델 교차 캡처"(같은 시간대에 네 모델을 번갈아 찍기)를 따로 해야 했다.',
    '',
    '[미완 항목에 대해]',
    '불응률은 provider 단위로는 얻었다. 하지만 "어떤 종류의 문항에서 불응이 나오는가"를',
    '갈래별로 전수 조사하지는 못했다. 현재 아는 것은 Claude가 윤리적 딜레마 문항에서',
    '한 글자 규칙을 어긴다는 정도다.',
  ].join('\n'));
}

{
  const s = content('06 다음', '남은 작업', '아직 안 한 것 — 대부분 돈이 안 드는 분석이다',
    '새 측정보다 이미 가진 데이터의 분석이 더 많이 밀려 있다.');
  table(s, [
    head(['항목', '비용', '왜 필요한가']),
    [{ text: 'Task B를 새 데이터로 재측정', options: { bold: true } }, { text: '무료', options: { bold: true, color: THEME.colors.accent3 } },
      { text: '11-20 R² 표는 전부 "답만" 조건 기준이다. 길이를 푼 조건에서 어떻게 되는지 미측정 — 주 타깃인데 이번 주 한 번도 안 돌렸다', options: { bold: true } }],
    ['조기 탐지(RQ6) 곡선', { text: '무료', options: { color: THEME.colors.accent3 } }, '결과 파일은 이미 디스크에 있는데 안 읽었다. 발표 자료의 0.972 / 533ms를 5단계·7모델로 갱신할 자리'],
    ['가우시안 vs RF 통제 대조', { text: '무료', options: { color: THEME.colors.accent3 } }, '지금 비교는 클래스 수·분할·피처가 다 달라 공정하지 않다'],
    ['모델 교차 캡처 분석', { text: '무료', options: { color: THEME.colors.accent3 } }, '데이터는 찍혔는데 평가를 안 했다. Task C의 시각 교란 통제가 여기 달렸다'],
    ['길이 arm의 Anthropic 재현', '약 $11', '길이 효과가 OpenAI 3모델뿐이다. provider 하나에서만 보이면 주장이 안 선다'],
    ['동시 플로 arm', '약 $3', '타이밍 피처의 외부 타당도. 위협모델이 선언한 관측 환경이 붐비는 지점이다'],
    ['연구 노트 갱신', { text: '무료', options: { color: THEME.colors.accent3 } }, '11-22~24 내용이 하나도 안 들어갔다. 특히 RF 정본표와 sonnet Realized=0'],
  ], { y: 1.6, colW: [3.3, 1.1, 7.69], rowH: 0.47 });

  s.addNotes([
    '[우선순위를 읽는 법]',
    '무료 항목이 여섯이고 유료가 둘이다. 즉 지금 막힌 것은 돈이 아니라 분석 시간이다.',
    '특히 첫 줄 — Task B는 이 연구의 주 타깃이라고 선언해 놓고 이번 주에 한 번도 안 돌렸다.',
    '',
    '[외부 타당도(external validity)란]',
    '실험실에서 얻은 결과가 실제 환경에서도 성립하는가를 말한다.',
    '아무리 실험실 숫자가 좋아도 현장에서 안 되면 쓸모가 없다.',
    '동시 플로 arm이 바로 이 항목을 시험하는 실험이다.',
    '',
    '[유료 항목의 예산 상황]',
    'OpenAI 크레딧 $100가 새로 들어왔고 Anthropic은 $12.45 남았다.',
    '위 두 유료 항목을 합쳐도 $14이므로 예산은 충분하다. 다만 유료 API는 기회가 한 번뿐이라',
    '상한을 걸고 소량으로 미리 확인한 뒤에 본 측정에 들어가는 절차를 지켜야 한다.',
  ].join('\n'));
}

{
  const s = content('06 다음', '오늘 논의', '"깨끗한 망에서만 재면 되는 것 아닌가"에 대한 답',
    '바이트는 망과 무관하다. 그런데 방어 논증의 절반이 타이밍 위에 서 있다.');
  s.addText([
    { text: '맞는 부분', options: { bold: true, fontSize: 14, color: THEME.colors.accent3, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      '바이트 채널은 구조적으로 망 독립이다. 지터가 끼든 RTT가 늘든 보내는 바이트 수는 안 바뀐다',
      '"공격자에게 최선인 조건에서 재서 누출의 상한을 구한다"는 것은 부채널 연구의 표준 관행이다. 변명이 아니라 정당한 프레이밍이다',
    ]),
  ], { x: M, y: 1.58, w: 6.1, h: 2.3, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  s.addText([
    { text: '빠진 부분', options: { bold: true, fontSize: 14, color: THEME.colors.accent4, breakLine: true, paraSpaceAfter: 7 } },
    ...bullets([
      '"패딩만으론 못 막는다"의 근거가 app_ttft다. 타이밍이다. "조용한 선이라 남은 것 아니냐"에 답이 없다',
      '발표 자료가 관측자를 "기관 네트워크 관리자"로 못 박았다. 그 사람은 조용한 선에 앉아 있지 않다',
      '11-22 사고가 동시 플로에서 타이밍이 무너지는 것을 이미 보여줬다',
    ]),
  ], { x: 7.0, y: 1.58, w: 5.7, h: 2.6, fontSize: 12.5, color: C.text1, isTextBox: true, valign: 'top' });

  table(s, [
    head(['', '할 가치', '이유']),
    [{ text: '관측지점 동시 플로', options: { bold: true } }, { text: '한다', options: { bold: true, color: THEME.colors.accent3 } },
      '위협모델이 요구한다. 11-22 사고가 실재를 증명했다. 4모델 50문항 약 $3'],
    ['RTT · 손실률 · ISP 행렬', { text: '안 한다', options: { bold: true, color: THEME.colors.accent4 } },
      '끝이 없고, 바이트 채널은 어차피 면역이다'],
  ], { y: 4.4, colW: [3.0, 1.4, 7.69], rowH: 0.48 });

  s.addText('결론: 깨끗한 측정을 주 결과로 두되 "상한"이라고 명시하고, 동시 플로 arm 하나만 붙인다.',
    { x: M, y: 5.85, w: W, h: 0.45, fontSize: 13, bold: true, color: THEME.colors.accent1, isTextBox: true });

  s.addNotes([
    '[이 논의가 왜 나왔나]',
    '"네트워크 부하나 지연은 어차피 더러운 현실의 잡음인데, 순수한 LLM 트래픽 신호만 보면 되는 것 아닌가"',
    '라는 질문에서 출발했다. 절반은 맞는 지적이다.',
    '',
    '[용어]',
    '· 지터(jitter) : 패킷 도착 간격이 들쭉날쭉한 정도. 망이 붐빌수록 커진다.',
    '· RTT : 왕복 지연 시간. 패킷이 갔다 오는 데 걸리는 시간.',
    '· 외부 타당도 : 실험 결과가 실제 환경에서도 성립하는가.',
    '· 상한(upper bound) : 가능한 최대치. 보안에서는 "공격자가 최선의 조건에서 얻을 수 있는 정보량"을',
    '  재는 것이 의미가 있다. 방어는 최선의 공격자를 막아야 하기 때문이다.',
    '',
    '[핵심 구분]',
    '바이트 피처(down_bytes, sig_chars)는 "몇 바이트를 보냈나"이므로 망 상태와 무관하다.',
    '타이밍 피처(app_ttft, stall_total, iat 계열)는 "언제 도착했나"이므로 망 상태에 직접 영향받는다.',
    '그래서 이 연구의 결과는 두 종류로 나뉘고, 망 조건 실험이 필요한 것은 후자뿐이다.',
    '',
    '[선을 어디 긋나]',
    '망 조건 실험은 끝없이 늘릴 수 있다(손실률 1%, 3%, 5%... RTT 20ms, 50ms, 100ms...).',
    '그 길로 가면 연구가 아니라 측정 노동이 된다. 그래서 "위협모델이 직접 요구하는 조건 하나"만',
    '추가한다 — 관측지점에 다른 트래픽이 동시에 흐르는 상황.',
  ].join('\n'));
}

// ═══════════════════════════════════════════════════════════════════════
// 마무리
// ═══════════════════════════════════════════════════════════════════════
pres.addSection({ title: '마무리' });
{
  const s = pres.addSlide({ masterName: 'CLOSING', sectionTitle: '마무리' });
  s.addText('12일 요약 — 세 문장', { placeholder: 'title' });
  s.addText([
    { text: '1.  누출은 세 제조사 전부에서 확인됐고, 기전까지 닫혔다.', options: { bold: true, fontSize: 19, color: 'FFFFFF', breakLine: true, paraSpaceAfter: 6 } },
    { text: '     모델이 생각한 내용을 암호화해 실어 보내는 "사고 서명"이 길이 그대로 전선에 나타난다.', options: { fontSize: 14, color: THEME.colors.lt2, breakLine: true, paraSpaceAfter: 18 } },
    { text: '2.  주 타깃이 Task A(설정)에서 Task B(실제 추론량)로 옮겨갔다.', options: { bold: true, fontSize: 19, color: 'FFFFFF', breakLine: true, paraSpaceAfter: 6 } },
    { text: '     설정 라벨이 실제 행동과 일대일로 대응하지 않기 때문이다. sonnet의 low와 medium은 둘 다 추론 0이다.', options: { fontSize: 14, color: THEME.colors.lt2, breakLine: true, paraSpaceAfter: 18 } },
    { text: '3.  답 길이를 한 글자로 묶은 것은 통제가 아니라 핸디캡이었다.', options: { bold: true, fontSize: 19, color: 'FFFFFF', breakLine: true, paraSpaceAfter: 6 } },
    { text: '     풀어주면 탐지가 +14~17%p 올라간다. 지금까지 보고한 수치는 전부 하한이다.', options: { fontSize: 14, color: THEME.colors.lt2, breakLine: true, paraSpaceAfter: 22 } },
    { text: '다음 — 이미 가진 데이터의 분석(무료) 여섯 가지가 밀려 있다. 새 측정은 그다음이다.', options: { fontSize: 15, bold: true, color: THEME.colors.accent3 } },
  ], { placeholder: 'body' });
  s.addNotes([
    '[마무리에서 말할 것]',
    '이 세 문장이 12일의 전부다. 하나는 전진(기전 규명), 둘은 정정(타깃 변경, 전제 역전)이다.',
    '정정이 둘이라는 것을 부끄러워할 필요가 없다. 데이터가 쌓이면서 더 정확해진 것이고,',
    '무엇보다 두 정정 모두 "결과가 더 강해지는" 방향이다 —',
    'Task B는 Task A보다 잘 되고, 길이를 풀면 탐지가 더 잘 된다.',
    '',
    '[마지막 줄의 의미]',
    '지금 연구가 막힌 지점은 돈이나 데이터가 아니라 분석이다.',
    '이미 찍어놓은 데이터로 할 수 있는 무료 분석이 여섯 가지 밀려 있고,',
    '그중 첫 번째가 이 연구가 주 타깃이라고 선언한 Task B다.',
  ].join('\n'));
}

// ── 출력 ────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, THEME))
  .then(() => console.log('완료: ' + OUT))
  .catch(e => { console.error('실패:', e && e.message ? e.message : e); process.exitCode = 1; });
