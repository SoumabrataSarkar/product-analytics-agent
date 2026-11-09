"""Build the one-page write-up PDF (submission/write-up.pdf) in the investigation report's visual style.

Usage, from the repository root:  python3 docs/deliverables/build_write_up.py [output.pdf]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import report_pdf as T  # noqa: E402  (registers fonts R/B/I and exposes the design tokens)

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

PAGE_W, PAGE_H = A4
M = 13 * mm
W = PAGE_W - 2 * M - 12  # frame padding (6 pt each side)
C = colors.HexColor


def st(name, **kw):
    base = dict(fontName="R", fontSize=8.1, leading=10.4, textColor=C(T.INK))
    base.update(kw)
    return ParagraphStyle(name, **base)


BODY = st("body", fontSize=8.3, leading=10.8)
SMALL = st("small", fontSize=7.3, leading=9.2, textColor=C(T.INK2))
CELL = st("cell", fontSize=7.0, leading=8.6)
CELLB = st("cellb", fontName="B", fontSize=7.0, leading=8.6)
HEAD = st("head", fontName="B", fontSize=7.2, leading=8.9, textColor=colors.white)
BUL = st("bul", fontSize=7.9, leading=10.1, leftIndent=9, bulletIndent=0, spaceBefore=0.6)


def h2(num, text):
    return Table([[Paragraph(f'<font color="{T.RED}">{num}</font>', st("n", fontName="B", fontSize=10.5, leading=12)),
                   Paragraph(text, st("h", fontName="B", fontSize=10.5, leading=12))]],
                 colWidths=[8 * mm, W - 8 * mm],
                 style=[("LINEBELOW", (0, 0), (-1, -1), 0.8, C(T.INK)), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 6)])


def bullets(items):
    return [Paragraph(t, BUL, bulletText="•") for t in items]


def table(rows, widths, status_col=None):
    data = [[Paragraph(c, HEAD) for c in rows[0]]] + [
        [Paragraph(c, CELLB if j == 0 else CELL) for j, c in enumerate(r)] for r in rows[1:]]
    s = [("BACKGROUND", (0, 0), (-1, 0), C(T.CHARCOAL)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
         ("LINEBELOW", (0, 1), (-1, -1), 0.4, C(T.RULE)), ("TOPPADDING", (0, 0), (-1, -1), 2),
         ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 3),
         ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    return Table(data, colWidths=widths, style=s)


def architecture():
    """Flow of one investigation, the shared files it reads, and the data layers it queries."""
    h = 41 * mm
    d = Drawing(W, h)
    steps = [("1 Clarify", "metric, period,", "population; asks", "if ambiguous"),
             ("2 Verify definition", "metric exists and", "its definition in", "registry + catalog"),
             ("3 Route to a layer", "Gold if it fits;", "Silver for detail;", "Bronze for raw audit"),
             ("4 Query + evidence", "read-only, bounded;", "one log per query,", "never overwritten"),
             ("5 Test hypotheses", "≤3 per round,", "≤3 rounds; stop", "when explained"),
             ("6 Report", "pattern ≠ cause;", "fixed PDF", "template, ≤10 pages")]
    n, gap = len(steps), 2.6 * mm
    bw = (W - (n - 1) * gap) / n
    top, bh = h - 0.5 * mm, 17.5 * mm
    for i, (t, *lines) in enumerate(steps):
        x = i * (bw + gap)
        d.add(Rect(x, top - bh, bw, bh, fillColor=C(T.PANEL), strokeColor=C(T.RULE), strokeWidth=0.6))
        d.add(Rect(x, top - 1.3 * mm, bw, 1.3 * mm, fillColor=C(T.RED), strokeColor=None))
        d.add(String(x + 2 * mm, top - 5.6 * mm, t, fontName="B", fontSize=7.4, fillColor=C(T.INK)))
        for k, ln in enumerate(lines):
            d.add(String(x + 2 * mm, top - 9.4 * mm - k * 2.9 * mm, ln, fontName="R", fontSize=6.6, fillColor=C(T.INK2)))
        if i < n - 1:
            ax, ay = x + bw + 0.3 * mm, top - bh / 2
            d.add(Polygon([ax, ay + 1.3 * mm, ax + gap - 0.6 * mm, ay, ax, ay - 1.3 * mm], fillColor=C(T.RED), strokeColor=None))
    # Shared knowledge band
    y2 = top - bh - 3 * mm
    d.add(Rect(0, y2 - 7 * mm, W * 0.58, 7 * mm, fillColor=colors.white, strokeColor=C(T.INK), strokeWidth=0.6))
    lab = "Read by every run, in Claude Code or Codex:"
    d.add(String(2 * mm, y2 - 4.6 * mm, lab, fontName="B", fontSize=6.9, fillColor=C(T.INK)))
    from reportlab.pdfbase.pdfmetrics import stringWidth
    d.add(String(2 * mm + stringWidth(lab, "B", 6.9) + 2 * mm, y2 - 4.6 * mm,
                 "AGENTS.md · SKILL.md · catalog · registry", fontName="R", fontSize=6.9, fillColor=C(T.INK2)))
    d.add(Rect(W * 0.60, y2 - 7 * mm, W * 0.40, 7 * mm, fillColor=C(T.RED_SOFT), strokeColor=C(T.RED), strokeWidth=0.6))
    d.add(String(W * 0.60 + 2 * mm, y2 - 4.6 * mm, "Guardrails: read-only authorizer · row and time limits",
                 fontName="R", fontSize=6.9, fillColor=C(T.INK)))
    # Layers
    y3 = y2 - 9.5 * mm
    layers = [("Gold", "8 monthly tables · fast standard answers", T.LAYER["Gold"]),
              ("Silver", "10 cleaned tables · detail for investigations", T.LAYER["Silver"]),
              ("Bronze", "20 views over raw tables · audits", T.LAYER["Bronze"])]
    lw = (W - 2 * gap) / 3
    for i, (nm, txt, col) in enumerate(layers):
        x = i * (lw + gap)
        d.add(Rect(x, y3 - 8 * mm, lw, 8 * mm, fillColor=C(col), strokeColor=None))
        d.add(String(x + 2 * mm, y3 - 3.6 * mm, nm, fontName="B", fontSize=7.2, fillColor=C(T.INK)))
        d.add(String(x + 2 * mm, y3 - 6.6 * mm, txt, fontName="R", fontSize=6.6, fillColor=C(T.INK)))
    d.add(String(0, y3 - 11.2 * mm, "One SQLite database; layers built in one transaction with 122 reconciliation checks. "
                 "Step 3 decides which layer each query reads.", fontName="I", fontSize=6.5, fillColor=C(T.MUTED)))
    return d


GREEN, YELLOW, PINK = "#dcefe2", "#fbf1cc", "#f8dcd8"
GREEN_D, YELLOW_D, RED_D = "#3c8d5a", "#b8860b", "#c0533f"
R1 = {"Q02": "F", "Q07": "F", "Q11": "P"}
R2 = {"Q11": "P"}


def scorecard():
    """Two rows of 18 chips, one per question, coloured by outcome in each round."""
    h = 17 * mm
    d = Drawing(W, h)
    lab_w, gap = 17 * mm, 1.1 * mm
    cw = (W - lab_w - 17 * gap) / 18
    fill = {"S": (GREEN, GREEN_D), "P": (YELLOW, YELLOW_D), "F": (PINK, RED_D)}
    for r, (name, res) in enumerate((("Round 1", R1), ("Round 2", R2))):
        y = h - (r + 1) * 6.4 * mm
        d.add(String(0, y + 1.9 * mm, name, fontName="B", fontSize=7.2, fillColor=C(T.INK)))
        for i in range(18):
            q = f"Q{i + 1:02d}"
            k = res.get(q, "S")
            bg, fg = fill[k]
            x = lab_w + i * (cw + gap)
            d.add(Rect(x, y, cw, 5.4 * mm, fillColor=C(bg), strokeColor=C(fg), strokeWidth=0.5))
            d.add(String(x + cw / 2, y + 1.9 * mm, q, fontName="B" if k != "S" else "R", fontSize=6.3,
                         fillColor=C(fg if k != "S" else T.INK2), textAnchor="middle"))
    y = 0.6 * mm
    x = lab_w
    for lab, k in (("Pass", "S"), ("Partial", "P"), ("Fail (strict rule)", "F")):
        bg, fg = fill[k]
        d.add(Rect(x, y, 3 * mm, 2.6 * mm, fillColor=C(bg), strokeColor=C(fg), strokeWidth=0.5))
        d.add(String(x + 4 * mm, y + 0.5 * mm, lab, fontName="R", fontSize=6.6, fillColor=C(T.INK2)))
        x += 4 * mm + len(lab) * 1.35 * mm + 5 * mm
    d.add(String(W, y + 0.5 * mm, "Round 1: 15 pass · 1 partial · 2 fail      Round 2: 17 · 1 · 0",
                 fontName="B", fontSize=6.8, fillColor=C(T.INK), textAnchor="end"))
    return d


def type_table():
    rows = [
        ("S", "Simple numbers and filters", "Q01 Q05 Q08 Q17 Q18", "All pass", "Exact to the user and the cent"),
        ("S", "Vague or ambiguous questions", "Q03 Q10 Q15 Q18", "All pass", "Asked before choosing a metric, period or meaning"),
        ("S", "Unanswerable question", "Q16", "Pass", "Declined and named the data that's missing"),
        ("S", "Data-quality traps", "Q12 Q13 Q14", "All pass", "Caught both planted issues; didn't claim to have detected a reviewed one"),
        ("S", "Comparisons and lifecycle", "Q04 Q06 Q09", "All pass", "Right time basis; groups reconcile to the total"),
        ("F", "Cohort conversion", "Q07", "Fail → Pass", "Used April, the month the subscriber base forms, as a normal baseline. "
         "A new skill rule fixed it"),
        ("P", "Funnel drop-off", "Q11", "Partial", "Right answer and gaps, but read April's start-up as a funnel decline; "
         "the new rule didn't trigger here"),
        ("F", "GM investigation", "Q02", "Fail → Pass", "v1: headline numbers and story right, but some conclusions stated more firmly than the "
         "evidence allowed. After review, three certainty rules joined the skill and the agent's v2 passed; the issue didn't recur in 17 later runs"),
    ]
    head = ["Question type", "Questions", "Result", "What happened"]
    data = [[Paragraph(c, HEAD) for c in head]]
    style = [("BACKGROUND", (0, 0), (-1, 0), C(T.CHARCOAL)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("LINEBELOW", (0, 1), (-1, -1), 0.6, colors.white)]
    bg = {"S": GREEN, "P": YELLOW, "F": PINK}
    fg = {"S": GREEN_D, "P": YELLOW_D, "F": RED_D}
    for i, (k, t, q, res, note) in enumerate(rows, start=1):
        data.append([Paragraph(t, CELLB), Paragraph(q, CELL),
                     Paragraph(f'<font color="{fg[k]}"><b>{res}</b></font>', CELL), Paragraph(note, CELL)])
        style.append(("BACKGROUND", (0, i), (-1, i), C(bg[k])))
    return Table(data, colWidths=[W * 0.21, W * 0.17, W * 0.11, W * 0.51], style=style)


def header(c, doc):
    c.saveState()
    c.setFillColor(C(T.RED)); c.circle(M + 2.2 * mm, PAGE_H - 11 * mm, 2.2 * mm, stroke=0, fill=1)
    c.setFillColor(C(T.INK)); c.setFont("B", 9.5); c.drawString(M + 7 * mm, PAGE_H - 12.3 * mm, "Product Analytics Agent")
    c.setFillColor(C(T.RED)); c.setFont("B", 11); c.drawRightString(PAGE_W - M, PAGE_H - 12.4 * mm, "+ + +")
    c.setFillColor(C(T.MUTED)); c.setFont("R", 6.8)
    c.drawString(M, 5.5 * mm, "PocketToons Lead Product Analyst assignment · one-page write-up · evidence: docs/evaluations/results.md")
    c.restoreState()


def build(out):
    story = [Paragraph(f'<font color="{T.RED}">Write-up</font>', st("t", fontName="B", fontSize=17, leading=19)),
             Paragraph("An analyst co-pilot that clarifies, checks definitions, picks the right data layer and shows its evidence.",
                       st("sub", fontSize=8.2, leading=10, textColor=C(T.INK2)))]

    story += [h2("01", "What I built and why"), Spacer(1, 2 * mm), architecture(), Spacer(1, 3 * mm)]
    story += bullets([
        "<b>Clarifies instead of assuming.</b> When the metric, period or meaning is open, it asks first and states every assumption it keeps.",
        "<b>Verifies the metric before computing it.</b> It confirms the metric exists and uses its approved definition and SQL from the "
        "metric registry, plus joins and known gaps from the data catalog. Unsupported requests are declined, not improvised.",
        "<b>Maps the question to a layer for speed.</b> Gold answers standard monthly questions directly; Silver keeps per-user detail; "
        "Bronze is only for auditing raw values. Fewer, smaller queries keep answers fast.",
        "<b>Evidence for every number and LLM-neutral by design.</b> Each query is logged with its SQL, layer and metric version. Definitions, "
        "rules and guardrails live in files, not prompts, so Claude Code and Codex behave the same and a lesson becomes a rule for every later run.",
    ])

    story += [h2("02", "How it performed: 18 blind test questions, two rounds"), Spacer(1, 2 * mm), scorecard(), Spacer(1, 2 * mm),
              type_table(), Spacer(1, 1.2 * mm),
              Paragraph("Scored against values computed beforehand from the raw tables. Correct numbers alone don't pass: a silent choice of "
                        "definition, a missing caveat or an overstated conclusion fails. Round 2: Q02 is the agent's v2 after review; Q07 and Q11 were rerun, "
                        "with Q01 and Q09 to check nothing broke; other results carry over. "
                        "<b>Hardest:</b> comparisons that need context the data doesn't announce, such as a start-up month.", SMALL)]

    story += [h2("03", "Running it for a 20-person product team"), Spacer(1, 1.6 * mm)]
    lat = [[Paragraph("<b>Time to answer</b> (observed)", CELL), Paragraph("<b>Simple</b> (MAU by month): 2–3 min", CELL),
            Paragraph("<b>Normal</b> (refund impact): 5–6 min", CELL), Paragraph("<b>Complex</b> (MAU up, revenue flat): 10–12 min", CELL)]]
    story.append(Table(lat, colWidths=[W * 0.19, W * 0.24, W * 0.25, W * 0.32],
                       style=[("BACKGROUND", (0, 0), (-1, -1), C(T.PANEL)), ("LINEBEFORE", (1, 0), (-1, -1), 0.6, colors.white),
                              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                              ("LEFTPADDING", (0, 0), (-1, -1), 4)]))
    story.append(Spacer(1, 1 * mm))
    story += bullets([
        "<b>Set-up for real data:</b> first build a data catalog and metric registry for the team's warehouse; the agent relies on both.",
        "<b>Cost (estimate):</b> running the 18 questions twice used about half of one 5-hour window on an INR 1,999-a-month Codex plan, so one "
        "seat covers a heavy day of questions: about INR 1,999 per active analyst a month. Token cost per run wasn't measured.",
        "<b>Lower cost and latency:</b> answer from the smallest layer that fits, with targeted queries instead of raw scans.",
        "<b>Guardrails:</b> data is only ever read: a read-only database role on a replica plus the query tool's read-only check, row and "
        "time limits; every figure traceable to its evidence log; sensitive columns kept out of the catalog.",
        "<b>Freshness:</b> real data keeps arriving, unlike this static dataset. Add a freshness tracker (last load per source and layer) "
        "that the agent checks first, warning or stopping when data is stale.",
        "<b>Quality over time:</b> rerun the 18 questions on every change to the skill, registry or data; track pass rate, clarification "
        "rate and query errors; review a weekly sample of real questions and turn failures into rules.",
    ])

    story += [h2("04", "With more time"), Spacer(1, 1.6 * mm)]
    story += bullets([
        "Run the same questions in both runtimes for a direct Claude vs Codex comparison, plus held-out questions.",
        "Log tokens and time per run to replace the cost estimate with a measured cost per question.",
        "A short-answer mode for simple questions; a helper that drafts the catalog for a new database; a Slack or web front end.",
    ])
    story += [Spacer(1, 1.8 * mm), Paragraph(
        "<b>Note on tools.</b> Claude Code (Claude Opus 5.5, medium) built the framework, ran the GM investigation and computed the answer key. "
        "Codex (GPT Terra 6.1, medium) ran the evaluation, so the agent was tested in a runtime that didn't build it. ChatGPT (Terra 5.6, "
        "later 6.1, medium) reviewed the GM report and evaluation decisions independently.", st("note", fontSize=7, leading=9, textColor=C(T.MUTED)))]

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=16 * mm, bottomMargin=9.5 * mm,
                            title="Write-up", author="Soumabrata Sarkar")
    doc.build(story, onFirstPage=header, onLaterPages=header)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "submission" / "write-up.pdf"
    build(out)
    from pypdf import PdfReader
    pages = len(PdfReader(str(out)).pages)
    print(out, pages, "page(s)")
    if pages > 1:
        raise SystemExit("write-up must fit on one page")
