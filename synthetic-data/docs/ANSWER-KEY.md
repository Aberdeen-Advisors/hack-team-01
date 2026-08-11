# ANSWER KEY — planted problems in this dataset

> **Spoiler warning.** This file lists the deliberate inconsistencies, conflicts and traps
> that were built into the dataset. It exists so you can score your tool: if your tool finds
> these, it works. Read it after you have had a go, or immediately if you would rather build
> straight at a known target. Your call.

Everything below is **intentional**. None of it is a bug in the data.

---

## A. Schedule conflicts — hard dependencies that are violated

These are in `data/dependency_conflicts.csv`, and the underlying edges are real rows in
`data/dependencies.csv`. The dependency graph itself is **acyclic** — these are scheduling
violations, not cycles.

| Ref | Predecessor | Successor | The problem |
|---|---|---|---|
| CONF-001 | INIT-039 Organisational Delayering (HR / People) ends **2028-06-08** | INIT-031 Finance Shared Services Centre (Finance) starts **2026-08-07** | Hard Finish-to-Start with 45-day lag. Successor starts **716 days** too early. |
| CONF-002 | INIT-039 Organisational Delayering (HR / People) ends **2028-06-08** | INIT-038 Shared Services HR Operating Model (HR / People) starts **2026-07-29** | Hard Finish-to-Start with 30-day lag. Successor starts **710 days** too early. |
| CONF-003 | INIT-005 Cloud Migration Wave 1 (Technology) ends **2027-09-22** | INIT-006 Cloud Migration Wave 2 (Technology) starts **2026-02-02** | Hard Finish-to-Start with 30-day lag. Wave 2 is scheduled to **finish before Wave 1 does**. Successor starts **627 days** too early. |

**Why these matter:** CONF-001 and CONF-002 are cross-function (HR gating Finance and HR
gating HR). A tool that only looks within a function will miss the worst one. All three are
discussed in prose in the business cases and the steering minutes, so they are also
recoverable from the documents alone.

A good tool should also be able to answer the follow-up: *what is the minimum set of date
changes that makes the plan feasible?*

---

## B. Document ↔ data contradictions

The structured data in `data/` is the source of truth. The documents in `docs/` disagree with
it in the following specific places.

### B1. INIT-035 HRIS Consolidation — "went live" but did not
- **`docs/status-reports/2026-06-pmo-monthly-report.md` §6** states the June go-live "has been
  achieved and the system is live across all entities", and moves it to Green.
- **Data says:** stage `At Risk`, RAG `Red`, 46% complete. In `milestones.csv` the Go-Live
  milestone is baselined 2026-09-25, forecast 2026-10-25, status `Not Started`.
- The messy tracker flags this in its notes column: *"June report said this went live - it has
  not gone live"*.

### B2. INIT-020 Supplier Rationalisation Wave 2 — "back on track"
- **`docs/status-reports/2026-07-pmo-monthly-report.md` §2** reports it as **Amber** and "back
  on track".
- **Data says:** RAG `Red`, 12% complete, forecast at completion $3,535,000 against a
  $2,635,000 budget (**+34%**), with a Critical open issue and a 90-day missed mobilisation gate.
- The RAG change was a sponsor decision over the delivery lead's recorded objection —
  see `docs/decision-logs/2026-07-21-steering-committee-decision-log.md`, decision D-2707-02.

### B3. INIT-017 Health & Safety Digital Reporting — "Green and on schedule"
- **`docs/status-reports/2026-07-pmo-monthly-report.md` §6** states it is Green and on schedule
  following resolution of the pause.
- **Data says:** stage `Paused`, RAG `Red`, 2% complete.
- The steering committee *directed* an unpause (D-2707-04) but the direction was not actioned.
  The report describes the intent as though it were the outcome.

### B4. "Broadly tracking to budget"
- **`docs/status-reports/2026-07-pmo-monthly-report.md` §3** says the portfolio is "broadly
  tracking to budget at portfolio level".
- **Data says:** spend is 6.9% over plan, **25 of 60** initiatives forecast completion above
  their approved budget, and aggregate forecast at completion is ~$101m against a $95.3m
  approved envelope.

### B5. July RAG table vs reality
The July report's RAG table totals **32 Green / 18 Amber / 10 Red**. The data totals
**31 Green / 17 Amber / 12 Red**. The delta is exactly the two initiatives above (B2 and B3).
Everything else in the table reconciles.

*(The May and June reports are historical snapshots as at 31 May and 30 June respectively.
Differences between those and today's data are legitimate elapsed time, not planted errors.)*

---

## C. Traps in the messy tracker (`docs/pmo-tracker-messy.csv`)

| Trap | Detail |
|---|---|
| Junk header rows | Rows 1–2 are a title and a note. The real header is on **row 3**. |
| Trailing junk row | Last row is a broken `=SUM()` formula. |
| Date formats | Three formats mixed, sometimes in the same row: `11/12/25` (DD/MM/YY), `2026-07-11` (ISO), `Jun-27` (MMM-YY). Note the DD/MM ordering — `04/08/26` is 4 August, not 8 April. |
| Budget formats | `$895,000`, `2,040,000`, `1.735m`, `$2.365m`, `TBD`, and bare `1900000`. |
| Free-text RAG | `GREEN`, `amber-ish`, `on track?`, `RED`, `green`, `Amber`, and blanks. |
| Duplicate rows | **INIT-011** appears twice (`Optimization` vs `Optimisation`, `Sinead Mehta` vs `S. Mehta`). **INIT-020** appears twice with **conflicting RAG** (`on track?` vs `RED`) and conflicting benefit (`$3,140,000` vs `2.5m-3.1m contested`). |
| Phantom initiative | **INIT-002a** "ERP Finance - Phase 2" exists only in the tracker. It is **not** in `initiatives.csv`. Its own note asks whether it is a real initiative. A good tool should flag it, not silently create it. |
| Blanks | Several rows have empty Start / End / Budget / Benefit cells. |
| RAG disagreement with data | The tracker lists INIT-006 as `Green`; `initiatives.csv` says `Amber`. |

---

## D. Sequencing problems visible only in prose

These are **not** in `dependency_conflicts.csv`. They are stated in documents and a strong
tool should surface them by reading the docs, or by cross-checking dates against dependencies.

1. **INIT-047 Subscription Maintenance Offering starts 2027-01-23. INIT-046 Aftermarket
   Services Proposition, on which it hard-depends, starts 2027-02-11.** The successor starts
   before the predecessor does. Raised in `INIT-046` business case and in the July steering log.
2. **INIT-059 Data Governance & Quality Framework is still at `Idea` stage** with four
   initiatives depending on it, and it is flagged regulatory. Raised in the July steering log
   with no owner assigned.
3. **The supplier data domain is an orphan.** `INIT-001`'s closure summary records that the
   supplier domain was descoped to protect the date, and that Master Data Management
   (INIT-008) has not formally picked it up. INIT-060 depends on a deduplicated supplier master.
4. **INIT-011 is recorded as `Paused` but was formally `Deferred`** (D-2707-01). The steering
   log explicitly notes the tracker was not corrected. Pause and deferral have different
   roadmap consequences.

---

## E. Benefit-case problems

1. **Double-counted benefit.** $400–600k of price harmonisation benefit is claimed by **both**
   INIT-020 and INIT-050. Unresolved since May 2026; Group Finance has refused to sign a
   baseline for either. Both still report the benefit in full, so the portfolio benefit total
   is overstated.
2. **Benefit claimed by one initiative but delivered by another.** INIT-035's business case
   claims ~$240k of HR admin effort reduction that only materialises if the HR operating model
   change (INIT-038) removes the roles. INIT-038 also claims its own saving.
3. **Enablers score badly on any benefit-to-cost ranking.** INIT-001 costs $895k and returns
   $70k a year on its own — a ratio that puts it last in any naive ROI ranking. Follow the
   dependency graph transitively and it **gates 28 of the 60 initiatives, carrying $38.6m of
   annual benefit between them**. Its closure summary explicitly warns about this. Same
   pattern applies to INIT-003, INIT-008 and INIT-059.

   This is the single best test of a roadmap tool in this dataset: *does your ranking
   understand that cutting the cheapest-looking initiative is the most expensive decision
   available?*
4. **Regulatory initiatives look like poor investments.** INIT-056 SOX Control Remediation
   returns $450k on $1.48m and cannot be cut. Any optimiser that maximises NPV without honouring
   `is_regulatory = TRUE` will cut it, and will be wrong.
5. **Nothing has been realised yet.** Benefit actual to 2026-07 across the whole portfolio is
   ~$1k. This is correct, not a data error — every initiative books value after delivery.

---

## F. Resource constraint

Three roles are deliberately over-allocated, concentrated in **2026Q4 and 2027Q1**:

| Role | Worst month | Available FTE | Demanded FTE | Utilisation |
|---|---|---|---|---|
| Data Engineer | 2027-03 | 36.5 | 54.1 | 148% |
| Supply Chain Analyst | 2026-10 | 12.4 | 19.2 | 155% |
| Change Manager | 2026-10 | 26.2 | 38.1 | 145% |

No other role breaches its supply in any month. The squeeze is deliberately concentrated so
that scenario comparison has a constraint that actually bites — a plan that ignores it is
not deliverable regardless of how good its financials look.

---

## G. Things that are correct and may look wrong

Do not "fix" these:

- **`dependencies.csv` contains no cycles.** It is acyclic by construction. If your tool
  reports a cycle, the bug is in your tool.
- **`pillar` and `function` are different columns on purpose.** `function` = who owns it
  (8 values). `pillar` = why we do it (4 value themes: Grow / Run Better / Cost Out / Protect).
- **All actuals stop at 2026-07** and are blank from 2026-08. Today is 2026-08-11.
- **Benefit actuals are near zero.** See E5.
- **Some initiatives are under budget.** Not every variance is an overrun.
- **`initiatives.json` is the same 60 records as `initiatives.csv`**, provided for convenience.
