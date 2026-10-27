# -*- coding: utf-8 -*-
"""
build_xlsx.py
목적: GCP 클라우드 환경 구성 실습의 리소스/비용/체크리스트 제출용 Excel 생성
입력: 없음(내용 하드코딩) / 출력: 클라우드환경구성_GCP.xlsx
작성일: 2026-09-08
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# 색상 (PPT와 통일: Ocean 팔레트)
DEEP = "065A82"
NAVY = "21295C"
ICE = "CADCFC"
LIGHT = "F4F7FA"

hdr_fill = PatternFill("solid", fgColor=DEEP)
hdr_font = Font(bold=True, color="FFFFFF", size=11)
title_font = Font(bold=True, color=NAVY, size=15)
thin = Side(style="thin", color="D0D8E0")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(vertical="center", wrap_text=True)
center = Alignment(horizontal="center", vertical="center")

def style_header(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = center
        cell.border = border

def style_body(ws, r0, r1, ncols):
    for r in range(r0, r1 + 1):
        fill = PatternFill("solid", fgColor=LIGHT) if (r - r0) % 2 else None
        for c in range(1, ncols + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = border
            cell.alignment = wrap
            if fill:
                cell.fill = fill

wb = Workbook()

# ---------- Sheet 1: 리소스 목록 ----------
ws = wb.active
ws.title = "리소스목록"
ws["A1"] = "GCP 클라우드 환경 구성 — 리소스 목록"
ws["A1"].font = title_font
ws["A2"] = "프로젝트: My First Project   |   Region: asia-northeast3 (Seoul)   |   작성일: 2026-09-08"
ws["A2"].font = Font(italic=True, color="5B6675", size=10)

headers = ["구분", "리소스 유형", "이름", "리전 / 영역", "CIDR / IP", "상태", "비고"]
ws.append([])  # row3 empty
ws.append(headers)  # row4
rows = [
    ["계정", "GCP 무료 체험판", "심규상 계정", "-", "-", "생성 완료", "$300(₩414,984) 크레딧"],
    ["IAM", "서비스 계정", "eks-admin", "-", "-", "사용 설정됨", "역할: 편집자(Editor)"],
    ["네트워크", "VPC", "eks-vpc", "asia-northeast3", "-", "생성 완료", "커스텀 서브넷 모드"],
    ["네트워크", "서브넷(public)", "public-a", "asia-northeast3", "10.0.1.0/24", "생성 완료", "Bastion 배치"],
    ["네트워크", "서브넷(private)", "private-a", "asia-northeast3", "10.0.11.0/24", "생성 완료", "K8s 노드 배치용"],
    ["컴퓨트", "VM (Bastion)", "bastion", "asia-northeast3-b", "내부 10.0.1.2 / 외부 부여", "실행 확인 후 삭제", "점프 서버 · e2-medium"],
]
for r in rows:
    ws.append(r)
style_header(ws, 4, len(headers))
style_body(ws, 5, 4 + len(rows), len(headers))
widths = [10, 16, 14, 18, 24, 18, 24]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[chr(64 + i)].width = w

# ---------- Sheet 2: 비용 관리 ----------
ws2 = wb.create_sheet("비용관리")
ws2["A1"] = "비용 관리 요약"
ws2["A1"].font = title_font
ws2.append([])
h2 = ["리소스", "과금 여부", "대략 단가", "비고"]
ws2.append(h2)
cost = [
    ["VPC / 서브넷 / IGW", "무료", "0", "네트워크 기본 구성은 과금 없음"],
    ["IAM 서비스 계정", "무료", "0", "생성/사용 무료"],
    ["Bastion VM (e2-medium)", "과금(크레딧)", "약 $0.04/시간", "유일한 과금 리소스 · 캡처 후 삭제"],
    ["외부 IP (임시)", "사용 중 무료", "0", "VM 삭제 시 함께 반납"],
]
for r in cost:
    ws2.append(r)
style_header(ws2, 3, len(h2))
style_body(ws2, 4, 3 + len(cost), len(h2))
for i, w in enumerate([26, 16, 16, 34], 1):
    ws2.column_dimensions[chr(64 + i)].width = w

note_row = 3 + len(cost) + 2
ws2.cell(row=note_row, column=1, value="결론").font = Font(bold=True, color=NAVY, size=12)
notes = [
    "· 실제 카드 청구액 = 0원. 무료 체험판이라 비용은 크레딧에서만 차감되며 자동 유료 전환 없음.",
    "· 과금 대상은 Bastion VM 하나뿐이었고, 스크린샷 확보 후 즉시 삭제하여 실시간 과금 리소스 없음.",
    "· 정리 순서: Bastion VM(부팅 디스크 포함) → VPC(서브넷 포함) → eks-admin 서비스 계정.",
    "· 주의: 콘솔의 '활성화 / 일반 계정 활성화' 버튼을 누르면 유료 전환되므로 누르지 않음.",
]
for i, n in enumerate(notes):
    ws2.cell(row=note_row + 1 + i, column=1, value=n).font = Font(size=10, color="1B2430")

# ---------- Sheet 3: 체크리스트 ----------
ws3 = wb.create_sheet("체크리스트")
ws3["A1"] = "과제 항목 체크리스트"
ws3["A1"].font = title_font
ws3.append([])
h3 = ["번호", "과제 항목", "수행 내용", "완료", "제출 스샷"]
ws3.append(h3)
chk = [
    ["1", "계정 생성", "GCP 무료 체험판 계정 생성 · 콘솔 진입", "O", "스샷 ①"],
    ["2", "IAM 설정", "eks-admin 서비스 계정 생성 · 편집자 부여", "O", "스샷 ②"],
    ["3", "VPC 구축", "eks-vpc + 이중화 서브넷(public/private)", "O", "스샷 ③"],
    ["4", "Bastion Host 생성", "public-a에 VM 생성 · 외부 IP · 실행 확인", "O", "스샷 ④"],
]
for r in chk:
    ws3.append(r)
style_header(ws3, 3, len(h3))
style_body(ws3, 4, 3 + len(chk), len(h3))
for i, w in enumerate([8, 20, 40, 10, 14], 1):
    ws3.column_dimensions[chr(64 + i)].width = w
for r in range(4, 4 + len(chk)):
    ws3.cell(row=r, column=1).alignment = center
    ws3.cell(row=r, column=4).alignment = center
    ws3.cell(row=r, column=4).font = Font(bold=True, color=DEEP)
    ws3.cell(row=r, column=5).alignment = center

wb.save("클라우드환경구성_GCP.xlsx")
print("saved 클라우드환경구성_GCP.xlsx")
