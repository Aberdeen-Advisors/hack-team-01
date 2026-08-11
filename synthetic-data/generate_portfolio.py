#!/usr/bin/env python3
"""
generate_portfolio.py — synthetic transformation-portfolio dataset generator.

Builds a realistic, internally-consistent portfolio of 60 transformation
initiatives for the fictional client "Harbourline Group" (a mid-cap industrial
services and distribution business). The output is raw material for a tool that
turns scattered plans into (1) a sequenced roadmap, (2) a dependency view,
(3) scenario comparison, and (4) a value-realization plan.

The 60 initiatives span EIGHT business functions — Technology, Operations,
Supply Chain, Finance, HR / People, Growth / Commercial, Cost Reduction and
Risk & Compliance — because the interesting sequencing problems in a real
transformation are the ones that cross functional boundaries. A large share of
the dependency edges are deliberately cross-function for that reason.

Two grouping columns are written, and they mean different things:
    function  — WHO owns it   (the eight functions above)
    pillar    — WHY we do it  (value theme: Grow / Run Better / Cost Out / Protect)

Everything is deterministic: the same --seed always produces identical files.
Standard library only — no faker, no numpy, no pandas. Runs on any Python 3.8+.

Files written into <outdir>/data/ :
    initiatives.csv / initiatives.json   the 60 initiatives, one row each
    dependencies.csv                     acyclic dependency edges between them
    dependency_conflicts.csv             a few deliberate sequencing problems
    milestones.csv                       3-6 milestones per initiative
    risks.csv                            risk register
    issues.csv                           issue log
    resources.csv                        role supply vs demand, by month
    burn.csv                             monthly spend, 24 months from 2026-01
    benefits.csv                         monthly benefit plan vs actual
    scenarios.json                       three scenario definitions (inputs only)

Usage:
    python3 generate_portfolio.py                       # 60 initiatives, seed 42
    python3 generate_portfolio.py --seed 7 --count 40
    python3 generate_portfolio.py --outdir ./somewhere
    python3 generate_portfolio.py --help

A note on "today": the dataset is pinned to 2026-08-11. Actuals therefore exist
up to and including 2026-07 and are blank from 2026-08 onwards. Change --today
if you need to move the clock.
"""

import argparse
import csv
import json
import math
import os
import random
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# 1. Reference data — the vocabulary the generator draws from
# ---------------------------------------------------------------------------

FUNCTIONS = [
    "Technology", "Operations", "Supply Chain", "Finance",
    "HR / People", "Growth / Commercial", "Cost Reduction", "Risk & Compliance",
]

VALUE_THEMES = ["Grow", "Run Better", "Cost Out", "Protect"]

# The 60 initiatives are hand-written rather than randomly assembled, so the
# names read like a real portfolio and are recognisably functional. Each tuple:
#   (name, function, value_theme, wave, benefit_type, is_regulatory)
# "wave" is the natural sequencing tier (1 = foundational enabler, 4 = last).
# Dependencies are only ever drawn from a lower position in the topological
# order to a higher one, which is what guarantees the graph is acyclic.
CATALOGUE = [
    # --- Technology (10) --------------------------------------------------
    ("Enterprise Data Platform (Lakehouse) Build",      "Technology", "Run Better", 1, "Capability",     False),
    ("ERP Finance Module Consolidation",                "Technology", "Run Better", 2, "Cost Save",      False),
    ("API Gateway & Integration Layer",                 "Technology", "Run Better", 1, "Capability",     False),
    ("Identity & Access Management Modernisation",      "Technology", "Protect",    1, "Risk Reduction", True),
    ("Cloud Migration Wave 1 - Non-Production",         "Technology", "Cost Out",   1, "Cost Save",      False),
    ("Cloud Migration Wave 2 - Production Workloads",   "Technology", "Cost Out",   2, "Cost Save",      False),
    ("CRM Platform Replacement",                        "Technology", "Grow",       2, "Revenue Uplift", False),
    ("Master Data Management - Customer & Product",     "Technology", "Run Better", 2, "Capability",     False),
    ("Legacy Mainframe Decommission - Order Mgmt",      "Technology", "Cost Out",   3, "Cost Save",      False),
    ("Field Mobility App Rollout",                      "Technology", "Run Better", 3, "Cost Save",      False),
    # --- Operations (9) ---------------------------------------------------
    ("Field Service Route Optimisation",                "Operations", "Run Better", 3, "Cost Save",      False),
    ("Preventive Maintenance Programme Overhaul",       "Operations", "Run Better", 2, "Cost Avoidance", False),
    ("Contact Centre Operating Model Redesign",         "Operations", "Run Better", 3, "Cost Save",      False),
    ("Depot Consolidation - Northern Region",           "Operations", "Cost Out",   4, "Cost Save",      False),
    ("Robotic Process Automation Factory",              "Operations", "Run Better", 2, "Cost Save",      False),
    ("Quality Management System Harmonisation",         "Operations", "Protect",    2, "Risk Reduction", True),
    ("Health & Safety Digital Reporting",               "Operations", "Protect",    2, "Risk Reduction", True),
    ("Service Scheduling & Dispatch Standardisation",   "Operations", "Run Better", 3, "Cost Save",      False),
    ("Asset Utilisation & Fleet Telematics",            "Operations", "Cost Out",   2, "Cost Save",      False),
    # --- Supply Chain (8) -------------------------------------------------
    ("Supplier Rationalisation Wave 2",                 "Supply Chain", "Cost Out",   2, "Cost Save",      False),
    ("Distribution Network Redesign",                   "Supply Chain", "Cost Out",   3, "Cost Save",      False),
    ("S&OP Process Standardisation",                    "Supply Chain", "Run Better", 3, "Cost Save",      False),
    ("Inbound Freight Cost Reduction",                  "Supply Chain", "Cost Out",   2, "Cost Save",      False),
    ("Warehouse Automation Pilot",                      "Supply Chain", "Run Better", 3, "Cost Avoidance", False),
    ("Inventory Optimisation & Safety Stock Reset",     "Supply Chain", "Cost Out",   3, "Cost Save",      False),
    ("Warehouse Management System Upgrade",             "Supply Chain", "Run Better", 2, "Cost Save",      False),
    ("Packaging & Consumables Standardisation",         "Supply Chain", "Cost Out",   2, "Cost Save",      False),
    # --- Finance (7) ------------------------------------------------------
    ("Order-to-Cash Automation",                        "Finance", "Run Better", 2, "Cost Save",      False),
    ("Month-End Close Acceleration",                    "Finance", "Run Better", 2, "Cost Save",      False),
    ("Procurement Source-to-Pay Redesign",              "Finance", "Cost Out",   2, "Cost Save",      False),
    ("Finance Shared Services Centre Stand-Up",         "Finance", "Cost Out",   3, "Cost Save",      False),
    ("Working Capital - Payables Terms Harmonisation",  "Finance", "Cost Out",   2, "Cost Avoidance", False),
    ("Group Planning & Forecasting Rebuild (FP&A)",     "Finance", "Run Better", 3, "Capability",     False),
    ("Insurance Programme Restructure",                 "Finance", "Cost Out",   2, "Cost Avoidance", False),
    # --- HR / People (7) --------------------------------------------------
    ("HRIS Consolidation to Workday",                   "HR / People", "Run Better", 2, "Cost Save",      False),
    ("Frontline Hiring Funnel Redesign",                "HR / People", "Run Better", 2, "Cost Avoidance", False),
    ("Manager Capability Programme",                    "HR / People", "Run Better", 3, "Capability",     False),
    ("Shared Services HR Operating Model",              "HR / People", "Cost Out",   3, "Cost Save",      False),
    ("Organisational Delayering & Span of Control",     "HR / People", "Cost Out",   2, "Cost Save",      False),
    ("Overtime & Absence Management",                   "HR / People", "Cost Out",   2, "Cost Save",      False),
    ("Contractor to Permanent Conversion",              "HR / People", "Cost Out",   2, "Cost Save",      False),
    # --- Growth / Commercial (8) ------------------------------------------
    ("Customer Segmentation & Pricing Analytics",       "Growth / Commercial", "Grow",       2, "Revenue Uplift", False),
    ("E-Commerce Channel Launch",                       "Growth / Commercial", "Grow",       3, "Revenue Uplift", False),
    ("Key Account Management Programme",                "Growth / Commercial", "Grow",       2, "Revenue Uplift", False),
    ("New Market Entry - Nordics",                      "Growth / Commercial", "Grow",       4, "Revenue Uplift", False),
    ("Aftermarket Services Proposition",                "Growth / Commercial", "Grow",       3, "Revenue Uplift", False),
    ("Subscription Maintenance Offering",               "Growth / Commercial", "Grow",       4, "Revenue Uplift", False),
    ("Bid & Tender Win-Rate Improvement",               "Growth / Commercial", "Grow",       2, "Revenue Uplift", False),
    ("Customer Self-Service Portal",                    "Growth / Commercial", "Run Better", 3, "Cost Save",      False),
    # --- Cost Reduction (6) -----------------------------------------------
    ("Indirect Spend Category Reset",                   "Cost Reduction", "Cost Out", 1, "Cost Save",      False),
    ("Real Estate Footprint Rationalisation",           "Cost Reduction", "Cost Out", 3, "Cost Save",      False),
    ("IT Application Portfolio Rationalisation",        "Cost Reduction", "Cost Out", 3, "Cost Save",      False),
    ("Telecoms & Connectivity Renegotiation",           "Cost Reduction", "Cost Out", 1, "Cost Save",      False),
    ("Energy Efficiency & Utilities Programme",         "Cost Reduction", "Cost Out", 2, "Cost Avoidance", False),
    ("Third-Party Advisory Spend Control",              "Cost Reduction", "Cost Out", 1, "Cost Save",      False),
    # --- Risk & Compliance (5) --------------------------------------------
    ("SOX Control Remediation",                         "Risk & Compliance", "Protect", 2, "Risk Reduction", True),
    ("Data Privacy Programme (GDPR/CCPA)",              "Risk & Compliance", "Protect", 2, "Risk Reduction", True),
    ("Cyber Security Uplift - Endpoint & SIEM",         "Risk & Compliance", "Protect", 1, "Risk Reduction", True),
    ("Data Governance & Quality Framework",             "Risk & Compliance", "Protect", 2, "Risk Reduction", True),
    ("Third-Party & Supplier Risk Management",          "Risk & Compliance", "Protect", 3, "Risk Reduction", True),
]

# Initiatives that lots of other things sensibly wait for. Used to bias the
# dependency generator so the graph looks like a real programme, not noise.
ENABLER_IDS = ["INIT-001", "INIT-002", "INIT-003", "INIT-004", "INIT-005", "INIT-008"]

# Hand-written cross-function dependencies. These are the edges that make the
# dependency view worth looking at: supply chain waiting on the data platform,
# shared services waiting on the HR operating model, and so on.
#
# Every entry goes from a LOWER wave to a HIGHER wave, which keeps the graph
# acyclic no matter how the dates fall. The generator asserts this.
#   (from_id, to_id, dependency_type, criticality, lag_days, note)
SEEDED_EDGES = [
    # --- The data platform feeds analytics work in four different functions
    ("INIT-001", "INIT-022", "Data", "Hard", 30,
     "S&OP standardisation consumes harmonised demand and supply history from the lakehouse."),
    ("INIT-001", "INIT-042", "Data", "Hard", 0,
     "Segmentation and price elasticity models cannot be built before the customer data domain lands."),
    ("INIT-001", "INIT-033", "Data", "Hard", 45,
     "The FP&A rebuild reads its actuals layer directly from the lakehouse."),
    ("INIT-001", "INIT-025", "Data", "Soft", 30,
     "Inventory optimisation is materially better with lakehouse history, but could start on extracts."),
    ("INIT-001", "INIT-059", "Technical Enabler", "Hard", 0,
     "Data governance controls are applied to the lakehouse; there is nothing to govern before it exists."),
    # --- ERP is the spine for finance and order management
    ("INIT-002", "INIT-031", "Technical Enabler", "Hard", 60,
     "The shared service centre operates on the consolidated finance module, not the old ledgers."),
    ("INIT-002", "INIT-033", "Data", "Hard", 30,
     "The forecasting rebuild depends on the consolidated chart of accounts."),
    ("INIT-002", "INIT-009", "Finish-to-Start", "Hard", 30,
     "Order management cannot leave the mainframe until finance postings are served by the ERP."),
    # --- Integration and identity foundations
    ("INIT-003", "INIT-043", "Technical Enabler", "Hard", 0,
     "The e-commerce channel calls pricing and stock through the API layer."),
    ("INIT-003", "INIT-049", "Technical Enabler", "Soft", 14,
     "Self-service portal services are exposed through the gateway."),
    ("INIT-004", "INIT-057", "Technical Enabler", "Hard", 0,
     "Privacy controls (consent, subject access, least privilege) are built on the new IAM stack."),
    ("INIT-004", "INIT-056", "Technical Enabler", "Hard", 30,
     "SOX access-control remediation depends on the modernised role model."),
    ("INIT-004", "INIT-010", "Technical Enabler", "Soft", 30,
     "Engineers authenticate to the mobility app through the new identity platform."),
    ("INIT-005", "INIT-006", "Finish-to-Start", "Hard", 30,
     "Production workloads only move once the non-production migration pattern is proven."),
    ("INIT-005", "INIT-052", "Technical Enabler", "Soft", 60,
     "Application rationalisation decisions follow the cloud landing-zone standards."),
    ("INIT-006", "INIT-009", "Technical Enabler", "Hard", 0,
     "The replacement order service runs on the migrated production platform."),
    # --- Master data and CRM feed the commercial and supply chain work
    ("INIT-008", "INIT-025", "Data", "Hard", 0,
     "Safety stock cannot be reset while the same product exists under four part numbers."),
    ("INIT-008", "INIT-046", "Data", "Soft", 30,
     "The aftermarket proposition needs a single view of installed base by customer."),
    ("INIT-008", "INIT-060", "Data", "Soft", 30,
     "Third-party risk scoring depends on a deduplicated supplier master."),
    ("INIT-007", "INIT-046", "Technical Enabler", "Hard", 30,
     "Aftermarket quoting and entitlement run in the new CRM."),
    ("INIT-007", "INIT-049", "Technical Enabler", "Hard", 0,
     "The self-service portal is a front end onto CRM case and asset data."),
    ("INIT-042", "INIT-046", "Data", "Soft", 30,
     "Aftermarket price points are set using the new segmentation and elasticity model."),
    ("INIT-044", "INIT-045", "Finish-to-Start", "Soft", 45,
     "Nordics entry leads with the named key accounts identified by the KAM programme."),
    # --- HR gates operating-model change in three other functions
    ("INIT-039", "INIT-038", "Finish-to-Start", "Hard", 30,
     "Spans and layers must be agreed before the HR shared service model is designed around them."),
    ("INIT-039", "INIT-031", "Finish-to-Start", "Hard", 45,
     "Finance SSC design assumes the delayered structure; building it first locks in the old shape."),
    ("INIT-039", "INIT-013", "Finish-to-Start", "Soft", 30,
     "The contact centre redesign inherits the new span-of-control standard."),
    ("INIT-039", "INIT-014", "Finish-to-Start", "Soft", 60,
     "Depot closures cannot be announced before the management structure is settled."),
    ("INIT-035", "INIT-038", "Technical Enabler", "Hard", 60,
     "HR shared services runs on Workday case management; there is no platform before it."),
    ("INIT-035", "INIT-037", "Data", "Soft", 30,
     "Manager capability targeting uses Workday performance and org data."),
    ("INIT-035", "INIT-031", "Data", "Soft", 45,
     "The Finance SSC resourcing model draws establishment data from the consolidated HRIS."),
    ("INIT-040", "INIT-018", "Data", "Soft", 0,
     "Dispatch standardisation uses the new absence and availability data to plan shifts."),
    ("INIT-036", "INIT-013", "Finish-to-Start", "Soft", 30,
     "The contact centre redesign depends on the reworked frontline hiring funnel to staff it."),
    ("INIT-041", "INIT-051", "Resource", "Soft", 0,
     "Both draw on the same small people-and-property change team."),
    # --- Procurement, supply chain and risk chain together
    ("INIT-050", "INIT-020", "Finish-to-Start", "Hard", 30,
     "Category strategies from the indirect reset set the shortlist for supplier rationalisation."),
    ("INIT-050", "INIT-030", "Finish-to-Start", "Soft", 30,
     "The category reset defines the requirements the source-to-pay redesign must implement."),
    ("INIT-055", "INIT-030", "Data", "Soft", 0,
     "Advisory spend approval rules are encoded into the new source-to-pay workflow."),
    ("INIT-030", "INIT-060", "Data", "Hard", 30,
     "Supplier risk management consumes the new vendor master and onboarding workflow."),
    ("INIT-020", "INIT-060", "Data", "Soft", 0,
     "Risk scoring is applied to the rationalised supplier base, not the old tail."),
    ("INIT-034", "INIT-060", "Data", "Soft", 30,
     "The restructured insurance programme sets the risk-transfer thresholds the framework applies."),
    ("INIT-026", "INIT-024", "Technical Enabler", "Hard", 60,
     "Automation equipment integrates with the upgraded WMS; the current version has no API."),
    ("INIT-026", "INIT-021", "Finish-to-Start", "Hard", 30,
     "Network redesign moves stock between sites, which the upgraded WMS must already support."),
    ("INIT-027", "INIT-024", "Finish-to-Start", "Hard", 30,
     "Automation cannot be commissioned until pack sizes and pallet patterns are standardised."),
    ("INIT-023", "INIT-021", "Data", "Soft", 0,
     "The network redesign reuses the lane cost model produced by the freight renegotiation."),
    ("INIT-021", "INIT-014", "Finish-to-Start", "Hard", 60,
     "Depots cannot be closed until the redesigned network has absorbed their volume."),
    ("INIT-021", "INIT-045", "Finish-to-Start", "Soft", 45,
     "Nordics entry depends on the redesigned distribution footprint reaching the region."),
    ("INIT-019", "INIT-011", "Data", "Hard", 0,
     "Route optimisation is fed by telematics location and utilisation data."),
    # --- Operations enables commercial propositions
    ("INIT-012", "INIT-047", "Technical Enabler", "Hard", 60,
     "The subscription maintenance offer is only sellable once preventive maintenance is standardised."),
    ("INIT-046", "INIT-047", "Finish-to-Start", "Hard", 30,
     "Subscription pricing is built on the aftermarket proposition's service catalogue."),
    ("INIT-015", "INIT-031", "Finish-to-Start", "Hard", 30,
     "The SSC target headcount assumes RPA has already removed the transactional volume."),
    ("INIT-015", "INIT-013", "Technical Enabler", "Soft", 30,
     "The contact centre redesign assumes RPA is handling back-office case volume."),
    # --- Compliance gates finance and commercial
    ("INIT-056", "INIT-031", "Finish-to-Start", "Hard", 30,
     "Control remediation must land before processes transfer, or the findings transfer with them."),
    ("INIT-058", "INIT-006", "Finish-to-Start", "Hard", 0,
     "Production workloads only migrate once endpoint and SIEM coverage extends to the cloud estate."),
    ("INIT-058", "INIT-043", "Technical Enabler", "Hard", 30,
     "A public-facing sales channel requires the uplifted monitoring and response baseline."),
    ("INIT-059", "INIT-033", "Data", "Hard", 0,
     "Forecasting will not be trusted without the data quality framework behind it."),
    ("INIT-059", "INIT-022", "Data", "Soft", 30,
     "S&OP inputs are certified through the governance framework."),
    ("INIT-028", "INIT-031", "Finish-to-Start", "Soft", 30,
     "Order-to-cash is the first process to transfer into the SSC, so it must be automated first."),
    ("INIT-029", "INIT-033", "Data", "Soft", 30,
     "A faster close is what makes a monthly rolling forecast possible at all."),
    # --- Cost programmes share the same commercial team
    ("INIT-053", "INIT-052", "Resource", "Soft", 0,
     "The same commercial team renegotiates telecoms and rationalises the application estate."),
]

FIRST_NAMES = [
    "Amara", "Callum", "Priya", "Tomas", "Freya", "Rohan", "Isla", "Marcus",
    "Sinead", "Devon", "Anika", "Gregor", "Lena", "Idris", "Nuala", "Bjorn",
    "Yusuf", "Clara", "Hamish", "Zoya", "Erik", "Maeve", "Olu", "Tessa",
    "Rafael", "Nadia", "Struan", "Beatriz", "Kofi", "Elise",
]
LAST_NAMES = [
    "Okonkwo", "Fraser", "Nair", "Vlach", "Lindqvist", "Mehta", "Buchanan",
    "Reinholt", "Doherty", "Achebe", "Kaur", "Sandison", "Novak", "Rahman",
    "Kilbride", "Halvorsen", "Demir", "Whitfield", "Menzies", "Petrova",
    "Arnesen", "Corrigan", "Adeyemi", "Bramley", "Mendes", "Farouk",
    "MacAulay", "Ferreira", "Boateng", "Duval",
]

# Sponsorship follows the function, the way it would in a real governance model.
FUNCTION_SPONSORS = {
    "Technology":          ["Chief Information Officer", "Chief Digital Officer"],
    "Operations":          ["Group COO", "MD Industrial Services"],
    "Supply Chain":        ["Group Supply Chain Director", "MD Distribution & Logistics"],
    "Finance":             ["Group CFO", "Group Financial Controller"],
    "HR / People":         ["Group HR Director", "Group COO"],
    "Growth / Commercial": ["Chief Commercial Officer", "MD Energy Solutions"],
    "Cost Reduction":      ["Group CFO", "Group Procurement Director"],
    "Risk & Compliance":   ["Chief Risk Officer", "Group General Counsel"],
}

BUSINESS_UNITS = [
    "Industrial Services", "Distribution & Logistics", "Energy Solutions",
    "Corporate Functions", "Digital & Customer",
]

REGIONS = ["UK & Ireland", "Nordics", "DACH", "Benelux", "Group-wide", "North America"]

# The resource pool spans the same functions as the portfolio, so contention
# shows up between (say) supply chain analysts and finance transformation leads,
# not just between technologists.
ROLES = [
    "Programme Manager", "Business Analyst", "Change Manager", "Data Engineer",
    "Solution Architect", "Integration Engineer", "ERP Consultant", "Test Lead",
    "Process Engineer", "Supply Chain Analyst", "Finance Transformation Lead",
    "HR Business Partner", "Procurement Category Manager", "Compliance Specialist",
    "Commercial Analyst",
]

# Which roles each function pulls on first.
FUNCTION_ROLES = {
    "Technology":          ["Solution Architect", "Data Engineer", "Integration Engineer", "ERP Consultant", "Test Lead"],
    "Operations":          ["Process Engineer", "Business Analyst", "Change Manager", "Programme Manager"],
    "Supply Chain":        ["Supply Chain Analyst", "Process Engineer", "Business Analyst", "Data Engineer"],
    "Finance":             ["Finance Transformation Lead", "ERP Consultant", "Business Analyst", "Process Engineer"],
    "HR / People":         ["HR Business Partner", "Change Manager", "Business Analyst", "Programme Manager"],
    "Growth / Commercial": ["Commercial Analyst", "Business Analyst", "Data Engineer", "Change Manager"],
    "Cost Reduction":      ["Procurement Category Manager", "Commercial Analyst", "Business Analyst"],
    "Risk & Compliance":   ["Compliance Specialist", "Solution Architect", "Business Analyst", "Data Engineer"],
}

SYSTEMS = [
    "SAP ECC", "SAP S/4HANA", "SAP IBP", "Salesforce", "Workday", "Oracle EBS",
    "Snowflake", "Azure", "AWS", "ServiceNow", "Coupa", "Manhattan WMS",
    "Dynamics 365", "Mainframe OMS", "Tableau", "MuleSoft", "Okta", "Blackline",
    "OneTrust", "Kinaxis", "Archer GRC", "Kronos",
]

TAG_POOL = [
    "quick-win", "foundational", "board-visible", "cross-function", "vendor-led",
    "people-impact", "customer-facing", "data-dependent", "site-based",
    "wave-1", "efficiency", "compliance", "automation", "commercial",
    "operating-model", "cash-release",
]

DEP_TYPES = [
    "Finish-to-Start", "Start-to-Start", "Finish-to-Finish",
    "Resource", "Data", "Technical Enabler",
]

RISK_CATEGORIES = [
    "Delivery", "Technical", "Change/Adoption", "Vendor",
    "Regulatory", "Financial", "Resource",
]

# Risk templates: (category, title, mitigation)
RISK_TEMPLATES = [
    ("Delivery", "Critical path compresses if design sign-off slips",
     "Weekly design authority; pre-book sign-off slots with sponsor"),
    ("Delivery", "Scope creep from business unit change requests",
     "Change control board; scope baselined and re-approved monthly"),
    ("Delivery", "Testing window overlaps with year-end freeze",
     "Negotiate early freeze exemption; shift regression to November"),
    ("Technical", "Legacy interfaces poorly documented",
     "Fund a discovery spike; engage original vendor for schema walkthrough"),
    ("Technical", "Data migration volumes exceed tested throughput",
     "Run full-volume rehearsal in pre-prod; add cutover contingency day"),
    ("Technical", "Environment availability constrains parallel testing",
     "Build second test environment; stagger test cycles"),
    ("Change/Adoption", "Frontline adoption below target after go-live",
     "Super-user network; adoption dashboard tied to manager objectives"),
    ("Change/Adoption", "Insufficient training capacity in peak season",
     "Move to blended e-learning; train-the-trainer in each depot"),
    ("Change/Adoption", "Union consultation extends implementation timeline",
     "Early engagement with employee representatives; phased site-by-site rollout"),
    ("Change/Adoption", "Line managers not equipped to lead the change",
     "Manager toolkit and briefing cascade ahead of each wave"),
    ("Vendor", "Vendor resource ramp slower than contracted",
     "Service credits in the SOW; escalate at monthly vendor governance"),
    ("Vendor", "Single-source dependency on niche implementation partner",
     "Knowledge transfer clauses; second supplier pre-qualified"),
    ("Vendor", "Licence pricing renegotiation lands above the business case",
     "Lock pricing at contract signature; cap uplift at CPI"),
    ("Regulatory", "Data residency requirements not met in target region",
     "Regional data enclave; legal review before cutover"),
    ("Regulatory", "Audit findings require rework of the control design",
     "Involve internal audit in design phase; pre-audit walkthrough"),
    ("Regulatory", "Control evidence not retained to the required standard",
     "Automate evidence capture; quarterly control self-assessment"),
    ("Financial", "Benefit case relies on headcount reductions not yet agreed",
     "Sponsor to confirm the headcount plan; hold benefit at Low confidence"),
    ("Financial", "FX movement erodes savings in non-GBP contracts",
     "Hedge material contracts; report benefits at constant currency"),
    ("Financial", "Capex approval deferred to the next budget cycle",
     "Phase the spend; seek bridge funding from the contingency pot"),
    ("Financial", "Savings double-counted with another initiative",
     "Benefit ownership matrix agreed with Finance; single booking point"),
    ("Resource", "Key SME shared across three concurrent initiatives",
     "Formal allocation agreement; backfill the BAU role"),
    ("Resource", "Data engineering demand exceeds the available pool",
     "Prioritisation forum; contract two additional engineers"),
    ("Resource", "Change manager vacancy unfilled for two months",
     "Interim contractor while permanent recruitment completes"),
    ("Resource", "Supply chain analyst capacity absorbed by peak trading",
     "Ring-fence project allocation; agree BAU cover with the site leads"),
]

ISSUE_TEMPLATES = [
    ("Design sign-off overdue with the business",
     "Business owners have not returned the signed design pack; the build team is idling."),
    ("Test environment unavailable",
     "The shared pre-production environment is locked by another programme's cutover rehearsal."),
    ("Data quality below migration threshold",
     "Master records are failing validation at a rate above the agreed tolerance."),
    ("Vendor invoice dispute blocking the next phase",
     "A commercial disagreement over change-request pricing has paused the statement of work."),
    ("Key resource resigned",
     "The lead architect is leaving and the handover plan is not yet agreed."),
    ("Integration defect in UAT",
     "A high-severity defect on the order interface is blocking end-to-end test completion."),
    ("Scope disagreement between functions",
     "Two functions disagree on the target process; the decision is escalated to the steering committee."),
    ("Budget overspend against phase forecast",
     "Phase spend is running ahead of plan, driven by contractor day rates."),
    ("Training materials not signed off",
     "Localisation of training content is behind schedule for the non-UK sites."),
    ("Upstream dependency slipped",
     "An upstream initiative has moved its go-live, invalidating our start assumption."),
    ("Cutover window clashes with peak trading",
     "The proposed go-live falls inside the seasonal peak; operations have objected."),
    ("Access provisioning delays",
     "New joiners and vendor staff are waiting on system access and losing productive days."),
    ("Works council consultation not started",
     "Consultation in the DACH entities has not been initiated, putting the rollout date at risk."),
    ("Benefit baseline disputed by Finance",
     "Finance will not sign the baseline, so realised savings cannot yet be booked."),
]


# ---------------------------------------------------------------------------
# 2. Small date helpers (stdlib only — no dateutil)
# ---------------------------------------------------------------------------

def add_months(d, n):
    """Return date d shifted by n whole months, clamping the day if needed."""
    total = (d.year * 12 + (d.month - 1)) + n
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, days_in_month(year, month))
    return date(year, month, day)


def days_in_month(year, month):
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def month_key(d):
    """'2026-08' — the month label used across the time-series files."""
    return "%04d-%02d" % (d.year, d.month)


def month_index(d):
    """Absolute month number, so two months can be subtracted."""
    return d.year * 12 + (d.month - 1)


def quarter_of(d):
    return "%dQ%d" % (d.year, (d.month - 1) // 3 + 1)


def iso(d):
    return d.isoformat() if d else ""


# ---------------------------------------------------------------------------
# 3. Initiative generation
# ---------------------------------------------------------------------------

# Earliest and latest start date allowed per wave. Wave 1 is already well
# underway by "today"; wave 4 has barely been thought about.
WAVE_START_WINDOW = {
    1: (date(2025, 7, 1),  date(2026, 3, 1)),
    2: (date(2026, 1, 1),  date(2026, 10, 1)),
    3: (date(2026, 6, 1),  date(2027, 4, 1)),
    4: (date(2027, 1, 1),  date(2027, 10, 1)),
}

# How big initiatives in each function tend to be, and how capital-heavy.
FUNCTION_SCALE = {
    "Technology": 1.35, "Operations": 1.00, "Supply Chain": 1.05, "Finance": 0.80,
    "HR / People": 0.65, "Growth / Commercial": 0.85, "Cost Reduction": 0.70,
    "Risk & Compliance": 0.75,
}
FUNCTION_CAPEX_SHARE = {
    "Technology": (0.45, 0.75), "Operations": (0.20, 0.50), "Supply Chain": (0.25, 0.60),
    "Finance": (0.15, 0.40), "HR / People": (0.10, 0.30), "Growth / Commercial": (0.15, 0.40),
    "Cost Reduction": (0.05, 0.25), "Risk & Compliance": (0.10, 0.35),
}

FUNCTION_OPENERS = {
    "Technology": "Replace fragmented legacy tooling with a single supported platform",
    "Operations": "Standardise how the operation runs day to day across sites",
    "Supply Chain": "Take cost and variability out of the end-to-end supply chain",
    "Finance": "Simplify and automate the finance process landscape",
    "HR / People": "Change how the organisation is structured, staffed and led",
    "Growth / Commercial": "Open a route to revenue that the current commercial model does not serve",
    "Cost Reduction": "Take structural cost out of the base without damaging service",
    "Risk & Compliance": "Close known control gaps and bring residual risk back inside appetite",
}


def pick_date_between(rng, start, end):
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, max(span, 1)))


def make_person(rng):
    return "%s %s" % (rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))


def build_description(rng, name, function, benefit_type):
    """Two to three sentences of plausible initiative narrative."""
    middles = [
        "Delivery is phased by business unit so that lessons from the pilot site inform the wider rollout.",
        "The programme runs a discovery phase first, then design, build and a site-by-site deployment.",
        "A pilot in one region proves the operating model before the group-wide rollout is committed.",
        "Work is sequenced behind the foundational platform initiatives to avoid rework.",
        "The team works with the affected functions to agree the target-state process before build starts.",
        "Scope is deliberately held to one function in the first phase, with cross-function extension in phase two.",
    ]
    closers = {
        "Cost Save": "Benefits are tracked as run-rate savings validated jointly with Finance.",
        "Revenue Uplift": "Value is measured as incremental margin against a pre-agreed baseline.",
        "Cost Avoidance": "Value is booked as cost avoided versus the do-nothing forecast.",
        "Risk Reduction": "Value is expressed as reduced residual risk exposure rather than cash.",
        "Capability": "This is an enabling investment; value is realised through the initiatives it unlocks.",
    }
    return "%s through %s. %s %s" % (
        FUNCTION_OPENERS[function], name.lower(),
        rng.choice(middles), closers[benefit_type],
    )


def build_objective(rng, benefit_type):
    objectives = {
        "Cost Save": [
            "Deliver a sustainable reduction in run-rate operating cost",
            "Remove duplicated activity and consolidate onto one way of working",
            "Reduce third-party spend through consolidation and renegotiation",
        ],
        "Revenue Uplift": [
            "Grow incremental revenue from existing and new customers",
            "Improve win rate and average deal value in target segments",
            "Establish a new revenue stream with a repeatable commercial model",
        ],
        "Cost Avoidance": [
            "Avoid future cost that would otherwise be incurred under the current model",
            "Defer capital replacement through better asset utilisation",
        ],
        "Risk Reduction": [
            "Reduce residual risk exposure to within board-agreed appetite",
            "Meet regulatory obligations and close known audit findings",
        ],
        "Capability": [
            "Build a reusable capability that later initiatives depend on",
            "Establish the data and integration foundation for the wider portfolio",
        ],
    }
    return rng.choice(objectives[benefit_type])


def generate_initiatives(rng, count, today):
    """Create the initiative master records with internally-consistent numbers."""
    catalogue = CATALOGUE[:count]
    initiatives = []

    for idx, (name, function, theme, wave, benefit_type, regulatory) in enumerate(catalogue, start=1):
        iid = "INIT-%03d" % idx
        lo, hi = WAVE_START_WINDOW[wave]
        start = pick_date_between(rng, lo, hi)

        complexity = rng.randint(1, 5)
        # Bigger, more complex things take longer.
        duration = rng.randint(4, 10) + complexity * rng.randint(1, 3)
        duration = max(4, min(duration, 26))
        end = add_months(start, duration)

        # ---- schedule position relative to "today" ---------------------------
        if end <= today:
            position = "past"
        elif start > today:
            position = "future"
        else:
            position = "current"

        # ---- stage ------------------------------------------------------------
        if position == "past":
            stage = "Complete"
        elif position == "future":
            stage = rng.choices(["Idea", "Business Case", "Approved"], weights=[3, 4, 3])[0]
        else:
            stage = rng.choices(["In Flight", "At Risk", "Paused", "Approved"],
                                weights=[10, 4, 2, 1])[0]

        # ---- RAG ---------------------------------------------------------------
        if stage == "Complete":
            rag = rng.choices(["Green", "Amber"], weights=[8, 2])[0]
        elif stage == "At Risk":
            rag = rng.choices(["Red", "Amber"], weights=[7, 3])[0]
        elif stage == "Paused":
            rag = rng.choices(["Amber", "Red"], weights=[6, 4])[0]
        elif stage == "In Flight":
            rag = rng.choices(["Green", "Amber", "Red"], weights=[11, 6, 3])[0]
        else:  # Idea / Business Case / Approved, not yet started
            rag = rng.choices(["Green", "Amber"], weights=[9, 1])[0]

        # ---- percent complete ---------------------------------------------------
        if position == "past":
            pct = 100
        elif position == "future":
            pct = 0 if stage != "Approved" else rng.randint(0, 3)
        else:
            elapsed = (today - start).days / max((end - start).days, 1)
            # Red initiatives are behind their elapsed time; green track it.
            drag = {"Green": rng.uniform(0.94, 1.04),
                    "Amber": rng.uniform(0.78, 0.95),
                    "Red": rng.uniform(0.50, 0.78)}[rag]
            pct = int(round(max(1.0, min(97.0, elapsed * 100 * drag))))

        # ---- money ---------------------------------------------------------------
        base = (120_000 + complexity * 260_000 + duration * 55_000) * FUNCTION_SCALE[function]
        total_budget = int(round(base * rng.uniform(0.7, 1.45) / 5_000) * 5_000)

        lo_cap, hi_cap = FUNCTION_CAPEX_SHARE[function]
        capex = int(round(total_budget * rng.uniform(lo_cap, hi_cap) / 1_000) * 1_000)
        opex = total_budget - capex

        # Spend tracks completion, with noise. Reds and a deliberate slice of
        # ambers burn faster than they deliver, so the burn view has content.
        burn_bias = {"Green": rng.uniform(0.92, 1.06),
                     "Amber": rng.uniform(1.02, 1.22),
                     "Red": rng.uniform(1.15, 1.55)}[rag]
        spend_to_date = int(total_budget * (pct / 100.0) * burn_bias)
        spend_to_date = max(0, min(spend_to_date, int(total_budget * 1.6)))

        # Forecast at completion: overrun for reds and a chunk of ambers.
        if rag == "Red":
            overrun = rng.uniform(1.10, 1.45)
        elif rag == "Amber":
            overrun = rng.uniform(0.99, 1.20)
        else:
            overrun = rng.uniform(0.93, 1.05)
        if stage == "Complete":
            overrun = min(overrun, rng.uniform(0.96, 1.12))
        forecast_at_completion = int(round(max(spend_to_date, total_budget * overrun) / 1_000) * 1_000)

        # ---- benefits --------------------------------------------------------------
        if benefit_type == "Capability":
            annual_benefit = int(round(total_budget * rng.uniform(0.05, 0.20) / 10_000) * 10_000)
        elif benefit_type == "Risk Reduction":
            annual_benefit = int(round(total_budget * rng.uniform(0.10, 0.35) / 10_000) * 10_000)
        elif benefit_type == "Revenue Uplift":
            annual_benefit = int(round(total_budget * rng.uniform(0.35, 1.30) / 10_000) * 10_000)
        else:  # Cost Save / Cost Avoidance
            annual_benefit = int(round(total_budget * rng.uniform(0.45, 1.60) / 10_000) * 10_000)

        # Value lands AFTER delivery: benefits start at (or just after) the end
        # of the initiative, then ramp to steady state.
        benefit_start_month = duration + rng.randint(0, 3)
        benefit_ramp_months = rng.choice([3, 4, 6, 6, 9, 12])

        value_confidence = rng.choices(["High", "Med", "Low"], weights=[3, 5, 3])[0]
        if benefit_type in ("Capability", "Risk Reduction"):
            value_confidence = rng.choices(["Med", "Low"], weights=[4, 6])[0]
        if rag == "Red":
            value_confidence = rng.choices(["Med", "Low"], weights=[3, 7])[0]

        # Simple 5-year NPV at 10%, benefits starting after delivery.
        discount = 0.10
        npv = -float(total_budget)
        for year in range(1, 6):
            realised = annual_benefit if year > (benefit_start_month / 12.0) else annual_benefit * 0.35
            npv += realised / ((1 + discount) ** year)
        npv = int(round(npv / 1_000) * 1_000)

        monthly_benefit = annual_benefit / 12.0 if annual_benefit else 0
        payback_months = (int(round(benefit_start_month + total_budget / monthly_benefit))
                          if monthly_benefit > 0 else 999)
        payback_months = min(payback_months, 240)

        run_rate_savings = (annual_benefit if benefit_type in ("Cost Save", "Cost Avoidance")
                            else int(annual_benefit * 0.35))

        # ---- scoring ----------------------------------------------------------------
        strategic_alignment = rng.randint(2, 5)
        if regulatory:
            strategic_alignment = max(strategic_alignment, 4)
        value_ratio = annual_benefit / max(total_budget, 1)
        raw = (strategic_alignment * 11) + min(value_ratio, 2.0) * 18 + (6 - complexity) * 4
        raw += {"High": 8, "Med": 3, "Low": -4}[value_confidence]
        raw += 12 if regulatory else 0
        raw += {"Green": 4, "Amber": 0, "Red": -5}[rag]
        priority_score = max(1, min(100, int(round(raw + rng.uniform(-6, 6)))))

        effort_fte = round(max(0.8, complexity * rng.uniform(0.9, 2.2) + duration * 0.09), 1)

        primary_role = rng.choice(FUNCTION_ROLES[function])

        initiatives.append({
            "initiative_id": iid,
            "name": name,
            "function": function,
            "pillar": theme,
            "owner": make_person(rng),
            "sponsor": rng.choice(FUNCTION_SPONSORS[function]),
            "business_unit": rng.choice(BUSINESS_UNITS),
            "description": build_description(rng, name, function, benefit_type),
            "objective": build_objective(rng, benefit_type),
            "start_date": iso(start),
            "end_date": iso(end),
            "duration_months": duration,
            "stage": stage,
            "rag_status": rag,
            "percent_complete": pct,
            "priority_score": priority_score,
            "strategic_alignment": strategic_alignment,
            "value_confidence": value_confidence,
            "complexity": complexity,
            "effort_fte": effort_fte,
            "capex": capex,
            "opex": opex,
            "total_budget": total_budget,
            "spend_to_date": spend_to_date,
            "forecast_at_completion": forecast_at_completion,
            "annual_benefit_target": annual_benefit,
            "benefit_type": benefit_type,
            "benefit_start_month": benefit_start_month,
            "benefit_ramp_months": benefit_ramp_months,
            "npv": npv,
            "payback_months": payback_months,
            "run_rate_savings": run_rate_savings,
            "resource_type_needed": primary_role,
            "key_systems": "; ".join(sorted(rng.sample(SYSTEMS, rng.randint(1, 3)))),
            "region": rng.choice(REGIONS),
            "is_regulatory": regulatory,
            "tags": "; ".join(sorted(rng.sample(TAG_POOL, rng.randint(2, 4)))),
            # private helpers, stripped before writing
            "_wave": wave,
            "_start": start,
            "_end": end,
        })

    return initiatives


# ---------------------------------------------------------------------------
# 4. Dependencies — acyclic by construction
# ---------------------------------------------------------------------------

def generate_dependencies(rng, initiatives):
    """
    Build a dependency DAG.

    Acyclicity is guaranteed structurally, not patched afterwards: the
    initiatives are sorted into a single topological order (by wave, then start
    date, then id) and an edge is only ever created from an EARLIER position to
    a LATER one. A cycle would need an edge pointing backwards, which this
    function cannot emit.

    Hand-written cross-function edges are laid down first, then the graph is
    topped up with generated edges that are biased towards crossing functions.
    """
    order = sorted(initiatives, key=lambda i: (i["_wave"], i["_start"], i["initiative_id"]))
    position = {ini["initiative_id"]: n for n, ini in enumerate(order)}
    by_id = {i["initiative_id"]: i for i in initiatives}
    known = set(by_id)

    edges = []
    seen = set()

    def add_edge(pred_id, succ_id, dtype, criticality, lag, notes):
        if pred_id not in known or succ_id not in known:
            return False
        if pred_id == succ_id:
            return False
        if (pred_id, succ_id) in seen:
            return False
        # The one invariant that keeps the graph acyclic.
        if position[pred_id] >= position[succ_id]:
            return False
        seen.add((pred_id, succ_id))
        edges.append({
            "from_initiative": pred_id,
            "to_initiative": succ_id,
            "dependency_type": dtype,
            "lag_days": lag,
            "criticality": criticality,
            "notes": notes,
        })
        return True

    # ---- 1. the hand-written cross-function backbone ----------------------
    # Every seeded edge runs from a lower wave to a higher one, so all of them
    # should be accepted. If one is rejected the catalogue and the seed list
    # have drifted apart, and we want to know loudly rather than silently lose
    # a dependency the docs refer to.
    rejected = [(p, s) for p, s, dt, c, l, n in SEEDED_EDGES
                if not add_edge(p, s, dt, c, l, n)]
    if rejected:
        raise SystemExit(
            "SEEDED_EDGES out of step with CATALOGUE — these could not be added "
            "(wrong direction, unknown id, or duplicate): %s" % rejected)

    # ---- 2. make sure nothing downstream is orphaned ----------------------
    def choose_predecessor(succ, n):
        """Weighted pick from everything earlier in the topological order."""
        candidates = order[:n]
        weights = []
        for cand in candidates:
            w = 1.0
            if cand["initiative_id"] in ENABLER_IDS:
                w += 3.5
            # Cross-function edges are the interesting ones, so favour them.
            if cand["function"] != succ["function"]:
                w += 2.0
            else:
                w += 0.8
            if cand["_wave"] == succ["_wave"] - 1:
                w += 2.0
            # Prefer near neighbours over very distant ancestors.
            w += 1.5 / (1 + (n - position[cand["initiative_id"]]) / 8.0)
            weights.append(w)
        return rng.choices(candidates, weights=weights)[0]

    def describe(pred, succ, dtype):
        return {
            "Technical Enabler": "%s cannot be built until the capability delivered by %s is available."
                                 % (succ["name"], pred["name"]),
            "Data": "%s consumes data produced by %s." % (succ["name"], pred["name"]),
            "Resource": "Shared %s capacity — the same team delivers both."
                        % succ["resource_type_needed"],
            "Finish-to-Start": "%s must complete before %s can start." % (pred["name"], succ["name"]),
            "Start-to-Start": "Both initiatives mobilise together to share the design phase.",
            "Finish-to-Finish": "Neither can be declared complete until both have landed.",
        }[dtype]

    def pick_type(pred, succ):
        if pred["initiative_id"] in ENABLER_IDS:
            return rng.choices(["Technical Enabler", "Data", "Finish-to-Start"],
                               weights=[5, 4, 3])[0]
        if pred["function"] != succ["function"]:
            return rng.choices(["Finish-to-Start", "Resource", "Data", "Start-to-Start"],
                               weights=[4, 3, 3, 2])[0]
        return rng.choices(DEP_TYPES, weights=[6, 3, 2, 3, 3, 3])[0]

    has_predecessor = {e["to_initiative"] for e in edges}
    for n, succ in enumerate(order):
        if n == 0 or succ["initiative_id"] in has_predecessor:
            continue
        for _ in range(12):
            pred = choose_predecessor(succ, n)
            dtype = pick_type(pred, succ)
            if add_edge(pred["initiative_id"], succ["initiative_id"], dtype,
                        rng.choices(["Hard", "Soft"], weights=[6, 4])[0],
                        rng.choice([0, 0, 0, 5, 10, 14, 20, 30, 45, 60]),
                        describe(pred, succ, dtype)):
                break

    # ---- 3. top up to a realistic edge count ------------------------------
    target = rng.randint(88, 104)
    attempts = 0
    while len(edges) < target and attempts < 2000:
        attempts += 1
        n = rng.randrange(1, len(order))
        succ = order[n]
        pred = choose_predecessor(succ, n)
        dtype = pick_type(pred, succ)
        add_edge(pred["initiative_id"], succ["initiative_id"], dtype,
                 rng.choices(["Hard", "Soft"], weights=[6, 4])[0],
                 rng.choice([0, 0, 0, 5, 10, 14, 20, 30, 45, 60]),
                 describe(pred, succ, dtype))

    # Stable, readable ordering in the file.
    edges.sort(key=lambda e: (e["from_initiative"], e["to_initiative"]))
    return edges


def generate_dependency_conflicts(initiatives, edges):
    """
    Pick out a handful of genuine sequencing problems for the team's tool to
    detect. These are NOT cycles — the graph stays acyclic. They are real
    schedule violations: hard dependencies where the successor is already
    scheduled to start before its predecessor can possibly finish.
    """
    by_id = {i["initiative_id"]: i for i in initiatives}

    scored = []
    for e in edges:
        pred, succ = by_id[e["from_initiative"]], by_id[e["to_initiative"]]
        required_start = pred["_end"] + timedelta(days=e["lag_days"])
        overlap = (required_start - succ["_start"]).days
        if overlap <= 0:
            continue
        preferred = (e["criticality"] == "Hard"
                     and e["dependency_type"] in ("Finish-to-Start", "Technical Enabler"))
        scored.append((0 if preferred else 1, -overlap, e, pred, succ, overlap))

    scored.sort(key=lambda c: (c[0], c[1]))

    conflicts = []
    for n, (_, _, e, pred, succ, overlap) in enumerate(scored[:3], start=1):
        conflicts.append({
            "conflict_id": "CONF-%03d" % n,
            "conflict_type": "Successor starts before predecessor finishes",
            "from_initiative": e["from_initiative"],
            "from_name": pred["name"],
            "from_function": pred["function"],
            "to_initiative": e["to_initiative"],
            "to_name": succ["name"],
            "to_function": succ["function"],
            "dependency_type": e["dependency_type"],
            "criticality": e["criticality"],
            "predecessor_end_date": iso(pred["_end"]),
            "lag_days": e["lag_days"],
            "required_successor_start": iso(pred["_end"] + timedelta(days=e["lag_days"])),
            "actual_successor_start": iso(succ["_start"]),
            "overlap_days": overlap,
            "severity": "High" if overlap > 120 else "Medium",
            "notes": ("INTENTIONAL TEST CASE. %s -> %s is a %s %s dependency, but %s is "
                      "currently scheduled to start %d days before its predecessor can "
                      "finish. A correct roadmap must push %s out, compress %s, or break "
                      "the dependency."
                      % (e["from_initiative"], e["to_initiative"], e["criticality"].lower(),
                         e["dependency_type"], e["to_initiative"], overlap,
                         e["to_initiative"], e["from_initiative"])),
        })
    return conflicts


# ---------------------------------------------------------------------------
# 5. Milestones
# ---------------------------------------------------------------------------

MILESTONE_PLAN = [
    ("Mobilisation & Scope Sign-Off", "Gate",               0.05),
    ("Design Complete",               "Deliverable",        0.30),
    ("Build Complete",                "Deliverable",        0.55),
    ("Stage Gate 2 - Ready for Test", "Gate",               0.70),
    ("Go-Live",                       "Go-Live",            0.90),
    ("Benefit Checkpoint 1",          "Benefit Checkpoint", 1.00),
]


def generate_milestones(rng, initiatives, today):
    rows = []
    counter = 0
    for ini in initiatives:
        n_ms = rng.randint(3, 6)
        # Always keep mobilisation and a go-live; sample the middle.
        plan = [MILESTONE_PLAN[0]]
        middle = MILESTONE_PLAN[1:5]
        rng.shuffle(middle)
        plan += sorted(middle[: max(1, n_ms - 2)], key=lambda m: m[2])
        plan.append(MILESTONE_PLAN[5] if n_ms >= 5 else MILESTONE_PLAN[4])
        plan = sorted({m[0]: m for m in plan}.values(), key=lambda m: m[2])

        total_days = (ini["_end"] - ini["_start"]).days
        for name, mtype, frac in plan:
            counter += 1
            baseline = ini["_start"] + timedelta(days=int(total_days * frac))

            # Slip is correlated with health.
            slip_pool = {"Green": [0, 0, 0, 3, 7],
                         "Amber": [0, 5, 10, 18, 25, 35],
                         "Red": [10, 21, 30, 45, 60, 90]}[ini["rag_status"]]
            slip = rng.choice(slip_pool)
            forecast = baseline + timedelta(days=slip)

            if forecast <= today:
                if slip > 20 and rng.random() < 0.5:
                    status, actual = "Missed", forecast + timedelta(days=rng.randint(1, 20))
                else:
                    status, actual = "Complete", forecast
            elif baseline <= today < forecast:
                status, actual = rng.choice(["In Progress", "In Progress", "Missed"]), None
            elif ini["_start"] <= today:
                status, actual = rng.choice(["Not Started", "In Progress"]), None
            else:
                status, actual = "Not Started", None

            if status != "Complete":
                actual = None

            rows.append({
                "milestone_id": "MS-%04d" % counter,
                "initiative_id": ini["initiative_id"],
                "name": name,
                "type": mtype,
                "baseline_date": iso(baseline),
                "forecast_date": iso(forecast),
                "actual_date": iso(actual),
                "status": status,
                "slip_days": slip,
                "owner": ini["owner"] if rng.random() < 0.6 else make_person(rng),
            })
    return rows


# ---------------------------------------------------------------------------
# 6. Risks and issues
# ---------------------------------------------------------------------------

RISK_DETAIL = {
    "Delivery": "Schedule and execution risk that could push the critical path to the right.",
    "Technical": "Technical uncertainty that may require rework or additional discovery effort.",
    "Change/Adoption": "People-side risk: the change may not stick without sustained reinforcement.",
    "Vendor": "Third-party performance risk against the contracted scope and timeline.",
    "Regulatory": "Compliance exposure if the control design is not accepted by audit or the regulator.",
    "Financial": "Risk to the funding envelope or to the credibility of the benefit case.",
    "Resource": "Capacity risk arising from contention for scarce specialist skills.",
}


def generate_risks(rng, initiatives, today):
    rows = []
    counter = 0
    for ini in initiatives:
        # Riskier, redder, more complex things carry more entries in the
        # register. Every initiative carries at least one.
        base = 1 + ini["complexity"] // 3
        bump = {"Green": 0, "Amber": 1, "Red": 2}[ini["rag_status"]]
        n = max(1, min(4, base + bump + rng.randint(-1, 1)))

        picks = rng.sample(RISK_TEMPLATES, min(n, len(RISK_TEMPLATES)))
        for category, title, mitigation in picks:
            counter += 1
            if ini["rag_status"] == "Red":
                prob, impact = rng.randint(3, 5), rng.randint(3, 5)
            elif ini["rag_status"] == "Amber":
                prob, impact = rng.randint(2, 4), rng.randint(2, 5)
            else:
                prob, impact = rng.randint(1, 3), rng.randint(1, 4)
            score = prob * impact

            exposure = int(round(ini["total_budget"] * (score / 25.0)
                                 * rng.uniform(0.05, 0.30) / 1_000) * 1_000)

            raised = pick_date_between(
                rng,
                max(ini["_start"] - timedelta(days=45), date(2025, 6, 1)),
                min(today, ini["_end"]),
            )
            target = raised + timedelta(days=rng.choice([30, 45, 60, 90, 120]))

            if ini["stage"] == "Complete":
                status = rng.choices(["Closed", "Mitigating"], weights=[8, 2])[0]
            elif score >= 15:
                status = rng.choices(["Open", "Mitigating"], weights=[5, 5])[0]
            else:
                status = rng.choices(["Open", "Mitigating", "Closed"], weights=[4, 4, 3])[0]

            rows.append({
                "risk_id": "RSK-%04d" % counter,
                "initiative_id": ini["initiative_id"],
                "title": title,
                "description": ("%s Carried on %s (%s, %s) and reported into the monthly "
                                "PMO review." % (RISK_DETAIL[category], ini["name"],
                                                 ini["initiative_id"], ini["function"])),
                "category": category,
                "probability": prob,
                "impact": impact,
                "score": score,
                "exposure_usd": exposure,
                "mitigation": mitigation,
                "owner": ini["owner"] if rng.random() < 0.5 else make_person(rng),
                "status": status,
                "raised_date": iso(raised),
                "target_resolution_date": iso(target),
            })
    return rows


def generate_issues(rng, initiatives, risks, today):
    rows = []
    counter = 0
    risks_by_ini = {}
    for r in risks:
        risks_by_ini.setdefault(r["initiative_id"], []).append(r["risk_id"])

    for ini in initiatives:
        if ini["stage"] in ("Idea", "Business Case"):
            n = 0
        elif ini["rag_status"] == "Red":
            n = rng.randint(2, 4)
        elif ini["rag_status"] == "Amber":
            n = rng.randint(1, 3)
        else:
            n = rng.randint(0, 2)

        picks = rng.sample(ISSUE_TEMPLATES, min(n, len(ISSUE_TEMPLATES)))
        for title, description in picks:
            counter += 1
            if ini["rag_status"] == "Red":
                severity = rng.choices(["Critical", "High", "Medium"], weights=[3, 5, 2])[0]
            elif ini["rag_status"] == "Amber":
                severity = rng.choices(["High", "Medium", "Low"], weights=[4, 5, 1])[0]
            else:
                severity = rng.choices(["Medium", "Low", "High"], weights=[5, 4, 1])[0]

            earliest = max(ini["_start"], date(2025, 9, 1))
            raised = pick_date_between(rng, min(earliest, today - timedelta(days=10)), today)
            age = (today - raised).days

            if ini["stage"] == "Complete":
                status = rng.choices(["Resolved", "In Progress"], weights=[9, 1])[0]
            elif severity in ("Critical", "High"):
                status = rng.choices(["Open", "In Progress", "Blocked", "Resolved"],
                                     weights=[4, 4, 3, 2])[0]
            else:
                status = rng.choices(["Open", "In Progress", "Resolved"], weights=[3, 3, 4])[0]

            sched_impact = {"Critical": rng.randint(15, 60), "High": rng.randint(5, 30),
                            "Medium": rng.randint(0, 12), "Low": rng.randint(0, 4)}[severity]
            cost_pct = {"Critical": rng.uniform(0.03, 0.12), "High": rng.uniform(0.01, 0.05),
                        "Medium": rng.uniform(0.0, 0.02), "Low": rng.uniform(0.0, 0.005)}[severity]
            cost_impact = int(round(ini["total_budget"] * cost_pct / 500) * 500)

            linked = ""
            pool = risks_by_ini.get(ini["initiative_id"], [])
            if pool and rng.random() < 0.45:
                linked = rng.choice(pool)

            rows.append({
                "issue_id": "ISS-%04d" % counter,
                "initiative_id": ini["initiative_id"],
                "title": title,
                "description": description,
                "severity": severity,
                "status": status,
                "raised_date": iso(raised),
                "age_days": age,
                "owner": ini["owner"] if rng.random() < 0.55 else make_person(rng),
                "impact_on_schedule_days": sched_impact,
                "impact_on_cost_usd": cost_impact,
                "linked_risk_id": linked,
            })
    return rows


# ---------------------------------------------------------------------------
# 7. Time series — burn, benefits, resources
# ---------------------------------------------------------------------------

WINDOW_START = date(2026, 1, 1)
WINDOW_MONTHS = 24  # 2026-01 .. 2027-12


def window_month_list():
    return [add_months(WINDOW_START, n) for n in range(WINDOW_MONTHS)]


def s_curve_weights(n):
    """
    Spend rarely arrives in equal slices — it ramps up, peaks, then tails off.
    Returns n weights summing to 1.0 following a smooth bell-shaped profile
    (the derivative of an S curve).
    """
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    raw = [math.exp(-(((i + 0.5) / n - 0.5) ** 2) / (2 * 0.22 ** 2)) for i in range(n)]
    total = sum(raw)
    return [r / total for r in raw]


def benefit_ramp_fraction(months_since_start, ramp_months):
    """Fraction of steady-state benefit achieved this far into the ramp."""
    if months_since_start < 0:
        return 0.0
    if ramp_months <= 0:
        return 1.0
    return min(1.0, (months_since_start + 1) / float(ramp_months))


def generate_burn_and_benefits(rng, initiatives, today):
    """
    Monthly spend and benefit series for every initiative across the 24-month
    window. Actuals stop at the last completed month (2026-07 for a 2026-08-11
    'today'); everything after that is left blank.
    """
    months = window_month_list()
    last_actual_key = month_key(add_months(date(today.year, today.month, 1), -1))

    burn_rows = []
    benefit_rows = []

    for ini in initiatives:
        start_i = month_index(ini["_start"])
        end_i = month_index(ini["_end"])
        active_months = max(1, end_i - start_i + 1)
        weights = s_curve_weights(active_months)
        forecast_ratio = ini["forecast_at_completion"] / max(ini["total_budget"], 1)

        cum_plan = 0
        cum_actual = 0

        for m in months:
            mi = month_index(m)
            mkey = month_key(m)
            is_future = mkey > last_actual_key

            # ---- planned spend -------------------------------------------
            planned = int(round(ini["total_budget"] * weights[mi - start_i])) \
                if start_i <= mi <= end_i else 0
            cum_plan += planned
            forecast = int(round(planned * forecast_ratio))

            # ---- actual spend --------------------------------------------
            if is_future:
                actual_str = ""
            else:
                if planned == 0:
                    actual = 0
                else:
                    noise = (rng.uniform(0.80, 1.05) if ini["rag_status"] == "Green"
                             else rng.uniform(0.95, 1.35))
                    actual = int(round(planned * noise))
                cum_actual += actual
                actual_str = str(actual)

            # ---- benefit --------------------------------------------------
            benefit_first_i = start_i + ini["benefit_start_month"]
            steady_monthly = ini["annual_benefit_target"] / 12.0
            if mi >= benefit_first_i:
                ramp = benefit_ramp_fraction(mi - benefit_first_i, ini["benefit_ramp_months"])
                plan_benefit = int(round(steady_monthly * ramp))
            else:
                plan_benefit = 0

            if is_future:
                actual_benefit_str = ""
            else:
                if plan_benefit == 0:
                    actual_benefit = 0
                else:
                    factor = {"High": rng.uniform(0.90, 1.08),
                              "Med": rng.uniform(0.70, 1.00),
                              "Low": rng.uniform(0.35, 0.85)}[ini["value_confidence"]]
                    actual_benefit = int(round(plan_benefit * factor))
                actual_benefit_str = str(actual_benefit)

            burn_rows.append({
                "initiative_id": ini["initiative_id"],
                "month": mkey,
                "planned_spend": planned,
                "actual_spend": actual_str,
                "cumulative_planned": cum_plan,
                "cumulative_actual": "" if is_future else cum_actual,
                "forecast_spend": forecast,
                "benefit_realized": actual_benefit_str,
            })

            pnl_type = {
                "Cost Save": "Opex reduction",
                "Cost Avoidance": "Cost avoided (non-cash)",
                "Revenue Uplift": "Gross margin",
                "Risk Reduction": "Non-financial / risk",
                "Capability": "Enabling (attributed to downstream)",
            }[ini["benefit_type"]]

            benefit_rows.append({
                "initiative_id": ini["initiative_id"],
                "month": mkey,
                "benefit_plan": plan_benefit,
                "benefit_actual": actual_benefit_str,
                "pnl_impact_type": pnl_type,
                "confidence": ini["value_confidence"],
            })

    return burn_rows, benefit_rows


# Roles deliberately over-subscribed in the busy quarters, so scenario
# comparison has a real constraint to trade against. Chosen to span functions.
OVERSUBSCRIBED_ROLES = ["Data Engineer", "Change Manager", "Supply Chain Analyst"]


def generate_resources(rng, initiatives):
    """
    Long-format resource supply and demand by role and month. Demand is derived
    from which initiatives are actually live in each month, so it moves with the
    roadmap rather than being decorative.
    """
    months = window_month_list()
    demand = {(r, month_key(m)): 0.0 for r in ROLES for m in months}

    for ini in initiatives:
        start_i, end_i = month_index(ini["_start"]), month_index(ini["_end"])
        primary = ini["resource_type_needed"]
        # Each initiative pulls mostly on its primary role plus two others,
        # at least one of which comes from outside its own function.
        own_pool = FUNCTION_ROLES[ini["function"]]
        outside = [r for r in ROLES if r not in own_pool]
        secondary = [rng.choice(outside)]
        secondary.append(rng.choice([r for r in ROLES if r != primary and r not in secondary]))

        for m in months:
            mi = month_index(m)
            if not (start_i <= mi <= end_i):
                continue
            # Effort peaks mid-delivery.
            phase = (mi - start_i) / max(end_i - start_i, 1)
            shape = 0.55 + 0.9 * math.exp(-((phase - 0.5) ** 2) / (2 * 0.28 ** 2))
            demand[(primary, month_key(m))] += ini["effort_fte"] * 0.5 * shape
            for role in secondary:
                demand[(role, month_key(m))] += ini["effort_fte"] * 0.18 * shape

    # The busiest quarters, where the pinch-point roles get squeezed hardest.
    def is_crunch(m):
        return ((m.year == 2026 and m.month in (9, 10, 11, 12))
                or (m.year == 2027 and m.month in (1, 2, 3)))

    # Apply the deliberate crunch before sizing supply, so the squeeze is real
    # rather than an artefact of an arbitrary headcount number.
    for role in OVERSUBSCRIBED_ROLES:
        for m in months:
            if is_crunch(m):
                demand[(role, month_key(m))] *= rng.uniform(1.45, 1.85)

    # Size each role's team off its own peak demand. Most functions are
    # resourced to cope; the three pinch-point roles are deliberately not,
    # so scenario comparison has a constraint that actually bites.
    base_supply = {}
    for role in ROLES:
        peak = max(demand[(role, month_key(m))] for m in months)
        if peak <= 0:
            base_supply[role] = 1.0
        elif role in OVERSUBSCRIBED_ROLES:
            base_supply[role] = peak * rng.uniform(0.58, 0.70)
        else:
            base_supply[role] = peak * rng.uniform(1.08, 1.22)

    rows = []
    for role in ROLES:
        for n, m in enumerate(months):
            mkey = month_key(m)
            supply = base_supply[role] * (1 + 0.004 * n) + rng.uniform(-0.2, 0.2)
            # Mild summer and December dip for annual leave.
            if m.month in (7, 8, 12):
                supply *= 0.94
            supply = round(max(1.0, supply), 1)

            dem = round(demand[(role, mkey)], 1)
            rows.append({
                "role": role,
                "month": mkey,
                "quarter": quarter_of(m),
                "available_fte": supply,
                "demanded_fte": dem,
                "gap_fte": round(supply - dem, 1),
                "utilisation_pct": round(dem / supply * 100, 1) if supply else 0.0,
                "over_allocated": "TRUE" if dem > supply else "FALSE",
            })
    return rows


# ---------------------------------------------------------------------------
# 8. Scenarios
# ---------------------------------------------------------------------------

def build_scenarios(initiatives):
    """
    Three scenario definitions. These are INPUTS only — deliberately no computed
    results, because working out what each scenario does to the roadmap is the
    team's job.
    """
    by_id = {i["initiative_id"]: i for i in initiatives}
    total_budget = sum(i["total_budget"] for i in initiatives)
    total_capex = sum(i["capex"] for i in initiatives)

    regulatory = sorted(i["initiative_id"] for i in initiatives if i["is_regulatory"])
    in_flight = sorted(i["initiative_id"] for i in initiatives
                       if i["stage"] in ("In Flight", "At Risk"))

    quick_wins = sorted(
        (i for i in initiatives
         if i["duration_months"] <= 10
         and i["total_budget"] <= 1_200_000
         and i["annual_benefit_target"] >= i["total_budget"] * 0.6
         and i["stage"] != "Complete"),
        key=lambda i: -i["priority_score"],
    )
    quick_win_ids = [i["initiative_id"] for i in quick_wins[:12]]

    deferral_pool = sorted(
        (i for i in initiatives
         if i["stage"] in ("Idea", "Business Case", "Approved")
         and not i["is_regulatory"]
         and i["priority_score"] < 60),
        key=lambda i: i["priority_score"],
    )
    deferrable_ids = [i["initiative_id"] for i in deferral_pool[:14]]

    def label(ids):
        return [{"initiative_id": i, "name": by_id[i]["name"],
                 "function": by_id[i]["function"]} for i in ids]

    return {
        "generated_for": "Aberdeen Advisors hack-team-01",
        "portfolio_total_budget": total_budget,
        "portfolio_total_capex": total_capex,
        "note": ("These are scenario INPUTS only. No results are pre-computed — the "
                 "tool being built is expected to work out the resulting sequence, cost "
                 "profile, resource feasibility and benefit curve for each one, then "
                 "compare them side by side."),
        "scenarios": [
            {
                "scenario_id": "SC-01",
                "name": "Board baseline",
                "description": (
                    "The portfolio exactly as it is currently planned and funded. This is "
                    "the comparison point the board already believes in, and the version "
                    "the incoming transformation leader inherited."),
                "constraints": {
                    "budget_cap_usd": total_budget,
                    "capex_cap_usd": total_capex,
                    "peak_fte_cap": None,
                    "mandatory_initiatives": label(regulatory),
                    "deferred_initiatives": [],
                    "must_finish_by": "2028-12-31",
                    "allow_resequencing": False,
                },
                "expected_qualitative_outcome": (
                    "Shows the problem rather than solving it: three pinch-point roles are "
                    "over-allocated across 2026Q4-2027Q1, several hard cross-function "
                    "dependencies are violated, and benefit realisation is back-loaded "
                    "into 2028. Expect the tool to surface an undeliverable plan."),
            },
            {
                "scenario_id": "SC-02",
                "name": "Cash-constrained (-25% capex)",
                "description": (
                    "The board removes a quarter of the capital envelope in response to a "
                    "weaker trading outlook. Regulatory work is protected; everything else "
                    "competes for what is left. Opex is untouched but headcount is frozen "
                    "at current levels."),
                "constraints": {
                    "budget_cap_usd": int(total_budget * 0.82),
                    "capex_cap_usd": int(total_capex * 0.75),
                    "peak_fte_cap": 85,
                    "mandatory_initiatives": label(sorted(set(regulatory + in_flight[:6]))),
                    "deferred_initiatives": label(deferrable_ids),
                    "must_finish_by": "2029-06-30",
                    "allow_resequencing": True,
                },
                "expected_qualitative_outcome": (
                    "Capital-heavy Technology and Supply Chain initiatives stretch right or "
                    "drop out, which in turn delays every dependent Finance and Operations "
                    "initiative. Total benefit falls less than total spend, so return on "
                    "investment improves while absolute value and delivery pace both worsen. "
                    "Watch for enablers being cut and silently breaking their dependents."),
            },
            {
                "scenario_id": "SC-03",
                "name": "Speed to value (front-load quick wins)",
                "description": (
                    "Same money, different order. Cheap, fast, high-confidence initiatives "
                    "are pulled forward to bank visible savings inside the first twelve "
                    "months and buy the new leader credibility with the board."),
                "constraints": {
                    "budget_cap_usd": total_budget,
                    "capex_cap_usd": total_capex,
                    "peak_fte_cap": 95,
                    "mandatory_initiatives": label(sorted(set(regulatory + quick_win_ids))),
                    "deferred_initiatives": label(deferrable_ids[:6]),
                    "must_finish_by": "2029-06-30",
                    "allow_resequencing": True,
                    "objective_function": "maximise cumulative realised benefit by 2027-06",
                },
                "expected_qualitative_outcome": (
                    "Benefit arrives materially earlier, but foundational enablers get pushed "
                    "back, so the second half of the portfolio becomes slower and more "
                    "expensive as initiatives are built on unfinished foundations. The "
                    "interesting tension for the board: better year-one optics, worse "
                    "three-year total value."),
            },
        ],
    }


# ---------------------------------------------------------------------------
# 9. Writers
# ---------------------------------------------------------------------------

def write_csv(path, rows, fieldnames=None):
    if not rows:
        raise ValueError("refusing to write an empty file: %s" % path)
    fieldnames = fieldnames or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def strip_private(rows):
    """Drop the helper keys (prefixed with _) before writing to disk."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


# ---------------------------------------------------------------------------
# 10. Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a synthetic transformation-portfolio dataset spanning "
                    "eight business functions (initiatives, dependencies, milestones, "
                    "risks, issues, resources, burn, benefits and scenarios).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:  python3 generate_portfolio.py --seed 42 --count 60",
    )
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed; the same seed always gives the same files (default: 42)")
    parser.add_argument("--count", type=int, default=60,
                        help="number of initiatives to generate, max 60 (default: 60)")
    parser.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)),
                        help="folder to write into; data goes in <outdir>/data (default: this script's folder)")
    parser.add_argument("--today", default="2026-08-11",
                        help="the 'as at' date. Actuals stop at the end of the previous "
                             "month (default: 2026-08-11)")
    args = parser.parse_args()

    if args.count < 1 or args.count > len(CATALOGUE):
        parser.error("--count must be between 1 and %d" % len(CATALOGUE))

    today = date.fromisoformat(args.today)
    rng = random.Random(args.seed)

    data_dir = os.path.join(args.outdir, "data")
    os.makedirs(data_dir, exist_ok=True)

    print("Generating %d initiatives (seed=%d, as at %s)..." % (args.count, args.seed, today))

    initiatives = generate_initiatives(rng, args.count, today)
    dependencies = generate_dependencies(rng, initiatives)
    conflicts = generate_dependency_conflicts(initiatives, dependencies)
    milestones = generate_milestones(rng, initiatives, today)
    risks = generate_risks(rng, initiatives, today)
    issues = generate_issues(rng, initiatives, risks, today)
    burn, benefits = generate_burn_and_benefits(rng, initiatives, today)
    resources = generate_resources(rng, initiatives)
    scenarios = build_scenarios(initiatives)

    public_initiatives = strip_private(initiatives)

    counts = {}
    counts["initiatives.csv"] = write_csv(os.path.join(data_dir, "initiatives.csv"), public_initiatives)
    write_json(os.path.join(data_dir, "initiatives.json"), public_initiatives)
    counts["initiatives.json"] = len(public_initiatives)
    counts["dependencies.csv"] = write_csv(os.path.join(data_dir, "dependencies.csv"), dependencies)
    counts["dependency_conflicts.csv"] = write_csv(os.path.join(data_dir, "dependency_conflicts.csv"), conflicts)
    counts["milestones.csv"] = write_csv(os.path.join(data_dir, "milestones.csv"), milestones)
    counts["risks.csv"] = write_csv(os.path.join(data_dir, "risks.csv"), risks)
    counts["issues.csv"] = write_csv(os.path.join(data_dir, "issues.csv"), issues)
    counts["resources.csv"] = write_csv(os.path.join(data_dir, "resources.csv"), resources)
    counts["burn.csv"] = write_csv(os.path.join(data_dir, "burn.csv"), burn)
    counts["benefits.csv"] = write_csv(os.path.join(data_dir, "benefits.csv"), benefits)
    write_json(os.path.join(data_dir, "scenarios.json"), scenarios)
    counts["scenarios.json"] = len(scenarios["scenarios"])

    print("\nWrote to %s" % data_dir)
    for name in sorted(counts):
        print("  %-28s %6d rows" % (name, counts[name]))

    cross = sum(1 for e in dependencies
                if next(i for i in initiatives if i["initiative_id"] == e["from_initiative"])["function"]
                != next(i for i in initiatives if i["initiative_id"] == e["to_initiative"])["function"])
    total = sum(i["total_budget"] for i in initiatives)
    benefit = sum(i["annual_benefit_target"] for i in initiatives)

    print("\nPortfolio: $%.1fm budget, $%.1fm annual benefit target at full run rate."
          % (total / 1e6, benefit / 1e6))
    print("RAG mix: " + ", ".join(
        "%s=%d" % (r, sum(1 for i in initiatives if i["rag_status"] == r))
        for r in ("Green", "Amber", "Red")))
    print("Dependencies: %d edges, %d (%.0f%%) cross-function."
          % (len(dependencies), cross, 100.0 * cross / max(len(dependencies), 1)))
    print("Functions: " + ", ".join(
        "%s=%d" % (f, sum(1 for i in initiatives if i["function"] == f)) for f in FUNCTIONS))


if __name__ == "__main__":
    main()
