# Dataset field reference

Every column in the synthetic transformation-portfolio dataset, read from the files themselves rather than from the generator. Types, allowed values and row counts below are what is actually in `synthetic-data/data/`.

**9 CSV files - 2 JSON files - 3,870 data rows - 60 initiatives - 17 documents in `docs/` - as-of month 2026-07**

## Which file feeds which view

| File | Rows | Cols | Challenge view |
|---|---:|---:|---|
| `data/initiatives.csv` | 60 | 37 | Sequenced roadmap |
| `data/dependencies.csv` | 95 | 6 | Dependency view |
| `data/dependency_conflicts.csv` | 3 | 17 | Dependency view |
| `data/milestones.csv` | 259 | 10 | Sequenced roadmap |
| `data/risks.csv` | 131 | 14 | Health / exec dashboard |
| `data/issues.csv` | 82 | 12 | Health / exec dashboard |
| `data/resources.csv` | 360 | 8 | Scenario comparison |
| `data/burn.csv` | 1,440 | 8 | Value realization |
| `data/benefits.csv` | 1,440 | 6 | Value realization |
| `data/scenarios.json` | 3 scenarios | 5 top-level keys | Scenario comparison |
| `data/initiatives.json` | 60 objects | 37 keys | Sequenced roadmap |

## `data/initiatives.csv`

**60 rows x 37 columns - feeds: Sequenced roadmap**

The spine of the dataset - one row per initiative, with dates, money, benefit shape and priority. Every other CSV joins back to `initiative_id`. Also feeds scenario comparison, because the budget and `is_regulatory` columns decide what can be cut.

Header row, in file order:

```
initiative_id,name,function,pillar,owner,sponsor,business_unit,description,objective,start_date,end_date,duration_months,stage,rag_status,percent_complete,priority_score,strategic_alignment,value_confidence,complexity,effort_fte,capex,opex,total_budget,spend_to_date,forecast_at_completion,annual_benefit_target,benefit_type,benefit_start_month,benefit_ramp_months,npv,payback_months,run_rate_savings,resource_type_needed,key_systems,region,is_regulatory,tags
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `initiative_id` | ID | INIT-001 | INIT-001 - INIT-060, unique, primary key for the whole dataset |
| `name` | Text | Enterprise Data Platform (Lakehouse) Build | 60 unique initiative names |
| `function` | Enum | Technology | `Cost Reduction`, `Finance`, `Growth / Commercial`, `HR / People`, `Operations`, `Risk & Compliance`, `Supply Chain`, `Technology` |
| `pillar` | Enum | Run Better | `Cost Out`, `Grow`, `Protect`, `Run Better` |
| `owner` | Text | Rafael Farouk | 59 distinct people (one owner appears twice) |
| `sponsor` | Enum | Chief Information Officer | `Chief Commercial Officer`, `Chief Digital Officer`, `Chief Information Officer`, `Chief Risk Officer`, `Group CFO`, `Group COO`, `Group Financial Controller`, `Group General Counsel`, `Group HR Director`, `Group Procurement Director`, `Group Supply Chain Director`, `MD Distribution & Logistics`, `MD Energy Solutions`, `MD Industrial Services` |
| `business_unit` | Enum | Corporate Functions | `Corporate Functions`, `Digital & Customer`, `Distribution & Logistics`, `Energy Solutions`, `Industrial Services` |
| `description` | Text | Replace fragmented legacy tooling with a single supported platf… | Free prose, 1-3 sentences |
| `objective` | Enum | Establish the data and integration foundation for the wider por… | `Avoid future cost that would otherwise be incurred under the current model`, `Build a reusable capability that later initiatives depend on`, `Defer capital replacement through better asset utilisation`, `Deliver a sustainable reduction in run-rate operating cost`, `Establish a new revenue stream with a repeatable commercial model`, `Establish the data and integration foundation for the wider portfolio`, `Grow incremental revenue from existing and new customers`, `Improve win rate and average deal value in target segments`, `Meet regulatory obligations and close known audit findings`, `Reduce residual risk exposure to within board-agreed appetite`, `Reduce third-party spend through consolidation and renegotiation`, `Remove duplicated activity and consolidate onto one way of working` |
| `start_date` | Date (ISO) | 2025-12-11 | 2025-08-04 - 2027-07-11 |
| `end_date` | Date (ISO) | 2026-07-11 | 2026-07-11 - 2029-02-22 |
| `duration_months` | Integer | 7 | 6 - 24 |
| `stage` | Enum | Complete | `Approved`, `At Risk`, `Business Case`, `Complete`, `Idea`, `In Flight`, `Paused` |
| `rag_status` | Enum | Green | `Amber`, `Green`, `Red` |
| `percent_complete` | Integer | 100 | 0 - 100 |
| `priority_score` | Integer | 73 | 36 - 100 |
| `strategic_alignment` | Integer | 5 | `2`, `3`, `4`, `5` |
| `value_confidence` | Enum | Low | `High`, `Low`, `Med` |
| `complexity` | Integer | 1 | `1`, `2`, `3`, `4`, `5` |
| `effort_fte` | Decimal | 2.3 | 1.6 - 11.9 |
| `capex` | Integer (USD) | 600000 | 84000 - 1735000 |
| `opex` | Integer (USD) | 295000 | 286000 - 2235000 |
| `total_budget` | Integer (USD) | 895000 | 370000 - 3375000 |
| `spend_to_date` | Integer (USD) | 908190 | 0 - 1770318 |
| `forecast_at_completion` | Integer (USD) | 908000 | 363000 - 3535000 |
| `annual_benefit_target` | Integer (USD) | 70000 | 40000 - 3910000 |
| `benefit_type` | Enum | Capability | `Capability`, `Cost Avoidance`, `Cost Save`, `Revenue Uplift`, `Risk Reduction` |
| `benefit_start_month` | Integer | 7 | 7 - 26 - Months after the initiative starts, not a calendar month |
| `benefit_ramp_months` | Integer | 9 | `12`, `3`, `4`, `6`, `9` |
| `npv` | Integer (USD) | -630000 | -1396000 - 9434000 - Negative for enabling initiatives |
| `payback_months` | Integer | 160 | 16 - 160 |
| `run_rate_savings` | Integer (USD) | 24500 | 14000 - 3910000 |
| `resource_type_needed` | Enum | Solution Architect | `Business Analyst`, `Change Manager`, `Commercial Analyst`, `Compliance Specialist`, `Data Engineer`, `ERP Consultant`, `HR Business Partner`, `Integration Engineer`, `Process Engineer`, `Procurement Category Manager`, `Programme Manager`, `Solution Architect`, `Test Lead` |
| `key_systems` | Text list | Snowflake | Semicolon-space separated, e.g. Kronos; Snowflake |
| `region` | Enum | DACH | `Benelux`, `DACH`, `Group-wide`, `Nordics`, `North America`, `UK & Ireland` |
| `is_regulatory` | Boolean | False | True / False (title case). True = cannot be cut in any scenario |
| `tags` | Text list | board-visible; customer-facing | Semicolon-space separated; never blank |

<details><summary>One full example row</summary>

```
initiative_id: INIT-001
name: Enterprise Data Platform (Lakehouse) Build
function: Technology
pillar: Run Better
owner: Rafael Farouk
sponsor: Chief Information Officer
business_unit: Corporate Functions
description: Replace fragmented legacy tooling with a single supported platform through enterprise data platform (lakehouse) build. A pilot in one region proves the operating model before the group-wide rollout is committed. This is an enabling investment; value is realised through the initiatives it unlocks.
objective: Establish the data and integration foundation for the wider portfolio
start_date: 2025-12-11
end_date: 2026-07-11
duration_months: 7
stage: Complete
rag_status: Green
percent_complete: 100
priority_score: 73
strategic_alignment: 5
value_confidence: Low
complexity: 1
effort_fte: 2.3
capex: 600000
opex: 295000
total_budget: 895000
spend_to_date: 908190
forecast_at_completion: 908000
annual_benefit_target: 70000
benefit_type: Capability
benefit_start_month: 7
benefit_ramp_months: 9
npv: -630000
payback_months: 160
run_rate_savings: 24500
resource_type_needed: Solution Architect
key_systems: Snowflake
region: DACH
is_regulatory: False
tags: board-visible; customer-facing
```

</details>

## `data/dependencies.csv`

**95 rows x 6 columns - feeds: Dependency view**

The edge list. One row per directed link between two initiatives, so this is what you build the graph from. `criticality = Hard` is a link the roadmap is not allowed to break.

Header row, in file order:

```
from_initiative,to_initiative,dependency_type,lag_days,criticality,notes
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `from_initiative` | ID (FK) | INIT-001 | 36 distinct predecessors, joins initiatives.initiative_id |
| `to_initiative` | ID (FK) | INIT-005 | 59 distinct successors, joins initiatives.initiative_id |
| `dependency_type` | Enum | Data | `Data`, `Finish-to-Start`, `Resource`, `Start-to-Start`, `Technical Enabler` |
| `lag_days` | Integer | 14 | `0`, `10`, `14`, `20`, `30`, `45`, `5`, `60` |
| `criticality` | Enum | Soft | `Hard`, `Soft` |
| `notes` | Text | Cloud Migration Wave 1 - Non-Production consumes data produced … | Plain-language reason for the link |

<details><summary>One full example row</summary>

```
from_initiative: INIT-001
to_initiative: INIT-005
dependency_type: Data
lag_days: 14
criticality: Soft
notes: Cloud Migration Wave 1 - Non-Production consumes data produced by Enterprise Data Platform (Lakehouse) Build.
```

</details>

## `data/dependency_conflicts.csv`

**3 rows x 17 columns - feeds: Dependency view**

Three deliberately broken dependencies, pre-diagnosed. Use it as a test fixture: a correct dependency view should independently find these three and flag them the same way.

Header row, in file order:

```
conflict_id,conflict_type,from_initiative,from_name,from_function,to_initiative,to_name,to_function,dependency_type,criticality,predecessor_end_date,lag_days,required_successor_start,actual_successor_start,overlap_days,severity,notes
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `conflict_id` | ID | CONF-001 | CONF-001 - CONF-003 |
| `conflict_type` | Enum | Successor starts before predecessor finishes | `Successor starts before predecessor finishes` |
| `from_initiative` | ID (FK) | INIT-039 | `INIT-005`, `INIT-039` |
| `from_name` | Text | Organisational Delayering & Span of Control |  |
| `from_function` | Enum | HR / People | `HR / People`, `Technology` |
| `to_initiative` | ID (FK) | INIT-031 | `INIT-006`, `INIT-031`, `INIT-038` |
| `to_name` | Text | Finance Shared Services Centre Stand-Up |  |
| `to_function` | Enum | Finance | `Finance`, `HR / People`, `Technology` |
| `dependency_type` | Enum | Finish-to-Start | `Finish-to-Start` |
| `criticality` | Enum | Hard | `Hard` |
| `predecessor_end_date` | Date (ISO) | 2028-06-08 | 2027-09-22 - 2028-06-08 |
| `lag_days` | Integer | 45 | `30`, `45` |
| `required_successor_start` | Date (ISO) | 2028-07-23 | 2027-10-22 - 2028-07-23 |
| `actual_successor_start` | Date (ISO) | 2026-08-07 | 2026-02-02 - 2026-08-07 |
| `overlap_days` | Integer | 716 | `627`, `710`, `716` - Days the successor starts ahead of where it legally could |
| `severity` | Enum | High | `High` |
| `notes` | Text | INTENTIONAL TEST CASE. INIT-039 -> INIT-031 is a hard Finish-to… | All three are flagged INTENTIONAL TEST CASE |

## `data/milestones.csv`

**259 rows x 10 columns - feeds: Sequenced roadmap**

Roughly four to five gates per initiative, each with a baseline, a forecast and (once done) an actual. `slip_days` is what drives the roadmap's slippage view.

Header row, in file order:

```
milestone_id,initiative_id,name,type,baseline_date,forecast_date,actual_date,status,slip_days,owner
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `milestone_id` | ID | MS-0001 | MS-0001 - MS-0259, unique |
| `initiative_id` | ID (FK) | INIT-001 | All 60 initiatives present |
| `name` | Enum | Mobilisation & Scope Sign-Off | `Benefit Checkpoint 1`, `Build Complete`, `Design Complete`, `Go-Live`, `Mobilisation & Scope Sign-Off`, `Stage Gate 2 - Ready for Test` |
| `type` | Enum | Gate | `Benefit Checkpoint`, `Deliverable`, `Gate`, `Go-Live` |
| `baseline_date` | Date (ISO) | 2025-12-21 | 2025-08-26 - 2029-02-22 |
| `forecast_date` | Date (ISO) | 2025-12-21 | 2025-09-16 - 2029-02-22 |
| `actual_date` | Date (ISO) | 2025-12-21 | Blank until the milestone completes - 216 of 259 rows are blank |
| `status` | Enum | Complete | `Complete`, `In Progress`, `Missed`, `Not Started` |
| `slip_days` | Integer | 0 | `0`, `10`, `18`, `21`, `25`, `3`, `30`, `35`, `45`, `5`, `60`, `7`, `90` - forecast_date minus baseline_date |
| `owner` | Text | Rafael Farouk | 133 distinct; not always the initiative owner |

<details><summary>One full example row</summary>

```
milestone_id: MS-0001
initiative_id: INIT-001
name: Mobilisation & Scope Sign-Off
type: Gate
baseline_date: 2025-12-21
forecast_date: 2025-12-21
actual_date: 2025-12-21
status: Complete
slip_days: 0
owner: Rafael Farouk
```

</details>

## `data/risks.csv`

**131 rows x 14 columns - feeds: Health / exec dashboard**

Standard risk register, scored probability x impact with a dollar exposure. Feeds the health view and, via `exposure_usd`, any risk-adjusted value calculation.

Header row, in file order:

```
risk_id,initiative_id,title,description,category,probability,impact,score,exposure_usd,mitigation,owner,status,raised_date,target_resolution_date
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `risk_id` | ID | RSK-0001 | RSK-0001 - RSK-0131, unique |
| `initiative_id` | ID (FK) | INIT-001 | All 60 initiatives carry at least one risk |
| `title` | Text | Environment availability constrains parallel testing | 23 recurring risk titles |
| `description` | Text | Technical uncertainty that may require rework or additional dis… | Prose, names the initiative and function |
| `category` | Enum | Technical | `Change/Adoption`, `Delivery`, `Financial`, `Regulatory`, `Resource`, `Technical`, `Vendor` |
| `probability` | Integer | 3 | `1`, `2`, `3`, `4`, `5` |
| `impact` | Integer | 4 | `1`, `2`, `3`, `4`, `5` |
| `score` | Integer | 12 | probability x impact, 1 - 25 |
| `exposure_usd` | Integer (USD) | 107000 | 2000 - 669000 |
| `mitigation` | Text | Build second test environment; stagger test cycles | 23 distinct mitigation statements |
| `owner` | Text | Olu Boateng | 103 distinct |
| `status` | Enum | Closed | `Closed`, `Mitigating`, `Open` |
| `raised_date` | Date (ISO) | 2026-07-03 | 2025-07-28 - 2027-05-28 |
| `target_resolution_date` | Date (ISO) | 2026-09-01 | 2025-08-27 - 2027-06-27 |

<details><summary>One full example row</summary>

```
risk_id: RSK-0001
initiative_id: INIT-001
title: Environment availability constrains parallel testing
description: Technical uncertainty that may require rework or additional discovery effort. Carried on Enterprise Data Platform (Lakehouse) Build (INIT-001, Technology) and reported into the monthly PMO review.
category: Technical
probability: 3
impact: 4
score: 12
exposure_usd: 107000
mitigation: Build second test environment; stagger test cycles
owner: Olu Boateng
status: Closed
raised_date: 2026-07-03
target_resolution_date: 2026-09-01
```

</details>

## `data/issues.csv`

**82 rows x 12 columns - feeds: Health / exec dashboard**

Live problems rather than potential ones. Carries real schedule and cost impact, and optionally links to the risk that predicted it.

Header row, in file order:

```
issue_id,initiative_id,title,description,severity,status,raised_date,age_days,owner,impact_on_schedule_days,impact_on_cost_usd,linked_risk_id
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `issue_id` | ID | ISS-0001 | ISS-0001 - ISS-0082, unique |
| `initiative_id` | ID (FK) | INIT-001 | 41 of 60 initiatives have issues |
| `title` | Enum | Upstream dependency slipped | `Access provisioning delays`, `Benefit baseline disputed by Finance`, `Budget overspend against phase forecast`, `Cutover window clashes with peak trading`, `Data quality below migration threshold`, `Design sign-off overdue with the business`, `Integration defect in UAT`, `Key resource resigned`, `Scope disagreement between functions`, `Test environment unavailable`, `Training materials not signed off`, `Upstream dependency slipped`, `Vendor invoice dispute blocking the next phase`, `Works council consultation not started` |
| `description` | Text | An upstream initiative has moved its go-live, invalidating our … | One fixed description per title |
| `severity` | Enum | Medium | `Critical`, `High`, `Low`, `Medium` |
| `status` | Enum | Resolved | `Blocked`, `In Progress`, `Open`, `Resolved` |
| `raised_date` | Date (ISO) | 2026-04-21 | 2025-09-04 - 2026-08-11 |
| `age_days` | Integer | 112 | 0 - 341 - Days since raised_date |
| `owner` | Text | Rafael Farouk | 69 distinct |
| `impact_on_schedule_days` | Integer | 0 | 0 - 59 |
| `impact_on_cost_usd` | Integer (USD) | 17000 | 0 - 301000 |
| `linked_risk_id` | ID (FK), nullable | _(blank)_ | Joins risks.risk_id; blank on 49 of 82 rows |

<details><summary>One full example row</summary>

```
issue_id: ISS-0001
initiative_id: INIT-001
title: Upstream dependency slipped
description: An upstream initiative has moved its go-live, invalidating our start assumption.
severity: Medium
status: Resolved
raised_date: 2026-04-21
age_days: 112
owner: Rafael Farouk
impact_on_schedule_days: 0
impact_on_cost_usd: 17000
linked_risk_id: 
```

</details>

## `data/resources.csv`

**360 rows x 8 columns - feeds: Scenario comparison**

Supply versus demand by role and month - the hard constraint on any resequencing. A roadmap that ignores `over_allocated` is not deliverable however good its financials look.

Header row, in file order:

```
role,month,quarter,available_fte,demanded_fte,gap_fte,utilisation_pct,over_allocated
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `role` | Enum | Programme Manager | `Business Analyst`, `Change Manager`, `Commercial Analyst`, `Compliance Specialist`, `Data Engineer`, `ERP Consultant`, `Finance Transformation Lead`, `HR Business Partner`, `Integration Engineer`, `Process Engineer`, `Procurement Category Manager`, `Programme Manager`, `Solution Architect`, `Supply Chain Analyst`, `Test Lead` |
| `month` | Month (YYYY-MM) | 2026-01 | 2026-01 - 2027-12, 24 months |
| `quarter` | Enum | 2026Q1 | `2026Q1`, `2026Q2`, `2026Q3`, `2026Q4`, `2027Q1`, `2027Q2`, `2027Q3`, `2027Q4` |
| `available_fte` | Decimal | 20.3 | 5.1 - 53.5 |
| `demanded_fte` | Decimal | 2.0 | 0 - 54.1 |
| `gap_fte` | Decimal | 18.3 | -17.6 - 40.3 - available_fte minus demanded_fte; negative means short |
| `utilisation_pct` | Decimal | 9.9 | 0 - 154.8 - Over 100 means the role is oversubscribed |
| `over_allocated` | Boolean | FALSE | TRUE / FALSE (upper case, unlike is_regulatory) |

## `data/burn.csv`

**1,440 rows x 8 columns - feeds: Value realization**

Monthly spend curve per initiative: plan, actual to date, and forecast for the full 24 months. Pair with benefits.csv to get net value over time.

Header row, in file order:

```
initiative_id,month,planned_spend,actual_spend,cumulative_planned,cumulative_actual,forecast_spend,benefit_realized
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `initiative_id` | ID (FK) | INIT-001 | All 60 initiatives |
| `month` | Month (YYYY-MM) | 2026-01 | 2026-01 - 2027-12, 24 rows per initiative |
| `planned_spend` | Integer (USD) | 75580 | 0 - 368560 |
| `actual_spend` | Integer (USD) | 64130 | Blank for months after the 2026-07 as-of date (1,020 of 1,440 rows) |
| `cumulative_planned` | Integer (USD) | 75580 | 0 - 3375000 |
| `cumulative_actual` | Integer (USD) | 64130 | Blank for future months (1,020 of 1,440 rows) |
| `forecast_spend` | Integer (USD) | 76678 | 0 - 439923 - Populated for all 24 months |
| `benefit_realized` | Integer (USD) | 0 | Blank for future months; 0 in 419 of the 420 past-month rows |

<details><summary>One full example row</summary>

```
initiative_id: INIT-001
month: 2026-01
planned_spend: 75580
actual_spend: 64130
cumulative_planned: 75580
cumulative_actual: 64130
forecast_spend: 76678
benefit_realized: 0
```

</details>

## `data/benefits.csv`

**1,440 rows x 6 columns - feeds: Value realization**

The other half of the value view - planned benefit per initiative per month, with a P&L category and a confidence grade so you can discount it.

Header row, in file order:

```
initiative_id,month,benefit_plan,benefit_actual,pnl_impact_type,confidence
```

| Column | Type | Example | Allowed values / range |
|---|---|---|---|
| `initiative_id` | ID (FK) | INIT-001 | All 60 initiatives |
| `month` | Month (YYYY-MM) | 2026-01 | 2026-01 - 2027-12, 24 rows per initiative |
| `benefit_plan` | Integer (USD) | 0 | 0 - 249167 - 0 in 1,113 of 1,440 rows - the plan is back-loaded |
| `benefit_actual` | Integer (USD) | 0 | Blank for future months; only one non-zero value in the whole file (507) |
| `pnl_impact_type` | Enum | Enabling (attributed to downstream) | `Cost avoided (non-cash)`, `Enabling (attributed to downstream)`, `Gross margin`, `Non-financial / risk`, `Opex reduction` |
| `confidence` | Enum | Low | `High`, `Low`, `Med` |

<details><summary>One full example row</summary>

```
initiative_id: INIT-001
month: 2026-01
benefit_plan: 0
benefit_actual: 0
pnl_impact_type: Enabling (attributed to downstream)
confidence: Low
```

</details>

## `data/scenarios.json`

**Object with 5 top-level keys - feeds: Scenario comparison**

Scenario **inputs only**; no results are pre-computed.

| Key | Type | Value / shape |
|---|---|---|
| `generated_for` | string | Aberdeen Advisors hack-team-01 |
| `portfolio_total_budget` | integer | 95,350,000 (USD) |
| `portfolio_total_capex` | integer | 33,352,000 (USD) |
| `note` | string | These are scenario INPUTS only. No results are pre-computed — the tool being built is expected to work out the resulting sequence, cost profile, resource feasibility and benefit curve for each one, then compare them side by side. |
| `scenarios` | array[3] | One object per scenario - keys listed below |

### `scenarios[]` object keys

| Key | Type | Notes |
|---|---|---|
| `scenario_id` | string | SC-01 SC-02 SC-03 |
| `name` | string | Board baseline / Cash-constrained (-25% capex) / Speed to value (front-load quick wins) |
| `description` | string | Prose framing of the board question |
| `constraints` | object | 7 keys on SC-01, 8 on SC-02 and SC-03 - see below |
| `expected_qualitative_outcome` | string | What a correct tool should surface. Prose, not numbers. |

### `scenarios[].constraints` keys

| Key | Type | Values across the 3 scenarios |
|---|---|---|
| `budget_cap_usd` | integer | 95,350,000 / 78,187,000 / 95,350,000 |
| `capex_cap_usd` | integer | 33,352,000 / 25,014,000 / 33,352,000 |
| `peak_fte_cap` | integer or null | null on SC-01, 85 on SC-02, 95 on SC-03 |
| `mandatory_initiatives` | array[object] | Objects of initiative_id, name, function. 8 / 13 / 16 entries. |
| `deferred_initiatives` | array[object] | Same object shape. Empty on SC-01, 6 entries on SC-02 and SC-03. |
| `must_finish_by` | string (date) | 2028-12-31 / 2029-06-30 / 2029-06-30 |
| `allow_resequencing` | boolean | false / true / true |
| `objective_function` | string | SC-03 only - “maximise cumulative realised benefit by 2027-06” |

## `data/initiatives.json`

**Top-level JSON array of 60 objects x 37 keys - feeds: Sequenced roadmap**

Not an object - there is no wrapper key. Each object carries exactly the 37 keys of `initiatives.csv`, in the same order. The only difference is typing: numbers are real numbers and `is_regulatory` is a real boolean, where the CSV has `"True"`/`"False"` strings.

```
initiative_id, name, function, pillar, owner, sponsor, business_unit, description, objective, start_date, end_date, duration_months, stage, rag_status, percent_complete, priority_score, strategic_alignment, value_confidence, complexity, effort_fte, capex, opex, total_budget, spend_to_date, forecast_at_completion, annual_benefit_target, benefit_type, benefit_start_month, benefit_ramp_months, npv, payback_months, run_rate_savings, resource_type_needed, key_systems, region, is_regulatory, tags
```

## `docs/` inventory

17 files. The unstructured half of the challenge - and they do not always agree with the CSVs.

**`docs/`**

- `ANSWER-KEY.md` - The planted problems, listed out. Grade your tool against this last, not first.
- `pmo-tracker-messy.csv` - The realistic input: 2 preamble lines, header on row 3, 64 data rows, mixed date formats, $895,000 next to 908000, a phantom INIT-002a, and a broken TOTALS row.

**`docs/business-cases/`**
  
Nine initiative business cases in prose. Numbers here deliberately disagree with the CSVs in places.

- `INIT-001-enterprise-data-platform.md`
- `INIT-006-cloud-migration-wave-2.md`
- `INIT-020-supplier-rationalisation-w2.md`
- `INIT-023-inbound-freight.md`
- `INIT-031-finance-shared-services.md`
- `INIT-035-hris-workday.md`
- `INIT-039-org-delayering.md`
- `INIT-046-aftermarket-services.md`
- `INIT-056-sox-control-remediation.md`

**`docs/decision-logs/`**
  
Two steering-committee records - where scope and sequencing decisions were actually made.

- `2026-06-16-steering-committee-minutes.md`
- `2026-07-21-steering-committee-decision-log.md`

**`docs/status-reports/`**
  
Three monthly PMO reports covering May to July 2026, the dataset's as-of window.

- `2026-05-pmo-monthly-report.md`
- `2026-06-pmo-monthly-report.md`
- `2026-07-pmo-monthly-report.md`

**`docs/strategy/`**
  
The one-page strategy the portfolio is supposed to deliver against.

- `transformation-strategy-one-pager.md`

## Things the field list will not tell you

- **The as-of date is 2026-07.** In `burn.csv` and `benefits.csv`, 1,020 of 1,440 rows have blank actuals - those are future months, not missing data. Only `planned_spend`, `cumulative_planned`, `forecast_spend` and `benefit_plan` are populated across all 24 months.
- **Realised benefit is essentially zero.** `benefit_actual` is 0 in 419 of the 420 past-month rows, with a single value of 507. Benefit is deliberately back-loaded into 2028.
- **Two different boolean spellings.** `initiatives.is_regulatory` is `True`/`False`; `resources.over_allocated` is `TRUE`/`FALSE`.
- **Blanks are meaningful.** `milestones.actual_date` is blank on 216 of 259 rows (not yet complete) and `issues.linked_risk_id` on 49 of 82 (no predicted risk).
- **`benefit_start_month` is an offset** in months from the initiative's own start date, not a calendar month like the `month` columns.
- **The messy tracker is the real input.** `docs/pmo-tracker-messy.csv` does not have its header on line 1 - two preamble lines come first, and the last column is unnamed.
