// nmlab_base.js — NMLAB 발표 양식(테마·레이아웃·보조 함수)을 한곳에 모은다.
//
// 무엇을 하는가
//   고려대 세종 네트워크관리연구실(NMLAB)의 공식 PPT 양식에서 뽑아낸 색·글꼴·
//   로고 배치를 pptxgenjs 레이아웃으로 재현한다. 내용 모듈(sec_*.js)은 여기서
//   내보내는 makePres() 와 보조 함수만 쓰고 좌표를 직접 만지지 않는다.
//
// 양식의 출처(실측)
//   C:\Users\GyuSang\OneDrive - 고려대학교\02_PPT\NMLAB PPT 양식.pptx 를 풀어
//   theme/slideLayout XML 에서 직접 읽었다.
//     - 슬라이드 크기 12192000 x 6858000 EMU = 13.333" x 7.5" (LAYOUT_WIDE)
//     - 색 : dk1 4D4D4D · lt1 FFFFFF · dk2 999999 · lt2 000000
//             accent1 F04E22(주황빨강) · accent2 F0B500(금색) · accent4 404040
//     - 글꼴 : latin Arial · 한글 HY견고딕 / 맑은 고딕
//     - 본문 레이아웃(layout6) : 제목 (1.01, 0.40) 11.57x0.56 24pt
//                                본문 (0.92, 1.18) 11.57x5.75 20/16pt
//                                좌하단 NMLab 로고 (0.92, 7.11) 1.63x0.27
//                                우하단 고려대 로고 (11.48, 7.05) 1.01x0.39
//
// 입력 : assets/ 의 로고 PNG 세 개
// 출력 : 없음(모듈)
//
// 주의
//   - 색 hex 에 '#' 을 붙이면 pptx 가 깨진다.
//   - 옵션 객체는 addText 호출마다 새로 만든다. pptxgenjs 가 제자리에서 EMU 로
//     바꿔치기 때문에 공유하면 두 번째 호출이 망가진다.
//   - 테마 색은 writeFile 이후 apply_theme.js 로 주입해야 실제로 반영된다.
//
// 작성일: 2026-11-26

const path = require('path');
const pptxgen = require('pptxgenjs');

const ASSETS = path.join(__dirname, 'assets');

// NMLAB 양식의 색을 그대로 옮긴다. accent3 은 양식에서 흰색이라 데이터 색으로
// 못 쓴다. 그래서 표·강조에는 accent1(주황빨강)·accent2(금색)·accent4(진회색)만 쓴다.
const THEME = {
  name: 'NMLAB',
  headFontFace: '맑은 고딕',
  bodyFontFace: '맑은 고딕',
  colors: {
    dk1: '4D4D4D', lt1: 'FFFFFF',
    dk2: '404040', lt2: 'F2F2F2',
    accent1: 'F04E22', accent2: 'F0B500', accent3: '7F7F7F',
    accent4: '404040', accent5: 'F6B2AB', accent6: 'D9A400',
    hlink: '0099FF', folHlink: '00A6AD',
  },
};

// 본문에서 자주 쓰는 색. 스킴 색은 표 셀·도형 일부에서 안 먹으므로 hex 로 둔다.
const INK = '404040';         // 본문 글자
const INK_SOFT = '7F7F7F';    // 보조 글자
const HOT = 'F04E22';         // 강조(결론·수치)
const GOLD = 'F0B500';        // 보조 강조
const RULE = 'D9D9D9';        // 가는 선
const BAND = 'F7F7F7';        // 옅은 바탕

const M = 0.92;               // 좌우 여백 — 양식 본문 개체틀과 같은 값
const W = 11.57;              // 본문 폭 — 양식과 동일

function makePres() {
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_WIDE';     // 13.333 x 7.5. 슬라이드 추가 전에 반드시 먼저.
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.author = '심규상';
  pres.company = 'Korea University Sejong NMLAB';
  pres.subject = '암호화 LLM 트래픽 Reasoning Effort 탐지';
  pres.title = '암호화 LLM 트래픽 기반 Reasoning Effort 탐지';

  // ── 표지 ──────────────────────────────────────────────────────────────
  // 양식 slide1 을 따른다. 제목이 화면 폭을 가로지르고, 그 아래 소속·이름·메일.
  pres.defineSlideMaster({
    title: 'COVER',
    background: { color: 'FFFFFF' },
    objects: [
      { rect: { x: 0, y: 0, w: 13.333, h: 0.30, fill: { color: HOT } } },
      { rect: { x: 0, y: 6.55, w: 13.333, h: 0.08, fill: { color: GOLD } } },
      { image: { x: 0.85, y: 0.75, w: 2.40, h: 0.62, path: path.join(ASSETS, 'ku_logo_big.png') } },
      {
        placeholder: {
          options: {
            name: 'title', type: 'title', x: 0.85, y: 2.15, w: 11.6, h: 1.50,
            fontSize: 40, bold: true, color: INK, align: 'left', valign: 'bottom',
          },
          text: '',
        },
      },
      {
        placeholder: {
          options: {
            name: 'subtitle', type: 'body', x: 0.88, y: 3.70, w: 11.6, h: 0.60,
            fontSize: 17, color: HOT, align: 'left', valign: 'top',
          },
          text: '',
        },
      },
      {
        placeholder: {
          options: {
            name: 'who', type: 'body', x: 0.88, y: 4.70, w: 11.6, h: 1.60,
            fontSize: 14, color: INK, align: 'left', valign: 'top',
          },
          text: '',
        },
      },
      { image: { x: 0.92, y: 6.85, w: 1.63, h: 0.27, path: path.join(ASSETS, 'nmlab_logo.png') } },
    ],
  });

  // ── 섹션 간지 ─────────────────────────────────────────────────────────
  pres.defineSlideMaster({
    title: 'SECTION',
    background: { color: INK },
    objects: [
      { rect: { x: 0, y: 0, w: 13.333, h: 0.30, fill: { color: HOT } } },
      {
        placeholder: {
          options: {
            name: 'title', type: 'title', x: M, y: 2.70, w: W, h: 1.00,
            fontSize: 34, bold: true, color: 'FFFFFF', align: 'left', valign: 'bottom',
          },
          text: '',
        },
      },
      {
        placeholder: {
          options: {
            name: 'body', type: 'body', x: M, y: 3.85, w: W, h: 1.20,
            fontSize: 15, color: 'D9D9D9', align: 'left', valign: 'top',
          },
          text: '',
        },
      },
      { image: { x: 11.48, y: 6.95, w: 1.01, h: 0.39, path: path.join(ASSETS, 'ku_logo.png') } },
    ],
  });

  // ── 본문 ──────────────────────────────────────────────────────────────
  // 양식 layout6 의 좌표를 그대로 쓰되, 맨 아래 한 줄을 '이 장의 결론' 자리로 둔다.
  // 그 줄이 없으면 표만 있는 장에서 청중이 무엇을 보아야 하는지 모른다.
  pres.defineSlideMaster({
    title: 'CONTENT',
    background: { color: 'FFFFFF' },
    objects: [
      { rect: { x: 0, y: 0, w: 13.333, h: 0.12, fill: { color: HOT } } },
      {
        placeholder: {
          options: {
            name: 'kicker', type: 'body', x: M, y: 0.30, w: W, h: 0.26,
            fontSize: 11, bold: true, color: HOT, align: 'left', valign: 'middle',
          },
          text: '',
        },
      },
      {
        placeholder: {
          options: {
            name: 'title', type: 'title', x: M, y: 0.56, w: W, h: 0.62,
            fontSize: 24, bold: true, color: INK, align: 'left', valign: 'middle',
          },
          text: '',
        },
      },
      { line: { x: M, y: 1.24, w: W, h: 0, line: { color: RULE, width: 1 } } },
      {
        placeholder: {
          options: {
            name: 'body', type: 'body', x: M, y: 1.36, w: W, h: 5.05,
            fontSize: 15, color: INK, align: 'left', valign: 'top',
          },
          text: '',
        },
      },
      { rect: { x: M, y: 6.52, w: W, h: 0.50, fill: { color: BAND } } },
      { rect: { x: M, y: 6.52, w: 0.07, h: 0.50, fill: { color: HOT } } },
      {
        placeholder: {
          options: {
            name: 'takeaway', type: 'body', x: M + 0.18, y: 6.52, w: W - 0.30, h: 0.50,
            fontSize: 12.5, bold: true, color: INK, align: 'left', valign: 'middle',
          },
          text: '',
        },
      },
      { image: { x: 0.92, y: 7.14, w: 1.30, h: 0.22, path: path.join(ASSETS, 'nmlab_logo.png') } },
      { image: { x: 11.60, y: 7.05, w: 0.88, h: 0.34, path: path.join(ASSETS, 'ku_logo.png') } },
    ],
    slideNumber: { x: 10.75, y: 7.12, w: 0.6, h: 0.25, fontSize: 10, color: INK_SOFT, align: 'right' },
  });

  // ── 마무리 ────────────────────────────────────────────────────────────
  pres.defineSlideMaster({
    title: 'CLOSING',
    background: { color: INK },
    objects: [
      { rect: { x: 0, y: 0, w: 13.333, h: 0.30, fill: { color: HOT } } },
      {
        placeholder: {
          options: {
            name: 'title', type: 'title', x: M, y: 0.80, w: W, h: 0.80,
            fontSize: 28, bold: true, color: 'FFFFFF', align: 'left', valign: 'middle',
          },
          text: '',
        },
      },
      {
        placeholder: {
          options: {
            name: 'body', type: 'body', x: M, y: 1.90, w: W, h: 4.60,
            fontSize: 15, color: 'E6E6E6', align: 'left', valign: 'top',
          },
          text: '',
        },
      },
      { image: { x: 11.48, y: 6.95, w: 1.01, h: 0.39, path: path.join(ASSETS, 'ku_logo.png') } },
    ],
  });

  return pres;
}

// ── 보조 함수 ───────────────────────────────────────────────────────────

/** 본문 슬라이드 한 장. 제목줄·꼭지·결론줄을 한 번에 채운다. */
function content(pres, section, kicker, title, takeaway) {
  const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: section });
  s.addText(kicker, { placeholder: 'kicker' });
  s.addText(title, { placeholder: 'title' });
  s.addText(takeaway, { placeholder: 'takeaway' });
  return s;
}

/** 섹션 간지. */
function section(pres, name, title, sub) {
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: name });
  s.addText(title, { placeholder: 'title' });
  s.addText(sub, { placeholder: 'body' });
  return s;
}

/**
 * 불릿 묶음을 pptxgenjs 텍스트 배열로 바꾼다.
 * items 는 문자열이거나 { t, sub, bold, color } 객체.
 * 리터럴 '•' 를 쓰지 않는다 — bullet:true 와 겹쳐 두 개가 찍힌다.
 */
function bullets(items, opt = {}) {
  const size = opt.size || 15;
  const gap = opt.gap === undefined ? 9 : opt.gap;
  const out = [];
  items.forEach((it, i) => {
    const o = typeof it === 'string' ? { t: it } : it;
    const last = i === items.length - 1 && !o.sub;
    out.push({
      text: o.t,
      options: {
        bullet: o.bullet === false ? false : true,
        bold: !!o.bold,
        fontSize: o.size || size,
        color: o.color || INK,
        breakLine: !last,
        paraSpaceAfter: o.sub ? 2 : gap,
      },
    });
    if (o.sub) {
      out.push({
        text: o.sub,
        options: {
          bullet: false, indentLevel: 1, fontSize: (o.size || size) - 2.5,
          color: INK_SOFT, breakLine: i !== items.length - 1, paraSpaceAfter: gap,
        },
      });
    }
  });
  return out;
}

/**
 * 표 한 장.
 * rows[0] 은 머리줄로 본다. colW 는 인치 배열이고 합이 표 폭이 된다.
 * 셀 문자열 앞에 '*' 를 붙이면 그 셀만 강조색 굵게가 된다 — 수치 강조용.
 */
function table(slide, rows, colW, opt = {}) {
  const x = opt.x === undefined ? M : opt.x;
  const y = opt.y === undefined ? 1.55 : opt.y;
  const fs = opt.fontSize || 12;
  const body = rows.map((r, ri) => r.map((c) => {
    const txt = String(c);
    const hot = txt.startsWith('*');
    const show = hot ? txt.slice(1) : txt;
    if (ri === 0) {
      return {
        text: show,
        options: { bold: true, color: 'FFFFFF', fill: { color: INK }, fontSize: fs, align: 'center' },
      };
    }
    return {
      text: show,
      options: {
        bold: hot, color: hot ? HOT : INK, fontSize: fs,
        align: opt.leftFirst !== false && r.indexOf(c) === 0 ? 'left' : 'center',
        fill: { color: ri % 2 ? 'FFFFFF' : 'FAFAFA' },
      },
    };
  }));
  slide.addTable(body, {
    x, y, w: colW.reduce((a, b) => a + b, 0), colW,
    border: { type: 'solid', color: RULE, pt: 0.75 },
    rowH: opt.rowH || 0.26,
    valign: 'middle',
    margin: 0.04,
  });
}

/** 큰 숫자 한 덩이. 결과 장에서 핵심 수치를 눈에 박을 때 쓴다. */
function stat(slide, x, y, w, value, label, sub, color) {
  slide.addText(value, {
    x, y, w, h: 0.70, isTextBox: true, margin: 0,
    fontSize: 32, bold: true, color: color || HOT, align: 'center', valign: 'bottom',
  });
  slide.addText(label, {
    x, y: y + 0.70, w, h: 0.28, isTextBox: true, margin: 0,
    fontSize: 12.5, bold: true, color: INK, align: 'center', valign: 'top',
  });
  if (sub) {
    slide.addText(sub, {
      x, y: y + 0.98, w, h: 0.46, isTextBox: true, margin: 0,
      fontSize: 10.5, color: INK_SOFT, align: 'center', valign: 'top',
    });
  }
}

/** 발표자 메모. 배열을 줄바꿈으로 잇는다. */
function notes(slide, lines) {
  slide.addNotes(lines.join('\n'));
}

module.exports = {
  THEME, INK, INK_SOFT, HOT, GOLD, RULE, BAND, M, W,
  makePres, content, section, bullets, table, stat, notes,
};
