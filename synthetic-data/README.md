# Synthetic Transformation Portfolio — hack-team-01

A ready-to-use, made-up dataset for the Aberdeen Advisors hackathon challenge:

> *A newly appointed transformation leader inherits 60 initiatives across the organisation
> with no integrated roadmap. Build a tool that converts existing plans and documents into
> (1) a sequenced roadmap, (2) a dependency view, (3) scenario comparison, and (4) a
> value-realization plan.*

Everything here is fictional. The client is "Harbourline Group", a $2.1bn industrial services
and distribution business. No real company, person or number appears anywhere.

**Build day is 2026-08-12. The dataset is pinned to "today = 2026-08-11".** Actuals exist up
to and including July 2026 and are blank after that, exactly as they would be in real life on
the 11th of the month.

---

## Start here (5 minutes)

1. Open `data/initiatives.csv`. That is the portfolio — one row per initiative, 60 rows.
2. Open `data/dependencies.csv`. That is what waits for what.
3. Open `docs/pmo-tracker-messy.csv`. That is what the data actually looks like before
   anyone cleans it. Your tool probably needs to cope with this, not with the clean version.
4. Read `docs/ANSWER-KEY.md` **when you are ready** — it lists every problem deliberately
   planted in the data, so you can check whether your tool found them. It is a spoiler.

---

## The two folders

| Folder | What it is | Think of it as |
|---|---|---|
| `data/` | Clean, structured, machine-readable. Consistent IDs, ISO dates, numeric columns. | What a PMO system would export if the PMO were good at its job. |
| `docs/` | Messy human documents — business cases, status reports, meeting minutes, a horrible spreadsheet. | What the transformation leader actually inherited. |

The two describe **the same 60 initiatives** and use **the same IDs** (`INIT-001` … `INIT-060`),
so you can reconcile one against the other. They deliberately **disagree in a few places**.
Finding those disagreements is part of the challenge.

---

## Which file feeds which challenge view

| Challenge view | Primary files | Also useful |
|---|---|---|
| **1. Sequenced roadmap** | `initiatives.csv`, `milestones.csv` | `dependencies.csv`, `resources.csv` |
| **2. Dependency view** | `dependencies.csv`, `dependency_conflicts.csv` | `initiatives.csv` for dates |
| **3. Scenario comparison** | `scenarios.json`, `resources.csv` | `initiatives.csv`, `burn.csv` |
| **4. Value-realization plan** | `benefits.csv`, `burn.csv` | `initiatives.csv` benefit columns |
| **Health / exec dashboard** | `risks.csv`, `issues.csv`, `milestones.csv` | all of the above |

---

## Every file, explained

### `data/initiatives.csv` — 60 rows, one per initiative
Also provided as `initiatives.json` (identical content, easier if you are working in JS).

**Two grouping columns, and they mean different things:**

- **`function`** = *who owns delivery*. Eight values: Technology, Operations, Supply Chain,
  Finance, HR / People, Growth / Commercial, Cost Reduction, Risk & Compliance.
- **`pillar`** = *why we are doing it* — the value theme it serves. Four values: Grow,
  Run Better, Cost Out, Protect. These map to the four strategic objectives in
  `docs/strategy/transformation-strategy-one-pager.md`.

A Technology-owned initiative can serve a Cost Out theme, and several do. Group by either.

| Column | Plain English |
|---|---|
| `initiative_id` | Unique ref, `INIT-001` to `INIT-060`. Used by every other file. |
| `name` | What it is called. |
| `function` | Which function delivers it (8 values, see above). |
| `pillar` | Which value theme it serves (4 values, see above). |
| `owner` | The person running it day to day. |
| `sponsor` | The executive accountable for the benefit. |
| `business_unit` | Which part of the business it lands in. |
| `description` | Two or three sentences of context. |
| `objective` | The one-line goal. |
| `start_date` / `end_date` | Planned dates, ISO format (`YYYY-MM-DD`). |
| `duration_months` | End minus start, in months. |
| `stage` | Idea → Business Case → Approved → In Flight → Complete. Plus At Risk and Paused. |
| `rag_status` | Green / Amber / Red. The health traffic light. |
| `percent_complete` | 0–100. |
| `priority_score` | 1–100, computed from alignment, value, complexity and health. |
| `strategic_alignment` | 1–5. How directly it serves a strategic objective. Regulatory work is floored at 4. |
| `value_confidence` | High / Med / Low. **How much you should believe the benefit number.** |
| `complexity` | 1–5. |
| `effort_fte` | Full-time-equivalent people needed at peak. |
| `capex` / `opex` | Capital vs operating split. Always sums to `total_budget`. |
| `total_budget` | Approved envelope. |
| `spend_to_date` | Spent so far. Tracks `percent_complete`, with noise. |
| `forecast_at_completion` | What we now think it will cost. **Higher than budget = trouble.** |
| `annual_benefit_target` | Value per year once fully ramped. Not the total value — the annual run rate. |
| `benefit_type` | Cost Save / Revenue Uplift / Cost Avoidance / Risk Reduction / Capability. |
| `benefit_start_month` | Months after the initiative *starts* before any value appears. **Always ≥ `duration_months`** — value lands after delivery, never during. |
| `benefit_ramp_months` | How long from first value to full run rate. |
| `npv` | 5-year net present value at 10%. Can be negative. |
| `payback_months` | Months to pay back the investment. |
| `run_rate_savings` | The cash-releasing portion of the benefit. |
| `resource_type_needed` | The scarcest role it needs. Joins to `resources.csv`. |
| `key_systems` | Systems touched, semicolon-separated. |
| `region` | Where it lands. |
| `is_regulatory` | `True` / `False`. **If True, it cannot be cut in any scenario.** |
| `tags` | Free labels, semicolon-separated. |

### `data/dependencies.csv` — 95 rows
What waits for what. `from_initiative` must happen before `to_initiative`.

**This graph has no cycles.** It is built acyclic by construction, so you can safely run a
topological sort or critical-path calculation on it. If your code reports a cycle, the bug is
in your code.

**70 of the 95 edges (74%) cross functions** — Supply Chain waiting on the data platform, HR
gating Finance, and so on. Those are the interesting ones.

| Column | Plain English |
|---|---|
| `from_initiative` / `to_initiative` | Predecessor and successor. |
| `dependency_type` | Finish-to-Start, Start-to-Start, Finish-to-Finish, Resource, Data, Technical Enabler. |
| `lag_days` | Wait this many days after the predecessor before the successor can proceed. |
| `criticality` | `Hard` = genuinely blocking. `Soft` = preferable, can be worked around. |
| `notes` | Why the dependency exists, in plain language. |

### `data/dependency_conflicts.csv` — 3 rows
**Deliberate sequencing problems** for your tool to detect and fix. Each one is a hard
dependency where the successor is currently scheduled to start *before its predecessor can
possibly finish*. They are real rows in `dependencies.csv` — the graph stays acyclic; it is
the *dates* that are wrong.

The worst one has a **716-day** violation and crosses from HR into Finance. Columns include
`overlap_days` (how badly it is violated) and `severity`.

### `data/milestones.csv` — 259 rows
Three to six per initiative. `baseline_date` is what was promised, `forecast_date` is what is
now expected, `slip_days` is the gap. `actual_date` is blank if it has not happened yet.
Types: Gate, Deliverable, Go-Live, Benefit Checkpoint.

### `data/risks.csv` — 131 rows
`probability` × `impact` = `score` (1–25). `exposure_usd` is the money at stake.
`status` is Open / Mitigating / Closed. Red initiatives carry more and worse risks.

### `data/issues.csv` — 82 rows
Problems that have already happened (risks are problems that might). `severity` is
Critical / High / Medium / Low. `impact_on_schedule_days` and `impact_on_cost_usd` quantify
the damage. `linked_risk_id` points at `risks.csv` when the issue is a risk that materialised
— it is blank about half the time.

### `data/resources.csv` — 360 rows (15 roles × 24 months)
**This is your scenario constraint.** One row per role per month.

| Column | Plain English |
|---|---|
| `role` | e.g. Data Engineer, HR Business Partner, Supply Chain Analyst. |
| `month` / `quarter` | `2026-01` / `2026Q1`. |
| `available_fte` | People you have. |
| `demanded_fte` | People the plan needs. Derived from which initiatives are live that month. |
| `gap_fte` | Available minus demanded. Negative = short. |
| `utilisation_pct` | Demand as a % of supply. Over 100 = impossible. |
| `over_allocated` | `TRUE` / `FALSE`. |

**Three roles are deliberately over-allocated in 2026Q4–2027Q1**: Data Engineer (peaks at
148%), Supply Chain Analyst (155%) and Change Manager (145%). No other role ever breaches.
A roadmap that ignores this is not deliverable, however good its financials look.

### `data/burn.csv` — 1,440 rows (60 initiatives × 24 months)
Monthly money, January 2026 to December 2027.

| Column | Plain English |
|---|---|
| `planned_spend` | What the plan said we would spend this month. |
| `actual_spend` | What we actually spent. **Blank from 2026-08 onwards** — the future has not happened. |
| `cumulative_planned` / `cumulative_actual` | Running totals. Cumulative actual also stops at 2026-07. |
| `forecast_spend` | Revised expectation, reflecting the overrun. |
| `benefit_realized` | Value actually banked that month. Blank for future months. |

Spend follows an S-curve — slow start, peak in the middle, tail off — not a flat line.

### `data/benefits.csv` — 1,440 rows
The value-realization view. `benefit_plan` vs `benefit_actual` per initiative per month.
`benefit_actual` is blank from 2026-08. `pnl_impact_type` says how it hits the P&L
(Opex reduction, Gross margin, Cost avoided, and so on). `confidence` mirrors the
initiative's `value_confidence`.

**Expect the actuals to be almost zero.** That is correct, not a bug — every initiative books
its value after it delivers, and almost nothing has delivered yet. That *is* the story.

### `data/scenarios.json` — 3 scenarios
Scenario **inputs only**. No results are pre-computed — working out what each scenario does to
the roadmap is your tool's job.

| Scenario | The question it asks |
|---|---|
| **SC-01 Board baseline** | What happens if we just do what is currently planned? (Answer: it is undeliverable.) |
| **SC-02 Cash-constrained (−25% capex)** | The board takes a quarter of the capital away. What survives, and what quietly breaks when an enabler is cut? |
| **SC-03 Speed to value** | Same money, different order. Front-load the quick wins. Better year-one optics — but at what three-year cost? |

Each has `constraints` (budget cap, capex cap, FTE cap, mandatory initiatives, deferred
initiatives, end date) and an `expected_qualitative_outcome` describing what a good tool
*should* conclude. Use that last field to sanity-check your output.

---

## The messy documents (`docs/`)

The challenge says the tool converts *existing plans and documents*. These are those documents.
They are deliberately inconsistent, incomplete and occasionally wrong.

| File | What it is |
|---|---|
| `strategy/transformation-strategy-one-pager.md` | The four strategic objectives. **Read this first** — it is what priority scoring aligns to. |
| `business-cases/` (8 files) | Real-feeling business cases. Different formats, missing fields, vague benefits ("~$2.2m, subject to validation"), and **dependencies mentioned only in prose**. |
| `status-reports/` (3 files) | Monthly PMO reports for May, June and July 2026. RAG tables, top risks, escalations. **At least three places contradict the structured data.** |
| `decision-logs/` (2 files) | Steering committee minutes and a decision log. Decisions, deferrals, and one unresolved priority argument that has been deferred four times. |
| `pmo-tracker-messy.csv` | The real-world spreadsheet. Junk header rows, three date formats, budgets as `$1.2m` / `1,200,000` / `TBD`, free-text RAG (`amber-ish`, `on track?`), duplicate rows, and one initiative that exists nowhere else. |
| `ANSWER-KEY.md` | **Spoilers.** Every planted problem, listed. Use it to score your tool. |

The business cases cover INIT-001, 006, 020, 023, 031, 035, 039, 046 and 056 — chosen to span
six functions and to include all three schedule conflicts.

---

## Regenerating the data

You do not need to. The files are committed. But if you want different data:

```bash
python3 generate_portfolio.py                 # exactly what is committed here
python3 generate_portfolio.py --seed 7        # a different portfolio
python3 generate_portfolio.py --count 30      # a smaller one
python3 generate_portfolio.py --help          # all options
```

Then check it still hangs together:

```bash
python3 validate_portfolio.py                 # 48 checks, all should pass
```

**Requirements: none.** Python 3.8 or later, standard library only. No pip install, no
pandas, no numpy, no internet. It runs anywhere.

The generator is seeded, so `--seed 42` (the default) always produces byte-identical files.
If you regenerate with a different seed, **the documents in `docs/` will no longer match the
data** — they were written by hand against seed 42. Regenerate at your own risk on build day.

`generate_portfolio.py` is written to be readable by a non-engineer. The initiative list is a
plain table near the top; the hand-written cross-function dependencies are a plain list below
it. Both are easy to edit if you want to change the story.

---

## Verified row counts

| File | Rows |
|---|---|
| `initiatives.csv` / `.json` | 60 |
| `dependencies.csv` | 95 |
| `dependency_conflicts.csv` | 3 |
| `milestones.csv` | 259 |
| `risks.csv` | 131 |
| `issues.csv` | 82 |
| `resources.csv` | 360 |
| `burn.csv` | 1,440 |
| `benefits.csv` | 1,440 |
| `scenarios.json` | 3 scenarios |

Portfolio totals: **$95.3m** approved budget, **$101.7m** forecast at completion,
**$84.3m** claimed annual benefit at full run rate. **31 Green / 17 Amber / 12 Red.**
**25 of 60** initiatives are forecasting over budget.

---

## Six things worth knowing before you start

1. **Value always lands after delivery.** No initiative books benefit while it is still being
   built. This is why the value-realization view looks empty in 2026 and steep in 2028.
2. **Enablers look like bad investments and are not.** The cheapest-looking cut in the
   portfolio gates 28 other initiatives.
3. **`is_regulatory = TRUE` means untouchable.** Five initiatives. An optimiser that maximises
   NPV will try to cut them and will be wrong.
4. **`value_confidence` matters as much as the benefit number.** A Low-confidence $3m is worth
   less than a High-confidence $1.5m, and the portfolio is full of the former.
5. **The documents and the data disagree on purpose.** Reconciling them is a feature of the
   challenge, not a data quality problem to report.
6. **Nothing in this portfolio has ever been cancelled.** In two years it grew from 34
   initiatives to 60. The question the PMO cannot answer — and the one your tool should —
   is *"if we could only do thirty of these, which thirty?"*
