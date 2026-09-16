from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _plain(value: str) -> str:
    value = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[*_`]+", "", value)
    return html.escape(value.strip())


def _markdown_table(lines: list[str]) -> Table:
    rows: list[list[str]] = []
    for line in lines:
        if set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append([_plain(cell) for cell in cells])
    table = Table(rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c7d9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf3f8")]),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _visualization(source_dir: Path | None) -> str | None:
    if source_dir is None:
        return None
    results = source_dir / "results.csv"
    if not results.exists():
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd

        frame = pd.read_csv(results)
        numeric = [column for column in frame.select_dtypes(include="number").columns if column not in {"seed"}]
        if not numeric:
            return None
        columns = numeric[:6]
        figure, axes = plt.subplots(len(columns), 1, figsize=(7.0, max(2.0, len(columns) * 1.6)), squeeze=False)
        for axis, column in zip(axes[:, 0], columns):
            axis.plot(frame[column].dropna().to_list(), color="#1f77b4", marker="o", markersize=2)
            axis.set_title(column, fontsize=8)
            axis.grid(alpha=0.25)
            axis.tick_params(labelsize=7)
        figure.tight_layout()
        output = source_dir / ".report_visualization.png"
        figure.savefig(output, dpi=150)
        plt.close(figure)
        return str(output)
    except Exception:
        return None


def markdown_to_pdf(markdown: str, output_path: str | Path, source_dir: str | Path | None = None) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#1f4e79")))
    styles.add(ParagraphStyle(name="ReportH2", parent=styles["Heading2"], textColor=colors.HexColor("#1f4e79"), spaceBefore=10))
    styles.add(ParagraphStyle(name="ReportBody", parent=styles["BodyText"], leading=12, spaceAfter=5))
    story: list[Any] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            story.extend([_markdown_table(table_lines), Spacer(1, 5)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(_plain(line[2:]), styles["ReportTitle"]))
        elif line.startswith("## "):
            story.append(Paragraph(_plain(line[3:]), styles["ReportH2"]))
        elif line.startswith("### "):
            story.append(Paragraph(_plain(line[4:]), styles["Heading3"]))
        elif line.startswith("- "):
            story.append(Paragraph("&bull; " + _plain(line[2:]), styles["ReportBody"]))
        else:
            story.append(Paragraph(_plain(line), styles["ReportBody"]))
        index += 1

    image = _visualization(Path(source_dir) if source_dir else None)
    if image:
        story.extend([PageBreak(), Paragraph("Study Visualizations", styles["ReportH2"]), Image(image, width=170 * mm, height=100 * mm)])

    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    document.build(story)
    return output
