"""将 docs/user_manual.md 渲染为图文 PDF（docs/user_manual.pdf）。

用法：python scripts\\make_pdf.py
"""
from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.line_break import Fragment

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "docs" / "user_manual.md"
OUT = ROOT / "docs" / "user_manual.pdf"

F_REG = "C:/Windows/Fonts/msyh.ttc"
F_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


class ManualPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("yahei", "", F_REG)
        self.add_font("yahei", "B", F_BOLD)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("yahei", "", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 6, "任务提醒助手 用户操作手册 v2.0", align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-14)
        self.set_font("yahei", "", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 8, f"第 {self.page_no()} 页", align="C")


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`(.+?)`")


def clean(s: str) -> str:
    s = CODE_RE.sub(r"\1", s)
    return s


def visual_width(s: str) -> float:
    """估算字符串显示宽度（全角按 2）。"""
    return sum(2.0 if unicodedata.east_asian_width(c) in "WF" else 1.0 for c in s)


def write_inline(pdf: ManualPDF, text: str, size: int = 10.5, base_style: str = ""):
    """处理 **粗体** 与普通文本混排。"""
    pdf.set_font("yahei", base_style, size)
    pos = 0
    for m in BOLD_RE.finditer(text):
        if m.start() > pos:
            pdf.write(6, text[pos:m.start()])
        pdf.set_font("yahei", "B" if "B" not in base_style else base_style, size)
        pdf.write(6, m.group(1))
        pdf.set_font("yahei", base_style, size)
        pos = m.end()
    if pos < len(text):
        pdf.write(6, text[pos:])
    pdf.ln(6)


def render_table(pdf: ManualPDF, rows: list[list[str]]):
    rows = [r for r in rows if not all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in r)]
    if not rows:
        return
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    epw = pdf.epw
    # 依据内容宽度比例分配列宽
    weights = []
    for c in range(ncol):
        w = max(visual_width(rows[r][c]) for r in range(len(rows)))
        weights.append(max(w, 4.0))
    total = sum(weights)
    widths = [epw * w / total for w in weights]

    pdf.set_draw_color(200, 205, 215)
    head = FontFace(family="yahei", emphasis="BOLD", size_pt=9.5, color=(255, 255, 255),
                    fill_color=(37, 99, 235))
    body = FontFace(family="yahei", size_pt=9.5)
    with pdf.table(col_widths=widths, text_align="LEFT", line_height=5.6,
                   borders_layout="ALL", first_row_as_headings=True,
                   headings_style=head, cell_fill_color=(245, 247, 250),
                   cell_fill_mode="ROWS") as table:
        for r in rows:
            row = table.row()
            for c in r:
                row.cell(clean(c))
    pdf.ln(3)


def render_image(pdf: ManualPDF, path: Path, alt: str):
    if not path.exists():
        return
    img = pdf.image(str(path), w=pdf.epw)
    pdf.set_font("yahei", "", 8.5)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, alt, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(30, 30, 30)
    pdf.ln(2)


def render_markdown(pdf: ManualPDF, md_text: str, base_dir: Path):
    lines = md_text.splitlines()
    i = 0
    first_h2 = True
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 表格块
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            render_table(pdf, rows)
            continue

        if not stripped:
            pdf.ln(1.5)
            i += 1
            continue
        if stripped == "---":
            i += 1
            continue

        if stripped.startswith("# "):
            pdf.add_page()
            pdf.set_font("yahei", "B", 26)
            pdf.set_text_color(30, 45, 90)
            pdf.cell(0, 20, clean(stripped[2:]), align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("yahei", "", 12)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(0, 10, f"版本 v2.0 · 更新日期 {datetime.now():%Y-%m-%d}", align="C",
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30)
            pdf.ln(4)
        elif stripped.startswith("## "):
            title = clean(stripped[3:])
            if not first_h2:
                pdf.add_page()
            first_h2 = False
            pdf.set_font("yahei", "B", 16)
            pdf.set_text_color(37, 99, 235)
            pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(37, 99, 235)
            pdf.set_line_width(0.6)
            pdf.line(16, pdf.get_y() + 1, 16 + 30, pdf.get_y() + 1)
            pdf.ln(6)
            pdf.set_text_color(30, 30, 30)
        elif stripped.startswith("### "):
            pdf.set_font("yahei", "B", 12.5)
            pdf.set_text_color(45, 55, 75)
            pdf.cell(0, 8, clean(stripped[4:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30)
            pdf.ln(1)
        elif stripped.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            pdf.set_font("courier", "", 9.5)
            pdf.set_fill_color(243, 244, 246)
            pdf.multi_cell(0, 5, "\n".join(block), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30)
            pdf.ln(2)
        elif stripped.startswith("!["):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
            if m:
                render_image(pdf, base_dir / m.group(2), m.group(1) or "插图")
        elif stripped.startswith("- "):
            pdf.set_font("yahei", "", 10.5)
            pdf.set_x(pdf.l_margin + 4)
            pdf.cell(4, 6, "•")
            write_inline(pdf, stripped[2:])
        elif re.match(r"^\d+\.\s", stripped):
            pdf.set_font("yahei", "", 10.5)
            num, rest = stripped.split(".", 1)
            pdf.set_x(pdf.l_margin + 2)
            pdf.cell(6, 6, f"{num}.")
            write_inline(pdf, rest.strip())
        else:
            write_inline(pdf, stripped)
        i += 1


def main() -> int:
    pdf = ManualPDF()
    render_markdown(pdf, MD.read_text(encoding="utf-8"), MD.parent)
    pdf.output(str(OUT))
    size = OUT.stat().st_size / 1024 / 1024
    print(f"PDF generated: {OUT} ({size:.1f} MB, {pdf.page_no()} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
