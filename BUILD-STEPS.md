# BUILD STEPS — how to actually build it

**For someone who has never used Claude Code.** Follow the steps in order. Each one gives you the
exact words to paste. You do not need to write any code yourself.

The companion file `BUILD-BRIEF.md` in this same folder is the specification. You do not need to read
it front to back — the prompts below tell Claude to read it. But do skim §5 (the trap) and §9 (the
money shot), because those are the two things you will be asked about in the demo.

---

## Before you start

**1. Open a terminal in the cloned repository folder.**

You should be inside the folder that contains `synthetic-data/`, `deck/`, `BUILD-BRIEF.md` and this
file. Check it with:

```
ls
```

If you do not see `synthetic-data` in that list, you are in the wrong folder. Move into the
`hack-team-01` folder and try again.

**2. Confirm you are on the default branch.**

```
git symbolic-ref refs/remotes/origin/HEAD
git branch --show-current
```

The first command prints `refs/remotes/origin/main`. The second should print `main`. If it prints
something else, run `git checkout main`.

**3. Start Claude Code.**

```
claude
```

You now have a prompt. Everything in a grey box below is text you paste in and press Enter.

**4. Two things to know about how this goes.**

- Claude will ask permission before it writes or changes a file. Read what it is about to do, then
  approve it. If it is about to touch anything inside `synthetic-data/`, say no — that folder is the
  system of record and must not change.
- If Claude produces something wrong, you do not start over. You tell it what is wrong in plain
  English, in the same conversation. "The bars are all the same colour, they should be coloured by
  function" is a perfectly good instruction.

---

## Step 1 — Build the data flattener

**What this step does:** turns the nine CSV files into one JSON file the web page can read, and
proves the logic is right by finding the three planted dependency conflicts on its own.

Paste this:

```
Read BUILD-BRIEF.md in this repository in full before doing anything else. It is the complete
specification for what we are building — do not skip it and do not summarise it back to me.

Then write a build-time Python script at the repo root called build_portfolio_json.py that reads
the nine CSV files and two JSON files in synthetic-data/data/ and emits a single file at
data/portfolio.json.

Requirements:

1. Do not modify anything under synthetic-data/. Read only. That directory is the system of record.

2. Do NOT read synthetic-data/data/dependency_conflicts.csv into the output JSON. It is a
   pre-diagnosed answer key. See section 5 of the brief. The app must never see it.

3. Normalise on ingest, per section 4 of the brief: is_regulatory is True/False title case,
   over_allocated is TRUE/FALSE upper case — both must become real JSON booleans. Blank actuals
   after 2026-07 are FUTURE months, not missing data: leave them as null and never impute or
   zero-fill them.

4. Prefer synthetic-data/data/initiatives.json over initiatives.csv for the initiative spine, since
   it is already correctly typed.

5. Collapse milestones, risks and issues into per-initiative rollups: open issue count, max risk
   score, total risk exposure, next upcoming milestone, total slip days.

6. Add four computed fields per initiative that do not exist in the source data:
   - transitive_downstream_count: how many initiatives it gates through the whole dependency
     closure, not just direct links
   - transitive_downstream_benefit: the sum of annual_benefit_target across that closure
   - naive_roi: annual_benefit_target divided by total_budget
   - naive_roi_rank and corrected_rank: the rank on naive ROI, and the rank on
     transitive_downstream_benefit

7. Port the integrity checks from synthetic-data/validate_portfolio.py as build-time assertions, so
   the script fails loudly if the data is not what we expect. Use the check() helper pattern at line
   31 of that file. Port these specifically: no self-referencing edges, no duplicate edges, the
   foreign-key loop, capex + opex == total_budget, end_date after start_date, and
   benefit_start_month >= duration_months.

8. Port the Kahn's-algorithm topological sort that is inline inside main() at lines 88-104 of
   validate_portfolio.py. Record the wave number for each initiative as you peel nodes off, and
   include wave in the output JSON. Assert that all 60 nodes sort with no cycle — if it reports a
   cycle, the bug is in the code, not the data.

9. Independently detect dependency conflicts from dependencies.csv and initiatives.csv alone. The
   rule: required_successor_start = predecessor.end_date + lag_days;
   overlap_days = required_successor_start - actual_successor_start; flag when positive.

At the end, print a summary to the terminal: the row counts read, the number of nodes sorted, and
every dependency conflict found with its predecessor, successor and overlap in days, sorted worst
first.

Then run the script and show me the output.
```

**You are done when:** the terminal prints exactly three conflicts — INIT-039 → INIT-031 at **716
days**, INIT-039 → INIT-038 at **710 days**, and INIT-005 → INIT-006 at **627 days** — and
`data/portfolio.json` exists. 716 is the number to look for. If you see three conflicts but different
numbers, tell Claude: "the overlaps should be 716, 710 and 627 days — check the lag_days handling".

If it found fewer than three, or more than three, say so and let it debug. Do not move on until this
is right; every later step is built on it.

---

## Step 2 — Build the engine

**What this step does:** writes the calculation core. Given a scenario, it produces the sequence, the
violations, the benefit curve and the totals. Nothing is drawn yet.

Paste this:

```
Now build the engine in app.js at the repo root, implementing the result-object contract in section 6
of BUILD-BRIEF.md exactly:

{
  scenario_id:   "SC-01",
  sequence:      [ { initiative_id, name, function, start, end, wave } ],
  violations:    [ { type, initiative_id, description, severity } ],
  benefit_curve: [ { month, cost_reduction, cost_avoidance, revenue_growth, non_financial } ],
  totals:        { budget, capex, peak_fte,
                   benefit_cash_backed, benefit_cost_avoidance,
                   benefit_revenue, benefit_non_financial }
}

Do not change this shape. The views are being written against it.

The engine takes a scenario_id, applies that scenario's constraints from scenarios.json (budget cap,
capex cap, peak FTE cap, mandatory initiatives, deferred initiatives, must-finish-by,
allow_resequencing) and returns one of these objects.

For the benefit curve, port the maths from synthetic-data/generate_portfolio.py rather than inventing
it, so our numbers reconcile to benefits.csv instead of being approximately right:
- s_curve_weights(n) at line 1170
- benefit_ramp_fraction(months_since_start, ramp_months) at line 1185
- the benefit block inside generate_burn_and_benefits at lines 1240-1247, which is the authoritative
  statement of the maths
- the date helpers add_months, month_key, month_index and quarter_of at lines 450-476
- the benefit_type to pnl_impact_type mapping at lines 1272-1278

Critical: benefit_start_month is an OFFSET in months from each initiative's own start_date. It is
NOT a calendar month. Getting this wrong shifts the whole value curve by up to two years. The rule is
benefit_first_month = add_months(initiative.start_date, benefit_start_month).

Map the four value bands using the table in section 6 of the brief: cost_reduction from Cost Save /
Opex reduction, cost_avoidance from Cost Avoidance / Cost avoided (non-cash), revenue_growth from
Revenue Uplift / Gross margin, non_financial from Risk Reduction and Capability. Do not sum cost
avoidance into cost reduction — it is non-cash and a CFO will challenge a combined figure.

Implement three of the four violation types now: dependency, resource and budget. Leave compliance
for a later step.

No framework, no npm, no build step, no network calls. Plain browser JavaScript reading
data/portfolio.json.

Then write a self-test I can run that checks: all 60 nodes topologically sort with no cycle; exactly
3 dependency violations are found with overlaps of 716, 710 and 627 days; the benefit curve has 24
monthly points each with all four bands; and the four benefit subtotals sum to approximately $84.3m
of claimed annual benefit. Run it and show me the output.
```

**You are done when:** the self-test passes on all four checks. In particular the benefit subtotals
should come to roughly **$84.3m** — that number is what tells you the value-band mapping is complete
rather than dropping a category.

---

## Step 3 — Build the leader view

**What this step does:** the first screen you can actually show someone.

Paste this:

```
Now build index.html at the repo root with the leader view, per section 8 of BUILD-BRIEF.md. It reads
data/portfolio.json and calls the engine in app.js.

Three components on this screen:

1. The sequenced roadmap. One horizontal bar per initiative, ordered by computed start date, grouped
   into the waves from the topological sort, coloured by function. Show rag_status as an edge or a
   dot, not as the bar fill — the fill is already carrying function. Month gridlines across the
   2026-01 to 2029-02 span, with year labels.

2. The exception list. Every violation in one table: type, initiative, description, severity. Sorted
   by severity for now. Clicking a row highlights that initiative in the roadmap above.

3. The "what this unblocks" ranking. For each initiative, how many initiatives it transitively gates
   and the total annual benefit those carry, sorted descending. INIT-055 should be top with 59
   initiatives worth $82.6m, then INIT-058 with 37 worth $53.1m, then INIT-003 with 33 worth $44.3m,
   then INIT-001 with 28 worth $38.6m.

Also put these verified headline figures across the top of the page, from section 11 of the brief:
60 initiatives; $95.3m approved vs $101.7m forecast; $84.3m claimed annual benefit against $507
actually banked; 95 dependencies of which 70 cross functions and 3 are already violated;
31 Green / 17 Amber / 12 Red; 25 of 60 forecasting over budget.

All charts must be inline SVG that you draw by hand. No chart library. No CDN script tags. No
framework. Currency formatted as USD.

Then start a local server with python3 -m http.server 8000 and tell me what to open.
```

**You are done when:** you open `localhost:8000` in a browser and see sixty bars, an exception list
with the three dependency conflicts in it, and INIT-055 at the top of the unblocks ranking.

**Commit now.** See the note at the bottom of this file.

---

## Step 4 — Build the board tab

**What this step does:** the executive view. This is a strong candidate for the opening twenty seconds
of the demo.

Paste this:

```
Now add a second tab to index.html: the board view, per section 8 of BUILD-BRIEF.md. Same engine,
same data, different level of aggregation — a tab, not a second application. Switching tabs and
switching scenario must both re-render without a page reload.

No initiative-level detail anywhere on this tab. A board does not want sixty bars.

Three components:

1. Three scenarios side by side. SC-01 Board baseline, SC-02 Cash-constrained, SC-03 Speed to value,
   as three columns from the same engine. Each column shows the totals block: budget, capex, peak
   FTE, and the four benefit subtotals broken out — cash-backed, cost avoidance, revenue, and
   non-financial. Under the financials, show the violation count by type for that scenario, so the
   cost of each scenario in broken dependencies and compliance breaches sits next to its money.

2. The stacked value bands. The benefit_curve as a stacked area chart across the 24-month window,
   bands bottom to top: cost_reduction, cost_avoidance, revenue_growth, non_financial. Four
   distinguishable fills with a legend. Inline SVG drawn by hand, no library. The point it makes is
   that the SHAPE of value changes between scenarios, not just the height. Annotate the $507 actually
   realised to date against the $84.3m claimed.

3. Top five board decisions. Five plain-English decisions, each with what it unlocks and what it
   costs. Use this as the register for the tone: "Fund the Enterprise Data Platform ahead of the
   cost-out programme. $895k. Unblocks 28 initiatives carrying $38.6m of annual benefit. Delay it and
   everything behind it slips."

Still inline SVG only, still no framework, still no network calls.
```

**You are done when:** you can click between the leader tab and the board tab, the three scenario
columns show different numbers from each other, and the stacked area chart visibly changes shape when
you switch scenario.

---

## Step 5 — Add the compliance violation type and the regulatory lock

**What this step does:** implements the fourth violation type and the rule that protects regulatory
work from being cut. This is a requirement from Suraj, not an optional extra.

Paste this:

```
Now implement the fourth violation type and the regulatory lock, exactly as specified in section 7 of
BUILD-BRIEF.md.

Add violation type "compliance". It fires when an initiative with is_regulatory true is in any of
these four states:

1. Deferred — it appears in a scenario's deferred_initiatives list.
2. Deprioritised — it has been pushed behind non-regulatory work it previously preceded, or its stage
   is Paused.
3. Sequenced after its required date — its scheduled finish falls after the date it has to be done
   by. There is no separate regulatory-deadline column in the dataset, so use the initiative's
   baseline end_date from initiatives.csv as its required date, and also test it against the
   scenario's must_finish_by.
4. Still at Idea stage despite having dependents — other initiatives are already planned on top of
   something that has not been shaped yet.

Two rules that follow, both mandatory:

A. Compliance violations always sort to the TOP of the exception list, regardless of severity score.
   A regulatory breach outranks a bigger-dollar budget breach every time. Sort by
   type === 'compliance' first, then by severity within each group.

B. Regulatory initiatives can NEVER be deferred by a scenario, even when a budget cap would
   otherwise drop them. When the solver trims scope to fit budget_cap_usd or capex_cap_usd, the 8
   regulatory initiatives are locked in and the cut comes from somewhere else. If the cap cannot be
   met without cutting regulatory work, emit a "budget" violation saying the cap is infeasible —
   never a dropped compliance item.

There are 8 regulatory initiatives: INIT-004, INIT-016, INIT-017, INIT-056, INIT-057, INIT-058,
INIT-059, INIT-060. Two of them are live compliance violations in the baseline data and your detector
must surface both without being told:
- INIT-059 Data Governance & Quality Framework is regulatory, still at Idea stage, and already has 2
  dependents planned on top of it (INIT-022 and INIT-033). That is rule 4.
- INIT-017 Health & Safety Digital Reporting is regulatory, Paused, and Red. That is rule 2.

Tie compliance back to the risk register: risks.csv has a Regulatory category — 14 risks, 13 still
Open or Mitigating, $1,089,000 of combined exposure_usd. Show that exposure alongside each compliance
violation so "this is late" becomes "this is late and here is what it is worth". Note that only
INIT-060 carries a Regulatory-category risk itself; the other 13 sit on initiatives nobody has
classified as regulatory, which is a finding worth surfacing in its own right.

Then verify for me: run every scenario and confirm no regulatory initiative is ever deferred, and
confirm INIT-059 and INIT-017 both appear as compliance violations at the top of the exception list.
```

**You are done when:** the exception list shows compliance violations first, INIT-059 and INIT-017 are
both in that group, and switching to SC-02 (the cash-constrained scenario, which cuts a quarter of the
capital) still leaves all 8 regulatory initiatives in the plan.

---

## Step 6 — Add the naive-vs-corrected ROI comparison

**What this step does:** the money shot. This is the demo's spine. Do not skip it and do not simplify
it.

Paste this:

```
Now build the money shot, per section 9 of BUILD-BRIEF.md. This is the single most important screen in
the application.

Add a side-by-side ranking comparison to the leader view. Left column: all 60 initiatives ranked by
naive return on investment, annual_benefit_target divided by total_budget, worst at the bottom. Right
column: the same 60 ranked by dependency-corrected value, which is the total annual benefit of every
initiative they transitively gate. Draw the movement between the two columns so the reader can see
which initiatives jump.

Highlight INIT-001 Enterprise Data Platform (Lakehouse) Build explicitly. It costs $895,000 and
returns $70,000 a year standalone, which is a ratio of 0.078 — the worst of all 60. Any spreadsheet
would cut it first. But it transitively gates 28 of the 60 initiatives carrying $38,580,000 of annual
benefit between them. That is 43 times the money back on the same $895k. Label it on screen:
"$895k gates $38.6m across 28 initiatives".

Show the same pattern for three more, all verified:
- INIT-003 API Gateway & Integration Layer: $2,040,000 budget, $170,000 standalone, 2nd worst on
  naive ROI, gates 33 initiatives worth $44,260,000
- INIT-008 Master Data Management - Customer & Product: $1,780,000 budget, $270,000 standalone, gates
  5 initiatives worth $5,300,000
- INIT-059 Data Governance & Quality Framework: $1,155,000 budget, $230,000 standalone, gates 2
  initiatives worth $2,580,000 — and it is also a regulatory initiative sitting at Idea stage, so it
  is the money shot and a compliance violation at the same time

The argument the screen has to make in one glance is not "we made a chart". It is "your existing
ranking method would have cut the one thing everything else needs".
```

**You are done when:** you can point at the screen and say the sentence "$895k gates $38.6m" without
having to explain what you are looking at.

---

## Step 7 — Write the root README for the AI judge

**What this step does:** defends the majority of the score that has nothing to do with the build. An
AI judge reads text in round one; it does not watch the demo. If the judge only reads the repository,
the README is the entire submission.

Paste this:

```
Write a README.md at the repo root, aimed at a reader who will never see the demo — an AI judge that
reads the repository as text. Plain words, no jargon, no bullet-point salad. Four sections:

1. TARGET USER. A newly appointed transformation leader who has inherited 60 initiatives written by 60
   different people, in incompatible formats, each optimised for its own initiative. Their problem is
   not that they lack a plan — it is that they have sixty of them, and the board asks three questions
   nobody can answer from the evidence that exists: what happens first, what depends on what, and
   when does value reach the P&L.

2. WORKFLOW. The repeatable six steps, described so it is obvious this is a product and not a one-off
   for one client: Collect (point it at wherever the plans already live — SharePoint, a PPM export, a
   shared drive; no migration, no data project). Extract (AI reads the messy documents — business
   cases with the cost buried in paragraph four, status decks, steering minutes, a tracker with three
   date formats — and produces one structured record per initiative). Reconcile (cross-check the
   documents against each other and against the tracker, and surface disagreements rather than
   silently picking one). Sequence (deterministic, not AI — build the dependency graph, topologically
   sort it, and detect what breaks). Compare (apply a scenario's constraints and re-run the
   sequencing). Publish (roadmap, what-this-unblocks view, value-realisation curve, exception list).
   Say plainly that sequencing is ordinary deterministic code, and that the AI work happens offline
   at extraction — a judge who asks "is that live?" and gets a straight answer thinks better of us
   than one who catches us.

3. BUSINESS VALUE. Use the real verified numbers from section 11 of BUILD-BRIEF.md, and lead with the
   one that matters: the Enterprise Data Platform costs $895k and returns $70k a year, which puts it
   last on any naive ranking — but it gates 28 of the 60 initiatives carrying $38.6m of annual
   benefit. A 43x return that a spreadsheet would have cut. Then the portfolio picture: $95.3m
   approved against $101.7m forecast, $84.3m of claimed annual benefit against $507 actually banked,
   95 dependencies of which 70 cross functions and 3 are already violated, 25 of 60 initiatives
   forecasting over budget. Also state what the compliance rules buy: regulatory work can never be
   cut by a budget scenario, and regulatory breaches always sort above dollar-value breaches.

4. PATH TO MARKET. Where the inputs come from, in three tiers. Tier 1 structured: exports from
   Clarity, Planview, ServiceNow SPM, Jira Align or Smartsheet; the PMO's Excel tracker on SharePoint
   or OneDrive; Azure DevOps or Planner for task dates; SAP, Oracle or Workday Adaptive for actual
   spend. Tier 2 documents: business cases, project initiation documents, board packs, monthly status
   reports and strategy one-pagers, as Word, PDF and PowerPoint in the SharePoint libraries where the
   client already keeps them. Tier 3 conversation: Teams transcripts and Copilot meeting recaps,
   steering committee minutes, Outlook approval chains, and the leader's own first-90-days interviews
   with initiative owners. Say that Tier 3 is the differentiator — no PPM tool reads what an owner
   actually said in a review, and that is how you catch the initiative that is Green on the tracker
   and dying in the room. All three tiers read-only, inside the client's own tenancy: that is also
   the answer to the security question. Then list what is configurable per client, which is the answer
   to "is this a tool or a one-off": taxonomy, field mapping, constraint types, fiscal calendar,
   benefit categories, and confidence rules. Everything else — extraction, sequencer, conflict
   detection, views — is the product.

Also include a short "how to run it" section: it is a static page, so python3 -m http.server 8000 and
open localhost:8000. No install, no build, no API key.

Do not overwrite BUILD-BRIEF.md or BUILD-STEPS.md.
```

**You are done when:** `README.md` exists at the repo root and someone who reads only that file could
explain what the tool is for, who uses it, and why it is worth money.

---

## Troubleshooting

**The page is completely blank.**

Almost always a JavaScript error, and the browser is hiding it. Open the developer console — F12 on
Windows, Cmd+Option+I on a Mac — and click the Console tab. Copy whatever red text is there and paste
it straight into Claude Code with "the page is blank and the console says this". Do not try to
interpret it yourself; the error text is the useful part.

**The JSON will not load, or the console mentions CORS, or "Cross-Origin Request Blocked", or
`file://`.**

You have opened `index.html` by double-clicking it. Browsers refuse to let a page opened from
`file://` read a local JSON file — this is a security rule, not a bug in the code, and no amount of
fixing the code will help. Serve the folder over HTTP instead. In a terminal, in the repository
folder:

```
python3 -m http.server 8000
```

Then open **http://localhost:8000** in your browser. Leave that terminal window running while you
work; closing it stops the server. If port 8000 is already taken, use `python3 -m http.server 8080`
and open `localhost:8080`.

**Claude proposes adding React, Vue, Next.js, Tailwind, D3, Chart.js, a bundler, `npm install`, or a
build step.**

Say no. Paste this:

```
No — keep it static. No framework, no npm install, no build step, no bundler. Plain browser
JavaScript in app.js, hand-drawn inline SVG for every chart, no external dependencies. This is a hard
constraint from BUILD-BRIEF.md section 2: the page has to work with nothing running but a static file
server. Please do it that way instead.
```

This matters more than it looks. A build step is one more thing that can fail, and an unreachable CDN
in the demo room turns a working application into a blank page.

**Claude wants to change something under `synthetic-data/`.**

Say no. That folder is the system of record — both the generator and the validator depend on those
files exactly as they are, and the hand-written documents in `synthetic-data/docs/` were authored
against one specific random seed, so regenerating the data silently breaks the alignment between the
documents and the numbers. Read from it, never write to it. Tell Claude: "do not modify anything under
synthetic-data/ — read only, and write your output to the repo root instead".

**The conflict detector finds a cycle in the dependency graph.**

The graph is acyclic by construction and `validate_portfolio.py` asserts it on every run, so a
reported cycle means the bug is in the code — usually a reversed edge, because `from_initiative` is
the predecessor and `to_initiative` is the successor. Tell Claude: "the dependency graph is acyclic by
construction, so this cycle is a bug in our traversal — check the edge direction, from_initiative is
the predecessor". Do not let it "fix" the data.

**Claude flags 1,020 missing values in the burn or benefit data.**

Those are future months, not missing data. The as-of month is 2026-07 and everything after it is
blank by design. Tell Claude: "those blanks are future months after the 2026-07 as-of date — do not
impute them, do not zero-fill them, and do not flag them as a data quality problem".

**The numbers on screen do not match the brief.**

Trust the brief. Every figure in `BUILD-BRIEF.md` §11 was computed from the files in this repository.
Tell Claude the number you expected and the number you got, and let it find the difference. The most
common cause by a distance is treating `benefit_start_month` as a calendar month rather than an offset
from each initiative's own start date.

**Claude has gone in a direction you do not want and the conversation is a mess.**

You do not need to start the whole build again. Say what you actually want in one sentence — "go back
to the version that had three columns and just change the colours" — and it will. If a file has got
into a bad state, `git checkout <filename>` throws away the uncommitted changes to that one file and
puts it back to your last commit. Which is why the next section exists.

---

## Commit after every step that works

The moment a step produces something that works in the browser, save it. It takes ten seconds and it
means a later mistake can never cost you more than one step's worth of progress.

```
git add index.html app.js data/portfolio.json
git commit -m "Add leader view with sequenced roadmap"
git push
```

Adjust the file list and the message to whatever that step actually produced. Only add the files you
meant to change — never `git add .`, because that sweeps up junk you did not intend to commit.

If you would rather not type it, you can just ask Claude Code: "commit and push what we just built
with a clear message". It will show you the commit before it makes it.

A working thing committed at one o'clock beats a better thing that only exists on your laptop at
half past five.
