"""Build the detailed evaluation-results PDF (submission/eval-results.pdf) in the report's visual style.

Usage, from the repository root:  python3 docs/evaluations/build_results_pdf.py [output.pdf]
Content mirrors docs/evaluations/results.md and the scored records in evaluation-results/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "docs" / "deliverables"))
import report_pdf as T  # noqa: E402  (fonts and design tokens)
import build_write_up as WU  # noqa: E402  (scorecard and table helpers in the same style)

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table)

C = colors.HexColor
REPO = "https://github.com/SoumabrataSarkar/product-analytics-agent"
TREE = f"{REPO}/tree/main"
BLOB = f"{REPO}/blob/main"
W = WU.W
st, BODY, SMALL, CELL, CELLB, HEAD = WU.st, WU.BODY, WU.SMALL, WU.CELL, WU.CELLB, WU.HEAD
MONO = st("mono", fontSize=6.6, leading=8.2, textColor=C(T.INK2))
LINK = st("link", fontSize=6.6, leading=8.2, textColor=C("#1f4e8c"))

# id, type, runtime, question, expected, agent result, round 1, round 2, folders
TESTS = [
    ("Q01", "Simple aggregate; time comparison", "Codex",
     "How did monthly active users change across the available months?",
     "MAU Apr–Sep: 7,937 · 9,134 · 9,976 · 10,138 · 10,871 · 11,447; +3,510 (+44.2%). Complete UTC months, distinct users; "
     "unidentified sessions excluded and not counted as people; metric version stated; months never summed.",
     "Every month exact, with month-on-month changes. Stated mau v1.1, excluded unidentified sessions (2,286–3,703 a month) "
     "and recounted from Silver, matching Gold. Round 2 identical.", "S", "S", ["Q01/codex-run-001", "Q01/codex-run-002"]),
    ("Q02", "Multi-step investigation (GM question)", "Claude Code",
     "MAU is up 20% QoQ but revenue is flat. What's happening and what should we do?",
     "Avg MAU 9,015.7 → 10,818.7 (+20.0%); net revenue $30,145.00 → $30,166.97 (+0.07%); paying users ~1,036 flat. Growth "
     "from new users (paid social +1,841); cohorts compared on complete windows; patterns stated as associations, not causes.",
     "v1: numbers exact and story right, but some conclusions too firm (cause stated, two hypotheses rejected too firmly, "
     "data-quality impact called \"none\"), conversion periods mislabelled and a monthly/quarterly mix-up. v2 after review: "
     "all points addressed. Blind rerun on the updated skill: numbers exact, review points fixed; minor wording issues.",
     "F", "S", ["Q02/run-001", "Q02/run-002-blind"]),
    ("Q03", "Decomposition; vague period", "Codex",
     "Which acquisition sources contributed most to the change in active users?",
     "Ask for or state the period. For the weeks the evaluator chose when asked (27 Jul–2 Aug vs 17–23 Aug; values computed after the run): WAU 5,914 → 5,831; organic "
     "−213, paid social +182, paid search −52, unknown 67 → 67 shown separately; no causal claim.",
     "Asked daily, weekly or monthly, then full Monday–Sunday weeks. Every figure exact; unknown kept separate; warned the "
     "weeks aren't adjacent; \"arithmetic contributions, not evidence of cause\".", "S", None, ["Q03/codex-run-001"]),
    ("Q04", "Comparison of two metrics", "Codex", "Did engaged users grow with active users?",
     "MEU 4,873 → 6,734 (+38.2%) vs MAU +44.2%; engagement rate 61.4% → 58.8%; 60-second rule with watch time allocated to the month.",
     "All six months exact; threshold and allocation stated; paid-social engagement split shown as an association.",
     "S", None, ["Q04/codex-run-001"]),
    ("Q05", "Filter; overlapping slices", "Codex", "Did the platform mix change?",
     "No material change. Sep: Android 6,312, iOS 5,237, web 3,140 of 11,447 MAU; Aug 6,022 / 4,926 / 3,041; about 28% of users "
     "on 2+ platforms, so platform counts can't be added.",
     "Aug vs Sep exact, shares and overlap (28.5%, 28.2%) exact; explained that rows can't be summed; stated its comparison months.",
     "S", None, ["Q05/codex-run-001"]),
    ("Q06", "Lifecycle (growth accounting)", "Codex", "Are more users new, retained or returning?",
     "May–Sep new / retained / returning, e.g. May 2,201 / 4,757 / 2,176 and Sep 1,720 / 5,071 / 4,656; April can't be classified; "
     "groups reconcile to MAU; no causal language.",
     "Every month exact with shares of MAU; April excluded with the reason; reconciled. Headline said retained is largest "
     "without stressing that returning users doubled.", "S", None, ["Q06/codex-run-001"]),
    ("Q07", "Cohort conversion", "Codex", "Did newer signup cohorts convert to subscription at a lower rate?",
     "Yes: May–Jun 1.94% (94 / 4,854) vs Jul–Aug 0.53% (29 / 5,426). April flagged as the start-up month (no subscribers at the "
     "start); September excluded (window incomplete).",
     "Round 1: rates exact but April pooled into the baseline (Apr–Jun 2.59%), overstating the drop (79%). Round 2: May–Jun "
     "baseline, exact, April shown separately.", "F", "S", ["Q07/codex-run-001", "Q07/codex-run-002"]),
    ("Q08", "Simple aggregate (revenue)", "Codex", "How much net revenue came from subscriptions versus PPV?",
     "Apr–Sep: subscription $59,900.04, PPV $411.93, total $60,311.97 (PPV 0.68%); gross vs net; refunds to the original type; "
     "unattributed refunds reported even at $0.",
     "Exact to the cent with gross, refunds and net by type; booked at payment success; \"zero unattributed refunds\".",
     "S", None, ["Q08/codex-run-001"]),
    ("Q09", "Time comparison", "Codex", "Did refunds materially change the revenue comparison?",
     "No. Gross $30,182.93 → $30,192.92; refunds $37.93 → $25.95; net $30,145.00 → $30,166.97. Refunds change the size of a tiny "
     "increase, not the conclusion.",
     "Exact; same conclusion; sensitivity on the 13 corrected payments. Round 2 also flagged April and added a fair May–Jun vs "
     "Aug–Sep comparison (gross −1.466%, net −1.409%, both verified).", "S", "S", ["Q09/codex-run-001", "Q09/codex-run-002"]),
    ("Q10", "Ambiguous definition", "Codex", "How many subscription cancellations took effect during a period?",
     "State the meaning: access actually ended vs a cancellation request. August: 113 access losses, 92 requests. Use subscription "
     "history, not the user snapshot.",
     "Gave both (113 ended, 92 requests) with exact August boundaries from history; Bronze recount agreed.", "S", None,
     ["Q10/codex-run-001"]),
    ("Q11", "Funnel", "Codex", "Where do users drop from viewing a paywall to starting checkout and purchasing?",
     "Biggest drop before checkout. Subscription May–Sep: 39.4% start checkout, 27.6% of checkouts purchase; rates flat from May; "
     "April is the start-up month; link gaps reported.",
     "Main answer, unit and link gaps right (175 checkouts without a paywall link; 56 purchases without a checkout link). In both "
     "rounds read April's start-up as a funnel decline and pointed at a \"May transition\".", "P", "P",
     ["Q11/codex-run-001", "Q11/codex-run-002"]),
    ("Q12", "Ambiguous measure; data trap", "Codex", "Which episodes are watched most, and how much is actually completed?",
     "State the measure. Top: title c01 ep 3, 3,738 viewers and 8,014 views; completion 28.3%; overall 33.0% (35,017 / 105,989). "
     "Trap: premium c03 ep 13, 0 of 1,455 completed.",
     "Ranked by viewers and said so; every figure exact; flagged the 0-of-1,455 episode as unexplained without claiming a cause.",
     "S", None, ["Q12/codex-run-001"]),
    ("Q13", "Data-quality trap", "Codex", "Is an unusually large source payment real?",
     "No. Raw 999.0 USD on 7 payments is a reviewed 100× unit error; correct amount $9.99. Using raw values would overstate revenue "
     "by $6,923.07. Review time unknown; correction came from the review, not new detection.",
     "Exactly as expected, including the $6,923.07 impact and unknown review time; raw, curated and review shown separately.",
     "S", None, ["Q13/codex-run-001"]),
    ("Q14", "Missing data", "Codex", "Can we trust acquisition-channel conclusions when source values are missing?",
     "Yes at channel level: unknown is 135 of 13,600 signups (1.0%) and 238 users; kept separate; a sensitivity bound; no causal "
     "or campaign attribution.",
     "Exact; showed the ranking holds even with all unknowns assigned to one channel; no causal claim.", "S", None,
     ["Q14/codex-run-001"]),
    ("Q15", "Vague question (should clarify)", "Codex", "\"Performance is down. What happened?\"",
     "Ask which metric and period before analysing. For the agreed scope (net revenue, Sep vs Aug): $9,819.93 → $10,175.51 (+3.62%).",
     "Asked first; for the agreed scope every figure exact; showed the premise wasn't supported and suggested confirming the KPI.",
     "S", None, ["Q15/codex-run-001"]),
    ("Q16", "Unanswerable (should decline)", "Codex", "Which advertising campaign caused each user's purchase?",
     "Decline: there is no campaign-level exposure or user link; explain what can be compared and what data is needed; no "
     "fabricated join.",
     "Declined; showed there are no campaign fields; listed the data needed (campaign IDs, click events, holdouts).", "S", None,
     ["Q16/codex-run-001"]),
    ("Q17", "Filter (subscribers by country)", "Codex", "How many US users had an active subscription at the end of September?",
     "349 at 1 Oct 2026 00:00 UTC: 312 renewing plus 37 cancelled but paid up; the user's country.",
     "349 exact, with the 37 explained; history recount also 349.", "S", None, ["Q17/codex-run-001"]),
    ("Q18", "Filter; time comparison", "Codex", "How many mobile sessions were there in September versus August?",
     "Define mobile (iOS + Android). 36,295 → 38,366 (+5.7%) counting sessions that touch each month; same counting in both months.",
     "Asked what mobile means; August exact; September 38,365 by start month and 38,366 by overlap, both stated.", "S", None,
     ["Q18/codex-run-001"]),
]

FILL = {"S": (WU.GREEN, WU.GREEN_D, "Pass"), "P": (WU.YELLOW, WU.YELLOW_D, "Partial"), "F": (WU.PINK, WU.RED_D, "Fail")}


def outcome(code):
    if code is None:
        return Paragraph('<font color="#9a9a9a">not rerun</font>', CELL)
    bg, fg, lab = FILL[code]
    return Paragraph(f'<font color="{fg}"><b>{lab}</b></font>', CELL)


def detail_table():
    head = ["Test", "Expected (answer key)", "Agent result", "R1", "R2"]
    data = [[Paragraph(h, HEAD) for h in head]]
    style = [("BACKGROUND", (0, 0), (-1, 0), C(T.CHARCOAL)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("LINEBELOW", (0, 1), (-1, -1), 0.5, C(T.RULE))]
    for i, (qid, typ, rt, q, exp, act, r1, r2, folders) in enumerate(TESTS, start=1):
        links = "<br/>".join(f'<a href="{TREE}/evaluation-results/{f}" color="#1f4e8c">{f}</a>' for f in folders)
        first = [Paragraph(f'<font color="{T.RED}"><b>{qid}</b></font> · {typ}', CELLB),
                 Paragraph(f"<i>{q}</i>", CELL), Paragraph(f"Runtime: {rt}", MONO), Paragraph(links, LINK)]
        data.append([first, Paragraph(exp, CELL), Paragraph(act, CELL), outcome(r1), outcome(r2 if r2 else None)])
        final = r2 or r1
        style.append(("BACKGROUND", (3, i), (4, i), C(FILL[final][0])))
    return Table(data, colWidths=[W * 0.24, W * 0.30, W * 0.32, W * 0.07, W * 0.07], style=style, repeatRows=1)


def kv_table(rows, widths, head=None):
    data = ([[Paragraph(h, HEAD) for h in head]] if head else []) + [
        [Paragraph(c, CELLB if j == 0 else CELL) for j, c in enumerate(r)] for r in rows]
    s = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, C(T.RULE)),
         ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
         ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if head:
        s.append(("BACKGROUND", (0, 0), (-1, 0), C(T.CHARCOAL)))
    return Table(data, colWidths=widths, style=s, repeatRows=1 if head else 0)


def header(c, doc):
    PW, PH, M = WU.PAGE_W, WU.PAGE_H, WU.M
    c.saveState()
    c.setFillColor(C(T.RED)); c.circle(M + 2.2 * mm, PH - 11 * mm, 2.2 * mm, stroke=0, fill=1)
    c.setFillColor(C(T.INK)); c.setFont("B", 9.5); c.drawString(M + 7 * mm, PH - 12.3 * mm, "Product Analytics Agent")
    c.setFillColor(C(T.RED)); c.setFont("B", 11); c.drawRightString(PW - M, PH - 12.4 * mm, "+ + +")
    c.setFillColor(C(T.MUTED)); c.setFont("R", 6.8)
    c.drawString(M, 5.5 * mm, "PocketToons Lead Product Analyst assignment · evaluation results · source: docs/evaluations/results.md")
    c.drawRightString(PW - M, 5.5 * mm, f"{doc.page:02d}")
    c.restoreState()


def build(out):
    S = []
    S += [Paragraph(f'<font color="{T.RED}">Evaluation results</font>', st("t", fontName="B", fontSize=17, leading=19)),
          Paragraph("18 test questions run blind and scored against an answer key computed from the raw tables, with one improvement round.",
                    st("sub", fontSize=8.6, leading=11, textColor=C(T.INK2))), Spacer(1, 1 * mm)]

    S += [WU.h2("01", "Summary"), Spacer(1, 2 * mm), WU.scorecard(), Spacer(1, 2.5 * mm)]
    S.append(kv_table([
        ["Round 1", "15 pass · 1 partial · 2 fail", "Every question in a fresh session. Q02 in Claude Code; the other 17 in Codex."],
        ["Round 2", "17 pass · 1 partial · 0 fail", "After skill updates: Q02 revised after review and rerun blind; Q07 and Q11 rerun; "
                                                   "Q01 and Q09 rerun to check nothing broke; other results carry over."],
        ["Fixed", "Q02, Q07", "Overstated certainty and mixed periods (Q02); the start-up month used as a normal baseline (Q07)."],
        ["Still open", "Q11", "The start-up rule didn't trigger for a trend description; recorded as the next fix."],
        ["Strongest", "Ambiguity and traps", "Asked or stated a clear choice when the question was open (Q03, Q10, Q15, Q18), declined the unanswerable question (Q16) "
                                            "and caught both planted data issues (Q12, Q13)."],
    ], [W * 0.13, W * 0.25, W * 0.62]))
    S += [Spacer(1, 2 * mm), WU.type_table()]

    S += [WU.h2("02", "How the evaluation worked"), Spacer(1, 1.5 * mm)]
    S += WU.bullets([
        "<b>Questions:</b> 18 scenarios covering every type the brief lists: simple aggregates, filtered queries, time comparisons, "
        "cohorts, ambiguous and unanswerable questions, data-quality traps and a multi-step investigation "
        f'(<a href="{BLOB}/docs/evaluations/investigation-paths.md" color="#1f4e8c">investigation-paths.md</a>).',
        "<b>Independent references:</b> expected values were computed with the metric registry's SQL on the <b>raw source tables only</b>, never "
        "on the Silver and Gold tables the agent uses. Q02 used reviewer source checks; other scenarios used approved answer-key batches. In Q03, the evaluator chose weeks "
        "outside the initial key, so their values were computed after the run using the same method. The reference queries are kept as "
        "evidence logs.",
        "<b>Who scored:</b> Claude Code scored every run against the key. The GM report (Q02 v1) was also reviewed independently with "
        "ChatGPT, and the project owner decided the borderline calls.",
        "<b>Blind runs:</b> one fresh session per question with the same prompt; the agent was told not to read evaluation files, earlier "
        "reports or the data generator's notes. When it asked a question, the reply named a choice only (e.g. \"Monthly, Q2 vs Q3 2026\").",
        "<b>Scoring:</b> exact counts and cents; rates within 0.1 point. Behaviour counts too: a conclusion firmer than the evidence, a "
        "silent choice of period or definition, or a missing required caveat fails even when the numbers are right.",
        "<b>Improvement loop:</b> each failure became a general rule in the shared skill (never a question-specific answer); failed "
        "questions and two passing ones were rerun in fresh sessions on the updated version.",
        "<b>Snapshot:</b> pockettoons.sqlite (SHA-256 8d39e78b…790b), build 3a0dbed2 with 122 of 122 layer checks passed; April–September "
        "2026, complete UTC months.",
    ])

    S += [PageBreak(), WU.h2("03", "Every test: expected vs actual"), Spacer(1, 1.5 * mm),
          Paragraph("R1 = round 1, R2 = round 2. Each folder link opens the run's scoring record, the agent's unedited output and its "
                    "evidence logs on GitHub.", SMALL), Spacer(1, 1.5 * mm), detail_table()]

    S += [PageBreak(), WU.h2("04", "What failed, why, and what changed"), Spacer(1, 1.5 * mm)]
    S.append(kv_table([
        ["Conclusions firmer than the evidence: a cause stated from an association; two hypotheses rejected too firmly; data-quality "
         "impact called \"none\"", "Q02 v1", "Skill rules: separate pattern from cause; quantify data-quality scope and impact or say "
         "\"unknown\"; keep unexplained anomalies open", "Not seen in the 17 Codex runs; the blind Q02 rerun passed but still worded two data-quality impacts a little too firmly"],
        ["Comparison periods mislabelled; a monthly amount compared with quarterly revenue", "Q02 v1",
         "Skill rule: exact periods, the same time basis, explicit start and end boundaries", "Not seen again"],
        ["The first month of data used as a normal baseline (the subscriber base starts at zero in April)", "Q07, Q11",
         "Skill rule: check whether the first period is a start-up period before using it as a baseline", "Q07 fixed and Q09 applied it "
         "correctly; Q11 unchanged because the question isn't phrased as a comparison"],
        ["A harmless registry-version warning repeated in every report", "All runs",
         "Verified the change since the build is documentation only (all 56 SQL definitions identical) and recorded it",
         "Still raised in 3 of 4 Codex round-2 runs; the blind Q02 run read the note and handled it correctly"],
    ], [W * 0.31, W * 0.10, W * 0.32, W * 0.27], head=["Failure", "Where", "What changed", "Result"]))
    S += [Spacer(1, 2 * mm), Paragraph(
        "<b>Hardest question type:</b> comparisons that need context the data doesn't announce, such as a start-up month. The agent "
        "computes correctly but only questions the fairness of a comparison when a rule names the situation.", BODY)]

    S += [WU.h2("05", "The GM question in detail (Q02)"), Spacer(1, 1.5 * mm)]
    S.append(kv_table([
        ["v1 (round 1)", "The agent's own report in Claude Code. Numbers and story right; scored Fail under the strict rule for "
                         "overstated conclusions, mislabelled periods and a monthly/quarterly mix-up."],
        ["Review", "A reviewer checked v1 against the evidence and source data: seven substance points plus format feedback, kept "
                   "word for word."],
        ["v2", "The agent's revision after that review: every point addressed and confirmed by five extra checks (17–21). This is the "
               "board report in the submission."],
        ["Blind rerun", "A fresh Claude Code agent on the updated skill, given only the standard prompt and a clean repository copy (no review, answer key or earlier reports; told not to read anything else): numbers exact, "
                        "material review points fixed, start-up month handled; two data-quality statements and one rejected "
                        "hypothesis still a little too firm. Pass with minor issues."],
    ], [W * 0.15, W * 0.85]))

    S += [WU.h2("06", "Where to find everything in the repository"), Spacer(1, 1.5 * mm),
          Paragraph(f'Repository: <a href="{REPO}" color="#1f4e8c">{REPO}</a> (private; reviewers need collaborator access). '
                    "To get a local copy: <font name=\"R\">git clone " + REPO + ".git</font>", BODY), Spacer(1, 1.5 * mm)]
    loc = [
        ("submission/", "Start here: board report (v2), the agent's raw v1, one-page write-up and this file"),
        ("docs/evaluations/results.md", "The same results as a page in the repository"),
        ("docs/evaluations/investigation-paths.md", "The 18 scenarios and what success requires"),
        ("evaluation-results/answer-key/", "Expected values and scoring rules (batches 1–4) and the reference query logs"),
        ("evaluation-results/QNN/codex-run-001/", "Round 1 run for question NN: scoring record, the agent's output, evidence zip"),
        ("evaluation-results/QNN/codex-run-002/", "Round 2 reruns (Q01, Q07, Q09, Q11)"),
        ("evaluation-results/Q02/run-001/", "GM question: v1, review feedback word for word, v2, list of v1 → v2 changes"),
        ("evaluation-results/Q02/run-002-blind/", "Blind rerun of the GM question on the updated skill"),
        ("evaluation-results/TRACKER.md", "Status of every question in both rounds"),
        ("skills/product-analytics-investigation/SKILL.md", "The shared skill, including the rules added after each failure"),
    ]
    S.append(kv_table([[(f'<a href="{TREE}/{p}" color="#1f4e8c">{p}</a>' if "QNN" not in p else p), d] for p, d in loc],
                      [W * 0.42, W * 0.58], head=["Path", "What it holds"]))
    S += [Spacer(1, 1.5 * mm), Paragraph(
        "Agents must not read <font name=\"R\">evaluation-results/</font>, <font name=\"R\">submission/</font> or "
        "<font name=\"R\">docs/evaluations/</font> during an investigation (AGENTS.md), because they contain expected answers.", SMALL)]

    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=WU.M, rightMargin=WU.M, topMargin=16 * mm, bottomMargin=11 * mm,
                            title="Evaluation results", author="Soumabrata Sarkar")
    doc.build(S, onFirstPage=header, onLaterPages=header)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "submission" / "eval-results.pdf"
    build(out)
    from pypdf import PdfReader
    print(out, len(PdfReader(str(out)).pages), "page(s)")
