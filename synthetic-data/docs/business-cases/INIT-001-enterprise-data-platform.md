# Enterprise Data Platform (Lakehouse) Build — Closure Summary

**INIT-001** | Technology | CIO sponsored | Lead: Rafael Farouk
**This document was originally the business case. It has been repurposed as the closure
summary because nobody wrote a separate one.** Original case dated Oct 2025; closure
sections added 20 July 2026.

---

## Original case (Oct 2025, unedited)

### Why

Harbourline holds customer, product, supplier and asset data across four ERPs, three HR
systems, eleven WMS instances and an unknown number of spreadsheets. Every analytical
question takes weeks because the first three of those weeks are spent arguing about which
number is right.

The lakehouse gives us one governed place where data lands, is conformed, and can be read by
downstream initiatives without each one building its own extract.

### Benefit — read this carefully

**This initiative has almost no standalone benefit.** The stated figure is $70k annually,
which is decommissioning a handful of legacy reporting servers. That is the honest number.

The *actual* value of this platform is that a large part of the rest of the portfolio cannot
proceed without it, or can only proceed by building something worse and throwing it away
later. At the time of writing the initiatives that consume this platform include:

- Customer Segmentation & Pricing Analytics — cannot build elasticity models without the
  conformed customer domain
- S&OP Process Standardisation — needs harmonised demand and supply history
- Group Planning & Forecasting Rebuild — reads its actuals layer directly from here
- Inventory Optimisation — better with it, technically possible without it
- Data Governance & Quality Framework — there is literally nothing to govern until this exists

Benefit type is therefore recorded as **Capability**, and value confidence as **Low**, which
looks bad on a portfolio dashboard and has caused this initiative to be questioned twice.
Both times the answer has been the same: cut this and you do not save $895k, you delay about
$8m of downstream value.

> I would ask whoever inherits the portfolio to look at how enabling initiatives are scored.
> A dashboard that ranks on benefit-to-cost ratio will always rank this last, and will always
> be wrong. — RF

### Cost

$895,000. Split roughly 60/40 capex/opex.

---

## Closure summary (added July 2026)

**Completed 11 July 2026.** Delivered essentially on plan — total actual spend $908k against
$895k budget, a 1.5% overrun which was absorbed within programme contingency.

Milestones: all five complete. The only slip of note was design complete, seven days late.

What landed:
- Ingestion for 14 source systems (target was 12 — two added in flight at no extra cost)
- Conformed customer and product domains
- Governed access model, integrated with the new IAM platform
- Self-service semantic layer

What did **not** land, and needs picking up by someone:
- The supplier domain was descoped in February to protect the date. Third-Party & Supplier
  Risk Management were told and have planned around it, but Master Data Management have not
  formally picked it up and I am not confident it is owned.
- Data quality rules are implemented but not *governed* — that is the Data Governance
  initiative's job and it has not started yet. Until it does, the platform is trustworthy
  because the build team is watching it, not because there is a control.

### Lessons

1. Building the enabler first was right and I would do it again. It was also unrewarding —
   this initiative was Amber on the portfolio dashboard for four months purely because its
   benefit-to-cost ratio looked poor next to a procurement saving.
2. Descoping the supplier domain was the right call for the date and the wrong call for the
   portfolio. It has created an orphan.
3. Downstream initiatives assumed availability dates from a plan they never read. Three of
   them built their own extracts anyway.
