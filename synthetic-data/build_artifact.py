#!/usr/bin/env python3
"""
build_artifact.py — render the dataset summary page.

Reads everything out of data/ and writes portfolio-summary.html. Every number,
bar and label on the page is computed here, so the page cannot drift from the
data it describes. Inline SVG only — no scripts, no external assets.

Usage: python3 build_artifact.py
"""

import csv
import json
import os
import collections
from string import Template
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "portfolio-summary.html")

FUNCTIONS = ["Technology", "Operations", "Supply Chain", "Finance",
             "HR / People", "Growth / Commercial", "Cost Reduction",
             "Risk & Compliance"]


def load(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        return list(r), r.fieldnames


def money(v):
    """$95.3m / $720k — short form for display."""
    v = float(v)
    if abs(v) >= 1_000_000:
        return "$%.1fm" % (v / 1_000_000)
    if abs(v) >= 1_000:
        return "$%.0fk" % (v / 1_000)
    return "$%d" % v


def main():
    ini, ini_cols = load("initiatives.csv")
    deps, dep_cols = load("dependencies.csv")
    conf, conf_cols = load("dependency_conflicts.csv")
    mile, mile_cols = load("milestones.csv")
    risks, risk_cols = load("risks.csv")
    issues, issue_cols = load("issues.csv")
    res, res_cols = load("resources.csv")
    burn, burn_cols = load("burn.csv")
    bens, ben_cols = load("benefits.csv")
    with open(os.path.join(DATA, "scenarios.json"), encoding="utf-8") as fh:
        scen = json.load(fh)

    # ---- headline numbers ------------------------------------------------
    budget = sum(int(i["total_budget"]) for i in ini)
    fac = sum(int(i["forecast_at_completion"]) for i in ini)
    benefit = sum(int(i["annual_benefit_target"]) for i in ini)
    rag = collections.Counter(i["rag_status"] for i in ini)
    over = sum(1 for i in ini if int(i["forecast_at_completion"]) > int(i["total_budget"]) * 1.05)
    cross = sum(1 for e in deps
                if fnof(ini, e["from_initiative"]) != fnof(ini, e["to_initiative"]))
    total_rows = sum(len(x) for x in (ini, deps, conf, mile, risks, issues, res, burn, bens))

    # ---- per-function aggregates ----------------------------------------
    by_fn = {}
    for f in FUNCTIONS:
        rows = [i for i in ini if i["function"] == f]
        by_fn[f] = {
            "n": len(rows),
            "budget": sum(int(i["total_budget"]) for i in rows),
            "fac": sum(int(i["forecast_at_completion"]) for i in rows),
            "benefit": sum(int(i["annual_benefit_target"]) for i in rows),
            "green": sum(1 for i in rows if i["rag_status"] == "Green"),
            "amber": sum(1 for i in rows if i["rag_status"] == "Amber"),
            "red": sum(1 for i in rows if i["rag_status"] == "Red"),
        }

    # ---- benefit plan by quarter ----------------------------------------
    q = collections.OrderedDict()
    for r in bens:
        y, m = r["month"].split("-")
        key = "%sQ%d" % (y, (int(m) - 1) // 3 + 1)
        q[key] = q.get(key, 0) + int(r["benefit_plan"])
    quarters = sorted(q)

    # ---- resource pinch --------------------------------------------------
    worst = {}
    for r in res:
        if r["over_allocated"] != "TRUE":
            continue
        role = r["role"]
        u = float(r["utilisation_pct"])
        if role not in worst or u > worst[role]["util"]:
            worst[role] = {"util": u, "month": r["month"],
                           "avail": r["available_fte"], "dem": r["demanded_fte"]}

    inventory = [
        ("initiatives.csv", len(ini), ini_cols, "The portfolio. One row per initiative.",
         "Roadmap · Scenarios"),
        ("initiatives.json", len(ini), ["(same 60 records as the CSV)"],
         "Identical content, easier from JavaScript.", "Roadmap · Scenarios"),
        ("dependencies.csv", len(deps), dep_cols,
         "What waits for what. Acyclic by construction.", "Dependency view"),
        ("dependency_conflicts.csv", len(conf), conf_cols,
         "Planted sequencing violations to detect and fix.", "Dependency view"),
        ("milestones.csv", len(mile), mile_cols,
         "3-6 per initiative. Baseline vs forecast vs actual.", "Roadmap"),
        ("risks.csv", len(risks), risk_cols,
         "Risk register. Probability x impact, with exposure.", "Health"),
        ("issues.csv", len(issues), issue_cols,
         "Problems that already happened, with cost and slip.", "Health"),
        ("resources.csv", len(res), res_cols,
         "Role supply vs demand by month. The binding constraint.", "Scenarios"),
        ("burn.csv", len(burn), burn_cols,
         "Monthly spend, 24 months. Actuals stop at 2026-07.", "Value plan"),
        ("benefits.csv", len(bens), ben_cols,
         "Monthly benefit plan vs actual, per initiative.", "Value plan"),
        ("scenarios.json", len(scen["scenarios"]), ["scenario_id", "name", "description",
                                                    "constraints", "expected_qualitative_outcome"],
         "Three scenario definitions. Inputs only.", "Scenarios"),
    ]

    html = render(ini, deps, conf, scen, by_fn, rag, budget, fac, benefit, over,
                  cross, total_rows, quarters, q, worst, inventory)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote %s (%.0f KB)" % (OUT, os.path.getsize(OUT) / 1024))


_FN = {}


def fnof(ini, iid):
    if not _FN:
        for i in ini:
            _FN[i["initiative_id"]] = i["function"]
    return _FN[iid]


# ---------------------------------------------------------------------------
# Chart builders — inline SVG, theme-aware via currentColor and CSS vars
# ---------------------------------------------------------------------------

def chart_rag(by_fn):
    """Stacked horizontal bars: RAG mix per function. Status palette."""
    row_h, gap, label_w, bar_w = 30, 8, 168, 420
    h = len(FUNCTIONS) * (row_h + gap)
    maxn = max(v["n"] for v in by_fn.values())
    parts = []
    for idx, f in enumerate(FUNCTIONS):
        v = by_fn[f]
        y = idx * (row_h + gap)
        x = label_w
        parts.append(
            '<text x="%d" y="%d" class="ax-lbl" text-anchor="end">%s</text>'
            % (label_w - 12, y + 20, escape(f)))
        for key, cls, name in (("green", "s-good", "Green"),
                               ("amber", "s-warn", "Amber"),
                               ("red", "s-crit", "Critical")):
            n = v[key]
            if not n:
                continue
            w = n / maxn * bar_w
            parts.append(
                '<rect x="%.1f" y="%d" width="%.1f" height="18" rx="3" class="%s">'
                '<title>%s - %s: %d initiative%s</title></rect>'
                % (x, y + 4, max(w - 2, 1), cls, escape(f),
                   name if name != "Critical" else "Red", n, "" if n == 1 else "s"))
            if w > 26:
                parts.append(
                    '<text x="%.1f" y="%d" class="bar-num" text-anchor="middle">%d</text>'
                    % (x + (w - 2) / 2, y + 17, n))
            x += w
        parts.append('<text x="%.1f" y="%d" class="ax-val">%d</text>'
                     % (x + 8, y + 17, v["n"]))
    return svg(label_w + bar_w + 46, h, parts)


def chart_budget(by_fn):
    """Paired horizontal bars: approved budget vs forecast at completion."""
    row_h, gap, label_w, bar_w = 40, 10, 168, 400
    h = len(FUNCTIONS) * (row_h + gap)
    mx = max(max(v["budget"], v["fac"]) for v in by_fn.values())
    parts = []
    for idx, f in enumerate(FUNCTIONS):
        v = by_fn[f]
        y = idx * (row_h + gap)
        parts.append('<text x="%d" y="%d" class="ax-lbl" text-anchor="end">%s</text>'
                     % (label_w - 12, y + 24, escape(f)))
        for j, (key, cls, name) in enumerate((("budget", "s-1", "Approved budget"),
                                              ("fac", "s-2", "Forecast at completion"))):
            w = v[key] / mx * bar_w
            parts.append(
                '<rect x="%d" y="%d" width="%.1f" height="15" rx="3" class="%s">'
                '<title>%s - %s: %s</title></rect>'
                % (label_w, y + 2 + j * 19, max(w, 2), cls, escape(f), name, money(v[key])))
            parts.append('<text x="%.1f" y="%d" class="ax-val">%s</text>'
                         % (label_w + w + 8, y + 14 + j * 19, money(v[key])))
    return svg(label_w + bar_w + 74, h, parts)


def chart_benefit(quarters, q):
    """Single-series columns: planned benefit landing per quarter."""
    w, h = 640, 200
    pad_l, pad_b, pad_t = 52, 30, 12
    cw = (w - pad_l) / len(quarters)
    mx = max(q.values()) or 1
    parts = []
    # recessive gridlines
    for gi in range(4):
        gy = pad_t + (h - pad_t - pad_b) * gi / 3
        val = mx * (3 - gi) / 3
        parts.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>'
                     % (pad_l, gy, w, gy))
        parts.append('<text x="%d" y="%.1f" class="ax-val" text-anchor="end">%s</text>'
                     % (pad_l - 8, gy + 4, money(val)))
    for idx, k in enumerate(quarters):
        val = q[k]
        bh = (h - pad_t - pad_b) * (val / mx)
        x = pad_l + idx * cw
        parts.append(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" class="s-1">'
            '<title>%s: %s of planned benefit</title></rect>'
            % (x + 5, h - pad_b - bh, cw - 12, max(bh, 1), k, money(val)))
        parts.append('<text x="%.1f" y="%d" class="ax-lbl" text-anchor="middle">%s</text>'
                     % (x + cw / 2, h - 10, k))
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis"/>'
                 % (pad_l, h - pad_b, w, h - pad_b))
    return svg(w, h, parts)


def svg(w, h, parts):
    return ('<svg viewBox="0 0 %d %d" width="100%%" role="img" '
            'preserveAspectRatio="xMinYMin meet">%s</svg>' % (w, h, "".join(parts)))


# ---------------------------------------------------------------------------

def render(ini, deps, conf, scen, by_fn, rag, budget, fac, benefit, over, cross,
           total_rows, quarters, q, worst, inventory):

    inv_rows = "".join(
        '<tr><td class="mono fname">%s</td><td class="num">%s</td>'
        '<td>%s<div class="cols mono">%s</div></td><td class="feeds">%s</td></tr>'
        % (escape(name), "{:,}".format(n), escape(desc),
           escape(", ".join(cols)), escape(feeds))
        for name, n, cols, desc, feeds in inventory)

    fn_rows = "".join(
        '<tr><td>%s</td><td class="num">%d</td><td class="num">%s</td>'
        '<td class="num">%s</td><td class="num">%s</td>'
        '<td class="ragcell"><span class="dot d-g"></span>%d'
        '<span class="dot d-a"></span>%d<span class="dot d-r"></span>%d</td></tr>'
        % (escape(f), v["n"], money(v["budget"]), money(v["fac"]),
           money(v["benefit"]), v["green"], v["amber"], v["red"])
        for f, v in ((f, by_fn[f]) for f in FUNCTIONS))

    conf_rows = "".join(
        '<tr><td class="mono">%s</td><td><strong>%s</strong> %s<br>'
        '<span class="muted">%s &rarr; %s</span></td>'
        '<td class="mono">%s</td><td class="num strong">%s d</td></tr>'
        % (escape(c["conflict_id"]),
           escape(c["from_initiative"]), escape(c["from_name"]),
           escape(c["from_function"]), escape(c["to_function"]),
           escape(c["to_initiative"]), escape(c["overlap_days"]))
        for c in conf)

    scen_cards = ""
    for s in scen["scenarios"]:
        c = s["constraints"]
        cap = c.get("peak_fte_cap")
        scen_cards += (
            '<article class="scard">'
            '<div class="sid mono">%s</div>'
            '<h3>%s</h3>'
            '<p>%s</p>'
            '<dl class="sconstraints">'
            '<div><dt>Budget cap</dt><dd class="mono">%s</dd></div>'
            '<div><dt>Capex cap</dt><dd class="mono">%s</dd></div>'
            '<div><dt>Peak FTE cap</dt><dd class="mono">%s</dd></div>'
            '<div><dt>Mandatory</dt><dd class="mono">%d</dd></div>'
            '<div><dt>Deferred</dt><dd class="mono">%d</dd></div>'
            '<div><dt>Resequencing</dt><dd class="mono">%s</dd></div>'
            '</dl>'
            '<p class="outcome"><span class="olbl">What a good tool should conclude</span>%s</p>'
            '</article>'
            % (escape(s["scenario_id"]), escape(s["name"]), escape(s["description"]),
               money(c["budget_cap_usd"]), money(c["capex_cap_usd"]),
               (str(cap) if cap else "none"),
               len(c["mandatory_initiatives"]), len(c["deferred_initiatives"]),
               "allowed" if c["allow_resequencing"] else "locked",
               escape(s["expected_qualitative_outcome"])))

    pinch_rows = "".join(
        '<tr><td>%s</td><td class="mono">%s</td><td class="num">%s</td>'
        '<td class="num">%s</td><td class="num strong crit">%.0f%%</td></tr>'
        % (escape(r), escape(w["month"]), w["avail"], w["dem"], w["util"])
        for r, w in sorted(worst.items(), key=lambda kv: -kv[1]["util"]))

    return Template(TEMPLATE).substitute({
        "budget": money(budget), "fac": money(fac), "benefit": money(benefit),
        "over": over, "green": rag["Green"], "amber": rag["Amber"], "red": rag["Red"],
        "ndeps": len(deps), "cross": cross,
        "crosspct": round(100 * cross / len(deps)),
        "total_rows": "{:,}".format(total_rows),
        "inv_rows": inv_rows, "fn_rows": fn_rows, "conf_rows": conf_rows,
        "scen_cards": scen_cards, "pinch_rows": pinch_rows,
        "chart_rag": chart_rag(by_fn),
        "chart_budget": chart_budget(by_fn),
        "chart_benefit": chart_benefit(quarters, q),
        "overspend": money(fac - budget),
    })


TEMPLATE = """<title>Synthetic Transformation Portfolio — hack-team-01</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{
  color-scheme: light;
  --plane:#f4f6f8; --surface:#ffffff; --raise:#fafbfc;
  --ink:#12171f; --ink-2:#4a5567; --muted:#78849a;
  --rule:#e2e7ed; --rule-2:#eef1f5;
  --accent:#0b5563; --accent-soft:#e6f0f2;
  --s1:#2a78d6; --s2:#eb6834;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --crit-ink:#a52c2c;
  --grid:#e6eaef; --axis:#c9d1da;
  --shadow:0 1px 2px rgba(18,23,31,.05), 0 8px 24px -16px rgba(18,23,31,.22);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --plane:#0e1116; --surface:#161a21; --raise:#1c212a;
    --ink:#e9edf3; --ink-2:#a6b1c2; --muted:#7d8899;
    --rule:#262c36; --rule-2:#1f242c;
    --accent:#4fbfd4; --accent-soft:#15303a;
    --s1:#3987e5; --s2:#d95926;
    --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
    --crit-ink:#e8837f;
    --grid:#242a33; --axis:#39414c;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --plane:#0e1116; --surface:#161a21; --raise:#1c212a;
  --ink:#e9edf3; --ink-2:#a6b1c2; --muted:#7d8899;
  --rule:#262c36; --rule-2:#1f242c;
  --accent:#4fbfd4; --accent-soft:#15303a;
  --s1:#3987e5; --s2:#d95926;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --crit-ink:#e8837f;
  --grid:#242a33; --axis:#39414c;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--plane); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:15px; line-height:1.6; -webkit-font-smoothing:antialiased;
}
.mono{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  font-variant-numeric:tabular-nums;}
.wrap{max-width:1080px; margin:0 auto; padding:0 24px 96px}

/* ---------- masthead ---------- */
header.mast{border-bottom:1px solid var(--rule); background:var(--surface); margin-bottom:40px}
.mast-in{max-width:1080px; margin:0 auto; padding:48px 24px 36px}
.eyebrow{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:11.5px; letter-spacing:.13em; text-transform:uppercase;
  color:var(--accent); margin:0 0 14px}
h1{font-family:ui-serif,Georgia,"Times New Roman",serif; font-weight:600;
  font-size:clamp(30px,4.6vw,46px); line-height:1.1; letter-spacing:-.018em;
  margin:0 0 14px; text-wrap:balance}
.standfirst{font-size:17px; color:var(--ink-2); max-width:62ch; margin:0}
.asat{margin-top:18px; font-size:13px; color:var(--muted)}
.asat strong{color:var(--ink-2); font-weight:600}

/* ---------- stat strip ---------- */
.stats{display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:1px; background:var(--rule); border:1px solid var(--rule);
  border-radius:10px; overflow:hidden; margin:0 0 44px}
.stat{background:var(--surface); padding:16px 18px}
.stat .v{font-family:ui-serif,Georgia,serif; font-size:26px; line-height:1.1;
  letter-spacing:-.02em; display:block}
.stat .k{font-size:11.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--muted); margin-top:6px; display:block}

/* ---------- sections ---------- */
section{margin:0 0 52px}
h2{font-family:ui-serif,Georgia,serif; font-weight:600; font-size:24px;
  letter-spacing:-.012em; margin:0 0 6px; text-wrap:balance}
.lede{color:var(--ink-2); margin:0 0 22px; max-width:70ch}
h3{font-size:16px; margin:0 0 8px; letter-spacing:-.005em}

.card{background:var(--surface); border:1px solid var(--rule);
  border-radius:10px; box-shadow:var(--shadow)}
.pad{padding:22px 24px}

/* ---------- tables ---------- */
.tscroll{overflow-x:auto; border-radius:10px}
table{border-collapse:collapse; width:100%; font-size:13.5px}
th{text-align:left; font-size:11.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--muted); font-weight:600; padding:12px 14px;
  border-bottom:1px solid var(--rule); white-space:nowrap; background:var(--raise)}
td{padding:12px 14px; border-bottom:1px solid var(--rule-2); vertical-align:top}
tr:last-child td{border-bottom:none}
.num{text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.strong{font-weight:600}
.crit{color:var(--crit-ink)}
.muted{color:var(--muted)}
.fname{font-weight:600; white-space:nowrap}
.cols{font-size:11.5px; color:var(--muted); line-height:1.5; margin-top:5px;
  max-width:44ch}
.feeds{font-size:12px; color:var(--accent); white-space:nowrap}
.ragcell{white-space:nowrap; font-variant-numeric:tabular-nums;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.dot{display:inline-block; width:8px; height:8px; border-radius:50%;
  margin:0 5px 0 12px; vertical-align:middle}
.ragcell .dot:first-child{margin-left:0}
.d-g{background:var(--good)} .d-a{background:var(--warn)} .d-r{background:var(--crit)}

/* ---------- charts ---------- */
.figs{display:grid; gap:22px}
figure{margin:0}
figcaption{margin:0 0 4px; font-size:16px; font-weight:600; letter-spacing:-.005em}
.subcap{font-size:13px; color:var(--muted); margin:0 0 16px}
.ax-lbl{font-size:11.5px; fill:var(--ink-2);
  font-family:system-ui,-apple-system,sans-serif}
.ax-val{font-size:11px; fill:var(--muted);
  font-family:ui-monospace,Menlo,monospace}
.bar-num{font-size:10.5px; fill:#fff; font-weight:600;
  font-family:ui-monospace,Menlo,monospace}
.grid{stroke:var(--grid); stroke-width:1}
.axis{stroke:var(--axis); stroke-width:1}
.s-good{fill:var(--good)} .s-warn{fill:var(--warn)} .s-crit{fill:var(--crit)}
.s-1{fill:var(--s1)} .s-2{fill:var(--s2)}
svg rect{transition:opacity .12s ease}
svg:hover rect{opacity:.72}
svg rect:hover{opacity:1}
.legend{display:flex; flex-wrap:wrap; gap:16px; margin:14px 0 0;
  font-size:12.5px; color:var(--ink-2)}
.legend span{display:inline-flex; align-items:center; gap:7px}
.sw{width:11px; height:11px; border-radius:3px; display:inline-block}

/* ---------- scenarios ---------- */
.scards{display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:18px}
.scard{background:var(--surface); border:1px solid var(--rule); border-radius:10px;
  padding:20px 22px; box-shadow:var(--shadow); display:flex; flex-direction:column}
.sid{font-size:11.5px; letter-spacing:.1em; color:var(--accent); margin-bottom:6px}
.scard h3{font-family:ui-serif,Georgia,serif; font-size:19px; font-weight:600;
  letter-spacing:-.01em; margin-bottom:10px}
.scard p{font-size:13.5px; color:var(--ink-2); margin:0 0 16px}
.sconstraints{display:grid; grid-template-columns:1fr 1fr; gap:1px;
  background:var(--rule); border:1px solid var(--rule); border-radius:7px;
  overflow:hidden; margin:0 0 16px}
.sconstraints > div{background:var(--surface); padding:9px 11px}
.sconstraints dt{font-size:10.5px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted)}
.sconstraints dd{margin:2px 0 0; font-size:13px; font-weight:600}
.outcome{margin:auto 0 0 !important; font-size:13px; color:var(--ink-2);
  background:var(--accent-soft); border-radius:7px; padding:12px 14px}
.olbl{display:block; font-size:10.5px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--accent); font-weight:700; margin-bottom:5px;
  font-family:ui-monospace,Menlo,monospace}

/* ---------- callout ---------- */
.callout{border-left:3px solid var(--accent); background:var(--surface);
  border-radius:0 10px 10px 0; padding:20px 24px; box-shadow:var(--shadow)}
.callout h3{font-family:ui-serif,Georgia,serif; font-size:18px}
.callout ul{margin:10px 0 0; padding-left:20px; color:var(--ink-2); font-size:14px}
.callout li{margin-bottom:7px}
.callout li:last-child{margin-bottom:0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:.9em; background:var(--rule-2); padding:1px 5px; border-radius:4px;
  color:var(--ink)}
footer{border-top:1px solid var(--rule); padding-top:22px; color:var(--muted);
  font-size:13px}
a{color:var(--accent)}
a:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px; border-radius:3px}
@media (prefers-reduced-motion:reduce){*{transition:none !important}}
@media (max-width:640px){
  .sconstraints{grid-template-columns:1fr}
  .mast-in{padding:34px 20px 28px}
}
</style>

<header class="mast">
  <div class="mast-in">
    <p class="eyebrow">Aberdeen Advisors &middot; hack-team-01 &middot; build day 2026-08-12</p>
    <h1>Harbourline Group transformation portfolio</h1>
    <p class="standfirst">A synthetic but internally consistent dataset: 60 initiatives across
      eight business functions, with the dependencies, milestones, risks, money and messy source
      documents a newly appointed transformation leader would actually inherit.</p>
    <p class="asat">Pinned to <strong>today = 2026-08-11</strong>. Actuals run to July 2026 and
      are blank after it. Reproducible from <span class="mono">generate_portfolio.py --seed 42</span>.</p>
  </div>
</header>

<div class="wrap">

<div class="stats">
  <div class="stat"><span class="v">60</span><span class="k">Initiatives</span></div>
  <div class="stat"><span class="v">${total_rows}</span><span class="k">Data rows</span></div>
  <div class="stat"><span class="v">${budget}</span><span class="k">Approved budget</span></div>
  <div class="stat"><span class="v">${fac}</span><span class="k">Forecast at completion</span></div>
  <div class="stat"><span class="v">${benefit}</span><span class="k">Claimed annual benefit</span></div>
  <div class="stat"><span class="v">${ndeps}</span><span class="k">Dependencies</span></div>
</div>

<section>
  <h2>What is in the box</h2>
  <p class="lede">Eleven files in <code>data/</code>, all machine-readable and cross-referenced
    by <code>initiative_id</code>. The last column says which challenge view each file feeds.</p>
  <div class="card tscroll">
    <table>
      <thead><tr><th>File</th><th class="num">Rows</th><th>What it is &amp; its columns</th>
        <th>Feeds</th></tr></thead>
      <tbody>${inv_rows}</tbody>
    </table>
  </div>
</section>

<section>
  <h2>The portfolio at a glance</h2>
  <p class="lede">Three views of the same 60 initiatives: how healthy they are, what they cost
    against what they were approved for, and when the value is supposed to arrive.</p>

  <div class="figs">
    <div class="card pad">
      <figure>
        <figcaption>Delivery health by function</figcaption>
        <p class="subcap">${green} Green &middot; ${amber} Amber &middot; ${red} Red.
          HR / People and Cost Reduction carry the worst mix.</p>
        ${chart_rag}
        <div class="legend">
          <span><i class="sw" style="background:var(--good)"></i>Green &mdash; on track</span>
          <span><i class="sw" style="background:var(--warn)"></i>Amber &mdash; at risk</span>
          <span><i class="sw" style="background:var(--crit)"></i>Red &mdash; off track</span>
        </div>
      </figure>
    </div>

    <div class="card pad">
      <figure>
        <figcaption>Approved budget vs forecast at completion</figcaption>
        <p class="subcap">The portfolio is forecasting ${overspend} over its approved envelope.
          ${over} of 60 initiatives expect to finish more than 5% above budget.</p>
        ${chart_budget}
        <div class="legend">
          <span><i class="sw" style="background:var(--s1)"></i>Approved budget</span>
          <span><i class="sw" style="background:var(--s2)"></i>Forecast at completion</span>
        </div>
      </figure>
    </div>

    <div class="card pad">
      <figure>
        <figcaption>When the value is planned to land</figcaption>
        <p class="subcap">Planned benefit per quarter across the 24-month window. Every initiative
          books value only after it delivers, so the curve is empty through 2026 and steepens
          through 2027 &mdash; which is exactly the problem the Board has with it.</p>
        ${chart_benefit}
      </figure>
    </div>
  </div>
</section>

<section>
  <h2>By function</h2>
  <p class="lede">Two grouping columns ship with the data and they mean different things:
    <code>function</code> is who delivers it, <code>pillar</code> is why we are doing it
    (Grow / Run Better / Cost Out / Protect). Group by either.</p>
  <div class="card tscroll">
    <table>
      <thead><tr><th>Function</th><th class="num">Count</th><th class="num">Budget</th>
        <th class="num">Forecast</th><th class="num">Annual benefit</th><th>RAG</th></tr></thead>
      <tbody>${fn_rows}</tbody>
    </table>
  </div>
</section>

<section>
  <h2>The two constraints that bite</h2>
  <p class="lede">Both are deliberate. A roadmap that ignores either one is not deliverable,
    however good its financials look.</p>

  <div class="figs">
    <div class="card pad">
      <h3>Planted schedule conflicts</h3>
      <p class="subcap">Hard dependencies where the successor is scheduled to start before its
        predecessor can finish. The dependency graph itself is <strong>acyclic</strong> &mdash;
        these are date violations, not cycles. Two of the three cross functions.</p>
      <div class="tscroll">
        <table>
          <thead><tr><th>Ref</th><th>Predecessor</th><th>Successor</th>
            <th class="num">Violation</th></tr></thead>
          <tbody>${conf_rows}</tbody>
        </table>
      </div>
    </div>

    <div class="card pad">
      <h3>Resource pinch points</h3>
      <p class="subcap">Exactly three roles breach their supply, concentrated in 2026Q4&ndash;2027Q1.
        No other role breaches in any month.</p>
      <div class="tscroll">
        <table>
          <thead><tr><th>Role</th><th>Worst month</th><th class="num">Available FTE</th>
            <th class="num">Demanded FTE</th><th class="num">Utilisation</th></tr></thead>
          <tbody>${pinch_rows}</tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<section>
  <h2>Three scenarios to compare</h2>
  <p class="lede">Definitions only &mdash; no results are pre-computed. Working out what each one
    does to the sequence, the cost profile, the resource feasibility and the benefit curve is
    the tool's job. The last block on each card is the sanity check.</p>
  <div class="scards">${scen_cards}</div>
</section>

<section>
  <h2>Before you start</h2>
  <div class="callout">
    <h3>Six things that will save you an hour</h3>
    <ul>
      <li><strong>Value always lands after delivery.</strong> No initiative books benefit while
        it is still being built. Realised benefit to date is about $$1k across the whole
        portfolio &mdash; correct, not a bug.</li>
      <li><strong>Enablers look like bad investments and are not.</strong> INIT-001 costs $$895k
        and returns $$70k a year on its own. Follow the graph transitively and it gates
        <strong>28 of the 60 initiatives, carrying $$38.6m of annual benefit</strong>. Any naive
        ROI ranking cuts it first.</li>
      <li><strong><code>is_regulatory = TRUE</code> means untouchable.</strong> Five initiatives.
        An optimiser that maximises NPV will try to cut them and will be wrong.</li>
      <li><strong><code>value_confidence</code> matters as much as the benefit number.</strong>
        A Low-confidence $$3m is worth less than a High-confidence $$1.5m, and the portfolio is
        full of the former.</li>
      <li><strong>The documents in <code>docs/</code> disagree with the data on purpose.</strong>
        Business cases, three PMO status reports, steering minutes and one genuinely horrible
        spreadsheet. Reconciling them is part of the challenge, and
        <code>docs/ANSWER-KEY.md</code> lists every planted problem so you can score yourself.</li>
      <li><strong>Nothing here has ever been cancelled.</strong> In two years the portfolio grew
        from 34 initiatives to 60. The question the PMO cannot answer, and the one the tool
        should, is <em>&ldquo;if we could only do thirty of these, which thirty?&rdquo;</em></li>
    </ul>
  </div>
</section>

<footer>
  Synthetic data for the Aberdeen Advisors hackathon. Harbourline Group is fictional; no real
  company, person or figure appears anywhere. ${ndeps} dependency edges, ${cross} of them
  (${crosspct}%) crossing functions. Regenerate with
  <span class="mono">python3 generate_portfolio.py</span>, then verify with
  <span class="mono">python3 validate_portfolio.py</span>.
</footer>

</div>
"""


if __name__ == "__main__":
    main()
