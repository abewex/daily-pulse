"""Abe's Daily Pulse — Kindle PDF builder.

Usage:  python3 builder/pulse.py <data.json> <out_dir>
Prints the output PDF path. Contains no personal data; everything comes from data.json
(schema: see RUNBOOK.md and examples/sample.json).
"""
import json, sys, os, datetime as dt
from collections import defaultdict
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame, Table, TableStyle, Spacer, Flowable, PageBreak, NextPageTemplate
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Line, String, PolyLine
from reportlab.graphics import renderPDF

W, H = 3.6*inch, 4.8*inch
M = 0.1*inch
CW = W - 2*M
INK = colors.HexColor("#111111"); GREY = colors.HexColor("#555555"); RULE = colors.HexColor("#999999")
LINK = "#1a4b8c"

ST = {
 "h2": ParagraphStyle("h2", fontName="Times-Bold", fontSize=8.6, leading=10.2, spaceBefore=3, spaceAfter=1),
 "p": ParagraphStyle("p", fontName="Times-Roman", fontSize=7.6, leading=9.1, spaceAfter=2.5),
 "note": ParagraphStyle("note", fontName="Times-Italic", fontSize=6.4, leading=7.6, textColor=GREY, spaceAfter=1.5),
 "bullet": ParagraphStyle("bullet", fontName="Times-Roman", fontSize=7.6, leading=9.1, leftIndent=7, bulletIndent=0, spaceAfter=2),
 "read": ParagraphStyle("read", fontName="Times-Roman", fontSize=7.6, leading=9.4, spaceAfter=3, firstLineIndent=8),
 "quote": ParagraphStyle("quote", fontName="Times-Italic", fontSize=7.6, leading=9.4, leftIndent=8, rightIndent=4, spaceAfter=3),
}
SECTIONS = ["Cover", "Your Money", "Markets", "Rates & Bonds", "Tech & Apple", "Industry", "NYC", "Commute Reads",
            "App: Balance Sheet", "App: Income & Cash Flow", "App: Spend & Audit", "Chart: Net Worth",
            "Chart: Spend Pace", "Methodology"]
TITLES = {1: "Cover", 2: "Your Money", 3: "Markets", 4: "Rates & Bonds", 5: "Tech & Apple Rumor Mill", 6: "Industry & Profession",
          7: "NYC", 8: "Commute Reads", 9: "Appendix A — Balance Sheet", 10: "Appendix B — Income & Cash Flow",
          11: "Appendix C — Spend & Audit Flags", 12: "Chart — Net Worth Trend",
          13: "Chart — Spend Pace vs Target", 14: "Methodology & Sources"}


GLYPHS = {"\u0394": "Chg ", "\u2212": "-", "\u2248": "~", "\u2009": " "}


def clean(s):
    """Standard PDF fonts (WinAnsi) lack some glyphs; swap them so nothing renders blank."""
    s = str(s)
    for a, b in GLYPHS.items():
        s = s.replace(a, b)
    return s


def num_cols(rows):
    import re
    body = rows[1:] or rows
    return tuple(c for c in range(len(rows[0]))
                 if all(re.fullmatch(r"[-+~]?\$?[\d,.]+%?[KMB]?|", str(r[c]).strip()) for r in body if c < len(r)))


def f(x, d=0):
    return ("-" if x < 0 else "") + f"${abs(x):,.{d}f}"


def fs(x, d=0):
    return ("+" if x >= 0 else "-") + f"${abs(x):,.{d}f}"


def tbl(rows, widths, bold_last=False, right_cols=None):
    rows = [[clean(c) for c in r] for r in rows]
    if right_cols is None:
        right_cols = num_cols(rows)
    t = Table(rows, colWidths=widths)
    sty = [("FONT", (0, 0), (-1, -1), "Helvetica", 6.4), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 6.4),
           ("LEADING", (0, 0), (-1, -1), 7.4), ("TOPPADDING", (0, 0), (-1, -1), 0.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6),
           ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1), ("LINEBELOW", (0, 0), (-1, 0), 0.4, INK)]
    for c in right_cols:
        if c < len(widths):
            sty.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    if bold_last:
        sty += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 6.4), ("LINEABOVE", (0, -1), (-1, -1), 0.4, INK)]
    t.setStyle(TableStyle(sty))
    return t


def blocks_to_flow(blocks):
    """Narrative blocks: {"type": h2|p|note|bullet|table|space, "text": reportlab markup, "rows": [[...]], "widths": [fractions]}"""
    out = []
    for b in blocks or []:
        t = b.get("type", "p")
        if t == "bullet":
            out.append(Paragraph(b["text"], ST["bullet"], bulletText="•"))
        elif t == "table":
            rows = b["rows"]
            n = len(rows[0])
            widths = [CW*w for w in b.get("widths", [1.0/n]*n)]
            out.append(tbl(rows, widths, bold_last=b.get("bold_last", False), right_cols=tuple(b["right_cols"]) if "right_cols" in b else None))
        elif t == "space":
            out.append(Spacer(1, b.get("h", 3)))
        else:
            out.append(Paragraph(clean(b["text"]), ST.get(t, ST["p"])))
    return out


def build(data, out_dir):
    D = data
    date = dt.date.fromisoformat(D["date"])
    BAL = D["balances"]                     # {"YYYY-MM-DD": {account: signed balance}}
    dates = sorted(BAL)
    d1 = D["date"]
    assert d1 in BAL, "balances must include today's date"
    prior = [d for d in dates if d < d1]
    d0 = prior[-1]                          # last month-end
    dm = prior[-2] if len(prior) > 1 else d0
    G = D["groups"]                         # cash, cards, retirement, other_assets, loans
    s = lambda d, ks: sum(BAL[d].get(k, 0) for k in ks)
    nw = lambda d: sum(BAL[d].values())
    NW0, NW1, NWm = nw(d0), nw(d1), nw(dm)
    CASH0, CASH1 = s(d0, G["cash"]), s(d1, G["cash"])
    CARDS0, CARDS1 = -s(d0, G["cards"]), -s(d1, G["cards"])
    RET0, RET1 = s(d0, G["retirement"]), s(d1, G["retirement"])

    def bycat(rows):
        c = defaultdict(float)
        for r in rows:
            c[r[-2]] += r[-1]
        return c
    EXP, PEXP = D["expenses_mtd"], D["expenses_prev_month"]   # [date?, category, amount]; spend negative
    oc, pc = bycat(EXP), bycat(PEXP)
    mtd_net = -sum(r[-1] for r in EXP)
    prev_net = -sum(r[-1] for r in PEXP)
    UNC = D.get("uncategorized_mtd", [])                     # [label, amount, date?] card charges negative
    OFF = D.get("uncategorized_offsets", [])                 # [label, amount] matched reimbursements (positive)
    unc = -sum(r[1] for r in UNC)
    off = sum(r[1] for r in OFF)
    all_in = mtd_net + unc - off
    BENCH = float(D["benchmark_monthly"])
    import calendar
    DAY, DAYS = date.day, calendar.monthrange(date.year, date.month)[1]
    pro = BENCH*DAY/DAYS
    pace = all_in/DAY*DAYS
    rent = -oc.get("Rent", 0)
    PINC = D.get("income_prev_month", {})
    pinc = sum(PINC.values())
    N = D.get("narrative", {})
    P = lambda t, k="p": Paragraph(t, ST[k])
    B = lambda t: Paragraph(t, ST["bullet"], bulletText="•")
    mon = lambda d: dt.date.fromisoformat(d).strftime("%-m/%-d")

    pages = {}
    # 1 Cover
    grid = Table([["NET WORTH", "LIQUID CASH"], [f(NW1), f(CASH1)], ["CARDS OWED", "MTD SPEND"], [f(CARDS1), f(all_in)]], colWidths=[CW/2]*2)
    grid.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 6.2), ("FONT", (0, 1), (-1, 1), "Times-Bold", 12),
        ("FONT", (0, 3), (-1, 3), "Times-Bold", 12), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOX", (0, 0), (-1, -1), 0.5, INK),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, RULE), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    toc = " &middot; ".join(f'<link dest="p{i}" color="{LINK}">{n}</link>' for i, n in enumerate(SECTIONS[1:], start=2))
    pace_bullet = (f"<b>Spend pace:</b> MTD {f(all_in)} through day {DAY}/{DAYS} runs {fs(all_in-pro)} vs pro-rata benchmark ({f(pro)}); "
                   f"straight-line month-end {f(pace)} vs {f(BENCH)}." + (" Rent is front-loaded, so the run-rate overstates." if rent and DAY < 15 else ""))
    pages[1] = [P("<b>Subway Delta</b>", "h2"), B(pace_bullet)] + blocks_to_flow(N.get("delta", [])[:2]) + [
        Spacer(1, 3), grid, Spacer(1, 3), P("<b>Contents</b>", "h2"), P(toc, "note"), P(D.get("as_of_note", ""), "note")]

    # 2 Your Money
    cash_chg, ret_chg = CASH1-CASH0, RET1-RET0
    card_chg = CARDS0-CARDS1
    oth = (NW1-NW0)-ret_chg-cash_chg-card_chg
    bridge = tbl([[f"Net-worth bridge {mon(d0)} → {mon(d1)}", "$"], [f"Opening net worth {mon(d0)}", f(NW0)],
                  ["Δ Retirement", fs(ret_chg)], ["Δ Liquid cash", fs(cash_chg)], ["Δ Card liabilities (paydown +)", fs(card_chg)],
                  ["Δ Other (residual)", fs(oth)], [f"Closing net worth {mon(d1)}", f(NW1)]], [CW*0.68, CW*0.32], bold_last=True)
    prev_name = dt.date.fromisoformat(d0).strftime("%b")
    mom_rows = [[f"MoM P&L ({prev_name})", "$"]] + [[k, f(v)] for k, v in PINC.items()] + [
        ["Net categorized spend", f(-prev_net)], ["Net surplus", f(pinc-prev_net)]]
    var_pro = (BENCH-rent)*DAY/DAYS if rent else None
    pace_txt = f"MTD all-in {f(all_in)} = {all_in/pro:.0%} of pro-rata benchmark ({f(BENCH)}/mo × {DAY}/{DAYS} = {f(pro)})."
    if rent:
        pace_txt += f" Ex-rent: {f(all_in-rent)} vs {f(var_pro)} pro-rata variable budget ({(all_in-rent)/var_pro:.0%})."
    pages[2] = [P(f"Net worth {f(NW1)}, {fs(NW1-NW0)} MTD; {fs(NW1-NWm)} vs {mon(dm)}."), bridge, Spacer(1, 3),
                tbl(mom_rows, [CW*0.68, CW*0.32], bold_last=True), Spacer(1, 2), P("<b>Pace barometer</b>", "h2"), P(pace_txt),
                P("<b>Auditor callouts</b>", "h2")] + blocks_to_flow(N.get("auditor_callouts", [])[:3])

    for i, key in [(3, "markets"), (4, "rates"), (5, "tech_apple"), (6, "industry"), (7, "nyc"), (8, "commute_reads")]:
        pages[i] = blocks_to_flow(N.get(key, []))

    # 9 Balance sheet
    bs = [["Balance sheet", mon(d0), mon(d1), "Δ"]]
    for k in G["cash"] + G["retirement"] + G.get("other_assets", []) + G["cards"] + G.get("loans", []):
        a, b = BAL[d0].get(k, 0), BAL[d1].get(k, 0)
        if a or b:
            bs.append([k + (" (loan)" if k in G.get("loans", []) else ""), f(a), f(b), fs(b-a)])
    bs.append(["Net worth", f(NW0), f(NW1), fs(NW1-NW0)])
    assets = sum(v for v in BAL[d1].values() if v > 0); liabs = -sum(v for v in BAL[d1].values() if v < 0)
    pages[9] = [tbl(bs, [CW*0.4, CW*0.2, CW*0.2, CW*0.2], bold_last=True), Spacer(1, 2),
                P(f"Total assets {f(assets)}; total liabilities {f(liabs)}. Liquidity: cash/cards {CASH1/CARDS1:.1f}x." if CARDS1 else
                  f"Total assets {f(assets)}; total liabilities {f(liabs)}.", "note")]

    # 10 Income & cash flow
    cats = sorted(set(pc) | set(oc), key=lambda c: pc.get(c, 0))
    inc = [["Category (net of reimb.)", prev_name, "MTD"]] + [[c, f(-pc.get(c, 0)), f(-oc.get(c, 0))] for c in cats]
    inc.append(["Net categorized spend", f(prev_net), f(mtd_net)])
    cv = D.get("cash_view_prev_month", [])
    p10 = [tbl(inc, [CW*0.5, CW*0.25, CW*0.25], bold_last=True)]
    if cv:
        p10 += [Spacer(1, 3), tbl([[f"{prev_name} cash view", "$"]] + [[l, f(a)] for l, a in cv] + [["Approx. free cash flow", f(sum(a for _, a in cv))]],
                                 [CW*0.68, CW*0.32], bold_last=True)]
    pages[10] = p10

    # 11 Spend & audit
    ua = [["Uncategorized MTD item", "$"]] + [[r[0], f(r[1], 2)] for r in UNC] + [[l, fs(a, 2)] for l, a in OFF]
    pages[11] = [P(f"Trailing: {prev_name} net spend {f(prev_net)} vs benchmark {f(BENCH)} ({prev_net/BENCH:.0%})."),
                 tbl(ua, [CW*0.72, CW*0.28]) if UNC or OFF else P("No uncategorized items.", "note"), Spacer(1, 2),
                 P("<b>Flags</b>", "h2")] + blocks_to_flow(N.get("audit_flags", []))
    pages[12] = "NW"
    pages[13] = "SP"
    method = [B("Source of record: WealthPosition ledger via read-only queries. No writes made."),
              B(f"Spend = expenditure entries net of reimbursements, plus uncategorized card charges less matched offsets. Pace = MTD ÷ {DAY} × {DAYS}; benchmark {f(BENCH)}/mo."),
              B("Granularity: MoM and MTD only. Net-worth 'other' line is the residual after cash, retirement and cards.")]
    srcs = D.get("sources", [])   # [[label, url], ...] - links live here instead of inline
    src_flow = ([P("<b>Sources</b>", "h2")] +
                [Paragraph(f'{clean(l)} <a href="{u}" color="{LINK}"><u>link</u></a>', ST["note"], bulletText="\u2022") for l, u in srcs]) if srcs else []
    pages[14] = method + blocks_to_flow(N.get("methodology", [])) + [B(f"Built {d1} by Claude. Not investment advice.")] + src_flow

    # -------- charts --------
    def chart_nw(c, x, y, w, h):
        vals = [nw(d) for d in dates]
        lo, hi = min(vals)*0.97, max(vals)*1.02
        g = Drawing(w, h); pts = []
        for i, v in enumerate(vals):
            px = 22 + i*(w-34)/max(len(vals)-1, 1); py = 14 + (v-lo)/((hi-lo) or 1)*(h-30); pts += [px, py]
            g.add(String(px, 4, mon(dates[i]), fontName="Helvetica", fontSize=5, textAnchor="middle"))
            g.add(String(px, py+4, f"${v/1000:.1f}K", fontName="Helvetica", fontSize=5, textAnchor="middle"))
        g.add(Line(20, 12, w-8, 12, strokeColor=INK, strokeWidth=0.4)); g.add(PolyLine(pts, strokeColor=INK, strokeWidth=1.2))
        renderPDF.draw(g, c, x, y)

    def chart_sp(c, x, y, w, h):
        daily = defaultdict(float); dated = True
        for r in EXP:
            if len(r) == 3:
                daily[dt.date.fromisoformat(r[0]).day] -= r[2]
            else:
                dated = False
        for r in UNC:
            if len(r) == 3:
                daily[dt.date.fromisoformat(r[2]).day] -= r[1]
            else:
                dated = False
        mx = max(BENCH, all_in)*1.08
        X = lambda t: 20+(t-1)*(w-30)/(DAYS-1); Y = lambda v: 14+v/mx*(h-26)
        g = Drawing(w, h)
        g.add(Line(X(1), Y(0), X(DAYS), Y(BENCH), strokeColor=GREY, strokeWidth=0.8, strokeDashArray=[2, 2]))
        if dated:
            cum, pts = 0, []
            for t in range(1, DAY+1):
                cum += daily.get(t, 0); pts.append((t, cum))
            pts[-1] = (DAY, all_in)  # offsets land on the endpoint
            g.add(PolyLine([v for t, cv_ in pts for v in (X(t), Y(cv_))], strokeColor=INK, strokeWidth=1.3))
        else:
            g.add(Line(X(1), Y(0), X(DAY), Y(all_in), strokeColor=INK, strokeWidth=1.3))
        g.add(Line(20, 14, w-8, 14, strokeColor=INK, strokeWidth=0.4))
        for t in sorted({1, 8, 15, 22, DAYS}):
            g.add(String(X(t), 5, f"{date.month}/{t}", fontName="Helvetica", fontSize=5, textAnchor="middle"))
        g.add(String(X(DAYS), Y(BENCH)+3, f"Target {f(BENCH)}", fontName="Helvetica", fontSize=5, textAnchor="end"))
        g.add(String(X(DAY), Y(all_in)+4, f"MTD {f(all_in)}", fontName="Helvetica-Bold", fontSize=5.5, textAnchor="middle"))
        renderPDF.draw(g, c, x, y)

    # -------- render: sections flow onto "(cont.)" pages instead of shrinking --------
    fname = f"Abes_Daily_Pulse_{date.strftime('%b')}_{date.day:02d}.pdf"
    out = os.path.join(out_dir, fname)
    TOP_BODY, TOP_COVER, BOTTOM = H-M-25, H-M-40, M+9

    class Marker(Flowable):
        def __init__(self, idx): super().__init__(); self.idx = idx
        def wrap(self, aw, ah): return (0, 0)
        def draw(self):
            doc = self.canv._doctemplate
            doc.sec, doc.sec_page = self.idx, self.canv.getPageNumber()
            self.canv.bookmarkPage(f"p{self.idx}"); self.canv.addOutlineEntry(SECTIONS[self.idx-1], f"p{self.idx}", 0)

    class Chart(Flowable):
        def __init__(self, fn, h): super().__init__(); self.fn, self.h = fn, h
        def wrap(self, aw, ah): self.w = aw; return (aw, self.h)
        def draw(self): self.fn(self.canv, 0, 0, self.w, self.h)

    chart_h = TOP_BODY - BOTTOM - 40
    pages[12] = [Chart(chart_nw, chart_h), P(f"Month-end net worth from ledger balances; {mon(d1)} is MTD.", "note")]
    pages[13] = [Chart(chart_sp, chart_h), P(f"Solid: cumulative spend (endpoint {f(all_in)} exact). Dashed: straight-line {f(BENCH)} target.", "note")]

    def story():
        s = []
        for i in range(1, 15):
            if i == 2:
                s.append(NextPageTemplate("body"))
            if i > 1:
                s.append(PageBreak())
            s.append(Marker(i))
            s.extend(pages[i])
        return s

    def chrome(c, doc):
        n, total = c.getPageNumber(), max(doc.total, c.getPageNumber())
        ty = H-M-6
        c.saveState()
        c.setStrokeColor(INK); c.setLineWidth(0.6); c.line(M+4, ty, W-M-4, ty)
        for k in range(total):
            sx = M+4 + k*(W-2*M-8)/max(total-1, 1)
            c.setFillColor(INK if k < n else colors.white); c.circle(sx, ty, 1.3, stroke=1, fill=1)
        tx = M+4 + (n-1)*(W-2*M-8)/max(total-1, 1)
        c.setFillColor(INK); c.roundRect(tx-7, ty-2.6, 14, 5.2, 1.5, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 4); c.drawCentredString(tx, ty-1.3, str(n)); c.setFillColor(INK)
        if n == 1:
            c.setFont("Times-Bold", 17); c.drawCentredString(W/2, H-M-26, "Abe's Daily Pulse")
            c.setFont("Times-Italic", 6.6); c.drawCentredString(W/2, H-M-34, f"{date.strftime('%A, %B')} {date.day}, {date.year}  \u00b7  {D.get('dateline', 'New York')}")
            c.setLineWidth(0.8); c.line(M, H-M-37, W-M, H-M-37); c.setLineWidth(0.3); c.line(M, H-M-38.5, W-M, H-M-38.5)
        else:
            title = TITLES[doc.sec] + ("" if doc.sec_page == n else " (cont.)")
            c.setFont("Times-Bold", 11.5); c.drawString(M, H-M-20, title)
            c.setFont("Helvetica", 5.6); c.drawRightString(W-M, H-M-20, f"{n}/{total}")
            c.setLineWidth(0.5); c.line(M, H-M-23, W-M, H-M-23)
        c.setLineWidth(0.3); c.line(M, M+7, W-M, M+7)
        if n > 1:
            c.setFont("Helvetica", 5.8); c.setFillColor(colors.HexColor(LINK)); c.drawString(M, M+1.5, "\u2039 Home")
            c.linkRect("", "p1", (M, M, M+24, M+7), relative=0); c.setFillColor(INK)
        c.setFont("Helvetica", 5.2); c.drawRightString(W-M, M+1.5, f"The Pulse \u00b7 {date.strftime('%b')} {date.day}, {date.year}")
        c.restoreState()
        fr = doc.frame
        doc.fills.append((n, doc.sec, round((fr._y1 + fr._height - fr._y) / fr._height, 2)))

    def render(path, total):
        doc = BaseDocTemplate(path, pagesize=(W, H), leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M,
                              title=f"Abe's Daily Pulse \u2014 {date.strftime('%b')} {date.day}, {date.year}", author="Claude",
                              pageCompression=1)
        doc.total, doc.sec, doc.sec_page, doc.fills = total, 1, 1, []
        doc.addPageTemplates([
            PageTemplate("cover", [Frame(M, BOTTOM, CW, TOP_COVER-BOTTOM, 0, 0, 0, 0, id="c")], onPageEnd=chrome),
            PageTemplate("body", [Frame(M, BOTTOM, CW, TOP_BODY-BOTTOM, 0, 0, 0, 0, id="b")], onPageEnd=chrome)])
        doc.build(story())
        return doc

    first = render(out, 0)                       # pass 1: learn the page count
    total = len(first.fills)
    doc = render(out, total)                     # pass 2: subway header knows the total
    # Fill of each section's LAST page: low numbers mean white space to fill with substance.
    last = {}
    for n, sec, fill in doc.fills:
        last[sec] = (n, fill)
    fills = {SECTIONS[s-1]: {"page": n, "last_page_fill": fl} for s, (n, fl) in sorted(last.items())}
    return out, {"net_worth": round(NW1, 2), "cash": round(CASH1, 2), "cards": round(CARDS1, 2),
                 "mtd_all_in": round(all_in, 2), "pages": total, "section_fill": fills}


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    os.makedirs(sys.argv[2], exist_ok=True)
    path, summary = build(data, sys.argv[2])
    print(json.dumps({"pdf": path, **summary}))
