#!/usr/bin/env python3
"""
validate_portfolio.py — sanity checks over the generated dataset.

Run this after generate_portfolio.py. It fails loudly rather than quietly, so
the team can trust the data they build on. Checks:

  * the dependency graph is acyclic (Kahn's algorithm)
  * every foreign key resolves — no orphan initiative_id / risk_id anywhere
  * row counts sit in the expected ranges
  * no negative budgets, spend or benefits
  * actuals stop at 2026-07 and are present before it
  * internal consistency: capex + opex == total_budget, dates in order
  * the deliberate conflicts really are conflicts

Usage:  python3 validate_portfolio.py [--data DIR]
Exit code 0 = all good, 1 = something failed.
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict, deque

FAILS = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    if not ok:
        FAILS.append("%s — %s" % (name, detail))
    print("  [%s] %-52s %s" % ("PASS" if ok else "FAIL", name, detail))


def load(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data"))
    args = ap.parse_args()
    d = args.data

    initiatives = load(os.path.join(d, "initiatives.csv"))
    deps = load(os.path.join(d, "dependencies.csv"))
    conflicts = load(os.path.join(d, "dependency_conflicts.csv"))
    milestones = load(os.path.join(d, "milestones.csv"))
    risks = load(os.path.join(d, "risks.csv"))
    issues = load(os.path.join(d, "issues.csv"))
    resources = load(os.path.join(d, "resources.csv"))
    burn = load(os.path.join(d, "burn.csv"))
    benefits = load(os.path.join(d, "benefits.csv"))
    with open(os.path.join(d, "scenarios.json"), encoding="utf-8") as fh:
        scenarios = json.load(fh)
    with open(os.path.join(d, "initiatives.json"), encoding="utf-8") as fh:
        initiatives_json = json.load(fh)

    ids = {r["initiative_id"] for r in initiatives}

    print("\n--- row counts -------------------------------------------------")
    ranges = {
        "initiatives.csv": (60, 60, initiatives),
        "dependencies.csv": (70, 110, deps),
        "dependency_conflicts.csv": (2, 3, conflicts),
        "milestones.csv": (250, 400, milestones),
        "risks.csv": (90, 135, risks),
        "issues.csv": (60, 95, issues),
        "resources.csv": (240, 400, resources),
        "burn.csv": (1440, 1440, burn),
        "benefits.csv": (1440, 1440, benefits),
    }
    for fname, (lo, hi, rows) in ranges.items():
        check("count %s = %d" % (fname, len(rows)), lo <= len(rows) <= hi,
              "expected %d-%d" % (lo, hi))
    check("count scenarios.json = %d" % len(scenarios["scenarios"]),
          len(scenarios["scenarios"]) == 3, "expected 3")
    check("initiatives.json matches CSV", len(initiatives_json) == len(initiatives),
          "%d vs %d" % (len(initiatives_json), len(initiatives)))

    print("\n--- dependency graph -------------------------------------------")
    # Kahn's algorithm: if we can peel every node off, there is no cycle.
    outgoing = defaultdict(list)
    indeg = {i: 0 for i in ids}
    for e in deps:
        outgoing[e["from_initiative"]].append(e["to_initiative"])
        indeg[e["to_initiative"]] += 1
    queue = deque([n for n, v in indeg.items() if v == 0])
    visited = 0
    while queue:
        n = queue.popleft()
        visited += 1
        for m in outgoing[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    check("dependency graph is acyclic", visited == len(ids),
          "topologically sorted %d of %d nodes" % (visited, len(ids)))

    check("no self-referencing edges",
          all(e["from_initiative"] != e["to_initiative"] for e in deps), "")
    check("no duplicate edges",
          len({(e["from_initiative"], e["to_initiative"]) for e in deps}) == len(deps), "")
    cross = sum(1 for e in deps if fn(initiatives, e["from_initiative"])
                != fn(initiatives, e["to_initiative"]))
    check("cross-function edges >= 40%%: %d of %d (%.0f%%)"
          % (cross, len(deps), 100.0 * cross / len(deps)),
          cross / len(deps) >= 0.40, "")

    print("\n--- foreign keys -----------------------------------------------")
    risk_ids = {r["risk_id"] for r in risks}
    for label, rows, col in [
        ("dependencies.from", deps, "from_initiative"),
        ("dependencies.to", deps, "to_initiative"),
        ("dependency_conflicts.from", conflicts, "from_initiative"),
        ("dependency_conflicts.to", conflicts, "to_initiative"),
        ("milestones", milestones, "initiative_id"),
        ("risks", risks, "initiative_id"),
        ("issues", issues, "initiative_id"),
        ("burn", burn, "initiative_id"),
        ("benefits", benefits, "initiative_id"),
    ]:
        bad = sorted({r[col] for r in rows} - ids)
        check("FK %s -> initiatives" % label, not bad, "orphans: %s" % bad[:5])

    bad_links = sorted({r["linked_risk_id"] for r in issues
                        if r["linked_risk_id"]} - risk_ids)
    check("FK issues.linked_risk_id -> risks", not bad_links, "orphans: %s" % bad_links[:5])

    covered = {r["initiative_id"] for r in burn}
    check("every initiative appears in burn.csv", covered == ids,
          "missing: %s" % sorted(ids - covered)[:5])
    ms_covered = {r["initiative_id"] for r in milestones}
    check("every initiative has milestones", ms_covered == ids,
          "missing: %s" % sorted(ids - ms_covered)[:5])

    scen_ids = {e["initiative_id"]
                for s in scenarios["scenarios"]
                for key in ("mandatory_initiatives", "deferred_initiatives")
                for e in s["constraints"][key]}
    check("FK scenarios -> initiatives", not (scen_ids - ids),
          "orphans: %s" % sorted(scen_ids - ids)[:5])

    print("\n--- money and numbers ------------------------------------------")
    neg = [r["initiative_id"] for r in initiatives
           if min(int(r["total_budget"]), int(r["capex"]), int(r["opex"]),
                  int(r["spend_to_date"]), int(r["forecast_at_completion"]),
                  int(r["annual_benefit_target"])) < 0]
    check("no negative budgets / spend / benefits", not neg, "offenders: %s" % neg[:5])

    mismatch = [r["initiative_id"] for r in initiatives
                if int(r["capex"]) + int(r["opex"]) != int(r["total_budget"])]
    check("capex + opex == total_budget", not mismatch, "offenders: %s" % mismatch[:5])

    bad_dates = [r["initiative_id"] for r in initiatives if r["end_date"] <= r["start_date"]]
    check("end_date after start_date", not bad_dates, "offenders: %s" % bad_dates[:5])

    bad_pct = [r["initiative_id"] for r in initiatives
               if not 0 <= int(r["percent_complete"]) <= 100]
    check("percent_complete within 0-100", not bad_pct, "offenders: %s" % bad_pct[:5])

    neg_burn = [r for r in burn if int(r["planned_spend"]) < 0
                or (r["actual_spend"] and int(r["actual_spend"]) < 0)]
    check("no negative spend in burn.csv", not neg_burn, "%d rows" % len(neg_burn))

    neg_ben = [r for r in benefits if int(r["benefit_plan"]) < 0
               or (r["benefit_actual"] and int(r["benefit_actual"]) < 0)]
    check("no negative benefit in benefits.csv", not neg_ben, "%d rows" % len(neg_ben))

    print("\n--- the clock (today = 2026-08-11) -----------------------------")
    CUTOFF = "2026-07"
    late_actuals = sorted({r["month"] for r in burn
                           if r["month"] > CUTOFF and r["actual_spend"] != ""})
    check("burn actuals stop at 2026-07", not late_actuals, "leaked: %s" % late_actuals[:5])

    late_cum = sorted({r["month"] for r in burn
                       if r["month"] > CUTOFF and r["cumulative_actual"] != ""})
    check("burn cumulative_actual stops at 2026-07", not late_cum, "leaked: %s" % late_cum[:5])

    late_realized = sorted({r["month"] for r in burn
                            if r["month"] > CUTOFF and r["benefit_realized"] != ""})
    check("burn benefit_realized stops at 2026-07", not late_realized,
          "leaked: %s" % late_realized[:5])

    late_ben = sorted({r["month"] for r in benefits
                       if r["month"] > CUTOFF and r["benefit_actual"] != ""})
    check("benefit actuals stop at 2026-07", not late_ben, "leaked: %s" % late_ben[:5])

    missing_actuals = [r for r in burn if r["month"] <= CUTOFF and r["actual_spend"] == ""]
    check("actuals present for every month up to 2026-07", not missing_actuals,
          "%d blank rows" % len(missing_actuals))

    months = sorted({r["month"] for r in burn})
    check("burn window is 24 months 2026-01..2027-12",
          len(months) == 24 and months[0] == "2026-01" and months[-1] == "2027-12",
          "%d months, %s..%s" % (len(months), months[0], months[-1]))

    future_actual_dates = [r["milestone_id"] for r in milestones
                           if r["actual_date"] and r["actual_date"] > "2026-08-11"]
    check("no milestone actual_date in the future", not future_actual_dates,
          "offenders: %s" % future_actual_dates[:5])

    print("\n--- value lands after delivery ---------------------------------")
    early_value = [r["initiative_id"] for r in initiatives
                   if int(r["benefit_start_month"]) < int(r["duration_months"])]
    check("benefit_start_month >= duration_months", not early_value,
          "offenders: %s" % early_value[:5])

    print("\n--- deliberate imperfections (these SHOULD be present) ---------")
    overburn = [r["initiative_id"] for r in initiatives
                if int(r["forecast_at_completion"]) > int(r["total_budget"]) * 1.05]
    check("some initiatives over-burn (>5%% over budget): %d" % len(overburn),
          len(overburn) >= 8, "need at least 8 for the burn view")

    # The constraint only means something if the squeeze is concentrated on a
    # few roles. If everything is over-allocated, nothing is.
    per_role = defaultdict(int)
    for r in resources:
        if r["over_allocated"] == "TRUE":
            per_role[r["role"]] += 1
    pinch = sorted(role for role, n in per_role.items() if n >= 4)
    incidental = sorted(role for role, n in per_role.items() if 0 < n < 4)
    check("2-4 roles are genuine pinch points: %s" % pinch,
          2 <= len(pinch) <= 4, "months over: %s" % {r: per_role[r] for r in pinch})
    check("the squeeze is concentrated, not universal",
          len(pinch) + len(incidental) <= 6,
          "incidental breaches: %s" % {r: per_role[r] for r in incidental})

    crunch = [r for r in resources
              if r["role"] in pinch and r["quarter"] in ("2026Q4", "2027Q1")]
    check("pinch roles are over-allocated in the crunch quarters",
          crunch and sum(1 for r in crunch if r["over_allocated"] == "TRUE") >= len(crunch) * 0.7,
          "%d of %d crunch months over"
          % (sum(1 for r in crunch if r["over_allocated"] == "TRUE"), len(crunch)))

    real_conflicts = [c for c in conflicts if int(c["overlap_days"]) > 0]
    check("dependency_conflicts are real overlaps: %d" % len(real_conflicts),
          len(real_conflicts) == len(conflicts) and len(conflicts) >= 2, "")

    reds = sum(1 for r in initiatives if r["rag_status"] == "Red")
    check("portfolio has Red initiatives: %d" % reds, reds >= 5, "")

    print("\n================================================================")
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print("%d of %d checks passed." % (passed, len(CHECKS)))
    if FAILS:
        print("\nFAILURES:")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("All checks passed.")
    return 0


_FN_CACHE = {}


def fn(initiatives, iid):
    if not _FN_CACHE:
        for r in initiatives:
            _FN_CACHE[r["initiative_id"]] = r["function"]
    return _FN_CACHE.get(iid)


if __name__ == "__main__":
    sys.exit(main())
