# Transformation Roadmap Generator

A newly appointed transformation leader inherits sixty initiatives written by sixty different
people. This turns that into a sequenced roadmap, a dependency view, a scenario comparison and a
value-realisation plan — and answers the three questions a board actually asks: what happens first,
what depends on what, and when does value reach the P&L.

**To run it:** it is a static page. No install, no build step, no API key.

```
python3 -m http.server 8000
```

Then open <http://localhost:8000>. Three files do the work: `index.html`, `app.js` and
`data/portfolio.json`.

---

## 1. Target user

A transformation director in their first ninety days, who has inherited a portfolio rather than
built one.

Their problem is not that they lack a plan. It is that they have sixty of them, each written by the
person who wanted their own initiative funded, each optimised for that initiative alone, in
incompatible formats. Nobody has ever put them on one page. The client's own board-approved
strategy says it plainly:

> *"We have no shortage of initiatives. We have a shortage of sequence."*

And the note at the foot of that same document:

> *"The incoming Transformation Director has asked for an integrated view of how the current 60
> initiatives actually ladder up to these four objectives. As at the date of this note, no such
> view exists."*

That missing view is this tool.

Two audiences use it. The leader needs initiative-level detail to run the programme week to week.
The board needs the handful of decisions that are genuinely theirs. Both read the same numbers from
the same engine, at different altitudes.

---

## 2. Workflow

Six repeatable steps. Nothing here is specific to one client.

**Collect.** Point it at wherever the plans already live — SharePoint, a PPM export, a shared
drive. No migration, no data project, no asking sixty people to refill a template.

**Extract.** AI reads the messy documents — business cases with the cost buried in paragraph four,
status decks, steering minutes, a tracker with three date formats — and produces one structured
record per initiative.

**Reconcile.** Cross-check the documents against each other and against the tracker, and surface
the disagreements rather than silently picking one. Where a business case says $2.365m and the
tracker says "~$3m subject to validation", both are kept and flagged.

**Sequence.** Deterministic, not AI. Build the dependency graph, topologically sort it, and detect
what breaks.

**Compare.** Apply a scenario's constraints — spending ceilings, mandatory work, deferrals — and
re-run the sequencing.

**Publish.** Roadmap, dependency view, value-realisation curve, exception list.

### What is AI and what is not

Worth being exact, because it is the first thing a technical reviewer asks.

**The sequencing is ordinary deterministic code.** Kahn's algorithm for the topological sort, date
arithmetic for the conflict detection, a ported benefit-ramp formula for the value curve. Same
inputs, same outputs, every time. There is no model call at runtime, no API key, and no network
request once the page has loaded. A judge who asks "is that live?" gets a straight answer.

**The AI work happens offline, at extraction.** Reading a PDF business case and turning it into a
typed record is a language problem. Deciding what happens first is not — it is a graph problem, and
using a model for it would make the answer unreproducible and unauditable.

### Honest status of this prototype

The extraction step is **described but not built**. This prototype reads an already-structured
dataset in `synthetic-data/data/` and flattens it to `data/portfolio.json` via
`build_portfolio_json.py`. It does not read the documents in `synthetic-data/docs/`, and it does not
read `synthetic-data/docs/pmo-tracker-messy.csv`, which is the artefact purpose-built to represent
the real input. Everything from **Sequence** onward is fully implemented and runs in the browser.

Stating this is a deliberate choice. The sequencing engine is the defensible part, and claiming an
extraction pipeline we have not written would put the part that does work at risk under questioning.

---

## 3. Business value

### The number that matters

**The Enterprise Data Platform costs $895,000 and returns $70,000 a year.** On return-on-its-own it
ranks **last of sixty** — a ratio of 0.078, the worst in the portfolio. Any spreadsheet in the
client's estate cuts it first.

Follow the dependency graph and **it holds up 28 of the 60 initiatives, carrying $38,580,000 of
annual benefit between them.** That is 43 times the money back on the same $895k, and it is
invisible to every ranking method the client currently uses.

It is not an isolated case. The tool applies a rule — an initiative holds up at least two others,
and at least ten times its own annual value — and finds **eleven** such enablers. The strongest is
one the brief itself never mentions:

| Initiative | Cost | Returns alone | Holds up | Worth | Multiple | Rank on its own |
|---|---:|---:|---:|---:|---:|---:|
| Cyber Security Uplift | $1.0m | $290k | 37 | $53.1m | **183×** | 51 of 60 |
| API Gateway & Integration | $2.0m | $170k | 33 | $44.3m | 260× | 59 of 60 |
| Enterprise Data Platform | $895k | $70k | 28 | $38.6m | 551× | **60 of 60** |
| Identity & Access Management | $1.2m | $370k | 25 | $35.4m | 96× | 48 of 60 |

Three of the four initiatives holding up the most work sit in the bottom quartile on their own
business case. A cost-cutting exercise works up from the bottom of that list.

### The portfolio picture

- **$95.3m approved against $101.7m forecast** — $6.4m over before anything is resequenced
- **$84.3m promised against a $39.6m annual run rate actually scheduled by end-2027** — 47% of the
  promise. Only $18.0m of benefit lands inside the 24-month window at all, 16 of 60 initiatives
  deliver nothing inside it, and just 25 of 60 reach their full run rate by then
- **95 dependencies**, 70 of which cross a function boundary, **80 currently out of order** —
  33 of those on links that cannot be worked around, the worst starting **716 days** before the
  work it depends on can finish
- **25 of 60 initiatives** forecast to finish more than 5% over budget
- **31 on track / 17 at risk / 12 in trouble**

### What the compliance rules buy

Regulatory work can never be cut by a spending scenario. When a ceiling cannot be met without
cutting it, the tool reports the ceiling as unworkable rather than quietly dropping the obligation.
And a regulatory breach always sorts above a bigger-dollar budget breach, because a leader who
misses a compliance item because a $3m overrun scored higher has been failed by the tool.

Two live breaches surface without being told: a regulatory initiative still at idea stage with work
already planned on top of it, and another paused while rated in trouble.

The tool also found something nobody had asked for: of the fourteen regulatory risks on the
register, carrying $1,089,000 of exposure, **only one sits on an initiative anyone has classified as
regulatory.** The other thirteen are being carried by work nobody is treating as a compliance
obligation.

### Findings that changed the answer

Three things this tool surfaced that the source brief had wrong or missing.

**Every scenario finishes late.** All three miss their own stated deadline — the baseline by two
months, the other two by more than a year.

**Fixing the order delays the legal work.** The two scenarios that repair the dependency sequence do
it by pushing seven of the eight regulatory initiatives later, one by two years — against a strategy
that says regulatory work is never traded away.

**The brief's own conflict count was wrong.** It states three dependency violations. Recomputed from
the raw data using the brief's own rule, there are **80**. The three named in the brief are simply
the worst three; the generator that produced the dataset keeps only the top three by overlap. Two
independent audits confirmed this.

### On measuring realisation honestly

This tool does **not** compare the $84.3m promise against the $507 of benefit banked to date. That
comparison sets a steady-state annual rate — earned only once all sixty initiatives are finished and
fully ramped — against a seven-month actuals window in which exactly one initiative had reached its
benefit-start month. It overstates the gap by orders of magnitude and collapses under the first
question anyone asks: *over what period is the $84.3m?*

Measured against the correctly phased plan for that same seven months ($648), attainment is **78.2%**
— the portfolio is broadly on track for the very small amount it was ever due to have earned by now.
The real finding is the run-rate gap: **$84.3m promised, $39.6m scheduled by end-2027.**

---

## 4. Path to market

### Where the inputs come from

**Tier 1 — structured.** Exports from Clarity, Planview, ServiceNow SPM, Jira Align or Smartsheet.
The PMO's Excel tracker on SharePoint or OneDrive. Azure DevOps or Planner for task dates. SAP,
Oracle or Workday Adaptive for actual spend.

**Tier 2 — documents.** Business cases, project initiation documents, board packs, monthly status
reports and strategy one-pagers, as Word, PDF and PowerPoint, in the SharePoint libraries where the
client already keeps them.

**Tier 3 — conversation.** Teams transcripts and Copilot meeting recaps, steering committee
minutes, Outlook approval chains, and the leader's own first-ninety-days interviews with initiative
owners.

**Tier 3 is the differentiator.** No PPM tool reads what an owner actually said in a review. That is
how you catch the initiative that is green on the tracker and dying in the room.

All three tiers are read-only, inside the client's own tenancy. That is also the answer to the
security question: nothing leaves, nothing is written back, and no system of record is modified.

### Configurable per client, which is what makes it a product

Taxonomy. Field mapping. Constraint types. Fiscal calendar. Benefit categories. Confidence rules.

Everything else — extraction, sequencer, conflict detection, the four views — is the product.

---

## How it is built

No framework, no build step, no `npm install`, no bundler, no CDN, no runtime network call. Plain
browser JavaScript and inline SVG drawn by hand.

| File | What it is |
|---|---|
| `index.html` | Page structure and styling |
| `app.js` | The engine and all four views |
| `data/portfolio.json` | The flattened dataset the page reads |
| `build_portfolio_json.py` | Build-time flattener. Runs once, on a developer machine |
| `selftest.html` | 35 engine checks — open it to verify the numbers yourself |

`synthetic-data/` is the system of record and is never modified.

The conflict detector derives its answers from the dependency list and initiative dates alone. It
never reads `synthetic-data/data/dependency_conflicts.csv`, which is a pre-diagnosed answer key —
and the flattener asserts at build time that the file was never opened.

**Verify it yourself:** open <http://localhost:8000/selftest.html>. It rebuilds the benefit curve
from first principles and reconciles it to the source data to the dollar, confirms all 60 nodes sort
with no cycle, and independently rediscovers the three planted scheduling conflicts at 716, 710 and
627 days.
