/*
 * build_ppt.js
 * 목적: GCP 기반 클라우드 환경 구성(계정/IAM/VPC/Bastion) 실습 제출용 PPT 생성
 * 입력: 없음 (내용 하드코딩) / 출력: 클라우드환경구성_GCP.pptx
 * 스샷 4개는 슬라이드의 빈 슬롯에 사용자가 직접 붙여넣음
 * 작성일: 2026-09-08
 */
const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE"; // 13.3 x 7.5 in
p.author = "심규상";

// 팔레트 (Ocean Gradient — 클라우드/네트워크 주제)
const NAVY = "21295C";   // 진한 남색 (제목/마감 배경)
const DEEP = "065A82";   // 딥블루 (주색)
const TEAL = "1C7293";   // 틸 (보조)
const ICE  = "CADCFC";   // 아이스블루
const LIGHT= "F4F7FA";   // 밝은 배경
const INK  = "1B2430";   // 본문 글자
const MUT  = "5B6675";   // 흐린 글자
const WHITE= "FFFFFF";
const SLOT = "E9EEF4";   // 스샷 슬롯 배경

const HEAD = "Bookman Old Style";
const BODY = "Calibri";

// 스샷 슬롯 헬퍼: 캡션 붙은 회색 박스 ("여기에 스샷 붙여넣기")
function slot(s, x, y, w, h, caption) {
  s.addShape("roundRect", { x, y, w, h, rectRadius: 0.06,
    fill: { color: SLOT }, line: { color: TEAL, width: 1, dashType: "dash" } });
  s.addText([
    { text: "🖼  ", options: { fontSize: 18 } },
    { text: caption, options: { fontSize: 13, bold: true, color: TEAL } },
    { text: "\n실제 콘솔 스크린샷을 이 자리에 붙여넣으세요", options: { fontSize: 10, color: MUT } },
  ], { x, y, w, h, align: "center", valign: "middle", isTextBox: true, fontFace: BODY });
}

// 상단 슬라이드 제목 (라이트 슬라이드용)
function title(s, num, txt) {
  s.addText(String(num).padStart(2, "0"), { x: 0.5, y: 0.42, w: 1.0, h: 0.7,
    fontFace: HEAD, fontSize: 40, bold: true, color: ICE, isTextBox: true, margin: 0, align: "left" });
  s.addText(txt, { x: 1.35, y: 0.5, w: 11.4, h: 0.7,
    fontFace: HEAD, fontSize: 30, bold: true, color: DEEP, isTextBox: true, margin: 0, valign: "middle" });
}

// ---------- Slide 1: 표지 ----------
{
  const s = p.addSlide();
  s.background = { color: NAVY };
  // 우측 장식 원 모티프
  s.addShape("oval", { x: 10.4, y: -1.6, w: 4.6, h: 4.6, fill: { color: DEEP } });
  s.addShape("oval", { x: 11.6, y: 4.5, w: 3.4, h: 3.4, fill: { color: TEAL } });
  s.addText("CLOUD INFRA PRACTICE", { x: 0.7, y: 1.5, w: 8, h: 0.4,
    fontFace: BODY, fontSize: 14, bold: true, color: ICE, charSpacing: 3, isTextBox: true, margin: 0 });
  s.addText("클라우드 환경 구성", { x: 0.7, y: 2.0, w: 11, h: 1.0,
    fontFace: HEAD, fontSize: 48, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addText("GCP 기반 VPC · IAM · Bastion Host 구축", { x: 0.7, y: 3.05, w: 11, h: 0.7,
    fontFace: HEAD, fontSize: 26, color: ICE, isTextBox: true, margin: 0 });
  s.addText("AWS Free Tier 대체 환경 — Kubernetes(EKS/GKE) 운영 전 네트워크 사전 구성",
    { x: 0.7, y: 3.8, w: 10.5, h: 0.5, fontFace: BODY, fontSize: 15, italic: true, color: "9FB6D6", isTextBox: true, margin: 0 });
  s.addShape("line", { x: 0.72, y: 4.7, w: 3.2, h: 0, line: { color: TEAL, width: 2 } });
  s.addText([
    { text: "심규상", options: { bold: true, color: WHITE } },
    { text: "   |   2026-09-08   |   Region: asia-northeast3 (Seoul)", options: { color: ICE } },
  ], { x: 0.7, y: 4.9, w: 11, h: 0.5, fontFace: BODY, fontSize: 14, isTextBox: true, margin: 0 });
  s.addNotes("AWS Free Tier 소진으로 GCP($300 무료 크레딧)로 동등한 네트워크 환경을 구성. 용어(VPC/IAM) 대응.");
}

// ---------- Slide 2: 개요 ----------
{
  const s = p.addSlide();
  s.background = { color: LIGHT };
  title(s, 1, "실습 개요");
  s.addText("쿠버네티스 클러스터를 올리기 전, 하나의 VPC 안에 이중화된 서브넷을 구성하고 Bastion Host로 접근 경로를 만든다. AWS Free Tier 소진으로 동일 개념을 GCP에서 구현했다.",
    { x: 0.5, y: 1.35, w: 12.3, h: 0.8, fontFace: BODY, fontSize: 15, color: INK, isTextBox: true });

  const items = [
    ["1", "계정 생성", "GCP 무료 체험판($300 크레딧) 계정 생성 및 콘솔 접근"],
    ["2", "IAM 설정", "작업용 서비스 계정(eks-admin) 생성 + 역할(편집자) 부여"],
    ["3", "VPC 구축", "eks-vpc 생성 · 이중화 서브넷(public / private) 구성"],
    ["4", "Bastion Host", "public 서브넷에 점프 서버(VM) 생성 · 외부 IP 부여"],
  ];
  let y = 2.35;
  items.forEach(([n, h, d]) => {
    s.addShape("oval", { x: 0.6, y: y, w: 0.7, h: 0.7, fill: { color: DEEP } });
    s.addText(n, { x: 0.6, y: y, w: 0.7, h: 0.7, align: "center", valign: "middle",
      fontFace: HEAD, fontSize: 22, bold: true, color: WHITE, isTextBox: true, margin: 0 });
    s.addText([
      { text: h + "\n", options: { bold: true, fontSize: 18, color: DEEP } },
      { text: d, options: { fontSize: 13, color: MUT } },
    ], { x: 1.5, y: y - 0.05, w: 11.2, h: 0.8, valign: "middle", isTextBox: true, fontFace: BODY, margin: 0 });
    y += 1.05;
  });
}

// ---------- Slide 3: 아키텍처 ----------
{
  const s = p.addSlide();
  s.background = { color: LIGHT };
  title(s, 2, "네트워크 아키텍처");

  // VPC 컨테이너
  s.addShape("roundRect", { x: 0.5, y: 1.5, w: 12.3, h: 5.2, rectRadius: 0.08,
    fill: { color: WHITE }, line: { color: DEEP, width: 2 } });
  s.addText("VPC  eks-vpc   (asia-northeast3)", { x: 0.7, y: 1.62, w: 6, h: 0.4,
    fontFace: BODY, fontSize: 13, bold: true, color: DEEP, isTextBox: true, margin: 0 });

  // 인터넷 / IGW (상단)
  s.addShape("roundRect", { x: 5.4, y: 0.95, w: 2.5, h: 0.45, rectRadius: 0.05, fill: { color: NAVY } });
  s.addText("인터넷 / 외부 IP", { x: 5.4, y: 0.95, w: 2.5, h: 0.45, align: "center", valign: "middle",
    fontFace: BODY, fontSize: 12, bold: true, color: WHITE, isTextBox: true, margin: 0 });
  s.addShape("line", { x: 6.65, y: 1.4, w: 0, h: 0.6, line: { color: NAVY, width: 2, endArrowType: "triangle" } });

  // public subnet
  s.addShape("roundRect", { x: 0.9, y: 2.15, w: 11.5, h: 1.85, rectRadius: 0.06,
    fill: { color: "E8F4EA" }, line: { color: "3E8E5A", width: 1.5 } });
  s.addText("Public Subnet   public-a   10.0.1.0/24", { x: 1.05, y: 2.24, w: 8, h: 0.35,
    fontFace: BODY, fontSize: 12, bold: true, color: "2C6E49", isTextBox: true, margin: 0 });
  s.addShape("roundRect", { x: 1.15, y: 2.7, w: 3.0, h: 1.05, rectRadius: 0.05, fill: { color: "EC7211" } });
  s.addText([{ text: "Bastion Host\n", options: { bold: true, fontSize: 14 } },
             { text: "VM · 외부 IP · SSH", options: { fontSize: 10 } }],
    { x: 1.15, y: 2.7, w: 3.0, h: 1.05, align: "center", valign: "middle", color: WHITE, isTextBox: true, fontFace: BODY, margin: 0 });

  // private subnet
  s.addShape("roundRect", { x: 0.9, y: 4.2, w: 11.5, h: 2.15, rectRadius: 0.06,
    fill: { color: "E7EEF7" }, line: { color: TEAL, width: 1.5 } });
  s.addText("Private Subnet   private-a   10.0.11.0/24", { x: 1.05, y: 4.29, w: 8, h: 0.35,
    fontFace: BODY, fontSize: 12, bold: true, color: DEEP, isTextBox: true, margin: 0 });
  s.addShape("roundRect", { x: 1.15, y: 4.75, w: 3.4, h: 1.35, rectRadius: 0.05,
    fill: { color: WHITE }, line: { color: DEEP, width: 1.2 } });
  s.addText([{ text: "K8s Worker Node\n", options: { bold: true, fontSize: 13, color: DEEP } },
             { text: "(EKS/GKE 노드 배치)\nPod · Pod · Pod", options: { fontSize: 10, color: MUT } }],
    { x: 1.15, y: 4.75, w: 3.4, h: 1.35, align: "center", valign: "middle", isTextBox: true, fontFace: BODY, margin: 0 });

  // SSH 화살표 bastion -> node
  s.addShape("line", { x: 2.6, y: 3.75, w: 0, h: 1.0, line: { color: "EC7211", width: 2, endArrowType: "triangle" } });
  s.addText("SSH", { x: 2.7, y: 4.05, w: 1.0, h: 0.3, fontFace: BODY, fontSize: 10, bold: true, color: "EC7211", isTextBox: true, margin: 0 });

  // 오른쪽 설명
  s.addText([
    { text: "구성 요약\n", options: { bold: true, fontSize: 14, color: DEEP, breakLine: true } },
    { text: "• 1 VPC + 이중화 서브넷(public/private)\n", options: { fontSize: 12, color: INK, breakLine: true } },
    { text: "• Bastion(public) → SSH → Worker(private)\n", options: { fontSize: 12, color: INK, breakLine: true } },
    { text: "• Worker Node는 private에 격리 배치\n", options: { fontSize: 12, color: INK, breakLine: true } },
    { text: "• 외부 접근은 Bastion 한 곳으로 단일화", options: { fontSize: 12, color: INK } },
  ], { x: 5.1, y: 4.75, w: 7.1, h: 1.4, valign: "top", isTextBox: true, fontFace: BODY, margin: 0 });
}

// ---------- Slide 4: 계정 생성 ----------
{
  const s = p.addSlide();
  s.background = { color: LIGHT };
  title(s, 3, "계정 생성");
  s.addText([
    { text: "무엇을\n", options: { bold: true, fontSize: 14, color: DEEP, breakLine: true } },
    { text: "GCP 무료 체험판 계정 생성. $300(₩414,984) 크레딧 제공.\n\n", options: { fontSize: 13, color: INK, breakLine: true } },
    { text: "확인 포인트\n", options: { bold: true, fontSize: 14, color: DEEP, breakLine: true } },
    { text: "• 콘솔 대시보드 정상 진입\n• 무료 크레딧 잔액 표시\n• 결제는 크레딧에서만 차감(카드 자동청구 없음)", options: { fontSize: 13, color: INK } },
  ], { x: 0.5, y: 1.5, w: 5.2, h: 3.5, valign: "top", isTextBox: true, fontFace: BODY });
  slot(s, 6.0, 1.5, 6.8, 4.9, "스샷 ① — 콘솔 대시보드 + 크레딧");
}

// ---------- Slide 5: IAM ----------
{
  const s = p.addSlide();
  s.background = { color: LIGHT };
  title(s, 4, "IAM 설정");
  s.addText([
    { text: "무엇을\n", options: { bold: true, fontSize: 14, color: DEEP, breakLine: true } },
    { text: "작업용 서비스 계정 생성 + 역할 부여(루트 대신 권한 분리).", options: { fontSize: 13, color: INK } },
  ], { x: 0.5, y: 1.5, w: 5.2, h: 1.1, valign: "top", isTextBox: true, fontFace: BODY });

  const rows = [
    [{ text: "항목", options: { bold: true, color: WHITE, fill: { color: DEEP } } }, { text: "값", options: { bold: true, color: WHITE, fill: { color: DEEP } } }],
    ["서비스 계정", "eks-admin"],
    ["역할", "기본 > 편집자 (Editor)"],
    ["상태", "사용 설정됨"],
  ];
  s.addTable(rows, { x: 0.5, y: 2.75, w: 5.2, colW: [1.8, 3.4], rowH: 0.5,
    fontFace: BODY, fontSize: 13, color: INK, border: { type: "solid", color: ICE, pt: 1 },
    align: "left", valign: "middle" });
  slot(s, 6.0, 1.5, 6.8, 4.9, "스샷 ② — 서비스 계정 목록(eks-admin)");
}

// ---------- Slide 6: VPC ----------
{
  const s = p.addSlide();
  s.background = { color: LIGHT };
  title(s, 5, "VPC 구축");
  s.addText([
    { text: "무엇을\n", options: { bold: true, fontSize: 14, color: DEEP, breakLine: true } },
    { text: "eks-vpc 생성 후 이중화 서브넷 구성(맞춤 모드).", options: { fontSize: 13, color: INK } },
  ], { x: 0.5, y: 1.5, w: 5.2, h: 1.0, valign: "top", isTextBox: true, fontFace: BODY });

  const rows = [
    [{ text: "서브넷", options: { bold: true, color: WHITE, fill: { color: DEEP } } },
     { text: "CIDR", options: { bold: true, color: WHITE, fill: { color: DEEP } } },
     { text: "리전", options: { bold: true, color: WHITE, fill: { color: DEEP } } }],
    ["public-a", "10.0.1.0/24", "asia-northeast3"],
    ["private-a", "10.0.11.0/24", "asia-northeast3"],
  ];
  s.addTable(rows, { x: 0.5, y: 2.65, w: 5.2, colW: [1.6, 1.9, 1.7], rowH: 0.5,
    fontFace: BODY, fontSize: 12.5, color: INK, border: { type: "solid", color: ICE, pt: 1 },
    align: "left", valign: "middle" });
  s.addText("VPC: eks-vpc · 커스텀 서브넷 모드 · MTU 1460",
    { x: 0.5, y: 4.0, w: 5.2, h: 0.5, fontFace: BODY, fontSize: 12, italic: true, color: MUT, isTextBox: true });
  slot(s, 6.0, 1.5, 6.8, 4.9, "스샷 ③ — eks-vpc 서브넷 목록(CIDR)");
}

// ---------- Slide 7: Bastion ----------
{
  const s = p.addSlide();
  s.background = { color: LIGHT };
  title(s, 6, "Bastion Host 생성");
  s.addText([
    { text: "무엇을\n", options: { bold: true, fontSize: 14, color: DEEP, breakLine: true } },
    { text: "public 서브넷에 점프 서버(VM) 생성 · 외부 IP 부여.", options: { fontSize: 13, color: INK } },
  ], { x: 0.5, y: 1.5, w: 5.2, h: 1.0, valign: "top", isTextBox: true, fontFace: BODY });

  const rows = [
    [{ text: "항목", options: { bold: true, color: WHITE, fill: { color: DEEP } } },
     { text: "값", options: { bold: true, color: WHITE, fill: { color: DEEP } } }],
    ["이름", "bastion"],
    ["영역", "asia-northeast3-b"],
    ["연결 서브넷", "public-a (10.0.1.0/24)"],
    ["내부 IP", "10.0.1.2"],
    ["외부 IP", "부여됨 (임시)"],
    ["상태", "실행 중"],
  ];
  s.addTable(rows, { x: 0.5, y: 2.65, w: 5.2, colW: [1.7, 3.5], rowH: 0.44,
    fontFace: BODY, fontSize: 12.5, color: INK, border: { type: "solid", color: ICE, pt: 1 },
    align: "left", valign: "middle" });
  slot(s, 6.0, 1.5, 6.8, 4.9, "스샷 ④ — bastion 인스턴스(실행 중 + 외부 IP)");
}

// ---------- Slide 8: 결과 & 정리 ----------
{
  const s = p.addSlide();
  s.background = { color: NAVY };
  s.addText("결과 요약 & 비용 관리", { x: 0.6, y: 0.55, w: 11, h: 0.8,
    fontFace: HEAD, fontSize: 32, bold: true, color: WHITE, isTextBox: true, margin: 0 });

  const cards = [
    ["계정", "무료 크레딧 계정 생성 완료"],
    ["IAM", "eks-admin 서비스 계정 · 편집자"],
    ["VPC", "eks-vpc · public/private 이중 서브넷"],
    ["Bastion", "public-a에 VM 생성 · 외부 IP · 실행 확인"],
  ];
  let x = 0.6;
  cards.forEach(([h, d]) => {
    s.addShape("roundRect", { x, y: 1.7, w: 2.95, h: 1.7, rectRadius: 0.06, fill: { color: DEEP } });
    s.addText([{ text: h + "\n", options: { bold: true, fontSize: 16, color: WHITE } },
               { text: d, options: { fontSize: 11, color: ICE } }],
      { x: x + 0.15, y: 1.85, w: 2.65, h: 1.4, valign: "top", isTextBox: true, fontFace: BODY, margin: 0 });
    x += 3.1;
  });

  s.addText([
    { text: "비용 / 정리\n", options: { bold: true, fontSize: 16, color: WHITE, breakLine: true } },
    { text: "• 실제 카드 청구 0원 — 무료 체험판, 크레딧 차감만, 자동 유료전환 없음\n", options: { fontSize: 13, color: ICE, breakLine: true } },
    { text: "• 과금 대상은 VM뿐(IAM·VPC는 무료). 캡처 후 전 리소스 삭제 완료\n", options: { fontSize: 13, color: ICE, breakLine: true } },
    { text: "• 정리 순서: Bastion VM → VPC(서브넷 포함) → 서비스 계정", options: { fontSize: 13, color: ICE } },
  ], { x: 0.6, y: 3.9, w: 12.1, h: 2.4, valign: "top", isTextBox: true, fontFace: BODY });
  s.addText("EKS는 AWS 전용 서비스로, GCP에서는 GKE가 대응(동일 개념: 관리형 K8s + 노드풀).",
    { x: 0.6, y: 6.5, w: 12.1, h: 0.5, fontFace: BODY, fontSize: 12, italic: true, color: "9FB6D6", isTextBox: true, margin: 0 });
}

p.writeFile({ fileName: "클라우드환경구성_GCP.pptx" }).then(f => console.log("saved", f));
