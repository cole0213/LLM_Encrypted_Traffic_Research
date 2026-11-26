// deck_nmlab.js — NMLAB 양식 발표자료를 만든다.
//
// 무엇을 하는가
//   2026-11-12 2차 진행 보고 이후의 연구 흐름을, 연구실 공식 PPT 양식(NMLAB)에 맞춰
//   7개 장으로 재구성해 출력한다. 11-24 판(deck.js)과 비교해 바뀐 점:
//     (1) 양식 — 색·글꼴·로고·레이아웃을 NMLAB 양식에서 실측해 재현했다.
//     (2) 구성 — 시간순 흐름에서 주제별 7장 구성으로 바꿨다.
//     (3) 2장(연구 목표)을 크게 늘렸다. 핵심 명제 · 가시성 축 · RQ 여섯 ·
//         Task A/B/C · 동기 네 개 · 범위 결정 · 기여 후보로 7장.
//     (4) 수정대기.md 항목 1~10 을 전부 반영했다. 폐기된 항목 6 은 넣지 않고,
//         그 자리에 항목 10(누출 감사)을 5장으로 세웠다.
//     (5) 2026-11-26 에 끝난 "에코 정확 교정" 판정을 5장에 추가했다.
//
// 입력 : assets/ 의 로고 PNG 세 개 (NMLAB 양식에서 추출)
// 출력 : C:\Users\GyuSang\OneDrive - 고려대학교\02_PPT\심규상_261126_암호화트래픽_연구정리_NMLAB.pptx
//
// 돌리는 법
//   NODE_PATH="<pptxgenjs 가 있는 node_modules>" node deck_nmlab.js
//   NODE_PATH 를 안 주면 테마 주입 단계에서 "pptxgenjs ... cannot be found" 로 실패하고,
//   pptx 는 이미 써진 뒤라 색이 Office 기본 팔레트인 파일이 남는다. 반드시 다시 돌릴 것.
//
// 작성일: 2026-11-26

const B = require('./nmlab_base');
const { applyTheme } = require('C:/Users/GyuSang/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/2de1d7bf-7449-4dfa-9ffd-00c6248b1a4e/a5d2ee58-683e-43ae-9b35-62f5c3acdc59/skills/pptx/scripts/apply_theme.js');

const OUT = 'C:/Users/GyuSang/OneDrive - 고려대학교/02_PPT/심규상_261126_암호화트래픽_연구정리_NMLAB.pptx';

const pres = B.makePres();

// ── 표지 ────────────────────────────────────────────────────────────────
pres.addSection({ title: '표지' });
{
  const s = pres.addSlide({ masterName: 'COVER', sectionTitle: '표지' });
  s.addText('암호화 LLM 트래픽 기반\nReasoning Effort 탐지', { placeholder: 'title' });
  s.addText('3차 진행 보고 — 2026. 11. 26.', { placeholder: 'subtitle' });
  s.addText([
    { text: '고려대학교 세종캠퍼스', options: { fontSize: 15, bold: true, breakLine: true, paraSpaceAfter: 2 } },
    { text: '네트워크 관리 연구실', options: { fontSize: 15, bold: true, breakLine: true, paraSpaceAfter: 10 } },
    { text: '심규상 학부 연구생', options: { fontSize: 14, breakLine: true, paraSpaceAfter: 2 } },
    { text: 'cole0213@korea.ac.kr', options: { fontSize: 13, color: B.INK_SOFT } },
  ], { placeholder: 'who' });
  s.addNotes([
    '[이 발표의 범위]',
    '2026-11-12 2차 진행 보고 이후 11-26 까지. 본 캡처 9,812콜, 7모델, 공통 250문항.',
    '',
    '[11-24 판과 달라진 점]',
    '· 연구실 공식 양식으로 바꿨다.',
    '· 시간순 흐름에서 주제별 7장 구성으로 재편했다.',
    '· 2장(연구 목표)을 7장으로 늘렸다 — 지금까지 가장 약했던 부분이다.',
    '· 11-24 에 "발견" 으로 적었던 조기 탐지 결과를 폐기하고, 그 자리를',
    '  "어떻게 잡았는가"(5장)로 바꿨다.',
  ].join('\n'));
}

// ── 본문 ────────────────────────────────────────────────────────────────
// 섹션은 각 모듈이 addSlide 에 넘기는 sectionTitle 과 이름이 같아야 한다.
// 섹션을 미리 선언하지 않으면 "Default-N" 이라는 빈 섹션이 생긴다.
['목차', '1 배경', '2 연구 목표', '3 측정', '4 결과',
 '5 자기 정정', '6 한계·계획', '7 의의', '마무리'].forEach((t) => pres.addSection({ title: t }));

require('./sec_1_2.js').build(pres);
require('./sec_3_4.js').build(pres);
require('./sec_5_7.js').build(pres);

// ── 출력 ────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, B.THEME))
  .then(() => console.log('완료: ' + OUT))
  .catch((e) => {
    console.error('실패:', e && e.message ? e.message : e);
    process.exitCode = 1;
  });
