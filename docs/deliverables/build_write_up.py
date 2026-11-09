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
CELL = st("cell", fontSize=7.2, leading=8.9)
CELLB = st("cellb", fontName="B", fontSize=7.2, leading=8.9)
HEAD = st("head", fontName="B", fontSize=7.2, leading=8.9, textColor=colors.white)
BUL = st("bul", fontSize=8.3, leading=10.8, leftIndent=8, bulletIndent=0, spaceBefore=0.6)


def h2(num, text):
    return Table([[Paragraph(f'<font color="{T.RED}">{num}</font>', st("n", fontName="B", fontSize=10.5, leading=12)),
                   Paragraph(text, st("h", fontName="B", fontSize=10.5, leading=12))]],
                 colWidths=[8 * mm, W - 8 * mm],
                 style=[("LINEBELOW", (0, 0), (-1, -1), 0.8, C(T.INK)), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 5)])


def bullets(items):
    return [Paragraph(t, BUL, bulletText="–") for t in items]


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
    h = 44 * mm
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
    y2 = top - bh - 4 * mm
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
    y3 = y2 - 11 * mm
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


def header(c, doc):
    c.saveState()
    c.setFillColor(C(T.RED)); c.circle(M + 2.2 * mm, PAGE_H - 11 * mm, 2.2 * mm, stroke=0, fill=1)
    c.setFillColor(C(T.INK)); c.setFont("B", 9.5); c.drawString(M + 7 * mm, PAGE_H - 12.3 * mm, "Product Analytics Agent")
    c.setFillColor(C(T.RED)); c.setFont("B", 11); c.drawRightString(PAGE_W - M, PAGE_H - 12.4 * mm, "+ + +")
    c.setFillColor(C(T.MUTED)); c.setFont("R", 6.8)
    c.drawString(M, 7 * mm, "PocketToons Lead Product Analyst assignment · one-page write-up · evidence: docs/evaluations/results.md")
    c.restoreState()


def build(out):
    story = [Paragraph(f'<font color="{T.RED}">Write-up</font>', st("t", fontName="B", fontSize=17, leading=19)),
             Paragraph("An analyst co-pilot that clarifies, checks definitions, picks the right data layer and shows its evidence.",
                       st("sub", fontSize=8.6, leading=11, textColor=C(T.INK2))), Spacer(1, 1 * mm)]

    story += [h2("01", "What I built and why"), Spacer(1, 1.5 * mm), architecture(), Spacer(1, 1 * mm)]
    story += bullets([
        "<b>Clarifies instead of assuming.</b> When the metric, period or meaning is open, it asks first, as it did in all four "
        "evaluation questions that needed it (\"which period?\", \"what counts as mobile?\"), and it states every assumption it keeps.",
        "<b>Verifies the metric before computing it.</b> It checks that the metric exists and reads its approved, versioned definition "
        "and SQL in the metric registry, plus grains, joins and known gaps in the data catalog. Unsupported requests are declined, not improvised.",
        "<b>Maps the question to a layer for speed.</b> Gold answers standard monthly questions in milliseconds and is reconciled; "
        "Silver keeps per-user and per-event detail; Bronze is used only to audit raw values.",
        "<b>Evidence for every number.</b> Each query writes its SQL, layer, metric version and row count to its own log, so any figure "
        "in a report can be traced.",
        "<b>LLM-neutral by design.</b> Definitions, rules and guardrails live in files, not prompts, so Claude Code and Codex behave the "
        "same and a failure becomes a rule that every later run reads. Trade-off: no UI; quality depends on the agent following the skill.",
    ])
    story.append(Paragraph("<b>Tools.</b> Claude Code (Claude Opus 5.5, medium) built the framework, ran the GM investigation and computed "
                           "the answer key. Codex (GPT Terra 6.1, medium) ran 17 of 18 evaluation runs, testing the agent in a runtime that "
                           "didn't build it. ChatGPT (Terra 5.6, later 6.1, medium) was the independent reviewer.", SMALL))

    story += [h2("02", "Where it breaks: before and after one improvement round"), Spacer(1, 1.5 * mm)]
    story.append(table([
        ["Failure mode", "Where", "Round 1", "What changed", "Round 2"],
        ["Stating a cause the data can't prove; mixed comparison periods", "GM report v1 (Q02)", "Fail",
         "Skill rules: pattern ≠ cause; exact periods; quantify or say \"unknown\"", "Not seen again in 17 later runs"],
        ["First month used as a normal baseline (subscriber base starts at zero)", "Q07 cohorts", "Fail",
         "Rule: check for a start-up period before using it as a baseline", "Pass"],
        ["Same, in a trend description", "Q11 funnel", "Partial", "(same rule)", "Partial: rule didn't trigger"],
        ["Harmless registry-version warning repeated", "All runs", "18 of 18", "Change verified as docs-only and recorded", "3 of 4"],
        ["<b>Overall, 18 questions (pass / partial / fail)</b>", "", "<b>15 / 1 / 2</b>", "", "<b>16 / 1 / 1</b>"],
    ], [W * 0.25, W * 0.12, W * 0.17, W * 0.26, W * 0.20]))
    story += [Spacer(1, 1 * mm), Paragraph(
        "<b>Hardest:</b> comparisons that need context the data doesn't announce, such as a start-up month. <b>Strongest:</b> ambiguity "
        "and traps: it asked when it should have, declined the unanswerable question and caught both planted data-quality issues. "
        "Every answer was scored blind against values computed beforehand from the raw tables.", BODY)]

    story += [h2("03", "Running it for a 20-person product team"), Spacer(1, 1.2 * mm)]
    story.append(table([
        ["Question type", "Example", "Time to answer (observed)"],
        ["Simple", "MAU by month; US subscribers", "2–3 minutes"],
        ["Normal", "Refund impact; funnel drop-off", "5–6 minutes"],
        ["Complex", "MAU up 20% but revenue flat: why?", "10–12 minutes, report included"],
    ], [W * 0.18, W * 0.42, W * 0.40]))
    story += bullets([
        "<b>Access and guardrails:</b> a read-only role on a warehouse replica; the query tool's limits stay on; sensitive columns kept out of the catalog (not built yet).",
        "<b>Cost:</b> not measured here; log tokens per run before setting a per-question budget.",
        "<b>Quality over time:</b> the 18 questions become a regression suite, rerun whenever the skill, registry or data model changes; "
        "track pass rate, clarification rate and query errors; review a weekly sample of real questions. Failures become rules, then a rerun.",
    ])

    story += [h2("04", "With more time"), Spacer(1, 1 * mm)]
    story += bullets([
        "Make the start-up check apply whenever the first month looks unusual, not only when choosing a baseline (the remaining Q11 issue).",
        "Run the same questions in both runtimes for a direct Claude vs Codex comparison; add held-out questions.",
        "Measure cost per run; a short-answer mode for simple questions; a machine-readable catalog; a simple UI.",
    ])

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=17 * mm, bottomMargin=11 * mm,
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
