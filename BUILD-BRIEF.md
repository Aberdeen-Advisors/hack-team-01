# BUILD BRIEF — Transformation Roadmap Generator

**Read this one file and you can build the whole MVP. Nothing else is required reading.**

Everything below was checked against the files in this repository, not remembered. Row counts, column
names, totals and identifiers are real. Where a number appears here, it came out of the data.

---

## 1. What we are building

A **Transformation Roadmap Generator** for a newly appointed transformation leader — someone who has
just walked into a job where sixty initiatives already exist, written by sixty different people, and
who has to tell a board what happens first. It converts that inherited portfolio of 60 initiatives
into four things: a sequenced roadmap, a dependency view, a comparison of three funding scenarios,
and a value-realisation plan showing when benefit actually reaches the P&L. It has two audiences —
the transformation leader, who needs initiative-level detail to run the programme day to day, and the
board, who needs the handful of decisions that are genuinely theirs to make.

---

## 2. Hard constraints

These are not preferences. A build that breaks them is the wrong build.

- **A static single-page app at the REPO ROOT.** Exactly three new artefacts:
  - `index.html`
  - `app.js`
  - `data/portfolio.json`

  The root location matters: the deployment target publishes a literal root `index.html`.
- **No backend. No build step. No `npm install`. No framework. No API key. No network call at
  runtime.** The page must work when opened from a local folder with a plain static file server and
  nothing else running.
- **All computation happens in plain browser JavaScript** — the sequencing, the conflict detection,
  the scenario filtering, the benefit curve. No live model call at demo time. A judge cannot tell a
  live model call from deterministic code, but a live call can fail in the room.
- **Charts are inline SVG, drawn by hand.** No chart library. If a chart genuinely cannot be drawn
  by hand, one single CDN `<script>` tag is the absolute ceiling — and it is a last resort, not a
  starting point.
- **Do NOT modify anything under `synthetic-data/`.** That directory is the system of record. Both
  `generate_portfolio.py` and `validate_portfolio.py` depend on those files exactly as they are, and
  the hand-written documents in `synthetic-data/docs/` were authored against one specific random
  seed — regenerating the dataset silently breaks the alignment between the documents and the data.
  Read from `synthetic-data/`, write only to the repo root.

The one piece of Python you may write is a **build-time flattener** that reads the CSVs and emits
`data/portfolio.json`. It runs once, on your machine, and the JSON it produces is committed. It is
not part of the running app.

---

## 3. The data model

Everything lives in `synthetic-data/data/`. **9 CSV files, 2 JSON files, 3,870 data rows,
60 initiatives, as-of month 2026-07.** All money is **USD**.

| File | Rows | Cols | Feeds |
|---|---:|---:|---|
| `initiatives.csv` | 60 | 37 | Sequenced roadmap |
| `dependencies.csv` | 95 | 6 | Dependency view |
| `dependency_conflicts.csv` | 3 | 17 | **Test fixture only — see §5** |
| `milestones.csv` | 259 | 10 | Sequenced roadmap |
| `risks.csv` | 131 | 14 | Health / exec dashboard |
| `issues.csv` | 82 | 12 | Health / exec dashboard |
| `resources.csv` | 360 | 8 | Scenario comparison |
| `burn.csv` | 1,440 | 8 | Value realisation |
| `benefits.csv` | 1,440 | 6 | Value realisation |
| `scenarios.json` | 3 scenarios | 5 top-level keys | Scenario comparison |
| `initiatives.json` | 60 objects | 37 keys | Sequenced roadmap |

`initiative_id` (`INIT-001` … `INIT-060`) is the primary key of the whole dataset. Every other file
joins back to it.

### 3.1 `initiatives.csv` — 60 rows × 37 columns

The spine. One row per initiative. Header row, in file order:

```
initiative_id,name,function,pillar,owner,sponsor,business_unit,description,objective,
start_date,end_date,duration_months,stage,rag_status,percent_complete,priority_score,
strategic_alignment,value_confidence,complexity,effort_fte,capex,opex,total_budget,
spend_to_date,forecast_at_completion,annual_benefit_target,benefit_type,
benefit_start_month,benefit_ramp_months,npv,payback_months,run_rate_savings,
resource_type_needed,key_systems,region,is_regulatory,tags
```

Values you will need to branch on:

- `function` — `Cost Reduction`, `Finance`, `Growth / Commercial`, `HR / People`, `Operations`,
  `Risk & Compliance`, `Supply Chain`, `Technology`
- `pillar` — `Cost Out`, `Grow`, `Protect`, `Run Better`
- `stage` — `Approved`, `At Risk`, `Business Case`, `Complete`, `Idea`, `In Flight`, `Paused`
  (actual spread: In Flight 29, Business Case 11, At Risk 8, Approved 6, Paused 3, Idea 2,
  Complete 1)
- `rag_status` — `Amber`, `Green`, `Red`
- `value_confidence` — `High`, `Low`, `Med`
- `benefit_type` — `Capability` (5), `Cost Avoidance` (6), `Cost Save` (33), `Revenue Uplift` (8),
  `Risk Reduction` (8)
- `resource_type_needed` — 13 roles, matching the `role` column in `resources.csv`
- `is_regulatory` — `True` / `False`, **title case**. 8 initiatives are `True`.
- `strategic_alignment` 2–5, `complexity` 1–5, `priority_score` 36–100, `percent_complete` 0–100
- `start_date` 2025-08-04 … 2027-07-11; `end_date` 2026-07-11 … 2029-02-22; `duration_months` 6–24
- `capex + opex == total_budget` always holds (the validator asserts it)
- `npv` can be negative — that is the signature of an enabling initiative
- `key_systems` and `tags` are semicolon-space separated lists

### 3.2 `dependencies.csv` — 95 rows × 6 columns

The edge list. This is the graph.

```
from_initiative,to_initiative,dependency_type,lag_days,criticality,notes
```

- `dependency_type` — `Data`, `Finish-to-Start`, `Resource`, `Start-to-Start`, `Technical Enabler`
- `lag_days` — one of 0, 5, 10, 14, 20, 30, 45, 60
- `criticality` — `Hard` (54 edges) or `Soft` (41 edges). A `Hard` link is one the roadmap is not
  allowed to break.
- 36 distinct predecessors, 59 distinct successors, **70 of 95 edges cross function boundaries**

### 3.3 `dependency_conflicts.csv` — 3 rows × 17 columns

**The app must not read this file.** See §5.

```
conflict_id,conflict_type,from_initiative,from_name,from_function,to_initiative,to_name,
to_function,dependency_type,criticality,predecessor_end_date,lag_days,
required_successor_start,actual_successor_start,overlap_days,severity,notes
```

### 3.4 `milestones.csv` — 259 rows × 10 columns

```
milestone_id,initiative_id,name,type,baseline_date,forecast_date,actual_date,status,slip_days,owner
```

- `name` — `Benefit Checkpoint 1`, `Build Complete`, `Design Complete`, `Go-Live`,
  `Mobilisation & Scope Sign-Off`, `Stage Gate 2 - Ready for Test`
- `type` — `Benefit Checkpoint`, `Deliverable`, `Gate`, `Go-Live`
- `status` — `Complete`, `In Progress`, `Missed`, `Not Started`
- `slip_days` = `forecast_date` − `baseline_date`
- `actual_date` is **blank on 216 of 259 rows** — those milestones have not completed yet
- All 60 initiatives have milestones (roughly 4–5 gates each)

### 3.5 `risks.csv` — 131 rows × 14 columns

```
risk_id,initiative_id,title,description,category,probability,impact,score,exposure_usd,
mitigation,owner,status,raised_date,target_resolution_date
```

- **`category` — the seven real distinct values are: `Change/Adoption` (18), `Delivery` (16),
  `Financial` (26), `Regulatory` (14), `Resource` (26), `Technical` (17), `Vendor` (14).**
  `Regulatory` is the one that ties the compliance violation type back to the risk register.
- `probability` and `impact` are 1–5; `score` = probability × impact, 1–25
- `exposure_usd` 2,000 – 669,000
- `status` — `Closed`, `Mitigating`, `Open`
- All 60 initiatives carry at least one risk
- The 14 `Regulatory` risks total **$1,089,000** of exposure, 13 of them still Open or Mitigating

### 3.6 `issues.csv` — 82 rows × 12 columns

```
issue_id,initiative_id,title,description,severity,status,raised_date,age_days,owner,
impact_on_schedule_days,impact_on_cost_usd,linked_risk_id
```

- `severity` — `Critical`, `High`, `Low`, `Medium`; `status` — `Blocked`, `In Progress`, `Open`,
  `Resolved`
- 41 of 60 initiatives have issues
- `linked_risk_id` joins `risks.risk_id` and is **blank on 49 of 82 rows** — meaning no risk
  predicted that issue, not missing data

### 3.7 `resources.csv` — 360 rows × 8 columns

Supply versus demand, by role and month. This is the hard constraint on any resequencing.

```
role,month,quarter,available_fte,demanded_fte,gap_fte,utilisation_pct,over_allocated
```

- 15 roles × 24 months (`2026-01` … `2027-12`)
- `gap_fte` = `available_fte` − `demanded_fte`; negative means short
- `utilisation_pct` 0 – 154.8. **Over 100 means the role is oversubscribed.**
- `over_allocated` — `TRUE` / `FALSE`, **UPPER CASE** (different from `is_regulatory`)
- Three genuine pinch-point roles: **Change Manager** (7 months over), **Data Engineer** (6),
  **Supply Chain Analyst** (5), concentrated in 2026Q4–2027Q1

### 3.8 `burn.csv` — 1,440 rows × 8 columns

```
initiative_id,month,planned_spend,actual_spend,cumulative_planned,cumulative_actual,
forecast_spend,benefit_realized
```

- 60 initiatives × 24 months
- `planned_spend`, `cumulative_planned` and `forecast_spend` are populated for **all** 24 months
- `actual_spend`, `cumulative_actual` and `benefit_realized` are **blank for the 1,020 rows after
  2026-07** — those are future months (see §4)

### 3.9 `benefits.csv` — 1,440 rows × 6 columns

```
initiative_id,month,benefit_plan,benefit_actual,pnl_impact_type,confidence
```

- `benefit_plan` is 0 in 1,113 of 1,440 rows — the plan is deliberately back-loaded into 2028
- `benefit_actual` is blank for future months and has exactly **one non-zero value in the entire
  file: 507**
- `pnl_impact_type` — `Cost avoided (non-cash)`, `Enabling (attributed to downstream)`,
  `Gross margin`, `Non-financial / risk`, `Opex reduction`
- `confidence` — `High`, `Low`, `Med`

### 3.10 `scenarios.json` — inputs only, no results

Top-level keys: `generated_for`, `portfolio_total_budget` (95,350,000),
`portfolio_total_capex` (33,352,000), `note`, `scenarios` (array of 3).

Each scenario object: `scenario_id`, `name`, `description`, `constraints`,
`expected_qualitative_outcome`.

| | SC-01 Board baseline | SC-02 Cash-constrained (−25% capex) | SC-03 Speed to value |
|---|---|---|---|
| `budget_cap_usd` | 95,350,000 | 78,187,000 | 95,350,000 |
| `capex_cap_usd` | 33,352,000 | 25,014,000 | 33,352,000 |
| `peak_fte_cap` | `null` | 85 | 95 |
| `mandatory_initiatives` | 8 | 13 | 16 |
| `deferred_initiatives` | 0 | 6 | 6 |
| `must_finish_by` | 2028-12-31 | 2029-06-30 | 2029-06-30 |
| `allow_resequencing` | `false` | `true` | `true` |
| `objective_function` | — | — | "maximise cumulative realised benefit by 2027-06" |

`mandatory_initiatives` and `deferred_initiatives` are arrays of
`{ initiative_id, name, function }`. The six deferred on SC-02 and SC-03 are the same six:
INIT-033, INIT-047, INIT-046, INIT-037, INIT-024, INIT-010. **None of them is regulatory** — which
is exactly the invariant §7 requires the code to preserve.

The file says so itself: *"These are scenario INPUTS only. No results are pre-computed."* Producing
the result is the job of the tool.

### 3.11 `initiatives.json` — 60 objects × 37 keys

A top-level JSON **array**, no wrapper key. Same 37 keys as the CSV in the same order, but properly
typed: numbers are real numbers and `is_regulatory` is a real boolean. **If you are reading the
initiative spine in JavaScript, prefer this file over the CSV** — it removes an entire class of
parsing bug.

---

## 4. Data quirks, written as rules the code must follow

These are not edge cases. Each one has bitten somebody.

1. **Boolean casing differs between files.** `initiatives.is_regulatory` is `True`/`False`
   (title case). `resources.over_allocated` is `TRUE`/`FALSE` (upper case). Normalise both on ingest
   into real booleans and never compare raw strings downstream.
2. **`benefit_start_month` is an OFFSET in months from that initiative's own `start_date`.** It is
   not a calendar month and it is not comparable to the `month` columns in `burn.csv` /
   `benefits.csv`. The range is 7–26. To get the calendar month benefit starts:
   `add_months(initiative.start_date, benefit_start_month)`. Getting this wrong shifts the entire
   value curve by up to two years.
3. **Blank burn and benefit cells after 2026-07 are FUTURE months, not missing data.** The as-of
   month is 2026-07. 1,020 of 1,440 rows have blank actuals for that reason alone. **Never impute
   them, never zero-fill them, never flag them as a data quality problem.** A tool that reports
   "1,020 missing values" has failed its first test in front of a PMO.
4. **All currency is USD.** No conversion, no symbols other than `$`, no ambiguity.
5. **The dependency graph is acyclic by construction** and `validate_portfolio.py` asserts it on
   every run. **If your code reports a cycle, the bug is in your code** — almost always a reversed
   edge direction (`from_initiative` is the predecessor, `to_initiative` is the successor) or a node
   visited twice in the traversal. Do not "fix" the data.
6. **Benefit is back-loaded, and that is the point.** `benefit_actual` sums to **$507** across the
   whole file — but that is a seven-month actuals window (2026-01..2026-07) in which only **1 of 60**
   initiatives had reached its benefit-start month. Against the correctly phased plan for the same
   period (`benefit_plan` summed 2026-01..2026-07 = **$648**) the portfolio is at **78.2%
   attainment**. The real finding is the run-rate gap, not the actuals gap: **$84.3m promised versus
   a $39.6m annual run-rate actually scheduled by end-2027 — 47% of the promise.** This is a finding
   to display, not a bug to correct. **Never compare the $507 to the $84.3m** — see §11.
7. **Blanks are meaningful elsewhere too.** `milestones.actual_date` blank = not yet complete.
   `issues.linked_risk_id` blank = no risk predicted it.

---

## 5. The trap: `dependency_conflicts.csv`

`synthetic-data/data/dependency_conflicts.csv` is a **pre-diagnosed answer key**. It contains the
three planted scheduling breaks with the dates that prove them, already worked out.

**The app must NOT read this file.** Not at build time, not at runtime, not "just to cross-check in
the browser". If the app reads it, the tool is displaying pre-baked answers instead of finding
problems, and the single most valuable claim in the demo becomes untrue.

Use it exactly once: after your detector runs, compare its output to this file by hand and confirm
your code found all three independently. Then keep it out of the code path entirely.

The three conflicts your detector must find on its own — all `Hard` `Finish-to-Start` links,
all severity `High`, all of type "Successor starts before predecessor finishes":

| Conflict | Predecessor | Successor | Predecessor ends | Successor legally can start | Successor actually starts | Overlap |
|---|---|---|---|---|---|---|
| CONF-001 | INIT-039 Organisational Delayering & Span of Control | INIT-031 Finance Shared Services Centre Stand-Up | 2028-06-08 | 2028-07-23 (lag 45d) | 2026-08-07 | **716 days** |
| CONF-002 | INIT-039 Organisational Delayering & Span of Control | INIT-038 Shared Services HR Operating Model | 2028-06-08 | 2028-07-08 (lag 30d) | 2026-07-29 | **710 days** |
| CONF-003 | INIT-005 Cloud Migration Wave 1 - Non-Production | INIT-006 Cloud Migration Wave 2 - Production Workloads | 2027-09-22 | 2027-10-22 (lag 30d) | 2026-02-02 | **627 days** |

The detection rule is simply:
`overlap_days = required_successor_start − actual_successor_start`, where
`required_successor_start = predecessor.end_date + lag_days`. Flag it when that number is positive.
**The worst is 716 days.** If your flattener prints those three IDs and 716, the engine works.

---

## 6. The result-object contract

Agreed and frozen. The engine takes a scenario and returns exactly this shape. Views are written
against it. Do not change it.

```
{
  scenario_id:   "SC-01",
  sequence:      [ { initiative_id, name, function, start, end, wave } ],
  violations:    [ { type, initiative_id, description, severity } ],
  benefit_curve: [ { month, cost_reduction, cost_avoidance, revenue_growth, non_financial } ],
  totals:        { budget, capex, peak_fte,
                   benefit_cash_backed, benefit_cost_avoidance,
                   benefit_revenue, benefit_non_financial }
}
```

### The value-type breakout

`benefit_curve` carries **one series per value category**, not a single planned/realised pair, so the
board tab can stack the bands and show the value mix shifting between scenarios. `totals` carries the
matching per-category subtotals, so a comparison shows what *kind* of value each scenario produces,
not only how much.

No new data is needed. Map the existing enums onto the four bands:

| Band | `initiatives.benefit_type` | `benefits.pnl_impact_type` |
|---|---|---|
| `cost_reduction` | `Cost Save` | `Opex reduction` |
| `cost_avoidance` | `Cost Avoidance` | `Cost avoided (non-cash)` |
| `revenue_growth` | `Revenue Uplift` | `Gross margin` |
| `non_financial` | `Risk Reduction`, `Capability` | `Non-financial / risk`, `Enabling (attributed to downstream)` |

Two decisions already taken, do not relitigate them:

- **Do not sum cost avoidance into cost reduction.** It is non-cash and a CFO will challenge a
  combined figure. It gets its own band, and the cash-backed subtotal (`benefit_cash_backed`) is
  labelled separately.
- **Keep the non-financial band.** `Risk Reduction` and `Capability` have no P&L line, but Capability
  is where the enabling initiatives sit — including the $895k one the whole demo turns on. Drop them
  and the totals will not tie back to the $84.3m of claimed annual benefit. Showing them as a fourth
  band marked non-financial strengthens the board argument: it shows how much claimed benefit never
  reaches the P&L directly.

`wave` in `sequence` is the topological layer the initiative lands in (wave 0 = no unmet
predecessors, wave 1 = depends only on wave 0, and so on). It is what makes the roadmap render as
bands rather than sixty unrelated bars.

---

## 7. The `violations` type enumeration

`violations[].type` is one of exactly four values.

| `type` | Fires when |
|---|---|
| `dependency` | A successor starts before its predecessor finishes, allowing for `lag_days`. The three known cases are in §5. |
| `resource` | A role exceeds 100% utilisation in a month. Derive it from role demand in the sequenced plan; `resources.csv` `utilisation_pct` and `over_allocated` give you the baseline to reconcile against. Real pinch points: Change Manager, Data Engineer, Supply Chain Analyst, in 2026Q4–2027Q1, peaking at 154.8%. |
| `budget` | `forecast_at_completion` exceeds `total_budget`, or the scenario's cumulative spend exceeds `budget_cap_usd` / `capex_cap_usd`. |
| `compliance` | **NEW REQUIREMENT FROM SURAJ — must be implemented.** See below. |

### The `compliance` violation type

A `compliance` violation fires when a **regulatory** initiative (`is_regulatory` true) is in any of
these four states:

1. **Deferred** — it appears in a scenario's `deferred_initiatives`.
2. **Deprioritised** — it has been pushed behind non-regulatory work that it previously preceded, or
   its `stage` is `Paused`.
3. **Sequenced after its required date** — its scheduled finish falls after the date it has to be
   done by. The dataset has no separate regulatory-deadline column, so use the initiative's baseline
   `end_date` from `initiatives.csv` as its required date, and also test it against the scenario's
   `must_finish_by`.
4. **Still at `Idea` stage despite having dependents** — other initiatives are already planned on top
   of something that has not even been shaped yet.

**Two rules that follow, both mandatory:**

- **Compliance violations always sort to the TOP of the exception list, regardless of severity
  score.** A regulatory breach outranks a bigger-dollar budget breach every time. Sort the exception
  list by `type === 'compliance'` first, then by severity within each group. A transformation leader
  who misses a regulatory item because a $3m budget overrun scored higher has been failed by the
  tool.
- **Regulatory initiatives can NEVER be deferred by a scenario**, even when a budget cap would
  otherwise drop them. When the scenario solver is trimming scope to fit `budget_cap_usd` or
  `capex_cap_usd`, regulatory initiatives are locked in and the cut has to come from somewhere else.
  If the cap cannot be met without cutting regulatory work, the correct output is a `budget`
  violation saying the cap is infeasible — not a dropped compliance item. This is why SC-01 lists all
  8 regulatory initiatives as mandatory, and why none of the 6 deferred initiatives on SC-02/SC-03 is
  regulatory: the data is consistent with the rule and your code must keep it that way.

**The 8 regulatory initiatives** (`is_regulatory` = `True`) — verified from `initiatives.csv`:

| ID | Name | Function | Stage | RAG | Direct dependents |
|---|---|---|---|---|---:|
| INIT-004 | Identity & Access Management Modernisation | Technology | In Flight | Amber | 7 |
| INIT-016 | Quality Management System Harmonisation | Operations | In Flight | Red | 0 |
| INIT-017 | Health & Safety Digital Reporting | Operations | **Paused** | Red | 0 |
| INIT-056 | SOX Control Remediation | Risk & Compliance | In Flight | Amber | 1 |
| INIT-057 | Data Privacy Programme (GDPR/CCPA) | Risk & Compliance | In Flight | Green | 0 |
| INIT-058 | Cyber Security Uplift - Endpoint & SIEM | Risk & Compliance | In Flight | Green | 6 |
| INIT-059 | Data Governance & Quality Framework | Risk & Compliance | **Idea** | Green | 2 |
| INIT-060 | Third-Party & Supplier Risk Management | Risk & Compliance | Approved | Green | 0 |

Two of these are live compliance violations in the baseline data, and your detector should surface
both without being told:

- **INIT-059** is regulatory, still at **Idea** stage, and already has **2 dependents**
  (INIT-022, INIT-033) planned on top of it. That is rule 4, exactly.
- **INIT-017** is regulatory and **Paused** with a **Red** RAG status. That is rule 2.

**Tying compliance back to the risk register:** `risks.csv` has a `Regulatory` category — 14 risks,
13 of them still Open or Mitigating, **$1,089,000** of combined `exposure_usd`. Join those to the
initiatives they sit on and show the exposure alongside each compliance violation. It turns
"this is late" into "this is late and here is what it is worth". Note that only INIT-060 carries a
`Regulatory`-category risk itself — the other 13 sit on non-regulatory initiatives, which is a
finding in its own right: the regulatory exposure in this portfolio is largely being carried by work
nobody has classified as regulatory.

---

## 8. The two views

One engine, two tabs. Not two applications.

### Leader view (default tab)

The working surface for the person running the transformation.

1. **Sequenced roadmap.** One horizontal bar per initiative, ordered by computed start, grouped into
   waves from the topological sort, coloured by `function`. Show `rag_status` as an edge or dot, not
   as the fill — the fill is carrying function. Month gridlines across the 2026-01 → 2029-02 span.
2. **Exception list.** All `violations` in one table: type, initiative, description, severity.
   **Compliance first, always** (§7), then dependency, then resource, then budget, sorted by severity
   within each block. Each row is clickable and highlights the initiative in the roadmap above.
3. **"What this unblocks" ranking.** For every initiative, the count of transitive downstream
   initiatives and the sum of their `annual_benefit_target`. Sorted descending, this is the list that
   makes the enabler argument by itself. Verified top of that list: INIT-055 unblocks 59 initiatives
   worth $82.6m, INIT-058 unblocks 37 worth $53.1m, INIT-003 unblocks 33 worth $44.3m, INIT-001
   unblocks 28 worth $38.6m.

### Board tab

No initiative-level detail. A board does not want sixty bars; it wants the choices that are theirs.

1. **Three scenarios side by side.** SC-01, SC-02, SC-03 as three columns from the same engine, each
   showing the `totals` block: budget, capex, peak FTE, and the four benefit subtotals. Violation
   counts by type per scenario, so the cost of each scenario in broken dependencies and compliance
   breaches is visible next to its financials.
2. **Stacked value bands.** The `benefit_curve` as a stacked area chart over the 24-month window —
   `cost_reduction`, `cost_avoidance`, `revenue_growth`, `non_financial`, in that order, bottom to
   top, four distinguishable fills with a legend. Drawn as inline SVG by hand. The story it tells is
   that the shape changes between scenarios, not just the height. Annotate the run-rate gap: $84.3m
   promised against the $39.6m annual run-rate actually scheduled by end-2027 (47% of the promise),
   with only $18.0m of benefit landing inside the 24-month window itself.
3. **Top five decisions.** Five plain-English board decisions, each with what it unlocks and what it
   costs. Example of the register: *"Fund the Enterprise Data Platform ahead of the cost-out
   programme. $895k. Unblocks 28 initiatives carrying $38.6m of annual benefit. Delay it and
   everything behind it slips."*

---

## 9. The demo money shot

This is the spine of the demo. Build it deliberately; never cut it.

**INIT-001 Enterprise Data Platform (Lakehouse) Build costs $895,000 and returns $70,000 a year
standalone.** On a naive benefit-to-cost ranking of all 60 initiatives it comes **last** — a ratio of
0.078, the worst in the portfolio. Any spreadsheet in the client's estate would cut it first.

**Follow the dependency graph and it transitively gates 28 of the 60 initiatives, carrying $38.6m
($38,580,000) of annual benefit between them.** That is a 43× return on the same $895k. It is the
single number the board should remember.

**The screen must show both rankings side by side** — naive ROI rank in one column, dependency-
corrected rank in the other, with the movement between them drawn. The contrast *is* the product
argument: not "we made a chart", but "your existing ranking method would have cut the one thing
everything else needs".

The same pattern, all verified, all worth showing in the same view:

| ID | Name | Budget | Standalone annual benefit | Naive ratio | Transitively gates | Downstream annual benefit |
|---|---|---:|---:|---:|---:|---:|
| INIT-001 | Enterprise Data Platform (Lakehouse) Build | $895,000 | $70,000 | 0.078 (worst of 60) | 28 | $38,580,000 |
| INIT-003 | API Gateway & Integration Layer | $2,040,000 | $170,000 | 0.083 (2nd worst) | 33 | $44,260,000 |
| INIT-008 | Master Data Management - Customer & Product | $1,780,000 | $270,000 | 0.152 | 5 | $5,300,000 |
| INIT-059 | Data Governance & Quality Framework | $1,155,000 | $230,000 | 0.199 | 2 | $2,580,000 |

INIT-059 carries the argument twice over: it is bottom-quartile on naive ROI, it gates two other
initiatives, **and** it is a regulatory initiative sitting at Idea stage — so it is simultaneously the
money shot and a compliance violation.

---

## 10. Reuse, do not rewrite

Working code already exists in this repo. Port it; do not reinvent it.

### `synthetic-data/validate_portfolio.py`

- **The topological sort** is **Kahn's algorithm, implemented inline inside `main()` at lines
  88–104**, under the `--- dependency graph ---` section. There is **no separately named
  topo-sort function** — do not go looking for one. Port that block: it builds an `outgoing`
  adjacency map and an `indeg` in-degree map from `dependencies.csv`, seeds a `deque` with every
  zero-in-degree node, peels nodes off and decrements successors. If the visited count equals the
  node count, the graph is acyclic. Extend it by one line to record the wave number as you peel, and
  you have both the acyclicity check and the `wave` field the roadmap needs.
- **The integrity checks** are the `check(name, ok, detail)` calls throughout `main()` — `check()` is
  defined at line 31 and is the single assertion helper for the whole file. The ones worth porting
  into your flattener as build-time assertions: no self-referencing edges (line 106), no duplicate
  edges (line 108), the foreign-key loop over every child table (lines 118–130),
  `capex + opex == total_budget` (line 157), `end_date` after `start_date` (line 161), actuals stop
  at the 2026-07 cutoff (lines 176–197), and `benefit_start_month >= duration_months` (line 210).
- Two supporting helpers: **`load(path)`** at line 38 (CSV → list of dicts) and **`fn(initiatives,
  iid)`** at line 264 (cached initiative → function lookup, which is how the cross-function edge
  count is computed).

### `synthetic-data/generate_portfolio.py`

These are the exact functions that produced the benefit and burn data, so a curve you rebuild from
them will reconcile to `benefits.csv` instead of being approximately right.

- **`s_curve_weights(n)`** — line 1170. Returns `n` weights summing to 1.0 on a bell profile (the
  derivative of an S curve). This is how `total_budget` is spread across an initiative's active
  months to give `planned_spend`.
- **`benefit_ramp_fraction(months_since_start, ramp_months)`** — line 1185. The fraction of
  steady-state benefit achieved this far into the ramp: `min(1.0, (months_since_start + 1) /
  ramp_months)`.
- **`generate_burn_and_benefits(rng, initiatives, today)`** — line 1194. The function that combines
  the two above. Read lines 1240–1247 in particular: they are the authoritative statement of the
  benefit maths, including the offset rule from §4.2 —
  `benefit_first_i = start_i + benefit_start_month`, `steady_monthly = annual_benefit_target / 12.0`,
  and `plan_benefit = steady_monthly × benefit_ramp_fraction(...)` once the month index reaches
  `benefit_first_i`.
- **`window_month_list()`** — line 1166, plus the `WINDOW_START` / `WINDOW_MONTHS` constants above
  it: the canonical 24-month window, 2026-01 to 2027-12.
- Date helpers, all stdlib-only and trivial to port to JS: **`add_months(d, n)`** (line 450),
  **`days_in_month(year, month)`** (459), **`month_key(d)`** (465, produces `"2026-08"`),
  **`month_index(d)`** (470, absolute month number so two months can be subtracted),
  **`quarter_of(d)`** (475, produces `"2026Q3"`), **`iso(d)`** (479).
- The `pnl_impact_type` mapping at lines 1272–1278 is the authoritative `benefit_type` →
  `pnl_impact_type` mapping — use it to drive the four value bands in §6.

### `synthetic-data/build_artifact.py`

A dependency-free inline-SVG chart layer already written for this dataset: **`chart_rag(by_fn)`**
(line 147), **`chart_budget(by_fn)`** (line 182), **`chart_benefit(quarters, q)`** (line 205), and
the **`svg(w, h, parts)`** wrapper (line 235). Read these before drawing anything — they show the
house style for hand-drawn SVG with no library, and `money(v)` (line 34) is the currency formatter.

---

## 11. Verified headline figures to display

Every number here was computed from the files in this repo. Put them on the screen.

> ### ⚠️ DO NOT REINTRODUCE THE `$507` COMPARISON
>
> The line *"$84.3m claimed annual benefit against $507 actually banked"* was **retired as wrong** and
> must not be put back in any file, slide, chart annotation or commit. It compares a steady-state
> full-year run-rate ($84.3m, earned only once all 60 initiatives are finished and fully ramped)
> against a single genuine cell from a seven-month actuals window in which only 1 of 60 initiatives
> had reached its benefit-start month — overstating the gap by roughly five orders of magnitude, and
> collapsing the moment anyone asks *"what period is the $84.3m over?"*. Use the like-for-like
> run-rate framing immediately below instead.

- **60 initiatives** in the inherited portfolio
- **$95.3m approved** ($95,350,000) against **$101.7m forecast** ($101,743,000) — a $6.4m overrun
  before anything is resequenced
- **$84.3m promised versus a $39.6m annual run-rate actually scheduled by end-2027 — 47% of the
  promise.** The exit run-rate ($39,643,848 = Dec-2027 `benefit_plan` × 12) is **47.0%** of the
  $84,270,000 promised. Only **$18,004,782** of benefit lands inside the 24-month window
  (2026-01..2027-12); **16 of 60** initiatives deliver zero benefit inside that window; and only
  **25 of 60** reach full run-rate by 2027-12
- Optional spend pairing: **$89,780,396** of planned in-window spend (`burn.csv` `planned_spend`,
  2026-01..2027-12) against that $18.0m of in-window benefit — roughly **$5 spent per $1 of benefit
  landed in-window**, with payback beyond 2027
- **95 dependencies**, of which **70 cross function boundaries** and **3 are already violated**
- **31 Green / 17 Amber / 12 Red**
- **25 of 60 initiatives forecasting over budget** (using the >5% threshold the validator applies;
  42 of 60 are over by any amount at all)
- Supporting: 33,352,000 total capex; 8 regulatory initiatives; 54 Hard dependency edges; 131 risks;
  82 issues; three pinch-point roles peaking at 154.8% utilisation

---

## 12. Acceptance criteria

A build is done when every line below is true. Test it against this list.

**Structure**
- [ ] `index.html`, `app.js` and `data/portfolio.json` exist at the repo root
- [ ] Nothing under `synthetic-data/` has been modified (`git status` shows no changes there)
- [ ] No `package.json`, no `node_modules`, no build step, no bundler config
- [ ] `app.js` contains no `fetch` to any external host, no API key, and at most one CDN `<script>`
      tag in `index.html` (ideally zero)
- [ ] The page renders with nothing running but a static file server

**Data**
- [ ] `data/portfolio.json` carries all 60 initiatives and all 95 dependency edges
- [ ] `is_regulatory` and `over_allocated` are real booleans in the JSON, not strings
- [ ] Nothing in the app reads `dependency_conflicts.csv`, at build time or runtime
      (`grep -r dependency_conflicts index.html app.js` returns nothing)
- [ ] No blank future month has been imputed or zero-filled; the as-of boundary at 2026-07 is
      preserved and labelled

**Engine**
- [ ] The topological sort completes over all 60 nodes and reports no cycle
- [ ] The conflict detector independently finds exactly 3 dependency violations: INIT-039→INIT-031
      (716 days), INIT-039→INIT-038 (710 days), INIT-005→INIT-006 (627 days)
- [ ] The engine returns the §6 result object for all three scenarios, with every field present
- [ ] `benefit_curve` has 24 monthly points, each with all four value bands
- [ ] The four `totals` benefit subtotals reconcile to the $84.3m of claimed annual benefit
- [ ] A rebuilt benefit curve reconciles against `benefits.csv` `benefit_plan` (proof that
      `benefit_start_month` was treated as an offset, not a calendar month)

**Violations**
- [ ] All four violation types are implemented: `dependency`, `resource`, `budget`, `compliance`
- [ ] Compliance violations sort above every other type in the exception list regardless of severity
- [ ] INIT-059 is flagged as a compliance violation (regulatory, Idea stage, 2 dependents)
- [ ] INIT-017 is flagged as a compliance violation (regulatory, Paused)
- [ ] No scenario, at any budget cap, ever defers one of the 8 regulatory initiatives; an infeasible
      cap produces a `budget` violation instead

**Views**
- [ ] Leader tab shows the sequenced roadmap, the exception list, and the "what this unblocks"
      ranking
- [ ] Board tab shows three scenarios side by side, the stacked value bands, and five board decisions
- [ ] Switching scenario re-renders both tabs from the same engine with no page reload
- [ ] Every chart is inline SVG

**Money shot**
- [ ] Naive ROI rank and dependency-corrected rank are shown side by side
- [ ] INIT-001 is visibly last on naive ROI and near the top corrected, labelled "$895k gates $38.6m
      across 28 initiatives"
- [ ] INIT-003, INIT-008 and INIT-059 show the same pattern in the same view

**Judging**
- [ ] A root `README.md` states target user, workflow, business value and path to market in plain
      words
- [ ] The headline figures in §11 appear on screen, not just in the README
