#!/usr/bin/env python3
"""
build_portfolio_json.py - build-time flattener.

Reads the CSV and JSON sources in synthetic-data/data/ and emits one typed file
at data/portfolio.json for the static single-page app to consume.

This runs ONCE, on a developer machine, and the JSON it produces is committed.
It is NOT part of the running application: the app reads data/portfolio.json and
nothing else. No network calls, no backend, no build step at runtime.

Two hard rules, both from BUILD-BRIEF.md:

  * synthetic-data/ is the system of record. This script opens it read-only and
    writes nothing back into it. All output goes to the repo root.

  * synthetic-data/data/dependency_conflicts.csv is DELIBERATELY NOT READ. It is
    a pre-diagnosed answer key holding the three planted scheduling breaks with
    the dates that prove them, already worked out. Reading it would mean the tool
    reprints answers instead of finding problems. This script derives the
    conflicts from dependencies.csv and the initiative dates alone - see
    detect_conflicts() - and asserts at build time that the answer key was never
    opened (see the "answer key never read" check).

Usage:  python build_portfolio_json.py
Exit code 0 = every build-time check passed, 1 = something failed.
"""

import csv
import json
import os
import sys
from collections import defaultdict, deque
from datetime import date, timedelta

# Windows consoles default to cp1252 and will crash on a stray non-ASCII
# character in an initiative name. Force UTF-8 on stdout where we can.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "synthetic-data", "data")
OUT_DIR = os.path.join(HERE, "data")
OUT_PATH = os.path.join(OUT_DIR, "portfolio.json")

# The as-of boundary. Blank actuals AFTER this month are future months, not
# missing data. They stay null. They are never imputed and never zero-filled.
AS_OF_MONTH = "2026-07"

# The canonical reporting window, from generate_portfolio.py WINDOW_START /
# WINDOW_MONTHS: 24 months, 2026-01 to 2027-12.
WINDOW_START = "2026-01"
WINDOW_MONTHS = 24

# The file that must never be read. Named here only so the build-time check can
# assert we did not open it.
ANSWER_KEY = "dependency_conflicts.csv"

# Which dependency types constrain a date, and against what. Mirrors
# DATE_CONSTRAINT in app.js - the detector and the sequencer must agree, or the
# tool reports breaches it then refuses to fix.
#   "finish"  successor cannot start until the predecessor finishes, plus lag
#   "start"   successor cannot start before the predecessor starts, plus lag
#   None      no date constraint; a capacity problem, caught as a resource issue
DATE_CONSTRAINT = {
    "Finish-to-Start": "finish",
    "Technical Enabler": "finish",
    "Data": "finish",
    "Start-to-Start": "start",
    "Resource": None,
}

# The three conflicts the detector must find on its own, from BUILD-BRIEF.md
# section 5. These are assertions about our own output, not an input to it:
# nothing below feeds detect_conflicts().
EXPECTED_CONFLICTS = [
    ("INIT-039", "INIT-031", 716),
    ("INIT-039", "INIT-038", 710),
    ("INIT-005", "INIT-006", 627),
]

FAILS = []
CHECKS = []
READ_FILES = []


# ---------------------------------------------------------------------------
# Helpers ported from synthetic-data/validate_portfolio.py
# ---------------------------------------------------------------------------

def check(name, ok, detail=""):
    """The single assertion helper for the whole file. Ported from
    validate_portfolio.py line 31. Fails loudly rather than quietly."""
    CHECKS.append((name, ok, detail))
    if not ok:
        FAILS.append("%s - %s" % (name, detail))
    print("  [%s] %-58s %s" % ("PASS" if ok else "FAIL", name, detail))


def load(path):
    """CSV -> list of dicts. Ported from validate_portfolio.py line 38.
    Records every path opened so we can prove the answer key was not read."""
    READ_FILES.append(os.path.basename(path))
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_json(path):
    READ_FILES.append(os.path.basename(path))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Date helpers ported from synthetic-data/generate_portfolio.py lines 450-479
# ---------------------------------------------------------------------------

def parse_iso(s):
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def days_in_month(year, month):
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def add_months(d, n):
    total = (d.year * 12 + (d.month - 1)) + n
    y, m = divmod(total, 12)
    m += 1
    return date(y, m, min(d.day, days_in_month(y, m)))


def month_key(d):
    """2026-08"""
    return "%04d-%02d" % (d.year, d.month)


def month_index(d):
    """Absolute month number, so two months can be subtracted."""
    return d.year * 12 + (d.month - 1)


def quarter_of(d):
    """2026Q3"""
    return "%04dQ%d" % (d.year, (d.month - 1) // 3 + 1)


def iso(d):
    return d.isoformat()


# ---------------------------------------------------------------------------
# Normalisers - BUILD-BRIEF.md section 4
# ---------------------------------------------------------------------------

def to_bool(v):
    """Boolean casing differs between files: initiatives.is_regulatory is
    True/False (title case), resources.over_allocated is TRUE/FALSE (upper
    case). Both become real booleans here so nothing downstream ever compares
    raw strings."""
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n", ""):
        return False
    raise ValueError("not a boolean: %r" % (v,))


def num_or_none(v):
    """Blank cell -> None, NEVER 0.

    1,020 of the 1,440 burn and benefit rows have blank actuals because they are
    months after the 2026-07 as-of date. Those are future months, not missing
    data. Imputing or zero-filling them would be a factual error about the
    portfolio, so a blank stays null all the way to the browser."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    f = float(s)
    return int(f) if f == int(f) else f


def num(v, default=0):
    r = num_or_none(v)
    return default if r is None else r


def text_or_none(v):
    """Blanks are meaningful: milestones.actual_date blank = not yet complete,
    issues.linked_risk_id blank = no risk predicted it."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


# ---------------------------------------------------------------------------
# The dependency graph
# ---------------------------------------------------------------------------

def topo_sort_with_waves(ids, deps):
    """Kahn's algorithm, ported from the inline block at validate_portfolio.py
    lines 88-104, extended by one line to record the wave each node lands in.

    from_initiative is the PREDECESSOR, to_initiative is the SUCCESSOR. Getting
    that backwards is the usual cause of a phantom cycle.

    wave 0 = no unmet predecessors, wave 1 = depends only on wave 0, and so on.
    A node's wave is 1 + the deepest of its predecessors, which is why the wave
    is written on every decrement rather than only on the last one.

    Returns (topo_order, wave_by_id). If len(topo_order) < len(ids) the graph
    has a cycle - and since the graph is acyclic by construction, that means the
    bug is here, not in the data.
    """
    outgoing = defaultdict(list)
    indeg = {i: 0 for i in ids}
    for e in deps:
        outgoing[e["from_initiative"]].append(e["to_initiative"])
        indeg[e["to_initiative"]] += 1

    wave = {}
    seeds = sorted(n for n, v in indeg.items() if v == 0)
    for n in seeds:
        wave[n] = 0
    queue = deque(seeds)

    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for m in outgoing[n]:
            indeg[m] -= 1
            wave[m] = max(wave.get(m, 0), wave[n] + 1)
            if indeg[m] == 0:
                queue.append(m)
    return order, wave, outgoing


def transitive_downstream(order, outgoing):
    """For every initiative, the full set of initiatives it gates through the
    whole dependency closure - not just its direct links.

    Walking the topological order in reverse means every successor's closure is
    already solved when we need it, so each node is a single union.
    """
    closure = {}
    for n in reversed(order):
        reach = set()
        for m in outgoing[n]:
            reach.add(m)
            reach |= closure.get(m, set())
        closure[n] = reach
    return closure


def detect_conflicts(by_id, deps):
    """Find scheduling breaks from dependencies.csv and the initiative dates
    alone. The answer key is not consulted.

    The rule, from BUILD-BRIEF.md section 5:
        required_successor_start = predecessor.end_date + lag_days
        overlap_days = required_successor_start - actual_successor_start
    Flag it when that number is positive: the successor is already scheduled to
    start before its predecessor can possibly finish.

    Applied to every edge, this surfaces more than three, which is correct - a
    Soft or Start-to-Start overlap is a real schedule tension, just not a
    blocking one. The ranking below is the same one generate_portfolio.py used
    to pick its headline cases: hard blocking links first, then worst overlap
    first. The top three are the planted conflicts.
    """
    found = []
    for e in deps:
        # Only edges that actually carry a date constraint. A Resource link is a
        # capacity dependency, not a scheduling one, and a Start-to-Start link
        # constrains start against start, not against finish. Applying the
        # finish-to-start rule to all 95 edges flagged 9 breaches (6 Resource,
        # 3 Start-to-Start) under a rule that does not govern them - and which
        # the app's own sequencer correctly declines to enforce.
        kind = DATE_CONSTRAINT.get(e["dependency_type"])
        if kind is None:
            continue

        pred = by_id[e["from_initiative"]]
        succ = by_id[e["to_initiative"]]
        pred_end = parse_iso(pred["end_date"])
        anchor = pred_end if kind == "finish" else parse_iso(pred["start_date"])
        required_start = anchor + timedelta(days=e["lag_days"])
        actual_start = parse_iso(succ["start_date"])
        overlap = (required_start - actual_start).days
        if overlap <= 0:
            continue

        # A Hard Finish-to-Start or Technical Enabler link is one the roadmap is
        # not allowed to break, so an overlap on it is blocking rather than
        # merely awkward.
        blocking = (e["criticality"] == "Hard"
                    and e["dependency_type"] in ("Finish-to-Start", "Technical Enabler"))

        found.append({
            "conflict_type": "Successor starts before predecessor finishes",
            "from_initiative": e["from_initiative"],
            "from_name": pred["name"],
            "from_function": pred["function"],
            "to_initiative": e["to_initiative"],
            "to_name": succ["name"],
            "to_function": succ["function"],
            "dependency_type": e["dependency_type"],
            "criticality": e["criticality"],
            "predecessor_end_date": iso(pred_end),
            "lag_days": e["lag_days"],
            "required_successor_start": iso(required_start),
            "actual_successor_start": iso(actual_start),
            "overlap_days": overlap,
            "blocking": blocking,
            "severity": "High" if overlap > 120 else "Medium",
        })

    found.sort(key=lambda c: (0 if c["blocking"] else 1,
                              -c["overlap_days"],
                              c["from_initiative"],
                              c["to_initiative"]))
    for n, c in enumerate(found, start=1):
        c["conflict_id"] = "DET-%03d" % n
    return found


# ---------------------------------------------------------------------------
# Per-initiative rollups
# ---------------------------------------------------------------------------

def rollups(ids, milestones, risks, issues):
    """Collapse the milestone, risk and issue tables into one summary per
    initiative, so the app does not have to re-aggregate 472 rows on every
    render."""
    out = {}
    for iid in ids:
        out[iid] = {
            "open_issue_count": 0,
            "issue_count": 0,
            "max_risk_score": 0,
            "total_risk_exposure": 0,
            "risk_count": 0,
            "open_regulatory_risk_exposure": 0,
            "regulatory_risk_count": 0,
            "next_milestone": None,
            "total_slip_days": 0,
            "milestone_count": 0,
        }

    for r in risks:
        b = out[r["initiative_id"]]
        b["risk_count"] += 1
        b["max_risk_score"] = max(b["max_risk_score"], int(num(r["score"])))
        b["total_risk_exposure"] += int(num(r["exposure_usd"]))
        # The Regulatory category is what ties a compliance breach back to a
        # dollar figure. Closed risks carry no live exposure.
        if r["category"] == "Regulatory":
            b["regulatory_risk_count"] += 1
            if r["status"] in ("Open", "Mitigating"):
                b["open_regulatory_risk_exposure"] += int(num(r["exposure_usd"]))

    for i in issues:
        b = out[i["initiative_id"]]
        b["issue_count"] += 1
        if i["status"] != "Resolved":
            b["open_issue_count"] += 1

    # Next upcoming milestone = the earliest forecast date still outstanding.
    # A blank actual_date means not yet complete, so status carries the truth.
    for m in milestones:
        b = out[m["initiative_id"]]
        b["milestone_count"] += 1
        b["total_slip_days"] += int(num(m["slip_days"]))
        if m["status"] == "Complete":
            continue
        cand = {
            "milestone_id": m["milestone_id"],
            "name": m["name"],
            "type": m["type"],
            "forecast_date": m["forecast_date"],
            "status": m["status"],
            "slip_days": int(num(m["slip_days"])),
        }
        cur = b["next_milestone"]
        if cur is None or cand["forecast_date"] < cur["forecast_date"]:
            b["next_milestone"] = cand
    return out


def rank_desc(values_by_id):
    """Rank 1 = highest value. Ties break on initiative_id so the output is
    byte-identical between runs."""
    ordered = sorted(values_by_id.items(), key=lambda kv: (-kv[1], kv[0]))
    return {iid: n for n, (iid, _) in enumerate(ordered, start=1)}


# ---------------------------------------------------------------------------

def main():
    print("\nReading from %s" % SRC)
    print("(%s is deliberately NOT read - it is a pre-diagnosed answer key)\n"
          % ANSWER_KEY)

    # ---- read -------------------------------------------------------------
    # initiatives.json is preferred over initiatives.csv for the spine: it is
    # already correctly typed, so numbers are real numbers and is_regulatory is
    # a real boolean. That removes an entire class of parsing bug.
    initiatives = load_json(os.path.join(SRC, "initiatives.json"))
    scenarios = load_json(os.path.join(SRC, "scenarios.json"))
    deps_raw = load(os.path.join(SRC, "dependencies.csv"))
    milestones = load(os.path.join(SRC, "milestones.csv"))
    risks = load(os.path.join(SRC, "risks.csv"))
    issues = load(os.path.join(SRC, "issues.csv"))
    resources_raw = load(os.path.join(SRC, "resources.csv"))
    burn_raw = load(os.path.join(SRC, "burn.csv"))
    benefits_raw = load(os.path.join(SRC, "benefits.csv"))

    ids = {i["initiative_id"] for i in initiatives}
    by_id = {i["initiative_id"]: i for i in initiatives}

    deps = [{
        "from_initiative": e["from_initiative"],
        "to_initiative": e["to_initiative"],
        "dependency_type": e["dependency_type"],
        "lag_days": int(num(e["lag_days"])),
        "criticality": e["criticality"],
        "notes": e["notes"],
    } for e in deps_raw]

    print("--- row counts read --------------------------------------------")
    counts = {
        "initiatives.json": len(initiatives),
        "dependencies.csv": len(deps),
        "milestones.csv": len(milestones),
        "risks.csv": len(risks),
        "issues.csv": len(issues),
        "resources.csv": len(resources_raw),
        "burn.csv": len(burn_raw),
        "benefits.csv": len(benefits_raw),
        "scenarios.json": len(scenarios["scenarios"]),
    }
    for name, n in counts.items():
        print("  %-22s %6d" % (name, n))
    total_rows = (len(initiatives) + len(deps) + len(milestones) + len(risks)
                  + len(issues) + len(resources_raw) + len(burn_raw)
                  + len(benefits_raw))
    print("  %-22s %6d" % ("TOTAL data rows", total_rows))

    # ---- build-time integrity checks -------------------------------------
    # Ported from validate_portfolio.py so this script fails loudly if the data
    # is not what the brief says it is.
    print("\n--- integrity checks -------------------------------------------")

    check("answer key never read", ANSWER_KEY not in READ_FILES,
          "opened: %s" % sorted(set(READ_FILES)) if ANSWER_KEY in READ_FILES else "")

    check("60 initiatives", len(initiatives) == 60, "got %d" % len(initiatives))
    check("95 dependency edges", len(deps) == 95, "got %d" % len(deps))

    check("no self-referencing edges",
          all(e["from_initiative"] != e["to_initiative"] for e in deps), "")

    check("no duplicate edges",
          len({(e["from_initiative"], e["to_initiative"]) for e in deps}) == len(deps),
          "")

    for label, rows, col in [
        ("dependencies.from", deps, "from_initiative"),
        ("dependencies.to", deps, "to_initiative"),
        ("milestones", milestones, "initiative_id"),
        ("risks", risks, "initiative_id"),
        ("issues", issues, "initiative_id"),
        ("burn", burn_raw, "initiative_id"),
        ("benefits", benefits_raw, "initiative_id"),
    ]:
        orphans = sorted({r[col] for r in rows} - ids)
        check("FK %s -> initiatives" % label, not orphans,
              "orphans: %s" % orphans[:5] if orphans else "")

    risk_ids = {r["risk_id"] for r in risks}
    bad_links = sorted({r["linked_risk_id"] for r in issues
                        if r["linked_risk_id"]} - risk_ids)
    check("FK issues.linked_risk_id -> risks", not bad_links,
          "orphans: %s" % bad_links[:5] if bad_links else "")

    scen_ids = {e["initiative_id"]
                for s in scenarios["scenarios"]
                for key in ("mandatory_initiatives", "deferred_initiatives")
                for e in s["constraints"][key]}
    check("FK scenarios -> initiatives", not (scen_ids - ids),
          "orphans: %s" % sorted(scen_ids - ids)[:5])

    mismatch = [i["initiative_id"] for i in initiatives
                if i["capex"] + i["opex"] != i["total_budget"]]
    check("capex + opex == total_budget", not mismatch,
          "offenders: %s" % mismatch[:5] if mismatch else "")

    bad_dates = [i["initiative_id"] for i in initiatives
                 if i["end_date"] <= i["start_date"]]
    check("end_date after start_date", not bad_dates,
          "offenders: %s" % bad_dates[:5] if bad_dates else "")

    early_value = [i["initiative_id"] for i in initiatives
                   if i["benefit_start_month"] < i["duration_months"]]
    check("benefit_start_month >= duration_months", not early_value,
          "offenders: %s" % early_value[:5] if early_value else "")

    # The as-of boundary must survive into the output untouched.
    leaked = sorted({r["month"] for r in burn_raw
                     if r["month"] > AS_OF_MONTH and r["actual_spend"] != ""})
    check("burn actuals stop at %s" % AS_OF_MONTH, not leaked,
          "leaked: %s" % leaked[:5] if leaked else "")
    leaked_ben = sorted({r["month"] for r in benefits_raw
                         if r["month"] > AS_OF_MONTH and r["benefit_actual"] != ""})
    check("benefit actuals stop at %s" % AS_OF_MONTH, not leaked_ben,
          "leaked: %s" % leaked_ben[:5] if leaked_ben else "")

    months = sorted({r["month"] for r in burn_raw})
    check("window is %d months %s..2027-12" % (WINDOW_MONTHS, WINDOW_START),
          len(months) == WINDOW_MONTHS and months[0] == WINDOW_START,
          "%d months, %s..%s" % (len(months), months[0], months[-1]))

    # ---- topological sort -------------------------------------------------
    print("\n--- dependency graph -------------------------------------------")
    order, wave, outgoing = topo_sort_with_waves(ids, deps)
    check("graph is acyclic", len(order) == len(ids),
          "topologically sorted %d of %d nodes" % (len(order), len(ids)))
    max_wave = max(wave.values()) if wave else 0
    per_wave = defaultdict(int)
    for w in wave.values():
        per_wave[w] += 1
    print("  waves 0..%d, sizes: %s"
          % (max_wave, {w: per_wave[w] for w in sorted(per_wave)}))

    cross = sum(1 for e in deps
                if by_id[e["from_initiative"]]["function"]
                != by_id[e["to_initiative"]]["function"])
    print("  %d of %d edges cross a function boundary" % (cross, len(deps)))
    hard = sum(1 for e in deps if e["criticality"] == "Hard")
    print("  %d Hard edges, %d Soft" % (hard, len(deps) - hard))

    # ---- transitive closure and rankings ---------------------------------
    closure = transitive_downstream(order, outgoing)

    down_count = {iid: len(closure.get(iid, set())) for iid in ids}
    down_benefit = {iid: sum(by_id[m]["annual_benefit_target"]
                             for m in closure.get(iid, set()))
                    for iid in ids}
    naive_roi = {}
    for iid in ids:
        b = by_id[iid]["total_budget"]
        naive_roi[iid] = (by_id[iid]["annual_benefit_target"] / b) if b else 0.0

    naive_rank = rank_desc(naive_roi)
    corrected_rank = rank_desc(down_benefit)

    # ---- conflict detection ----------------------------------------------
    print("\n--- dependency conflicts (detected independently) --------------")
    conflicts = detect_conflicts(by_id, deps)
    blocking = [c for c in conflicts if c["blocking"]]

    print("  %d edges of %d have a positive overlap; %d of those are blocking"
          % (len(conflicts), len(deps), len(blocking)))
    print("  (blocking = Hard AND Finish-to-Start or Technical Enabler)\n")
    print("  %-4s %-9s %-9s %-16s %-5s %-11s %-11s %8s"
          % ("#", "PRED", "SUCC", "TYPE", "CRIT", "PRED ENDS", "SUCC STARTS", "OVERLAP"))
    for n, c in enumerate(conflicts, start=1):
        print("  %-4s %-9s %-9s %-16s %-5s %-11s %-11s %6d d%s"
              % (n, c["from_initiative"], c["to_initiative"],
                 c["dependency_type"], c["criticality"],
                 c["predecessor_end_date"], c["actual_successor_start"],
                 c["overlap_days"], "  <-- BLOCKING" if c["blocking"] else ""))

    print("")
    top3 = [(c["from_initiative"], c["to_initiative"], c["overlap_days"])
            for c in conflicts[:3]]
    check("worst 3 conflicts match the expected planted cases",
          top3 == EXPECTED_CONFLICTS,
          "got %s" % (top3,) if top3 != EXPECTED_CONFLICTS else "716, 710, 627 days")
    check("worst overlap is 716 days",
          bool(conflicts) and conflicts[0]["overlap_days"] == 716,
          "got %s" % (conflicts[0]["overlap_days"] if conflicts else None))

    for a, b, days in EXPECTED_CONFLICTS:
        hit = [c for c in conflicts
               if c["from_initiative"] == a and c["to_initiative"] == b]
        check("%s -> %s detected at %d days" % (a, b, days),
              bool(hit) and hit[0]["overlap_days"] == days,
              "got %s" % (hit[0]["overlap_days"] if hit else "not found"))

    # ---- assemble the output ---------------------------------------------
    roll = rollups(ids, milestones, risks, issues)

    out_initiatives = []
    for i in initiatives:
        iid = i["initiative_id"]
        rec = dict(i)
        # is_regulatory arrives as a real boolean from initiatives.json; force it
        # anyway so the contract holds no matter which source is used.
        rec["is_regulatory"] = to_bool(i["is_regulatory"])
        rec["key_systems_list"] = [s.strip() for s in
                                   str(i["key_systems"]).split(";") if s.strip()]
        rec["tags_list"] = [s.strip() for s in
                            str(i["tags"]).split(";") if s.strip()]

        # benefit_start_month is an OFFSET in months from this initiative's own
        # start_date, NOT a calendar month. Resolve it once, here, so no
        # downstream consumer can make that mistake.
        start = parse_iso(i["start_date"])
        first = add_months(start, i["benefit_start_month"])
        rec["benefit_first_month"] = month_key(first)
        rec["benefit_first_month_index"] = month_index(first)
        rec["start_month"] = month_key(start)
        rec["end_month"] = month_key(parse_iso(i["end_date"]))
        rec["start_quarter"] = quarter_of(start)

        rec["wave"] = wave[iid]
        rec["direct_downstream_count"] = len(outgoing.get(iid, []))
        rec["transitive_downstream_count"] = down_count[iid]
        rec["transitive_downstream_benefit"] = down_benefit[iid]
        rec["transitive_downstream_ids"] = sorted(closure.get(iid, set()))
        rec["naive_roi"] = round(naive_roi[iid], 6)
        rec["naive_roi_rank"] = naive_rank[iid]
        rec["corrected_rank"] = corrected_rank[iid]
        rec["rank_movement"] = naive_rank[iid] - corrected_rank[iid]
        rec["rollup"] = roll[iid]
        out_initiatives.append(rec)

    out_resources = [{
        "role": r["role"],
        "month": r["month"],
        "quarter": r["quarter"],
        "available_fte": num(r["available_fte"]),
        "demanded_fte": num(r["demanded_fte"]),
        "gap_fte": num(r["gap_fte"]),
        "utilisation_pct": num(r["utilisation_pct"]),
        "over_allocated": to_bool(r["over_allocated"]),
    } for r in resources_raw]

    out_burn = [{
        "initiative_id": r["initiative_id"],
        "month": r["month"],
        "planned_spend": num(r["planned_spend"]),
        "cumulative_planned": num(r["cumulative_planned"]),
        "forecast_spend": num(r["forecast_spend"]),
        # null for months after the as-of date. Future, not missing.
        "actual_spend": num_or_none(r["actual_spend"]),
        "cumulative_actual": num_or_none(r["cumulative_actual"]),
        "benefit_realized": num_or_none(r["benefit_realized"]),
    } for r in burn_raw]

    out_benefits = [{
        "initiative_id": r["initiative_id"],
        "month": r["month"],
        "benefit_plan": num(r["benefit_plan"]),
        "benefit_actual": num_or_none(r["benefit_actual"]),
        "pnl_impact_type": r["pnl_impact_type"],
        "confidence": r["confidence"],
    } for r in benefits_raw]

    out_milestones = [{
        "milestone_id": m["milestone_id"],
        "initiative_id": m["initiative_id"],
        "name": m["name"],
        "type": m["type"],
        "baseline_date": m["baseline_date"],
        "forecast_date": m["forecast_date"],
        # blank = not yet complete
        "actual_date": text_or_none(m["actual_date"]),
        "status": m["status"],
        "slip_days": int(num(m["slip_days"])),
        "owner": m["owner"],
    } for m in milestones]

    out_risks = [{
        "risk_id": r["risk_id"],
        "initiative_id": r["initiative_id"],
        "title": r["title"],
        "category": r["category"],
        "probability": int(num(r["probability"])),
        "impact": int(num(r["impact"])),
        "score": int(num(r["score"])),
        "exposure_usd": int(num(r["exposure_usd"])),
        "mitigation": r["mitigation"],
        "owner": r["owner"],
        "status": r["status"],
        "raised_date": r["raised_date"],
        "target_resolution_date": r["target_resolution_date"],
    } for r in risks]

    out_issues = [{
        "issue_id": i["issue_id"],
        "initiative_id": i["initiative_id"],
        "title": i["title"],
        "severity": i["severity"],
        "status": i["status"],
        "raised_date": i["raised_date"],
        "age_days": int(num(i["age_days"])),
        "owner": i["owner"],
        "impact_on_schedule_days": int(num(i["impact_on_schedule_days"])),
        "impact_on_cost_usd": int(num(i["impact_on_cost_usd"])),
        # blank = no risk predicted this issue
        "linked_risk_id": text_or_none(i["linked_risk_id"]),
    } for i in issues]

    # Portfolio-level figures, computed here so the page never has to.
    totals = {
        "initiative_count": len(initiatives),
        "total_budget": sum(i["total_budget"] for i in initiatives),
        "total_capex": sum(i["capex"] for i in initiatives),
        "total_opex": sum(i["opex"] for i in initiatives),
        "total_forecast_at_completion": sum(i["forecast_at_completion"]
                                            for i in initiatives),
        "total_spend_to_date": sum(i["spend_to_date"] for i in initiatives),
        "total_annual_benefit_target": sum(i["annual_benefit_target"]
                                            for i in initiatives),
        "benefit_actual_to_date": sum(r["benefit_actual"] or 0
                                       for r in out_benefits),
        "dependency_count": len(deps),
        "cross_function_dependency_count": cross,
        "hard_dependency_count": hard,
        "detected_conflict_count": len(conflicts),
        "blocking_conflict_count": len(blocking),
        "regulatory_count": sum(1 for i in initiatives
                                if to_bool(i["is_regulatory"])),
        "rag_counts": {
            "Green": sum(1 for i in initiatives if i["rag_status"] == "Green"),
            "Amber": sum(1 for i in initiatives if i["rag_status"] == "Amber"),
            "Red": sum(1 for i in initiatives if i["rag_status"] == "Red"),
        },
        "over_budget_count_5pct": sum(
            1 for i in initiatives
            if i["forecast_at_completion"] > i["total_budget"] * 1.05),
        "over_budget_count_any": sum(
            1 for i in initiatives
            if i["forecast_at_completion"] > i["total_budget"]),
        "regulatory_risk_exposure_open": sum(
            r["exposure_usd"] for r in out_risks
            if r["category"] == "Regulatory"
            and r["status"] in ("Open", "Mitigating")),
        "regulatory_risk_exposure_total": sum(
            r["exposure_usd"] for r in out_risks if r["category"] == "Regulatory"),
        "risk_count": len(out_risks),
        "issue_count": len(out_issues),
        "max_wave": max_wave,
    }

    payload = {
        "meta": {
            "as_of_month": AS_OF_MONTH,
            "window_start": WINDOW_START,
            "window_months": WINDOW_MONTHS,
            "currency": "USD",
            "source_row_counts": counts,
            "answer_key_excluded": ANSWER_KEY,
            "note": ("Blank actual_spend, cumulative_actual, benefit_realized and "
                     "benefit_actual values are null because the month is after the "
                     "%s as-of date. They are future months, not missing data, and "
                     "have not been imputed or zero-filled." % AS_OF_MONTH),
        },
        "totals": totals,
        "initiatives": out_initiatives,
        "dependencies": deps,
        "detected_conflicts": conflicts,
        "topological_order": order,
        "milestones": out_milestones,
        "risks": out_risks,
        "issues": out_issues,
        "resources": out_resources,
        "burn": out_burn,
        "benefits": out_benefits,
        "scenarios": scenarios,
    }

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUT_PATH) / (1024.0 * 1024.0)

    # ---- summary ----------------------------------------------------------
    print("\n--- portfolio figures ------------------------------------------")
    print("  initiatives                  %d" % totals["initiative_count"])
    print("  approved budget              $%s" % "{:,}".format(totals["total_budget"]))
    print("  forecast at completion       $%s" % "{:,}".format(totals["total_forecast_at_completion"]))
    print("  overrun                      $%s" % "{:,}".format(
        totals["total_forecast_at_completion"] - totals["total_budget"]))
    # Deliberately NOT printed side by side with benefit_actual_to_date. Setting
    # a steady-state annual rate against a seven-month actuals window overstates
    # the gap by orders of magnitude; the like-for-like comparison is the annual
    # run rate the plan reaches by the end of the window, which the app computes
    # as _exit_run_rate ($39.6m, 47% of the promise).
    print("  promised annual benefit      $%s"
          % "{:,}".format(totals["total_annual_benefit_target"]))
    print("  RAG                          %d Green / %d Amber / %d Red"
          % (totals["rag_counts"]["Green"], totals["rag_counts"]["Amber"],
             totals["rag_counts"]["Red"]))
    print("  over budget (>5%%)            %d of %d" % (totals["over_budget_count_5pct"],
                                                        totals["initiative_count"]))
    print("  regulatory initiatives       %d" % totals["regulatory_count"])

    print("\n  top 5 by what they unblock:")
    top_unblock = sorted(out_initiatives,
                         key=lambda r: -r["transitive_downstream_benefit"])[:5]
    for r in top_unblock:
        print("    %s  gates %2d initiatives worth $%-14s (naive ROI rank %d of 60)"
              % (r["initiative_id"], r["transitive_downstream_count"],
                 "{:,}".format(r["transitive_downstream_benefit"]),
                 r["naive_roi_rank"]))

    print("\n  the money shot:")
    m = next(r for r in out_initiatives if r["initiative_id"] == "INIT-001")
    print("    INIT-001 %s" % m["name"])
    print("    costs $%s, returns $%s a year standalone (ratio %.3f, naive rank %d of 60)"
          % ("{:,}".format(m["total_budget"]),
             "{:,}".format(m["annual_benefit_target"]),
             m["naive_roi"], m["naive_roi_rank"]))
    print("    gates %d initiatives carrying $%s -> corrected rank %d"
          % (m["transitive_downstream_count"],
             "{:,}".format(m["transitive_downstream_benefit"]),
             m["corrected_rank"]))

    print("\n--- output -----------------------------------------------------")
    print("  wrote %s (%.2f MB)" % (os.path.relpath(OUT_PATH, HERE), size_mb))
    print("  nodes topologically sorted: %d of %d" % (len(order), len(ids)))
    print("  dependency conflicts detected: %d (%d blocking)"
          % (len(conflicts), len(blocking)))

    print("\n================================================================")
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print("%d of %d build-time checks passed." % (passed, len(CHECKS)))
    if FAILS:
        print("\nFAILURES:")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
