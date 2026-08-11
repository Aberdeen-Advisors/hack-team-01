# Cloud Migration Wave 2 — Production Workloads (INIT-006)

Function: Technology
Sponsor: Chief Digital Officer
Lead: Gregor Rahman
Doc status: **Approved** (IC, 15 January 2026)

## Purpose

Move the remaining production workloads out of the two owned data centres and into the group
cloud landing zone. Wave 1 (non-production) proved the migration pattern. Wave 2 is the one
that actually delivers the saving, because it is the wave that lets us exit the Hartlepool
data centre lease and decommission the associated hardware refresh.

## Benefit

$1.75m annually at full run rate. Components:

- Data centre lease exit and facilities cost — the largest single component
- Avoided hardware refresh (the 2027 refresh cycle does not happen)
- Reduced managed service fees under the renegotiated contract
- Some efficiency from autoscaling non-peak workloads, which we have deliberately excluded
  from the number because we cannot evidence it yet

Confidence: **Low**. Not because we doubt the lease exit — that is contractual and certain —
but because the timing of the exit is tied to the migration completing, and the migration
date has moved twice. The saving is all-or-nothing on the lease break date. If we miss the
break clause we carry another twelve months of lease.

## Sequencing — please read this

Wave 2 obviously cannot complete before Wave 1. That is stated everywhere and understood.

What is **not** understood, and what I have been trying to get onto the portfolio agenda since
April, is that the Wave 1 plan of record now runs to **September 2027**, while Wave 2 is
currently shown in the portfolio as starting February 2026 and finishing March 2027.

Wave 2 is therefore scheduled to *finish six months before its predecessor finishes*.

This is not a real plan. What has actually happened is that Wave 1's scope grew (it absorbed
the DR environment and the test data management work) and its end date moved right, but
nobody moved Wave 2. The two plans are maintained by different people in different tools.

We are proceeding on the basis that Wave 2 can start migrating the *lower-tier* production
workloads before Wave 1 fully completes, because the pattern is proven for those. But the
tier-1 workloads genuinely cannot move until Wave 1 is done, and roughly 60% of the benefit
sits in tier 1.

Other dependencies:
- Cyber Security Uplift must have extended endpoint and SIEM coverage to the cloud estate
  before any production workload moves. This is a hard control gate, not a preference —
  the CISO has been clear. Good news is that work is well advanced.
- The mainframe order-management decommission is downstream of us; they cannot run the
  replacement order service until we have migrated the platform it sits on.

## Financials

Budget $1,635,000. Forecast at completion $1,785,000 — we are running about 9% over,
driven by extended parallel-running costs while both estates are live.

## Milestones

| Milestone | Baseline | Forecast | Status |
|---|---|---|---|
| Mobilisation & scope sign-off | 21 Feb 2026 | 26 Feb 2026 | Complete |
| Design complete | 30 May 2026 | 30 May 2026 | Complete |
| Stage gate 2 — ready for test | 04 Nov 2026 | 04 Nov 2026 | Not started |
| Go-live | 21 Jan 2027 | 25 Feb 2027 | Not started |
| Benefit checkpoint 1 | 02 Mar 2027 | 07 Mar 2027 | Not started |

## Risks

1. Environment availability constrains parallel testing — the shared pre-prod environment is
   contended with three other initiatives.
2. Lease break clause is missed and we carry twelve more months.
3. Vendor resource ramp on the migration partner is behind contracted numbers.

## Ask

A single owner for the Wave 1 / Wave 2 sequence. At the moment Wave 1 and Wave 2 are
separately governed and the joint plan does not exist anywhere.
