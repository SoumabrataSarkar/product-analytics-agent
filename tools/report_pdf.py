"""Build an investigation report PDF with one fixed, white-paper style template.

Every investigation uses the same cover, contents page, chapters, chart styles,
colours, header and footer. Only the content file (JSON) changes. A report
longer than MAX_PAGES (10) is refused: the output file is removed and the
command exits non-zero, so the content must be shortened.

Usage (from the repository root):
    python3 tools/report_pdf.py content.json output.pdf

Requires reportlab and matplotlib. Example content:
docs/deliverables/report-content-example.json (illustrative numbers only).

Fixed chapters (mapped from docs/deliverables/investigation-report-template.md):
  01 The answer                <- executive
  02 How we investigated       <- scope, workflow
  03 What happened             <- baseline, decomposition
  04 Why it happened           <- drivers
  05 Data quality and limits   <- data_quality, limitations
  06 What to do next           <- recommendations
  A  Evidence appendix         <- appendix
The contents page always carries "How to read this report" and the glossary.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

# ---------------------------------------------------------------- design tokens
# Brand accent (headings, page furniture) - a deep, calm red.
RED, RED_SOFT = "#c0392b", "#fbecea"
INK, INK2, MUTED, LABEL = "#1c1c1c", "#555555", "#9a9a9a", "#c4c4c4"
GRID, RULE, PANEL = "#ececec", "#d6d6d6", "#f4f4f2"
# Data colours: one blue scale for ordered groups, green/red only for gain/loss.
BLUE_LIGHT, BLUE_MID, BLUE_DARK = "#9cc3ee", "#3f86d4", "#1f4e8c"
NEUTRAL, CHARCOAL = "#cfcfcf", "#3a3a3a"
GAIN, LOSS = "#3c8d5a", "#c0533f"
STATUS = {"Supported": ("#3c8d5a", "white"), "Passed": ("#3c8d5a", "white"),
          "Pattern supported": ("#8cc29f", "#123a20"),
          "Rejected": ("#e4e4e1", "#444444"), "Inconclusive": ("#e8b04b", "#1c1c1c"),
          "Not tested": ("#f0f0ee", "#777777")}
LAYER = {"Gold": "#efdca2", "Silver": "#dfe3e8", "Bronze": "#ebcfb8", "Build log": "#e8e8e8"}

MAX_PAGES = 10  # docs/deliverables/investigation-report-template.md: at most 10 pages
PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
TEXT_W = PAGE_W - 2 * MARGIN

CHAPTERS = [  # number, title, content sections, starts a new page
    ("01", "The answer", ["executive"], True),
    ("02", "How we investigated", ["scope", "workflow"], True),
    ("03", "What happened", ["baseline", "decomposition"], False),
    ("04", "Why it happened", ["drivers"], False),
    ("05", "Data quality and limits", ["data_quality", "limitations"], False),
    ("06", "What to do next", ["recommendations"], False),
    ("A", "Evidence appendix", ["appendix"], False),
]
SUBHEAD = {"scope": "What data we used", "workflow": "Investigation path",
           "baseline": "The movement", "decomposition": "Who drove it", "drivers": None,
           "data_quality": "Data quality", "limitations": "Limitations",
           "recommendations": None, "appendix": None, "executive": None}


class PageLimitError(ValueError):
    """The rendered report is longer than MAX_PAGES."""


FONT_CANDIDATES = [  # (regular, bold, italic); the first complete set is used
    tuple(f"/usr/share/fonts/truetype/liberation/LiberationSans-{w}.ttf" for w in ("Regular", "Bold", "Italic")),
    tuple(f"/System/Library/Fonts/Supplemental/{n}.ttf" for n in ("Arial", "Arial Bold", "Arial Italic")),
    tuple(f"/Library/Fonts/{n}.ttf" for n in ("Arial", "Arial Bold", "Arial Italic")),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
]


def _fonts():
    for reg, bold, ital in FONT_CANDIDATES:
        if all(Path(p).exists() for p in (reg, bold, ital)):
            pdfmetrics.registerFont(TTFont("R", reg))
            pdfmetrics.registerFont(TTFont("B", bold))
            pdfmetrics.registerFont(TTFont("I", ital))
            pdfmetrics.registerFontFamily("R", normal="R", bold="B", italic="I", boldItalic="B")
            for p in (reg, bold):
                font_manager.fontManager.addfont(p)
            return font_manager.FontProperties(fname=reg).get_name()
    raise SystemExit("No usable TTF font found; add one to FONT_CANDIDATES")


CHART_FONT = _fonts()


def style(name, **kw):
    base = dict(fontName="R", fontSize=9.5, leading=14, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


S = {
    "kicker": style("kicker", fontSize=15, leading=18, textColor=LABEL),
    "chapter": style("chapter", fontName="B", fontSize=21, leading=25, textColor=RED),
    "sub": style("sub", fontName="B", fontSize=10.5, leading=14, textColor=RED, spaceBefore=10, spaceAfter=5, keepWithNext=1),
    "body": style("body", spaceAfter=6),
    "bullet": style("bullet", leftIndent=14, bulletIndent=0, spaceAfter=4, bulletColor=RED, bulletFontName="B"),
    "cell": style("cell", fontSize=8.3, leading=11.2),
    "cellh": style("cellh", fontName="B", fontSize=8.3, leading=11.2),
    "caption": style("caption", fontSize=7.4, leading=10, textColor=MUTED, spaceAfter=10),
    "kpi_v": style("kpi_v", fontName="B", fontSize=21, leading=25, textColor=RED),
    "kpi_l": style("kpi_l", fontSize=8, leading=10.8, textColor=INK2),
    "band": style("band", fontName="B", fontSize=12.5, leading=18, textColor=colors.white),
    "math": style("math", fontSize=8.6, leading=12.5, textColor=INK),
    "wf_round": style("wf_round", fontName="B", fontSize=9, leading=12, textColor=RED),
    "wf_goal": style("wf_goal", fontName="I", fontSize=8.3, leading=11.5, textColor=INK2, spaceAfter=3),
    "wf_line": style("wf_line", fontSize=8.3, leading=12.2, spaceAfter=2),
    "wf_next": style("wf_next", fontName="B", fontSize=8.3, leading=11.5, textColor=RED, spaceBefore=2),
}


def pill(text, status):
    bg, fg = STATUS.get(status, STATUS["Not tested"])
    return f'<font backColor="{bg}" color="{fg}"><b>&nbsp;{text.replace(" ", "&nbsp;")}&nbsp;</b></font>'


def chip(layer):
    return f'<font backColor="{LAYER.get(layer, "#eeeeee")}" color="{INK}">&nbsp;{layer}&nbsp;</font>'


# ---------------------------------------------------------------- page furniture
class ChapterOpener(Flowable):
    def __init__(self, number: str, title: str):
        super().__init__()
        self.number, self.title = number, title
        self.width, self.height = TEXT_W, 25 * mm

    def draw(self):
        c = self.canv
        kicker = "Appendix" if self.number == "A" else f"{self.number}. Chapter"
        c.setFont("R", 15); c.setFillColor(colors.HexColor(LABEL)); c.drawString(0, self.height - 15, kicker)
        c.setFont("B", 21); c.setFillColor(colors.HexColor(RED)); c.drawString(0, self.height - 38, self.title)
        c.setFillColor(colors.HexColor(INK)); c.rect(0, self.height - 58, 22 * mm, 1.6, stroke=0, fill=1)
        c.setFont("B", 34); c.setFillColor(colors.HexColor(RED)); c.drawRightString(self.width, self.height - 38, self.number)


class DocTemplate(BaseDocTemplate):
    def __init__(self, filename, meta, **kw):
        super().__init__(filename, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=22 * mm, bottomMargin=20 * mm, **kw)
        self.meta = meta
        self.pages_drawn = 0
        body = Frame(MARGIN, 20 * mm, TEXT_W, PAGE_H - 42 * mm, id="body", leftPadding=0, rightPadding=0)
        cover = Frame(MARGIN, 20 * mm, TEXT_W, PAGE_H - 40 * mm, id="cover", leftPadding=0, rightPadding=0)
        self.addPageTemplates([PageTemplate("cover", [cover], onPage=self._cover),
                               PageTemplate("body", [body], onPage=self._frame)])

    def afterFlowable(self, f):
        if isinstance(f, ChapterOpener):
            self.notify("TOCEntry", (0, f"{f.number}    {f.title}", self.page))

    def _frame(self, c, doc):
        self.pages_drawn = max(self.pages_drawn, doc.page)
        m = self.meta
        c.saveState()
        c.setFillColor(colors.HexColor(RED)); c.setFont("B", 9)
        c.drawString(MARGIN, PAGE_H - 13 * mm, "+")
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 13 * mm, "+")
        c.setFillColor(colors.HexColor(MUTED)); c.setFont("R", 7.2)
        c.drawString(MARGIN + 5 * mm, PAGE_H - 13 * mm, f'Investigation report {m["date"][:4]}')
        c.drawRightString(PAGE_W - MARGIN - 5 * mm, PAGE_H - 13 * mm, m["short_title"])
        c.setFillColor(colors.HexColor(RED)); c.setFont("B", 8); c.drawString(MARGIN, 11 * mm, "– –")
        c.setFillColor(colors.HexColor(INK2)); c.setFont("R", 7.2); c.drawString(MARGIN + 8 * mm, 11 * mm, f"{doc.page:04d}")
        c.setFillColor(colors.HexColor(MUTED))
        c.drawRightString(PAGE_W - MARGIN, 11 * mm, f'Data snapshot {m["snapshot"]} · build {m["build"]} · {m["evidence"]}')
        c.restoreState()

    def _cover(self, c, doc):
        m = self.meta
        c.saveState()
        c.setFillColor(colors.HexColor(RED)); c.circle(MARGIN + 2.2 * mm, PAGE_H - 21 * mm, 2.2 * mm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor(INK)); c.setFont("B", 10); c.drawString(MARGIN + 7 * mm, PAGE_H - 22.3 * mm, m["project"])
        c.setFillColor(colors.HexColor(RED)); c.setFont("B", 12); c.drawRightString(PAGE_W - MARGIN, PAGE_H - 22.5 * mm, "+ + +")
        top, h = PAGE_H - 34 * mm, 128 * mm
        c.setFillColor(colors.HexColor(PANEL)); c.rect(MARGIN, top - h, TEXT_W, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor(RED)); c.setFont("B", 22); c.drawString(MARGIN + 12 * mm, top - 26 * mm, "+ +")
        c.setFillColor(colors.HexColor(INK)); c.setFont("B", 30)
        c.drawString(MARGIN + 12 * mm, top - 42 * mm, "Investigation")
        c.drawString(MARGIN + 12 * mm, top - 54 * mm, "report")
        y = top - 76 * mm
        for text, st in ((m["title"], style("ct", fontName="B", fontSize=13, leading=17, textColor=RED)),
                         (m["question"], style("cq", fontSize=9.5, leading=13.5, textColor=INK2))):
            p = Paragraph(text, st)
            _, ph = p.wrap(TEXT_W - 24 * mm, 60 * mm)
            p.drawOn(c, MARGIN + 12 * mm, y - ph)
            y -= ph + 5 * mm
        base = 58 * mm
        c.setFillColor(colors.HexColor(INK)); c.rect(MARGIN, base, TEXT_W, 1.4, stroke=0, fill=1)
        cols = [("Data", [m["dataset"], m["periods"]]), ("Snapshot", [m["snapshot"], f'Build {m["build"]}']),
                ("Run", [m["mode"], m["date"], m["evidence"]])]
        cw = TEXT_W / 3
        for i, (head, lines) in enumerate(cols):
            x = MARGIN + i * cw
            c.setFont("B", 8); c.setFillColor(colors.HexColor(INK)); c.drawString(x, base - 9 * mm, head)
            yy = base - 13 * mm
            for line in lines:
                p = Paragraph(line, style("cc", fontSize=7.6, leading=10, textColor=INK2))
                _, ph = p.wrap(cw - 6 * mm, 30 * mm)
                p.drawOn(c, x, yy - ph)
                yy -= ph + 1.5
        c.restoreState()


# ---------------------------------------------------------------- charts
def _axes(h=2.7, ncols=1):
    plt.rcParams.update({"font.family": CHART_FONT, "font.size": 8.5, "axes.edgecolor": RULE,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK2})
    fig, axs = plt.subplots(1, ncols, figsize=(7.0, h), dpi=220)
    for ax in (axs if ncols > 1 else [axs]):
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(length=0)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    return fig, axs


def _legend(ax, items, y=-0.13):
    handles = [Line2D([0], [0], color=c, linewidth=2.2, marker="o", markersize=4) if kind == "line"
               else Patch(facecolor=c, edgecolor="none") for name, c, kind in items]
    ax.legend(handles, [i[0] for i in items], frameon=False, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, y), ncol=len(items), handlelength=1.4, columnspacing=1.6)


def _finish(fig, ax, c, title=True):
    if title:
        ax.set_title(c["title"], loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=22)
        if c.get("subtitle"):
            ax.text(0, 1.03, c["subtitle"], transform=ax.transAxes, fontsize=8, color=INK2)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    fw, fh = fig.get_size_inches()
    return Image(buf, width=TEXT_W, height=TEXT_W * fh / fw)


def _break(ax, c, offset=0.06):
    if c.get("break_after") is None:
        return
    b = c["break_after"] + 0.5
    ax.axvline(b, color=MUTED, linestyle=":", linewidth=1)
    for txt, dx, ha in ((c["break_labels"][0], -offset, "right"), (c["break_labels"][1], offset, "left")):
        ax.text(b + dx, 0.98, txt, transform=ax.get_xaxis_transform(), ha=ha, va="top", fontsize=8, color=INK2)


def chart_stacked_with_line(c):
    """Stacked bars of a partitioned total (one blue scale, oldest group lightest) plus a line measure."""
    fig, ax = _axes(c.get("height", 2.8))
    xs = list(range(len(c["x"])))
    shades = [BLUE_LIGHT, BLUE_MID, BLUE_DARK]
    bottom = [0] * len(xs)
    items = []
    for k, s in enumerate(c["stacks"]):
        col = shades[k % 3]
        ax.bar(xs, s["values"], bottom=bottom, color=col, width=0.62, edgecolor="white", linewidth=0.8)
        bottom = [b + v for b, v in zip(bottom, s["values"])]
        items.append((s["name"], col, "bar"))
    for x, t in zip(xs, bottom):
        ax.text(x, t + max(bottom) * 0.015, f"{t:,.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold", color=INK)
    ln = c["line"]
    ax.plot(xs, ln["values"], color=CHARCOAL, linewidth=2, marker="o", markersize=4)
    for x, v in zip(xs, ln["values"]):
        ax.text(x, v + max(bottom) * 0.03, f"{v:,.0f}", ha="center", va="bottom", fontsize=7.5, color=CHARCOAL)
    items.append((ln["name"], CHARCOAL, "line"))
    ax.set_xticks(xs, c["x"])
    ax.set_ylim(0, max(bottom) * 1.16)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _break(ax, c)
    _legend(ax, items)
    return _finish(fig, ax, c)


def chart_index_lines(c):
    fig, ax = _axes(c.get("height", 2.6))
    xs = c["x"]
    for s in c["series"]:
        idx = [v / s["values"][0] * 100 for v in s["values"]]
        acc = s.get("accent", False)
        col = BLUE_MID if acc else ("#a8a8a8" if s.get("dashed") else CHARCOAL)
        ax.plot(xs, idx, color=col, linewidth=2.4 if acc else 1.7, linestyle="--" if s.get("dashed") else "-", marker="o", markersize=3.4)
        ax.annotate(f'{s["name"]} {idx[-1]:.0f}', (len(xs) - 1, idx[-1]), xytext=(8, s.get("label_dy", 0)),
                    textcoords="offset points", va="center", fontsize=8.5, color=col, fontweight="bold" if acc else "normal")
    ax.axhline(100, color=MUTED, linewidth=0.8)
    _break(ax, c, 0.08)
    ax.set_xlim(-0.3, len(xs) - 1 + 1.3)
    return _finish(fig, ax, c)


def chart_before_after(c):
    """Per group: before vs after as paired horizontal bars, with the signed change. Ends with the sum."""
    groups = c["groups"]
    fig, ax = _axes(c.get("height", 2.6))
    ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.spines[["bottom"]].set_visible(False)
    n = len(groups)
    ys = list(range(n))[::-1]
    top = max(max(g["before"], g["after"]) for g in groups)
    for y, g in zip(ys, groups):
        ax.barh(y + 0.18, g["before"], height=0.34, color=NEUTRAL)
        ax.barh(y - 0.18, g["after"], height=0.34, color=BLUE_DARK)
        ax.text(g["before"] + top * 0.01, y + 0.18, f'{g["before"]:,.0f}', va="center", fontsize=7.8, color=INK2)
        ax.text(g["after"] + top * 0.01, y - 0.18, f'{g["after"]:,.0f}', va="center", fontsize=7.8, color=INK)
        d = g["after"] - g["before"]
        ax.text(top * 1.28, y, f'{d:+,.0f}'.replace("-", "−"), va="center", ha="right", fontsize=10,
                fontweight="bold", color=GAIN if d >= 0 else LOSS)
    ax.text(top * 1.28, n - 0.45, "Change", ha="right", fontsize=8, color=INK2)
    ax.set_yticks(ys, [g["label"] for g in groups], fontsize=8.5)
    ax.set_xlim(0, top * 1.3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}" if v <= top * 1.05 else ""))
    _legend(ax, [(c["before_label"], NEUTRAL, "bar"), (c["after_label"], BLUE_DARK, "bar")], y=-0.12)
    return _finish(fig, ax, c)


def chart_total_vs_part(c):
    """Monthly total (light) with the part that did something (dark) and the share printed above."""
    fig, ax = _axes(c.get("height", 2.7))
    xs = list(range(len(c["x"])))
    ax.bar(xs, c["total"]["values"], width=0.62, color=NEUTRAL)
    ax.bar(xs, c["part"]["values"], width=0.62, color=BLUE_DARK)
    top = max(c["total"]["values"])
    for x, t, p in zip(xs, c["total"]["values"], c["part"]["values"]):
        ax.text(x, t + top * 0.015, f"{t:,.0f}", ha="center", va="bottom", fontsize=7.6, color=INK2)
        ax.text(x, p + top * 0.015, f"{p:,.0f}", ha="center", va="bottom", fontsize=7.6, color=INK, fontweight="bold")
        ax.text(x, top * 1.17, f"{p / t:.1%}", ha="center", va="bottom", fontsize=9, fontweight="bold", color=BLUE_DARK)
    ax.text(-0.45, top * 1.17, c.get("share_label", "Share"), ha="right", va="bottom", fontsize=7.6, color=INK2)
    ax.set_xticks(xs, c["x"])
    ax.set_ylim(0, top * 1.42)
    ax.set_yticks([t for t in matplotlib.ticker.MaxNLocator(4).tick_values(0, top) if 0 <= t <= top])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    _break(ax, c)
    _legend(ax, [(c["total"]["name"], NEUTRAL, "bar"), (c["part"]["name"], BLUE_DARK, "bar")])
    return _finish(fig, ax, c)


def chart_cohort_rates(c):
    """One panel per measure. Each bar = count / base for a group, labelled 'x%' and 'count of base'."""
    panels = c["panels"]
    fig, axs = _axes(c.get("height", 2.9), ncols=len(panels))
    base = c["base"]
    labels = c["groups"]
    for ax, p in zip(axs, panels):
        rates = [n / b * 100 for n, b in zip(p["counts"], base)]
        top = max(rates)
        cols = [BLUE_LIGHT if i <= c.get("break_after", -1) else BLUE_DARK for i in range(len(rates))]
        ax.bar(range(len(rates)), rates, color=cols, width=0.62)
        for i, (r, n, b) in enumerate(zip(rates, p["counts"], base)):
            ax.text(i, r + top * 0.03, f"{r:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color=INK)
        ax.set_xticks(range(len(labels)), [f"{g}\n{n}/{b:,}" for g, n, b in zip(labels, p["counts"], base)], fontsize=7.2)
        ax.set_ylim(0, top * 1.3)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.set_title(p["title"], loc="left", fontsize=9.5, fontweight="bold", color=INK, pad=6)
        _break(ax, c, 0.08)
    _legend(axs[0], [(c["legend"][0], BLUE_LIGHT, "bar"), (c["legend"][1], BLUE_DARK, "bar")], y=-0.22)
    fig.suptitle(c["title"], x=0.02, ha="left", fontsize=10.5, fontweight="bold", color=INK)
    fig.text(0.02, 0.885, c.get("subtitle", ""), fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    fw, fh = fig.get_size_inches()
    return Image(buf, width=TEXT_W, height=TEXT_W * fh / fw)


CHARTS = {"stacked_with_line": chart_stacked_with_line, "index_lines": chart_index_lines,
          "before_after": chart_before_after, "total_vs_part": chart_total_vs_part,
          "cohort_rates": chart_cohort_rates}


# ---------------------------------------------------------------- blocks
def P(text, st="body"):
    return Paragraph(text, S[st])


def table(rows, widths, status_col=None, layer_col=None):
    data = []
    for r, row in enumerate(rows):
        cells = []
        for k, val in enumerate(row):
            val = str(val)
            if r and status_col == k and val in STATUS:
                val = pill(val, val)
            elif r and layer_col == k and val in LAYER:
                val = chip(val)
            cells.append(P(val, "cellh" if r == 0 else "cell"))
        data.append(cells)
    t = Table(data, colWidths=[w * TEXT_W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 1.4, colors.HexColor(INK)),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(RULE)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor(GRID)),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def kpis(items):
    n = len(items)
    t = Table([[P(k["value"], "kpi_v") for k in items], [P(k["label"], "kpi_l") for k in items]], colWidths=[TEXT_W / n] * n)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.4, colors.HexColor(INK)),
                           ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    return t


def boxed(flowables, bg, bar=None, pad=10):
    t = Table([[f] for f in flowables], colWidths=[TEXT_W])
    st = [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)), ("LEFTPADDING", (0, 0), (-1, -1), pad),
          ("RIGHTPADDING", (0, 0), (-1, -1), pad), ("TOPPADDING", (0, 0), (-1, 0), 7),
          ("BOTTOMPADDING", (0, -1), (-1, -1), 6), ("TOPPADDING", (0, 1), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -2), 1)]
    if bar:
        st.append(("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(bar)))
    t.setStyle(TableStyle(st))
    return t


def workflow(steps, legend):
    """Investigation path: one row per stage with its goal, each check (status, layer, result) and the next step."""
    rows = []
    for st in steps:
        card = [P(st["goal"], "wf_goal")]
        for chk in st["checks"]:
            ref = f' <font color="{MUTED}">(check {chk["checks"]})</font>' if chk.get("checks") else ""
            card.append(P(f'{pill(chk["status"], chk["status"])} {chip(chk["layer"])} <b>{chk["name"]}</b>{ref}<br/>'
                          f'<font color="{INK2}">{chk["result"]}</font>', "wf_line"))
        if st.get("next"):
            card.append(P(f"→ {st['next']}", "wf_next"))
        rows.append([P(st["stage"], "wf_round"), card])
    t = Table(rows, colWidths=[24 * mm, TEXT_W - 24 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBEFORE", (1, 0), (1, -1), 2, colors.HexColor(RED)),
                           ("LEFTPADDING", (1, 0), (1, -1), 10), ("LEFTPADDING", (0, 0), (0, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor(GRID))]))
    key = P("<b>How to read:</b> " + " ".join(f'{chip(k)} {v}' for k, v in legend["layers"].items()) + "<br/>"
            + " ".join(f'{pill(k, k)} {v}' for k, v in legend["statuses"].items()), "wf_line")
    return [key, Spacer(1, 6), t]


def render(b):
    k = b["type"]
    if k == "lead":
        return [boxed([P(b["text"], "band")], RED, pad=12), Spacer(1, 10)]
    if k == "text":
        p = P(b["text"])
        p.keepWithNext = b["text"].rstrip().endswith(":")
        return [p]
    if k == "bullets":
        return [Paragraph(x, S["bullet"], bulletText="–") for x in b["items"]]
    if k == "numbered":
        return [Paragraph(x, S["bullet"], bulletText=f"{i:02d}") for i, x in enumerate(b["items"], 1)]
    if k == "kpis":
        return [kpis(b["items"]), Spacer(1, 10)]
    if k == "callout":
        return [Spacer(1, 2), boxed([P(f'<font color="{RED}"><b>{b["title"]}</b></font> {b["text"]}')], RED_SOFT, RED), Spacer(1, 8)]
    if k == "math":
        lines = [P(f'<b>{b["title"]}</b>', "math")] + [P(x, "math") for x in b["lines"]]
        return [boxed(lines, PANEL, CHARCOAL), Spacer(1, 8)]
    if k == "table":
        return [table(b["rows"], b["widths"], b.get("status_col"), b.get("layer_col")), Spacer(1, 8)]
    if k == "chart":
        return [KeepTogether([CHARTS[b["chart"]["kind"]](b["chart"]), P(b["chart"]["source"], "caption")])]
    if k == "workflow":
        return workflow(b["steps"], b["legend"])
    raise ValueError(f"Unknown block type: {k}")


# ---------------------------------------------------------------- document
def build(content: dict, out: Path) -> int:
    """Render the report and return its page count; refuse reports over MAX_PAGES."""
    meta, secs = content["meta"], content["sections"]
    known = {s for _, _, ss, _ in CHAPTERS for s in ss} | {"glossary", "how_to_read"}
    if set(secs) - known:
        raise ValueError(f"Unknown sections: {set(secs) - known}")
    doc = DocTemplate(str(out), meta, title=meta["title"], author=meta.get("author", ""), subject=meta["question"])
    toc = TableOfContents(dotsMinLevel=-1)
    toc.levelStyles = [style("toc0", fontSize=10.5, leading=22, textColor=INK)]
    story = [NextPageTemplate("body"), PageBreak(),
             Paragraph("Table of contents", S["kicker"]), Paragraph(meta["short_title"], S["chapter"]), Spacer(1, 6),
             Table([[""]], colWidths=[22 * mm], rowHeights=[1.6], hAlign="LEFT",
                   style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(INK))]),
             Spacer(1, 10), toc, Spacer(1, 8)]
    if secs.get("how_to_read"):
        story += [P("How to read this report", "sub")] + [Paragraph(x, S["bullet"], bulletText="–")
                                                          for x in secs["how_to_read"]["items"]]
    if secs.get("glossary"):
        story += [P("Terms used in this report", "sub"), table([["Term", "Meaning"]] + secs["glossary"]["items"], [0.24, 0.76])]
    first = True
    for number, title, keys, new_page in CHAPTERS:
        present = [k for k in keys if secs.get(k)]
        if not present:
            continue
        if new_page or first:
            story.append(PageBreak())
        else:
            story += [CondPageBreak(60 * mm), Spacer(1, 16)]
        first = False
        story += [ChapterOpener(number, title), Spacer(1, 4)]
        for key in present:
            blocks = [render(b) for b in secs[key]["blocks"]]
            if SUBHEAD.get(key):
                head = P(SUBHEAD[key], "sub")
                if blocks and secs[key]["blocks"][0]["type"] == "chart":
                    blocks[0] = [KeepTogether([head] + blocks[0])]  # a subheading never sits apart from its chart
                else:
                    story.append(head)
            for items in blocks:
                story += items
    doc.multiBuild(story)
    if doc.pages_drawn > MAX_PAGES:
        Path(out).unlink(missing_ok=True)
        raise PageLimitError(f"Report has {doc.pages_drawn} pages; the limit is {MAX_PAGES}. Shorten the content.")
    return doc.pages_drawn


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 report_pdf.py content.json output.pdf")
    try:
        pages = build(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]))
    except PageLimitError as exc:
        sys.exit(f"Not written: {exc}")
    print(f"Wrote {sys.argv[2]} ({pages} pages)")
