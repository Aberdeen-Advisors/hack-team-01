/* ==========================================================================
   app.js - Transformation Roadmap Generator
   ==========================================================================

   Step 2: the engine. Given a scenario, it returns the sequence, the
   violations, the benefit curve and the totals - the frozen result-object
   contract from BUILD-BRIEF.md section 6.

   Plain browser JavaScript. No framework, no build step, no npm, no network
   call at runtime. Everything below is deterministic: the same portfolio.json
   and the same scenario_id always produce byte-identical output, so nothing
   can fail in the demo room that did not fail on the bench.

   The benefit maths is PORTED from synthetic-data/generate_portfolio.py rather
   than reinvented, so our curve reconciles exactly to benefits.csv instead of
   being approximately right:

     s_curve_weights          -> line 1170
     benefit_ramp_fraction    -> line 1185
     the benefit block        -> lines 1240-1247  (authoritative)
     date helpers             -> lines 450-479
     benefit_type -> pnl map  -> lines 1272-1278

   The trap that ruins this if you get it wrong: benefit_start_month is an
   OFFSET IN MONTHS from each initiative's own start_date. It is not a calendar
   month. See resolveBenefitFirstIndex().
   ========================================================================== */

(function (global) {
  'use strict';

  /* ------------------------------------------------------------------------
     Date helpers - ported from generate_portfolio.py lines 450-479.
     Months are handled as absolute integer indexes so two months can simply
     be subtracted, which is how the source data does it.
     ---------------------------------------------------------------------- */

  var MS_PER_DAY = 86400000;

  function parseISO(s) {
    // "2026-07-11" -> UTC Date. UTC throughout: a local-timezone Date would
    // shift dates by a day for anyone west of Greenwich.
    return new Date(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)));
  }

  function isoOf(d) {
    return d.toISOString().slice(0, 10);
  }

  function addDaysISO(s, n) {
    return isoOf(new Date(parseISO(s).getTime() + n * MS_PER_DAY));
  }

  function daysBetweenISO(a, b) {
    // a - b, in whole days.
    return Math.round((parseISO(a).getTime() - parseISO(b).getTime()) / MS_PER_DAY);
  }

  function monthIndexOfISO(s) {
    // Absolute month number. generate_portfolio.py month_index(), line 470.
    return (+s.slice(0, 4)) * 12 + (+s.slice(5, 7) - 1);
  }

  function monthKeyOfIndex(mi) {
    // "2026-08". generate_portfolio.py month_key(), line 465.
    var y = Math.floor(mi / 12), m = (mi % 12) + 1;
    return y + '-' + (m < 10 ? '0' : '') + m;
  }

  function monthIndexOfKey(key) {
    return (+key.slice(0, 4)) * 12 + (+key.slice(5, 7) - 1);
  }

  function quarterOfKey(key) {
    var m = +key.slice(5, 7);
    return key.slice(0, 4) + 'Q' + (Math.floor((m - 1) / 3) + 1);
  }

  function pyRound(x) {
    // Python's round() is half-to-even; JavaScript's Math.round is half-up.
    // The difference is one dollar on the odd row, which is enough to stop the
    // benefit curve reconciling exactly against benefits.csv.
    var f = Math.floor(x), diff = x - f;
    if (diff > 0.5) return f + 1;
    if (diff < 0.5) return f;
    return (f % 2 === 0) ? f : f + 1;
  }

  /* ------------------------------------------------------------------------
     Benefit maths - ported from generate_portfolio.py
     ---------------------------------------------------------------------- */

  function sCurveWeights(n) {
    // Line 1170. n weights summing to 1.0 on a bell profile (the derivative
    // of an S curve). Spend ramps up, peaks, then tails off.
    if (n <= 0) return [];
    if (n === 1) return [1.0];
    var raw = [], total = 0, i, r;
    for (i = 0; i < n; i++) {
      r = Math.exp(-Math.pow((i + 0.5) / n - 0.5, 2) / (2 * Math.pow(0.22, 2)));
      raw.push(r);
      total += r;
    }
    return raw.map(function (v) { return v / total; });
  }

  function benefitRampFraction(monthsSinceStart, rampMonths) {
    // Line 1185. Fraction of steady-state benefit achieved this far in.
    if (monthsSinceStart < 0) return 0.0;
    if (rampMonths <= 0) return 1.0;
    return Math.min(1.0, (monthsSinceStart + 1) / rampMonths);
  }

  // Lines 1272-1278. The authoritative benefit_type -> pnl_impact_type map.
  var PNL_BY_BENEFIT_TYPE = {
    'Cost Save': 'Opex reduction',
    'Cost Avoidance': 'Cost avoided (non-cash)',
    'Revenue Uplift': 'Gross margin',
    'Risk Reduction': 'Non-financial / risk',
    'Capability': 'Enabling (attributed to downstream)'
  };

  /* ------------------------------------------------------------------------
     The four value bands - BUILD-BRIEF.md section 6.

     Cost avoidance is deliberately NOT summed into cost reduction: it is
     non-cash, and a CFO will challenge a combined figure. The non-financial
     band is deliberately kept: Risk Reduction and Capability have no P&L line,
     but Capability is where the enabling initiatives sit - including the $895k
     one the whole argument turns on - and dropping them stops the totals tying
     back to the $84.3m of claimed annual benefit.
     ---------------------------------------------------------------------- */

  var BANDS = ['cost_reduction', 'cost_avoidance', 'revenue_growth', 'non_financial'];

  var BAND_BY_BENEFIT_TYPE = {
    'Cost Save': 'cost_reduction',
    'Cost Avoidance': 'cost_avoidance',
    'Revenue Uplift': 'revenue_growth',
    'Risk Reduction': 'non_financial',
    'Capability': 'non_financial'
  };

  var BAND_BY_PNL_TYPE = {
    'Opex reduction': 'cost_reduction',
    'Cost avoided (non-cash)': 'cost_avoidance',
    'Gross margin': 'revenue_growth',
    'Non-financial / risk': 'non_financial',
    'Enabling (attributed to downstream)': 'non_financial'
  };

  var BAND_LABEL = {
    cost_reduction: 'Cost reduction (cash-backed)',
    cost_avoidance: 'Cost avoidance (non-cash)',
    revenue_growth: 'Revenue growth',
    non_financial: 'Non-financial / enabling'
  };

  /* ------------------------------------------------------------------------
     Which dependency types constrain a date, and how.

     'finish'  the successor cannot start until the predecessor has finished,
               plus the lag. This is the constraint the conflict rule tests.
     'start'   the successor cannot start before the predecessor starts.
     null      no date constraint. A Resource link is a capacity problem, and
               it is caught by the resource violations instead.
     ---------------------------------------------------------------------- */

  var DATE_CONSTRAINT = {
    'Finish-to-Start': 'finish',
    'Technical Enabler': 'finish',
    'Data': 'finish',
    'Start-to-Start': 'start',
    'Resource': null
  };

  // An enabler holds up at least this many times its own annual benefit.
  var ENABLER_MULTIPLE = 10;
  var ENABLER_MIN_DEPENDENTS = 2;

  // A Hard link on a blocking type is one the roadmap is not allowed to break.
  // This is the same test generate_portfolio.py:912 used to rank its headline
  // conflicts, which is why the three planted cases sort to the top.
  function isBlocking(edge) {
    return edge.criticality === 'Hard' &&
      (edge.dependency_type === 'Finish-to-Start' ||
       edge.dependency_type === 'Technical Enabler');
  }

  /* ======================================================================
     Engine
     ====================================================================== */

  function Engine(data) {
    this.data = data;
    this.meta = data.meta;
    this.initiatives = data.initiatives;
    this.dependencies = data.dependencies;
    this.scenarios = data.scenarios.scenarios;

    this.byId = {};
    this.initiatives.forEach(function (i) { this.byId[i.initiative_id] = i; }, this);

    this.windowStartIndex = monthIndexOfKey(data.meta.window_start);
    this.windowMonths = data.meta.window_months;
    this.windowKeys = [];
    for (var k = 0; k < this.windowMonths; k++) {
      this.windowKeys.push(monthKeyOfIndex(this.windowStartIndex + k));
    }

    this._buildGraph();
    this._buildResourceBaseline();
    this._markEnablers();
  }

  /* ---- enablers --------------------------------------------------------- *
     An enabler is an initiative that holds up far more value than it delivers
     itself. That is a RULE, applied to all 60, not a list of examples: it has
     to survive "how did you pick those?" in the room.

     Two tests, both required:
       * it holds up at least 2 other initiatives, so a single downstream link
         cannot make something an enabler by accident; and
       * the annual benefit it holds up is at least 10x its own, which is what
         makes cutting it a false economy rather than a judgement call.

     The rule catches all four cases BUILD-BRIEF.md section 9 names by hand, and
     seven more it does not - including INIT-058 Cyber Security Uplift, which
     holds up $53.1m against $290k of its own (183x) from 51st place on its own
     business case. Hard-coding the brief's four would have hidden the strongest
     piece of evidence in the portfolio.
     -------------------------------------------------------------------- */

  Engine.prototype._markEnablers = function () {
    this.initiatives.forEach(function (i) {
      var own = i.annual_benefit_target,
          held = i.transitive_downstream_benefit;
      i.enabled_multiple = own > 0 ? held / own : (held > 0 ? Infinity : 0);
      i.is_enabler = i.transitive_downstream_count >= ENABLER_MIN_DEPENDENTS &&
                     own > 0 && held >= own * ENABLER_MULTIPLE;
    });
    this.enablers = this.initiatives.filter(function (i) { return i.is_enabler; })
      .sort(function (a, b) {
        return b.transitive_downstream_benefit - a.transitive_downstream_benefit;
      });
  };

  /* ---- the graph -------------------------------------------------------- */

  Engine.prototype._buildGraph = function () {
    var outgoing = {}, incoming = {}, indeg = {}, self = this;

    this.initiatives.forEach(function (i) {
      outgoing[i.initiative_id] = [];
      incoming[i.initiative_id] = [];
      indeg[i.initiative_id] = 0;
    });

    // from_initiative is the PREDECESSOR, to_initiative is the SUCCESSOR.
    // Reversing these is the usual cause of a phantom cycle.
    this.dependencies.forEach(function (e) {
      outgoing[e.from_initiative].push(e);
      incoming[e.to_initiative].push(e);
      indeg[e.to_initiative] += 1;
    });

    this.outgoing = outgoing;
    this.incoming = incoming;

    // Kahn's algorithm, ported from validate_portfolio.py lines 88-104, with
    // the wave recorded as nodes are peeled off. wave 0 = no unmet
    // predecessors; a node's wave is 1 + the deepest of its predecessors.
    var wave = {}, queue = [], order = [], n, i, e;

    Object.keys(indeg).sort().forEach(function (id) {
      if (indeg[id] === 0) { wave[id] = 0; queue.push(id); }
    });

    while (queue.length) {
      n = queue.shift();
      order.push(n);
      for (i = 0; i < outgoing[n].length; i++) {
        e = outgoing[n][i];
        indeg[e.to_initiative] -= 1;
        wave[e.to_initiative] = Math.max(wave[e.to_initiative] || 0, wave[n] + 1);
        if (indeg[e.to_initiative] === 0) queue.push(e.to_initiative);
      }
    }

    this.topoOrder = order;
    this.baseWave = wave;
    this.acyclic = order.length === this.initiatives.length;

    if (!this.acyclic) {
      // The graph is acyclic by construction and validate_portfolio.py asserts
      // it on every run, so this can only mean a bug here - not bad data.
      console.error('Engine: topological sort covered ' + order.length + ' of ' +
        this.initiatives.length + ' nodes. The graph is acyclic by ' +
        'construction, so this is a traversal bug (check edge direction).');
    }
  };

  /* ---- resource baseline ----------------------------------------------- *
     resources.csv already holds the demand implied by the baseline dates,
     including secondary-role pull that was assigned randomly at generation
     time and cannot be reproduced. So rather than rebuilding demand from
     scratch and landing near it, the engine takes the file as the baseline and
     applies a DELTA when an initiative moves or is dropped: subtract its own
     primary-role contribution from the months it used to occupy, add it to the
     months it now occupies.

     The pay-off is that SC-01, which does not resequence, reconciles exactly
     to resources.csv utilisation_pct rather than approximately.
     -------------------------------------------------------------------- */

  Engine.prototype._buildResourceBaseline = function () {
    var avail = {}, demand = {}, roles = {}, self = this;

    this.data.resources.forEach(function (r) {
      avail[r.role + '|' + r.month] = r.available_fte;
      demand[r.role + '|' + r.month] = r.demanded_fte;
      roles[r.role] = true;
    });

    this.resourceAvailable = avail;
    this.resourceBaselineDemand = demand;
    this.roles = Object.keys(roles).sort();

    // The deterministic half of the generator's demand shape, from
    // generate_portfolio.py lines 1321-1323: an initiative pulls
    // effort_fte * 0.5 * shape on its primary role, peaking mid-delivery.
    this.primaryDemandOf = function (ini, startISO, endISO) {
      var startI = monthIndexOfISO(startISO),
          endI = monthIndexOfISO(endISO),
          span = Math.max(endI - startI, 1),
          out = {}, mi, phase, shape;
      for (mi = startI; mi <= endI; mi++) {
        phase = (mi - startI) / span;
        shape = 0.55 + 0.9 * Math.exp(-Math.pow(phase - 0.5, 2) / (2 * Math.pow(0.28, 2)));
        out[monthKeyOfIndex(mi)] = ini.effort_fte * 0.5 * shape;
      }
      return out;
    };
  };

  /* ---- scenario lookup -------------------------------------------------- */

  Engine.prototype.scenario = function (scenarioId) {
    var s = this.scenarios.filter(function (x) { return x.scenario_id === scenarioId; })[0];
    if (!s) throw new Error('Unknown scenario: ' + scenarioId);
    return s;
  };

  /* ---- sequencing ------------------------------------------------------- */

  Engine.prototype._sequence = function (scenario, included) {
    var c = scenario.constraints, self = this, seq = {};

    // Baseline first: every initiative keeps the dates it was handed.
    this.initiatives.forEach(function (i) {
      seq[i.initiative_id] = {
        initiative_id: i.initiative_id,
        name: i.name,
        function: i.function,
        start: i.start_date,
        end: i.end_date,
        wave: self.baseWave[i.initiative_id],
        moved_days: 0
      };
    });

    if (!c.allow_resequencing) return seq;

    // Resequence: walk the topological order so every predecessor is already
    // placed, and push each initiative to the earliest date its Hard links
    // permit. Duration is preserved - this moves work, it does not compress it.
    // Soft links are left alone: they are the ones a roadmap is allowed to
    // break, and breaking them is often the right call.
    this.topoOrder.forEach(function (iid) {
      if (!included[iid]) return;
      var ini = self.byId[iid], row = seq[iid],
          durationDays = daysBetweenISO(ini.end_date, ini.start_date),
          earliest = ini.start_date, i, e, kind, cand;

      for (i = 0; i < self.incoming[iid].length; i++) {
        e = self.incoming[iid][i];
        if (e.criticality !== 'Hard') continue;
        if (!included[e.from_initiative]) continue;
        kind = DATE_CONSTRAINT[e.dependency_type];
        if (!kind) continue;
        cand = (kind === 'finish')
          ? addDaysISO(seq[e.from_initiative].end, e.lag_days)
          : addDaysISO(seq[e.from_initiative].start, e.lag_days);
        if (cand > earliest) earliest = cand;
      }

      row.start = earliest;
      row.end = addDaysISO(earliest, durationDays);
      row.moved_days = daysBetweenISO(earliest, ini.start_date);
    });

    // Waves are NOT recomputed here, and deliberately so: a wave is the depth
    // of a node in the dependency graph, and resequencing moves dates without
    // moving edges, so the layering is identical by construction. (An earlier
    // comment in this spot claimed they were recomputed. They never were, and
    // the claim was wrong rather than merely redundant.)
    return seq;
  };

  /* ---- which initiatives are in the plan -------------------------------- */

  Engine.prototype._selectIncluded = function (scenario) {
    var c = scenario.constraints, self = this,
        included = {}, deferred = {}, trimmed = [], mandatory = {};

    this.initiatives.forEach(function (i) { included[i.initiative_id] = true; });

    (c.mandatory_initiatives || []).forEach(function (m) {
      mandatory[m.initiative_id] = true;
    });

    // The scenario's own explicit deferrals.
    (c.deferred_initiatives || []).forEach(function (dfr) {
      included[dfr.initiative_id] = false;
      deferred[dfr.initiative_id] = 'scenario';
    });

    // If the cap still is not met, trim further. Mandatory initiatives are
    // locked, and so are regulatory ones - BUILD-BRIEF.md section 7 rule B
    // says regulatory work can never be cut by a budget cap, and the cut has
    // to come from somewhere else. Lowest dependency-corrected value goes
    // first, because cutting by naive ROI is exactly the mistake this tool
    // exists to prevent.
    // Which cap actually binds decides what to cut. Ranking by downstream value
    // alone left 15 candidates tied at zero, so the old tiebreak (ASCENDING
    // budget) cut the smallest initiatives first - the ordering that maximises
    // how many get dropped per dollar released. On SC-02 that cut 11 to shed
    // $4.37m of capex when the four largest would have shed $4.82m, and two of
    // the casualties mattered: INIT-022 (a dependent of regulatory INIT-059)
    // and INIT-031 (the successor in the headline 716-day conflict, whose
    // removal flattered the conflict count by deleting the edge).
    //
    // Now: least downstream value first as before, but among equals release the
    // binding resource fastest - cut fewer, larger initiatives.
    var capexBinds = (c.capex_cap_usd != null) &&
      (this.initiatives.reduce(function (a, i) {
        return a + (included[i.initiative_id] ? i.capex : 0); }, 0) > c.capex_cap_usd);

    var candidates = this.initiatives.filter(function (i) {
      return included[i.initiative_id] &&
             !mandatory[i.initiative_id] &&
             !i.is_regulatory;
    }).sort(function (a, b) {
      return a.transitive_downstream_benefit - b.transitive_downstream_benefit ||
             (capexBinds ? b.capex - a.capex : b.total_budget - a.total_budget) ||
             (a.initiative_id < b.initiative_id ? -1 : 1);
    });

    function sums() {
      var b = 0, cx = 0;
      self.initiatives.forEach(function (i) {
        if (included[i.initiative_id]) { b += i.total_budget; cx += i.capex; }
      });
      return { budget: b, capex: cx };
    }

    var budgetCap = c.budget_cap_usd, capexCap = c.capex_cap_usd, s = sums(), k = 0;

    while (((budgetCap != null && s.budget > budgetCap) ||
            (capexCap != null && s.capex > capexCap)) && k < candidates.length) {
      included[candidates[k].initiative_id] = false;
      deferred[candidates[k].initiative_id] = 'budget_cap';
      trimmed.push(candidates[k].initiative_id);
      k++;
      s = sums();
    }

    return {
      included: included,
      deferred: deferred,
      trimmed: trimmed,
      mandatory: mandatory,
      // Still over after every legal cut: the cap itself is infeasible.
      infeasible: (budgetCap != null && s.budget > budgetCap) ||
                  (capexCap != null && s.capex > capexCap),
      finalBudget: s.budget,
      finalCapex: s.capex
    };
  };

  /* ---- violations: dependency ------------------------------------------ */

  Engine.prototype._dependencyViolations = function (seq, included) {
    var out = [], self = this;

    // The rule from BUILD-BRIEF.md section 5, applied to every edge:
    //   required_successor_start = predecessor.end + lag_days
    //   overlap_days = required_successor_start - actual_successor_start
    // Positive means the successor is already scheduled to start before its
    // predecessor can possibly finish.
    //
    // Applied honestly this catches 88 of the 95 edges in the baseline, not 3.
    // That is the real finding: this portfolio was never sequenced. The three
    // planted cases are simply the worst of them, and they sort to the top.
    this.dependencies.forEach(function (e) {
      if (!included[e.from_initiative] || !included[e.to_initiative]) return;

      // Test each edge against the constraint the engine says it carries.
      // Applying the finish-to-start rule to every edge reported 9 breaches
      // (6 Resource, 3 Start-to-Start) against a rule DATE_CONSTRAINT says does
      // not apply to them - and which _sequence correctly refuses to enforce.
      // The detector and the sequencer have to agree or the tool contradicts
      // itself: it would report a breach it then declines to fix.
      var kind = DATE_CONSTRAINT[e.dependency_type];
      if (!kind) return;                       // Resource: a capacity constraint

      var pred = seq[e.from_initiative], succ = seq[e.to_initiative];
      var required = (kind === 'finish')
        ? addDaysISO(pred.end, e.lag_days)
        : addDaysISO(pred.start, e.lag_days);  // Start-to-Start
      var overlap = daysBetweenISO(required, succ.start);
      if (overlap <= 0) return;

      var blocking = isBlocking(e);
      out.push({
        type: 'dependency',
        initiative_id: e.to_initiative,
        description: self.byId[e.to_initiative].name + ' is due to start ' +
          humanDuration(overlap) + ' before ' + self.byId[e.from_initiative].name +
          ' finishes - the work it depends on' +
          (blocking ? '. This link cannot be broken.' : ''),
        severity: overlap > 120 ? 'High' : 'Medium',
        // detail, for the views
        from_initiative: e.from_initiative,
        to_initiative: e.to_initiative,
        dependency_type: e.dependency_type,
        criticality: e.criticality,
        lag_days: e.lag_days,
        predecessor_end: pred.end,
        required_successor_start: required,
        actual_successor_start: succ.start,
        overlap_days: overlap,
        blocking: blocking,
        // A blocking breach is one the roadmap is not allowed to leave standing.
        // A soft one may be a deliberate, defensible choice.
        must_fix: blocking
      });
    });

    out.sort(function (a, b) {
      return (a.blocking === b.blocking ? 0 : (a.blocking ? -1 : 1)) ||
        b.overlap_days - a.overlap_days ||
        (a.from_initiative < b.from_initiative ? -1 : 1);
    });
    return out;
  };

  /* ---- violations: resource -------------------------------------------- */

  Engine.prototype._resourceViolations = function (seq, included, scenario) {
    var self = this, demand = {}, key;

    // Start from the file's own demand, then apply the delta for anything
    // dropped or moved. See _buildResourceBaseline.
    for (key in this.resourceBaselineDemand) {
      if (Object.prototype.hasOwnProperty.call(this.resourceBaselineDemand, key)) {
        demand[key] = this.resourceBaselineDemand[key];
      }
    }

    function shift(ini, fromStart, fromEnd, sign) {
      var d = self.primaryDemandOf(ini, fromStart, fromEnd), mk, k;
      for (mk in d) {
        if (!Object.prototype.hasOwnProperty.call(d, mk)) continue;
        k = ini.resource_type_needed + '|' + mk;
        if (!(k in demand)) continue;   // outside the 24-month window
        demand[k] = Math.max(0, demand[k] + sign * d[mk]);
      }
    }

    this.initiatives.forEach(function (ini) {
      var row = seq[ini.initiative_id];
      if (!included[ini.initiative_id]) {
        shift(ini, ini.start_date, ini.end_date, -1);       // dropped
      } else if (row.start !== ini.start_date) {
        shift(ini, ini.start_date, ini.end_date, -1);       // moved: off the old
        shift(ini, row.start, row.end, +1);                 //        onto the new
      }
    });

    var out = [], peakFte = 0, byMonth = {}, util = {};

    this.roles.forEach(function (role) {
      self.windowKeys.forEach(function (mk) {
        var k = role + '|' + mk,
            av = self.resourceAvailable[k],
            dm = demand[k];
        if (av == null || dm == null) return;
        byMonth[mk] = (byMonth[mk] || 0) + dm;
        // A role with no supply and real demand is infinitely oversubscribed,
        // which is true but unprintable - "Infinity%" would reach the KPI tile
        // and the exception table. Cap it and let the description carry the
        // fact that there is no supply at all.
        var noSupply = !(av > 0) && dm > 0;
        var pct = av > 0 ? (dm / av) * 100 : (noSupply ? 9999 : 0);
        util[k] = pct;
        if (pct > 100) {
          out.push({
            type: 'resource',
            initiative_id: null,
            role: role,
            month: mk,
            quarter: quarterOfKey(mk),
            available_fte: Math.round(av * 10) / 10,
            demanded_fte: Math.round(dm * 10) / 10,
            utilisation_pct: Math.round(pct * 10) / 10,
            description: role + ' is oversubscribed in ' + fmtMonthYear(mk + '-01') +
              ' - ' + Math.round(dm) + ' people needed against ' +
              (noSupply ? 'none available at all'
                        : Math.round(av) + ' available (' + Math.round(pct) + '%)'),
            severity: pct > 130 ? 'High' : 'Medium',
            must_fix: false
          });
        }
      });
    });

    self.windowKeys.forEach(function (mk) {
      if ((byMonth[mk] || 0) > peakFte) peakFte = byMonth[mk];
    });
    peakFte = Math.round(peakFte * 10) / 10;

    // The scenario's own peak-people ceiling.
    //
    // SC-02 and SC-03 state ceilings of 85 and 95. The portfolio cannot be run
    // below roughly 278 people under ANY sequencing, and the resource plan
    // supplies 377 at peak, so those ceilings were never reconciled against the
    // resource data. That is a finding about the scenario definition, not a
    // staffing problem to solve, and saying so is more useful than reporting a
    // 3x breach as though the ceiling were achievable.
    var cap = scenario.constraints.peak_fte_cap;
    if (cap != null && peakFte > cap) {
      var unreconciled = unreconciledFteCap(cap, peakFte);
      out.push({
        type: 'resource',
        initiative_id: null,
        role: null,
        month: null,
        description: unreconciled
          ? 'This scenario states a ceiling of ' + cap + ' people, but the portfolio ' +
            'needs ' + Math.round(peakFte) + ' at its busiest point and cannot be run ' +
            'below roughly 278 however it is sequenced. The ceiling has not been ' +
            'reconciled against the resource plan - it needs restating before it can ' +
            'be tested.'
          : 'This plan needs ' + Math.round(peakFte) + ' people at its busiest point, ' +
            'against a ceiling of ' + cap + '. It cannot be staffed as sequenced.',
        severity: 'High',
        must_fix: !unreconciled
      });
    }

    out.sort(function (a, b) {
      return (b.utilisation_pct || 0) - (a.utilisation_pct || 0);
    });

    return { violations: out, peakFte: peakFte, utilisation: util, demand: demand };
  };

  /* ---- violations: budget ---------------------------------------------- */

  Engine.prototype._budgetViolations = function (scenario, selection) {
    var out = [], c = scenario.constraints, self = this;

    // Per-initiative overrun. Section 7 says "forecast_at_completion exceeds
    // total_budget", which is 42 of 60. The validator's >5% threshold is what
    // gives the headline figure of 25, so that is carried as the severity split
    // rather than as a different rule.
    this.initiatives.forEach(function (i) {
      if (!selection.included[i.initiative_id]) return;
      if (i.forecast_at_completion <= i.total_budget) return;
      var over = i.forecast_at_completion - i.total_budget,
          pct = (over / i.total_budget) * 100;
      out.push({
        type: 'budget',
        initiative_id: i.initiative_id,
        description: i.name + ' will spend ' + money(i.forecast_at_completion) +
          ' against a budget of ' + money(i.total_budget) + ' - ' + money(over) +
          ' over (' + pct.toFixed(0) + '%)',
        severity: pct > 5 ? 'High' : 'Medium',
        over_usd: over,
        over_pct: Math.round(pct * 10) / 10,
        must_fix: false
      });
    });

    // The scenario's caps.
    if (c.budget_cap_usd != null && selection.finalBudget > c.budget_cap_usd) {
      out.push({
        type: 'budget',
        initiative_id: null,
        description: 'This scenario needs ' + money(selection.finalBudget) +
          ' against a ceiling of ' + money(c.budget_cap_usd) + ' - ' +
          money(selection.finalBudget - c.budget_cap_usd) + ' more than it has. ' +
          'The ceiling cannot be met without cutting regulatory work, which is ' +
          'protected, so the ceiling itself does not work.',
        severity: 'High',
        must_fix: true
      });
    }
    if (c.capex_cap_usd != null && selection.finalCapex > c.capex_cap_usd) {
      out.push({
        type: 'budget',
        initiative_id: null,
        description: 'This scenario needs ' + money(selection.finalCapex) +
          ' of capital against a ceiling of ' + money(c.capex_cap_usd) + '. ' +
          'Regulatory work is protected, so the ceiling itself does not work.',
        severity: 'High',
        must_fix: true
      });
    }

    // Cap-level rows carry no over_usd. Defaulting both sides to Infinity made
    // the comparator return NaN when two of them met, which is undefined sort
    // behaviour. Cap breaches are the more serious finding, so they sort first
    // by construction rather than by arithmetic accident.
    out.sort(function (a, b) {
      var ac = a.over_usd == null, bc = b.over_usd == null;
      if (ac !== bc) return ac ? -1 : 1;
      if (ac) return 0;
      return b.over_usd - a.over_usd;
    });
    return out;
  };

  /* ---- violations: compliance ------------------------------------------ *
     BUILD-BRIEF.md section 7. Fires when a REGULATORY initiative is in any of
     four states. Compliance always sorts above every other type regardless of
     severity: a regulatory breach outranks a bigger-dollar budget breach every
     time, because a leader who misses a regulatory item because a $3m overrun
     scored higher has been failed by the tool.

     The client's own board said this out loud - "Regulatory work is protected.
     SO4 initiatives are funded ahead of everything else" - so the rule is
     theirs, not ours.
     -------------------------------------------------------------------- */

  Engine.prototype._complianceViolations = function (seq, included, scenario, enabled) {
    var out = [], self = this, mustFinishBy = scenario.constraints.must_finish_by;

    // One row per initiative, with every rule it breaks listed inside it.
    // Emitting a row per rule produced 16 breaches across 8 regulatory
    // initiatives, which reads as double-counting - and "pushed later" and
    // "now finishes later" are the same event described twice.
    this.initiatives.forEach(function (ini) {
      if (!ini.is_regulatory) return;
      var iid = ini.initiative_id,
          row = seq[iid],
          // Dependents STILL IN THE PLAN. Counting the portfolio-wide closure
          // here put a wrong number inside violations[].description: under
          // SC-02 both of INIT-059's dependents are cut, yet the sentence still
          // read "2 initiatives are already planned on top of it".
          dependents = enabled[iid] ? enabled[iid].count : 0,
          rules = [], why = [];

      // Rule 1 - deferred. The regulatory lock should make this unreachable; it
      // is tested anyway so a future change cannot break the rule silently.
      if (!included[iid]) {
        rules.push('deferred');
        why.push('has been dropped from this scenario entirely');
      } else {
        // Rule 2 - deprioritised: paused, or pushed later to make room.
        if (ini.stage === 'Paused') {
          rules.push('deprioritised');
          why.push('is paused' + (ini.rag_status === 'Red' ? ' and rated in trouble' : '') +
            ', so nothing is moving on a legal obligation');
        } else if (row.moved_days > 0) {
          rules.push('deprioritised');
          why.push('is pushed ' + humanDuration(row.moved_days) +
            ' later by this scenario to make room for other work');
        }

        // Rule 4 - still an idea, with work already planned on top of it.
        if (ini.stage === 'Idea' && dependents > 0) {
          rules.push('unshaped');
          why.push('has not been shaped beyond an idea, yet ' + dependents +
            ' initiative' + (dependents === 1 ? ' is' : 's are') +
            ' already planned on top of it');
        }

        // Rule 3 - finishing later than required. The dataset has no separate
        // regulatory deadline column, so the initiative's own baseline end_date
        // is its required date; the scenario's must-finish-by is tested too.
        //
        // Both tests run. Section 7 says to use the baseline date "and ALSO
        // test it against the scenario's must_finish_by" - an else-if made them
        // mutually exclusive, so an initiative past both reported only the
        // first and the deadline breach never reached the description.
        if (row.end > ini.end_date) {
          rules.push('late');
          why.push('now finishes ' + fmtMonthYear(row.end) + ', ' +
            humanDuration(daysBetweenISO(row.end, ini.end_date)) +
            ' later than the ' + fmtMonthYear(ini.end_date) + ' it was committed to');
        }
        if (mustFinishBy && row.end > mustFinishBy) {
          if (rules.indexOf('late') === -1) rules.push('late');
          why.push('finishes past the ' + fmtMonthYear(mustFinishBy) +
            ' deadline this scenario promises');
        }
      }

      if (!rules.length) return;

      out.push({
        type: 'compliance',
        initiative_id: iid,
        description: ini.name + ' is regulatory and ' + joinClauses(why) + '.',
        severity: 'High',
        must_fix: true,
        rules: rules,
        rule: rules[0],
        regulatory_exposure_usd: ini.rollup.open_regulatory_risk_exposure || 0,
        dependents: dependents
      });
    });

    // Worst exposure first inside the compliance block.
    out.sort(function (a, b) {
      return (b.regulatory_exposure_usd - a.regulatory_exposure_usd) ||
        (b.dependents - a.dependents) ||
        (a.initiative_id < b.initiative_id ? -1 : 1);
    });
    return out;
  };

  /* ---- the benefit curve ----------------------------------------------- */

  Engine.prototype.resolveBenefitFirstIndex = function (ini, startISO) {
    // generate_portfolio.py line 1241:  benefit_first_i = start_i + benefit_start_month
    //
    // benefit_start_month is an OFFSET IN MONTHS from this initiative's own
    // start_date. It is NOT a calendar month and it is NOT comparable to the
    // month column in benefits.csv. Treating it as a calendar month shifts the
    // whole value curve by up to two years.
    return monthIndexOfISO(startISO) + ini.benefit_start_month;
  };

  /* startIndex / months default to the canonical 24-month window, which is what
     the frozen section 6 contract requires and what reconciles to benefits.csv.
     Passing a longer horizon produces the same maths over more months, which is
     how the value-realisation view shows benefit landing AFTER 2027-12 - and
     most of it does. Truncating at the window would have hidden 79-90% of the
     claimed benefit and answered "when does value reach the P&L" with silence. */

  Engine.prototype._benefitCurve = function (seq, included, startIndex, months) {
    var self = this, curve = [], k, i;
    var from = startIndex == null ? this.windowStartIndex : startIndex;
    var n = months == null ? this.windowMonths : months;

    for (k = 0; k < n; k++) {
      curve.push({
        month: monthKeyOfIndex(from + k),
        cost_reduction: 0, cost_avoidance: 0, revenue_growth: 0, non_financial: 0
      });
    }

    this.initiatives.forEach(function (ini) {
      if (!included[ini.initiative_id]) return;
      var band = BAND_BY_BENEFIT_TYPE[ini.benefit_type];
      if (!band) return;

      var startISO = seq[ini.initiative_id].start,
          benefitFirstI = self.resolveBenefitFirstIndex(ini, startISO),
          steadyMonthly = ini.annual_benefit_target / 12.0,
          mi, ramp, plan;

      // generate_portfolio.py lines 1243-1247.
      for (var w = 0; w < n; w++) {
        mi = from + w;
        if (mi < benefitFirstI) continue;
        ramp = benefitRampFraction(mi - benefitFirstI, ini.benefit_ramp_months);
        plan = pyRound(steadyMonthly * ramp);
        curve[w][band] += plan;
      }
    });

    return curve;
  };

  /* ---- totals ----------------------------------------------------------- */

  Engine.prototype._totals = function (seq, included, selection, peakFte) {
    var t = {
      budget: 0, capex: 0, peak_fte: peakFte,
      benefit_cash_backed: 0, benefit_cost_avoidance: 0,
      benefit_revenue: 0, benefit_non_financial: 0
    };

    // The four benefit subtotals are annual_benefit_target grouped by band, so
    // they reconcile to the $84.3m of CLAIMED annual benefit. They are not the
    // sum of the 24-month curve: the plan is deliberately back-loaded into
    // 2028, so the curve inside the window is a fraction of the claim - which
    // is itself one of the findings worth showing.
    this.initiatives.forEach(function (i) {
      if (!included[i.initiative_id]) return;
      t.budget += i.total_budget;
      t.capex += i.capex;
      var band = BAND_BY_BENEFIT_TYPE[i.benefit_type];
      if (band === 'cost_reduction') t.benefit_cash_backed += i.annual_benefit_target;
      else if (band === 'cost_avoidance') t.benefit_cost_avoidance += i.annual_benefit_target;
      else if (band === 'revenue_growth') t.benefit_revenue += i.annual_benefit_target;
      else t.benefit_non_financial += i.annual_benefit_target;
    });

    return t;
  };

  /* ---- run -------------------------------------------------------------- */

  Engine.prototype.run = function (scenarioId) {
    var scenario = this.scenario(scenarioId),
        selection = this._selectIncluded(scenario),
        included = selection.included,
        seq = this._sequence(scenario, included),
        depV = this._dependencyViolations(seq, included),
        res = this._resourceViolations(seq, included, scenario),
        budV = this._budgetViolations(scenario, selection),
        enabled = enabledUnder(this.initiatives, included, this.outgoing, this.byId),
        cmpV = this._complianceViolations(seq, included, scenario, enabled),
        curve = this._benefitCurve(seq, included),
        totals = this._totals(seq, included, selection, res.peakFte),
        self = this;

    // Compliance sorts above everything else regardless of severity, which is
    // why sortViolations keys on type first rather than severity first.
    var violations = sortViolations([].concat(cmpV, depV, res.violations, budV));

    var sequence = this.topoOrder
      .filter(function (iid) { return included[iid]; })
      .map(function (iid) {
        var r = seq[iid];
        return {
          initiative_id: r.initiative_id,
          name: r.name,
          function: r.function,
          start: r.start,
          end: r.end,
          wave: r.wave
        };
      })
      .sort(function (a, b) {
        return (a.start < b.start ? -1 : a.start > b.start ? 1 : 0) ||
          a.wave - b.wave ||
          (a.initiative_id < b.initiative_id ? -1 : 1);
      });

    return {
      scenario_id: scenarioId,
      sequence: sequence,
      violations: violations,
      benefit_curve: curve,
      totals: totals,

      // ---- everything below is additive detail for the views. The four keys
      // above are the frozen contract from section 6 and are not changed.
      _scenario: scenario,
      _selection: selection,
      _seq: seq,
      _violation_counts: countBy(violations, 'type'),
      _dependency_summary: dependencySummary(this.dependencies.length, depV),
      _schedule: scheduleSummary(scenario, seq, included),
      _resource: { utilisation: res.utilisation, peak_fte: res.peakFte },
      // Scenario-specific money. `totals` carries the frozen seven keys and no
      // more, so the figures a scenario needs beyond that live here. Reading
      // portfolio-wide totals instead would show the same overspend for all
      // three scenarios, which is simply wrong once a scenario defers work.
      _finance: financeFor(this.initiatives, included),
      // What each initiative holds up UNDER THIS SCENARIO. The portfolio-wide
      // figures on the initiative record count all 60; once a scenario defers
      // work, an initiative no longer holds up what is no longer being done.
      // Reading the portfolio-wide number here overstated enabled value by up
      // to a third on SC-02 and made the Value view identical in all three
      // scenarios, which is exactly the thing this tool exists to disprove.
      _enabled: enabled,
      _must_fix_count: violations.filter(function (v) { return v.must_fix; }).length,
      // The board's stated demand, from the approved strategy on a page: "We want
      // to see value inside twelve months. The Board has been patient for two
      // years and is no longer patient." This measures the plan against it.
      _benefit_next_12: benefitInWindow(curve, this.data.meta.as_of_month, 12),
      _benefit_in_window: benefitInWindow(curve, null, 0),
      // The full realisation horizon: from the start of the reporting window to
      // three years past the last initiative finishing, so the ramp is visible
      // rather than cut off. `benefit_curve` above stays at the contracted 24
      // points; this is additive detail for the view.
      _benefit_curve_full: this._benefitCurve(seq, included, this.windowStartIndex,
        fullHorizonMonths(this.windowStartIndex, seq, included)),
      _benefit_actual_to_date: this.data.totals.benefit_actual_to_date,
      // The like-for-like gap: the annual run rate this plan has actually
      // reached by the end of the reporting window, against the run rate it
      // promises. Both are annual rates, so they compare directly.
      //
      // This replaces an earlier framing that set the $84.3m promise against
      // the $507 of benefit banked to date. That comparison was retired as
      // wrong: $84.3m is a steady-state annual rate earned only once all 60
      // initiatives are finished and ramped, while $507 comes from a
      // seven-month actuals window in which exactly one initiative had reached
      // its benefit-start month. Measured against the correctly phased plan for
      // that same period ($648), attainment is 78.2% - a different story
      // entirely from "nothing has landed".
      _exit_run_rate: exitRunRate(curve),
      _deferred: Object.keys(selection.deferred).sort(),
      _included_count: Object.keys(included).filter(function (k) { return included[k]; }).length
    };
  };

  /* ---- violation ordering ---------------------------------------------- *
     Compliance first, always, regardless of severity - a regulatory breach
     outranks a bigger-dollar budget breach every time (section 7). Then
     dependency, resource, budget; severity within each block.
     -------------------------------------------------------------------- */

  // Internal type keys stay as the frozen contract requires. These are the
  // words that reach the screen.
  var TYPE_LABEL = {
    all: 'Everything',
    compliance: 'Regulatory',
    dependency: 'Sequencing',
    resource: 'People',
    budget: 'Cost'
  };

  var TYPE_ORDER = { compliance: 0, dependency: 1, resource: 2, budget: 3 };
  var SEVERITY_ORDER = { High: 0, Medium: 1, Low: 2 };

  function sortViolations(list) {
    return list.slice().sort(function (a, b) {
      var ta = TYPE_ORDER[a.type], tb = TYPE_ORDER[b.type];
      if (ta !== tb) return ta - tb;
      var sa = SEVERITY_ORDER[a.severity] == null ? 9 : SEVERITY_ORDER[a.severity],
          sb = SEVERITY_ORDER[b.severity] == null ? 9 : SEVERITY_ORDER[b.severity];
      if (sa !== sb) return sa - sb;
      return (b.overlap_days || b.over_usd || b.utilisation_pct || 0) -
             (a.overlap_days || a.over_usd || a.utilisation_pct || 0);
    });
  }

  function countBy(list, key) {
    var out = {};
    list.forEach(function (x) { out[x[key]] = (out[x[key]] || 0) + 1; });
    return out;
  }

  /* How many months the realisation view needs to cover: from the window start
     to the last initiative finishing, plus three years for its benefit to ramp
     to steady state. Benefit does not stop when delivery does. */

  function fullHorizonMonths(startIndex, seq, included) {
    var lastEnd = startIndex, id;
    for (id in seq) {
      if (!Object.prototype.hasOwnProperty.call(seq, id) || !included[id]) continue;
      var mi = monthIndexOfISO(seq[id].end);
      if (mi > lastEnd) lastEnd = mi;
    }
    return Math.max(24, (lastEnd - startIndex) + 1 + 36);
  }

  /* Money for the initiatives a scenario actually funds. */

  /* A stated ceiling this far below what the work unavoidably needs is an input
     that was never reconciled, not a constraint the plan failed to meet. */
  function unreconciledFteCap(cap, peak) {
    return cap != null && peak > 0 && cap < peak * 0.6;
  }

  /* Scenario-aware enabled value.

     For each initiative: how many of the things it gates are still in the plan,
     and what they are worth. Also re-tests the enabler rule against those
     figures, because an initiative whose downstream work has been cut is no
     longer holding much up - and saying otherwise would overstate the case for
     funding it. Ranks are over funded initiatives only, so "60 of 60" becomes
     "43 of 43" when a scenario funds 43. */

  function enabledUnder(initiatives, included, outgoing, byId) {
    var out = {}, funded = [];

    // Reachability is recomputed by traversal over the FUNDED sub-graph, not by
    // filtering the portfolio-wide closure. Those differ whenever a node is
    // reachable only THROUGH a cut node: intersecting the old closure would
    // keep counting a successor that nothing funded can now reach, overstating
    // what an initiative still holds up. Today the two happen to agree, because
    // almost every cut initiative is a leaf - one edge of data change breaks it.
    function reachFrom(root) {
      var seen = {}, stack = [root], node, i, e;
      while (stack.length) {
        node = stack.pop();
        for (i = 0; i < (outgoing[node] || []).length; i++) {
          e = outgoing[node][i];
          var to = e.to_initiative;
          if (!included[to] || seen[to]) continue;   // cut nodes do not conduct
          seen[to] = 1;
          stack.push(to);
        }
      }
      return Object.keys(seen);
    }

    initiatives.forEach(function (i) {
      var reach = included[i.initiative_id] ? reachFrom(i.initiative_id)
        : (i.transitive_downstream_ids || []).filter(function (x) { return included[x]; });
      var value = 0;
      reach.forEach(function (x) { value += byId[x].annual_benefit_target; });
      out[i.initiative_id] = {
        count: reach.length,
        value: value,
        multiple: i.annual_benefit_target > 0 ? value / i.annual_benefit_target : 0,
        is_enabler: reach.length >= ENABLER_MIN_DEPENDENTS &&
                    i.annual_benefit_target > 0 &&
                    value >= i.annual_benefit_target * ENABLER_MULTIPLE,
        funded: !!included[i.initiative_id]
      };
      if (included[i.initiative_id]) funded.push(i);
    });

    // Ranks over the funded set only.
    funded.slice().sort(function (a, b) {
      return b.naive_roi - a.naive_roi || (a.initiative_id < b.initiative_id ? -1 : 1);
    }).forEach(function (i, n) { out[i.initiative_id].standalone_rank = n + 1; });

    funded.slice().sort(function (a, b) {
      return out[b.initiative_id].value - out[a.initiative_id].value ||
        out[b.initiative_id].count - out[a.initiative_id].count ||
        (a.initiative_id < b.initiative_id ? -1 : 1);
    }).forEach(function (i, n) { out[i.initiative_id].enabled_rank = n + 1; });

    out._funded_count = funded.length;
    out._enabler_count = funded.filter(function (i) {
      return out[i.initiative_id].is_enabler;
    }).length;
    return out;
  }

  function financeFor(initiatives, included) {
    var f = { budget: 0, forecast: 0, spend_to_date: 0, benefit_promised: 0,
              over_budget_count: 0, over_budget_5pct_count: 0 };
    initiatives.forEach(function (i) {
      if (!included[i.initiative_id]) return;
      f.budget += i.total_budget;
      f.forecast += i.forecast_at_completion;
      f.spend_to_date += i.spend_to_date;
      f.benefit_promised += i.annual_benefit_target;
      if (i.forecast_at_completion > i.total_budget) f.over_budget_count += 1;
      if (i.forecast_at_completion > i.total_budget * 1.05) f.over_budget_5pct_count += 1;
    });
    f.overspend = f.forecast - f.budget;
    return f;
  }

  /* Total planned benefit across all four bands. Pass an as-of month and a
     number of months to measure a window starting the month after as-of;
     pass null to total the whole 24-month curve. */

  /* The annual run rate reached by the last month of the reporting window:
     that month's benefit multiplied by twelve. Comparable, like for like,
     against the promised annual figure. */

  function exitRunRate(curve) {
    if (!curve.length) return 0;
    var last = curve[curve.length - 1], monthly = 0;
    BANDS.forEach(function (b) { monthly += last[b]; });
    return monthly * 12;
  }

  function benefitInWindow(curve, asOfMonth, months) {
    var from = asOfMonth ? monthIndexOfKey(asOfMonth) + 1 : -Infinity,
        to = asOfMonth ? from + months - 1 : Infinity, total = 0;
    curve.forEach(function (p) {
      var mi = monthIndexOfKey(p.month);
      if (mi < from || mi > to) return;
      BANDS.forEach(function (b) { total += p[b]; });
    });
    return total;
  }

  /* ---- summaries -------------------------------------------------------- *
     The headline conflict figure has to be the worst BLOCKING overlap, not the
     worst overlap of any kind. Resequencing clears every blocking breach but
     deliberately widens some Soft ones - a Soft link is exactly the kind a
     roadmap is allowed to break, and pushing a predecessor out to satisfy a
     Hard chain will stretch the Soft links hanging off it. Quoting the widest
     Soft gap as "the worst conflict" would make a scenario that fixed
     everything that matters look worse than the one that fixed nothing.
     -------------------------------------------------------------------- */

  function dependencySummary(edgeCount, depV) {
    var blocking = depV.filter(function (v) { return v.blocking; });
    var hard = depV.filter(function (v) { return v.criticality === 'Hard'; });
    return {
      edges: edgeCount,
      violated: depV.length,
      blocking: blocking.length,
      hard: hard.length,
      soft: depV.length - hard.length,
      // the number to put on screen
      worst_blocking: blocking.length ? blocking[0].overlap_days : 0,
      worst_blocking_edge: blocking.length
        ? blocking[0].from_initiative + ' -> ' + blocking[0].to_initiative : null,
      // kept separate so a view can show it without confusing the two
      worst_any: depV.length ? depV[0].overlap_days : 0,
      worst_any_criticality: depV.length ? depV[0].criticality : null
    };
  }

  /* Does the plan actually land inside the date the scenario promises?

     This is reported rather than raised as a violation: the violations[].type
     enum is exactly four values (section 7) and a portfolio-level date breach
     is not one of them. Where it does become a violation is compliance rule 3,
     for regulatory work specifically, which lands in a later step. */

  function scheduleSummary(scenario, seq, included) {
    var mustFinishBy = scenario.constraints.must_finish_by,
        latestEnd = '', latestId = null, moved = 0, maxPush = 0, id;

    for (id in seq) {
      if (!Object.prototype.hasOwnProperty.call(seq, id) || !included[id]) continue;
      if (seq[id].end > latestEnd) { latestEnd = seq[id].end; latestId = id; }
      if (seq[id].moved_days > 0) {
        moved += 1;
        if (seq[id].moved_days > maxPush) maxPush = seq[id].moved_days;
      }
    }

    return {
      must_finish_by: mustFinishBy,
      latest_end: latestEnd,
      latest_initiative: latestId,
      breaches_deadline: !!(mustFinishBy && latestEnd > mustFinishBy),
      days_past_deadline: (mustFinishBy && latestEnd > mustFinishBy)
        ? daysBetweenISO(latestEnd, mustFinishBy) : 0,
      resequenced_count: moved,
      max_push_days: maxPush
    };
  }

  /* ---- formatting ------------------------------------------------------- */

  function fmtInt(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  /* ---- human-readable output ------------------------------------------- *
     Nothing on screen should read like a database. ISO dates, decimal people
     and raw day counts are all engine-internal formats.
     -------------------------------------------------------------------- */

  var MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function fmtMonthYear(iso) {
    // "2029-02-22" -> "Feb 2029"
    if (!iso) return '';
    return MONTH_ABBR[(+iso.slice(5, 7)) - 1] + ' ' + iso.slice(0, 4);
  }

  function humanDuration(days) {
    // 716 -> "2 years"; 140 -> "5 months"; 20 -> "20 days"
    var d = Math.abs(days);
    if (d >= 365) {
      var y = d / 365.25,
          // Pluralise on what is actually printed, not on the rounded value:
          // 1.5 rounds to 1 but reads "1.5 years".
          shown = (y >= 1.95 ? String(Math.round(y)) : y.toFixed(1));
      return shown + ' year' + (shown === '1' || shown === '1.0' ? '' : 's');
    }
    if (d >= 45) return Math.round(d / 30.44) + ' months';
    return d + ' day' + (d === 1 ? '' : 's');
  }

  function joinClauses(list) {
    // "a", "a and b", "a, b and c"
    if (list.length <= 1) return list[0] || '';
    return list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1];
  }

  function people(n) {
    // Nobody has 0.4 of a person.
    return Math.round(n);
  }

  function money(v) {
    // Matches the house style in synthetic-data/build_artifact.py money(), l.34.
    // The sign is carried OUTSIDE the dollar mark: "-$1k", not "$-1k". Deriving
    // the magnitude from Math.abs while formatting the signed value produced
    // the latter, which reads as a typo on any under-budget figure.
    var a = Math.abs(v), sign = v < 0 ? '-' : '';
    if (a >= 1e9) return sign + '$' + (a / 1e9).toFixed(2) + 'bn';
    if (a >= 1e6) return sign + '$' + (a / 1e6).toFixed(1) + 'm';
    if (a >= 1e3) return sign + '$' + Math.round(a / 1e3) + 'k';
    return sign + '$' + fmtInt(a);
  }

  /* ---- data loading ---------------------------------------------------- */

  function loadPortfolio(url) {
    // Same-origin fetch of a committed local file. No external host, no API
    // key, no runtime dependency on anything but a static file server.
    return fetch(url || 'data/portfolio.json').then(function (r) {
      if (!r.ok) throw new Error('Could not load ' + (url || 'data/portfolio.json') +
        ' (HTTP ' + r.status + '). Serve the folder over HTTP - a page opened ' +
        'from file:// is not allowed to read local JSON.');
      return r.json();
    });
  }

  /* ---- exports --------------------------------------------------------- */

  /* ======================================================================
     VIEWS
     ======================================================================
     Every chart below is inline SVG, assembled by hand as strings. No chart
     library, no CDN, no framework - an unreachable CDN in the demo room turns
     a working application into a blank page.
     ====================================================================== */

  /* ---- palette --------------------------------------------------------- *
     Fill carries PILLAR - the client's own board-approved value theme, one per
     strategic objective. Four colours is a legend a board can hold in its head;
     eight functions is not. The client's strategy on a page is explicit that
     the two fields are deliberately different lenses: `pillar` is what the work
     is FOR, `function` is WHO delivers it. A board cares about the former, so
     that is what colour carries. Function is still available on hover.

     Red, amber and green appear NOWHERE in this palette. They are reserved
     entirely for status and problems, so red only ever means "wrong".
     -------------------------------------------------------------------- */

  var PILLAR_META = [
    { key: 'Grow',       so: 'SO1', colour: '#1d4ed8', meaning: 'new or better revenue' },
    { key: 'Run Better', so: 'SO2', colour: '#64748b', meaning: 'simpler, faster, more standard' },
    { key: 'Cost Out',   so: 'SO3', colour: '#0f766e', meaning: 'structural cost removed' },
    { key: 'Protect',    so: 'SO4', colour: '#6d28d9', meaning: 'risk, control, compliance' }
  ];

  var PILLAR_COLOUR = {}, PILLAR_SO = {};
  PILLAR_META.forEach(function (p) {
    PILLAR_COLOUR[p.key] = p.colour;
    PILLAR_SO[p.key] = p.so;
  });

  function pillarColour(ini) { return PILLAR_COLOUR[ini.pillar] || '#94a3b8'; }

  // Function is shown as words on hover ("delivered by Technology") and carries
  // no colour of its own. Eight colours was a legend nobody could use.

  var RAG_COLOUR = { Green: '#16a34a', Amber: '#f59e0b', Red: '#dc2626' };

  var BAND_COLOUR = {
    cost_reduction: '#1e6f5c',
    cost_avoidance: '#63ab90',
    revenue_growth: '#3b6fd4',
    non_financial:  '#94a3b8'
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function svgWrap(w, h, parts, extra) {
    // The house wrapper, after synthetic-data/build_artifact.py svg(), line 235.
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" width="' + w + '" height="' + h +
      '" role="img"' + (extra || '') + '>' + parts.join('') + '</svg>';
  }

  /* ======================================================================
     App state
     ====================================================================== */

  var App = {
    data: null,
    engine: null,
    scenarioId: 'SC-01',
    result: null,
    results: {},        // cached per scenario
    excFilter: 'all',
    focus: null,        // initiative_id highlighted across panels
    compare: false,
    // One surface, four views. No single ranking answers every question a
    // reader has, so rather than compromise them into one list, the view is a
    // control. The prototype has no leader/board tab pair: the scenario
    // comparison strip covers the board-level question of which one to pick.
    view: 'current',
    showAllUnblocks: false,
    showAllProblems: false
  };

  /* Four views, each answering one question. Replaces the earlier single
     ranking, which could only answer one of them and silently hid the rest. */

  var VIEWS = [
    { key: 'current',    id: 'view-current',    label: 'Current state',
      hint: 'What you inherited: when everything runs, and what depends on what' },
    { key: 'value',      id: 'view-value',      label: 'Value',
      hint: 'What each initiative returns on its own, against what it holds up' },
    { key: 'risk',       id: 'view-risk',       label: 'Risk',
      hint: 'What is in trouble, and everything that needs fixing' },
    { key: 'compliance', id: 'view-compliance', label: 'Compliance & regulatory',
      hint: 'The 8 regulatory initiatives, their state, and the exposure behind them' }
  ];

  var TOP_ROADMAP = 15, TOP_UNBLOCKS = 15, TOP_PROBLEMS = 10;

  function byEnabledValue() {
    return App.engine.initiatives.slice().sort(function (a, b) {
      return b.transitive_downstream_benefit - a.transitive_downstream_benefit ||
        b.transitive_downstream_count - a.transitive_downstream_count ||
        (a.initiative_id < b.initiative_id ? -1 : 1);
    });
  }

  /* Enabler membership is decided by the rule in Engine._markEnablers and read
     off i.is_enabler. There is deliberately no hard-coded list of ids here: an
     earlier version pinned the four the brief names by hand, which was both
     brittle and incomplete - it omitted INIT-058, the strongest case in the
     portfolio. */

  function resultFor(id) {
    if (!App.results[id]) App.results[id] = App.engine.run(id);
    return App.results[id];
  }

  /* ======================================================================
     1. Sequenced roadmap
     ====================================================================== */

  function renderRoadmap() {
    var host = document.getElementById('roadmap');
    if (!host) return;
    var r = App.result, seq = r.sequence;

    // The current-state view is the standard timeline: everything the scenario
    // funds, unfiltered. Selecting what matters is what the other views are for.
    renderRoadmapHeader(seq.length, 60);
    if (!seq.length) {
      host.innerHTML = '<div class="empty">Nothing matches this lens in this scenario.</div>';
      return;
    }

    // The time span is computed from the plan, not hard-coded: a resequenced
    // scenario runs past 2029 and a fixed axis would clip it silently.
    var minI = Infinity, maxI = -Infinity;
    seq.forEach(function (s) {
      minI = Math.min(minI, monthIndexOfISO(s.start));
      maxI = Math.max(maxI, monthIndexOfISO(s.end));
    });
    minI -= 1; maxI += 1;
    var months = maxI - minI + 1;

    var LBL = 288, MW = 21, ROW = 17, PAD_T = 34, GAP = 15;
    var chartW = months * MW;
    var W = LBL + chartW + 18;

    // Group by wave, then by computed start inside each wave.
    var byWave = {};
    seq.forEach(function (s) { (byWave[s.wave] = byWave[s.wave] || []).push(s); });
    var waveKeys = Object.keys(byWave).map(Number).sort(function (a, b) { return a - b; });
    waveKeys.forEach(function (w) {
      byWave[w].sort(function (a, b) { return a.start < b.start ? -1 : a.start > b.start ? 1 : 0; });
    });

    var H = PAD_T + waveKeys.reduce(function (acc, w) {
      return acc + GAP + byWave[w].length * ROW;
    }, 0) + 12;

    var p = [], x, i, y = PAD_T;

    // ---- month + year gridlines
    for (i = 0; i < months; i++) {
      var mi = minI + i, mk = monthKeyOfIndex(mi), isJan = mk.slice(5) === '01';
      x = LBL + i * MW;
      p.push('<line class="gridline' + (isJan ? ' year' : '') + '" x1="' + x +
        '" y1="' + (PAD_T - 12) + '" x2="' + x + '" y2="' + (H - 6) + '"/>');
      if (isJan) {
        p.push('<text class="axis-t" x="' + (x + 4) + '" y="' + (PAD_T - 18) +
          '" style="font-weight:700;fill:#4a5a6e">' + mk.slice(0, 4) + '</text>');
      }
      if (mk.slice(5) === '01' || mk.slice(5) === '07') {
        p.push('<text class="axis-t" x="' + (x + 3) + '" y="' + (PAD_T - 4) + '">' +
          ['Jan', '', '', '', '', '', 'Jul'][+mk.slice(5) - 1] + '</text>');
      }
    }

    // ---- the as-of line: everything right of it has not happened yet
    var asOfI = monthIndexOfKey(App.data.meta.as_of_month) + 1;
    if (asOfI >= minI && asOfI <= maxI) {
      x = LBL + (asOfI - minI) * MW;
      p.push('<line class="today" x1="' + x + '" y1="' + (PAD_T - 12) + '" x2="' + x +
        '" y2="' + (H - 6) + '"/>');
      // Label at the top, clear of the bars. Anything right of this line has
      // not happened yet - that is the whole point of the as-of boundary.
      p.push('<text class="today-t" x="' + (x + 4) + '" y="' + (PAD_T - 20) + '">TODAY</text>');
    }

    // ---- wave bands and bars
    waveKeys.forEach(function (w) {
      var rows = byWave[w], bandH = rows.length * ROW + GAP - 5;
      p.push('<rect class="wave-band" x="0" y="' + (y - 3) + '" width="' + W +
        '" height="' + bandH + '" rx="3"/>');
      // Waves are displayed from 1. Zero-indexing is an engineering artefact.
      p.push('<text class="wave-t" x="10" y="' + (y + 9) + '">WAVE ' + (w + 1) + '</text>');
      y += GAP;

      rows.forEach(function (s) {
        var ini = App.engine.byId[s.initiative_id],
            s0 = monthIndexOfISO(s.start), s1 = monthIndexOfISO(s.end),
            bx = LBL + (s0 - minI) * MW,
            bw = Math.max(4, (s1 - s0 + 1) * MW - 2),
            dim = App.focus && App.focus !== s.initiative_id &&
                  !isDownstreamOf(App.focus, s.initiative_id),
            sel = App.focus === s.initiative_id,
            g = 'class="' + (dim ? 'dimmed' : '') + '"';

        p.push('<g ' + g + ' data-iid="' + s.initiative_id + '">');
        p.push('<text class="bar-id" x="10" y="' + (y + 11) + '">' + s.initiative_id + '</text>');
        p.push('<text class="bar-lbl" x="66" y="' + (y + 11) + '">' +
          esc(clip(ini.name, 34)) + '</text>');
        p.push('<circle cx="' + (LBL - 12) + '" cy="' + (y + 7) + '" r="4" fill="' +
          (RAG_COLOUR[ini.rag_status] || '#94a3b8') + '"/>');
        p.push('<rect x="' + bx + '" y="' + (y + 1) + '" width="' + bw + '" height="' +
          (ROW - 5) + '" rx="2.5" fill="' + pillarColour(ini) + '"' +
          (sel ? ' stroke="#16202e" stroke-width="2"' : '') + '>' +
          '<title>' + esc(ini.name) +
          '\n' + esc(PILLAR_SO[ini.pillar] + ' ' + ini.pillar) +
          '  ·  delivered by ' + esc(s.function) +
          '\n' + esc(ini.stage) + '  ·  ' + esc(statusWord(ini.rag_status)) +
          '\n' + fmtMonthYear(s.start) + ' to ' + fmtMonthYear(s.end) +
          '\nbudget ' + money(ini.total_budget) +
          '\nholds up ' + enOf(s.initiative_id).count + ' initiatives worth ' +
          money(enOf(s.initiative_id).value) + '</title></rect>');
        if (ini.is_regulatory) {
          p.push('<rect x="' + bx + '" y="' + (y + 1) + '" width="3" height="' + (ROW - 5) +
            '" fill="#fff" opacity=".85"/>');
        }
        p.push('</g>');
        y += ROW;
      });
      y += 2;
    });

    host.innerHTML = svgWrap(W, H, p, ' id="roadmap-svg"');

    host.querySelectorAll('g[data-iid]').forEach(function (g) {
      g.style.cursor = 'pointer';
      g.addEventListener('click', function () { setFocus(g.getAttribute('data-iid')); });
    });
  }

  function clip(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  /* Scenario-aware reach for one initiative. Every view must read through this
     rather than the portfolio-wide fields on the initiative record, or two
     panels in the same scenario print different numbers for the same thing. */
  function enOf(iid) {
    return (App.result && App.result._enabled && App.result._enabled[iid]) ||
      { count: 0, value: 0, multiple: 0, is_enabler: false, funded: false };
  }

  // RAG is internal shorthand. On screen it reads as plain English.
  function statusWord(rag) {
    return { Green: 'On track', Amber: 'At risk', Red: 'In trouble' }[rag] || rag;
  }

  /* The "showing 15 of 60 / Show all" control, shared by the roadmap and the
     enabled-value ranking. The true total is always printed, so a simplified
     default can never read as a smaller portfolio than the one that exists. */

  function showAllControl(id, shown, total, flag) {
    if (shown >= total) {
      return '<span class="pill mute">all ' + total + ' shown</span>';
    }
    return '<span class="pill mute">showing ' + shown + ' of ' + total + '</span>' +
      '<button class="chip" id="' + id + '" data-flag="' + flag + '">Show all ' +
      total + '</button>';
  }

  function wireShowAll(id) {
    var b = document.getElementById(id);
    if (!b) return;
    b.addEventListener('click', function () {
      var f = b.getAttribute('data-flag');
      App[f] = !App[f];
      render();
    });
  }

  /* Initiatives carrying a must-fix problem in the current scenario. */
  function mustFixIds() {
    var m = {};
    App.result.violations.forEach(function (v) {
      if (v.must_fix && v.initiative_id) m[v.initiative_id] = 1;
    });
    return m;
  }

  function renderRoadmapHeader(shown, total) {
    var el = document.getElementById('roadmap-ctl');
    if (el) {
      el.innerHTML = '<span class="pill mute">' + shown + ' initiatives' +
        (shown < total ? ' of ' + total : '') + '</span>';
    }
    // Panel copy states counts, so it has to move with the scenario. Hard-coded
    // "All 60" read as a lie the moment a scenario funded 43.
    var why = document.getElementById('roadmap-why');
    if (why) {
      why.innerHTML = (shown === total ? 'All ' + total + ' initiatives' :
        'The ' + shown + ' initiatives this scenario funds') +
        ', when each one runs, grouped by what has to happen first. ' +
        'The dot is its current health.' +
        (shown < total ? ' <b>' + (total - shown) + ' are not funded.</b>' : '');
    }
  }

  function isDownstreamOf(focusId, candidateId) {
    var f = App.engine.byId[focusId];
    return !!(f && f.transitive_downstream_ids &&
              f.transitive_downstream_ids.indexOf(candidateId) !== -1);
  }

  /* ======================================================================
     2. Dependency view  (the fourth panel)
     ======================================================================
     A layered node-link diagram: one column per topological wave, so the graph
     reads left to right as "what has to happen before what". Clicking a node
     lights up its whole transitive closure, which is what turns the sentence
     "$895k gates $38.6m across 28 initiatives" into something you can point at.
     ====================================================================== */

  function renderDependencyGraph() {
    var host = document.getElementById('depgraph');
    if (!host) return;

    var seq = App.result.sequence,
        inPlan = {}, byWave = {};
    seq.forEach(function (s) { inPlan[s.initiative_id] = s; });

    // Lay out every initiative, in or out of plan, so a deferred one is still
    // visible as a hole in the graph rather than vanishing without trace.
    App.engine.initiatives.forEach(function (i) {
      var w = App.engine.baseWave[i.initiative_id];
      (byWave[w] = byWave[w] || []).push(i);
    });
    var waveKeys = Object.keys(byWave).map(Number).sort(function (a, b) { return a - b; });
    waveKeys.forEach(function (w) {
      byWave[w].sort(function (a, b) {
        return b.transitive_downstream_count - a.transitive_downstream_count ||
          (a.initiative_id < b.initiative_id ? -1 : 1);
      });
    });

    var COL = 148, NW = 104, NH = 21, VG = 7, PAD_L = 22, PAD_T = 40;
    var maxRows = Math.max.apply(null, waveKeys.map(function (w) { return byWave[w].length; }));
    var W = PAD_L * 2 + (waveKeys.length - 1) * COL + NW;
    var H = PAD_T + maxRows * (NH + VG) + 26;

    var pos = {};
    waveKeys.forEach(function (w, ci) {
      var rows = byWave[w],
          off = (maxRows - rows.length) * (NH + VG) / 2;
      rows.forEach(function (i, ri) {
        pos[i.initiative_id] = {
          x: PAD_L + ci * COL,
          y: PAD_T + off + ri * (NH + VG)
        };
      });
    });

    var focus = App.focus,
        lit = {}, litEdge = {};
    if (focus) {
      lit[focus] = true;
      (App.engine.byId[focus].transitive_downstream_ids || []).forEach(function (id) {
        lit[id] = true;
      });
    }

    var edges = [], nodes = [], labels = [];

    // ---- wave column headers
    waveKeys.forEach(function (w, ci) {
      edges.push('<text class="wave-t" x="' + (PAD_L + ci * COL) + '" y="' + (PAD_T - 20) +
        '">WAVE ' + (w + 1) + '</text>');
      edges.push('<text class="axis-t" x="' + (PAD_L + ci * COL) + '" y="' + (PAD_T - 8) +
        '">' + byWave[w].length + ' initiative' + (byWave[w].length === 1 ? '' : 's') + '</text>');
    });

    // ---- edges, drawn first so nodes sit on top
    var violated = {};
    App.result.violations.forEach(function (v) {
      if (v.type === 'dependency') violated[v.from_initiative + '>' + v.to_initiative] = v;
    });

    App.engine.dependencies.forEach(function (e) {
      var a = pos[e.from_initiative], b = pos[e.to_initiative];
      if (!a || !b) return;

      var x1 = a.x + NW, y1 = a.y + NH / 2, x2 = b.x, y2 = b.y + NH / 2,
          mx = (x1 + x2) / 2,
          key = e.from_initiative + '>' + e.to_initiative,
          bad = violated[key],
          onPath = focus && lit[e.from_initiative] && lit[e.to_initiative],
          dim = focus && !onPath;

      var stroke = bad ? (isBlocking(e) ? '#dc2626' : '#f0a742') : '#c3ccd8';
      if (onPath) stroke = '#1f4e9c';

      edges.push('<path class="dep-edge" d="M' + x1 + ',' + y1 + ' C' + mx + ',' + y1 +
        ' ' + mx + ',' + y2 + ' ' + x2 + ',' + y2 + '" stroke="' + stroke +
        '" stroke-width="' + (onPath ? 1.9 : bad ? 1.3 : 0.9) + '"' +
        (e.criticality === 'Soft' ? ' stroke-dasharray="3 3"' : '') +
        (dim ? ' opacity=".07"' : bad ? ' opacity=".85"' : ' opacity=".5"') + '>' +
        '<title>' + esc(App.engine.byId[e.from_initiative].name + '  must come before  ' +
        App.engine.byId[e.to_initiative].name +
        '\n' + (e.criticality === 'Hard' ? 'Cannot be broken' : 'Could be broken if needed') +
        (bad ? '\nOUT OF ORDER by ' + humanDuration(bad.overlap_days) : '\nCorrectly ordered')) +
        '</title></path>');
    });

    // ---- nodes
    App.engine.initiatives.forEach(function (i) {
      var pt = pos[i.initiative_id],
          deferred = !inPlan[i.initiative_id],
          dim = focus && !lit[i.initiative_id],
          isFocus = focus === i.initiative_id,
          fill = deferred ? '#e2e8f0' : pillarColour(i);

      nodes.push('<g class="dep-node" data-iid="' + i.initiative_id + '"' +
        (dim ? ' opacity=".13"' : '') + '>');
      nodes.push('<rect x="' + pt.x + '" y="' + pt.y + '" width="' + NW + '" height="' + NH +
        '" rx="4" fill="' + fill + '"' +
        (isFocus ? ' stroke="#16202e" stroke-width="2.5"'
                 : deferred ? ' stroke="#c3ccd8" stroke-dasharray="3 2"' : '') + '>' +
        '<title>' + esc(i.name + '\n' + PILLAR_SO[i.pillar] + ' ' + i.pillar +
        '  ·  delivered by ' + i.function + '\n' + i.stage + '  ·  ' +
        statusWord(i.rag_status) + (deferred ? '\nNOT FUNDED in this scenario' : '') +
        '\nholds up ' + enOf(i.initiative_id).count + ' initiatives worth ' +
        money(enOf(i.initiative_id).value)) + '</title></rect>');
      // Regulatory work gets a white keyline so it can never be lost in a scan.
      if (i.is_regulatory) {
        nodes.push('<rect x="' + (pt.x + 1.5) + '" y="' + (pt.y + 1.5) + '" width="' +
          (NW - 3) + '" height="' + (NH - 3) + '" rx="3" fill="none" stroke="#fff" ' +
          'stroke-width="1.4" opacity=".9"/>');
      }
      labels.push('<text class="dep-lbl" x="' + (pt.x + 6) + '" y="' + (pt.y + 14) + '"' +
        (dim ? ' opacity=".2"' : '') + (deferred ? ' fill="#64748b"' : '') + '>' +
        i.initiative_id.replace('INIT-', '') + ' ' +
        esc(clip(i.name.replace(/[^A-Za-z0-9 &-]/g, ''), 11)) + '</text>');
      nodes.push('</g>');
      nodes.push('<circle cx="' + (pt.x + NW - 6) + '" cy="' + (pt.y + 5.5) + '" r="3" fill="' +
        (RAG_COLOUR[i.rag_status] || '#94a3b8') + '"' + (dim ? ' opacity=".2"' : '') +
        ' stroke="#fff" stroke-width="1"/>');
    });

    host.innerHTML = svgWrap(W, H, edges.concat(nodes, labels));

    host.querySelectorAll('g[data-iid]').forEach(function (g) {
      g.addEventListener('click', function () { setFocus(g.getAttribute('data-iid')); });
    });

    renderDepReadout();
  }

  function renderDepReadout() {
    var el = document.getElementById('dep-readout');
    if (!el) return;
    var d = App.result._dependency_summary;

    if (!App.focus) {
      el.innerHTML = '<b>' + d.violated + ' of ' + d.edges +
        '</b> dependencies are out of order' +
        (d.blocking ? ', and <b>' + d.blocking + '</b> of those cannot be worked around' +
          (d.worst_blocking ? ' &mdash; the worst by <b>' +
            humanDuration(d.worst_blocking) + '</b>' : '')
          : '. <b>None</b> of them is on a link that cannot be broken') +
        '. <span class="muted">Solid lines cannot be broken, dashed ones can. ' +
        'Click any box to trace what it holds up.</span>';
      return;
    }

    // Scenario-aware: quoting the portfolio-wide rank and reach here while the
    // Value view showed the funded figures would put two different numbers for
    // the same initiative on the same screen.
    var i = App.engine.byId[App.focus], e = App.result._enabled[App.focus],
        n = App.result._enabled._funded_count;

    el.innerHTML = '<b>' + esc(i.name) + '</b> &mdash; costs ' + money(i.total_budget) +
      ', returns ' + money(i.annual_benefit_target) + ' a year on its own. ' +
      (e.funded
        ? 'Holds up <b>' + e.count + ' initiatives</b> carrying <b>' + money(e.value) +
          '</b> a year. Ranked <b>' + e.standalone_rank + ' of ' + n +
          '</b> on its standalone business case, <b>' + e.enabled_rank +
          '</b> once dependencies are counted.'
        : '<b>Not funded in this scenario.</b> Across the full portfolio it holds up ' +
          i.transitive_downstream_count + ' initiatives worth ' +
          money(i.transitive_downstream_benefit) + '.') +
      (e.is_enabler ? ' <span class="pill bad">ENABLER &mdash; holds up ' +
        Math.round(e.multiple) + '&times; its own value</span>' : '') +
      ' <button class="chip" id="clear-focus" style="margin-left:8px">clear</button>';

    var btn = document.getElementById('clear-focus');
    if (btn) btn.addEventListener('click', function () { setFocus(null); });
  }

  function setFocus(iid) {
    App.focus = (App.focus === iid) ? null : iid;
    render();
  }

  /* ======================================================================
     3. Exception list
     ====================================================================== */

  function renderExceptions() {
    var host = document.getElementById('exceptions');
    if (!host) return;
    var all = App.result.violations,
        counts = App.result._violation_counts,
        mustFix = all.filter(function (v) { return v.must_fix; }),
        pool = App.excFilter === 'all'
          ? all : all.filter(function (v) { return v.type === App.excFilter; });

    // Must-fix items lead, then the worst of the rest fills the list out.
    var ordered = pool.filter(function (v) { return v.must_fix; })
      .concat(pool.filter(function (v) { return !v.must_fix; }));
    var shown = App.showAllProblems ? ordered : ordered.slice(0, TOP_PROBLEMS);

    // ---- filter chips, in plain-English type names
    var fbar = document.getElementById('exc-filter');
    if (fbar) {
      var types = ['all', 'compliance', 'dependency', 'resource', 'budget']
        .filter(function (t) { return t === 'all' || counts[t]; });
      fbar.innerHTML = types.map(function (t) {
        return '<button class="chip" data-t="' + t + '" aria-pressed="' +
          (App.excFilter === t ? 'true' : 'false') + '">' + TYPE_LABEL[t] +
          ' <b>' + (t === 'all' ? all.length : counts[t]) + '</b></button>';
      }).join('');
      fbar.querySelectorAll('.chip').forEach(function (c) {
        c.addEventListener('click', function () {
          App.excFilter = c.getAttribute('data-t');
          renderExceptions();
        });
      });
    }

    // The true total is always on screen next to the heading, so a top-ten
    // default can never be mistaken for "we only found ten things".
    var cnt = document.getElementById('exc-count');
    if (cnt) {
      cnt.innerHTML = (mustFix.length
        ? '<b>' + mustFix.length + ' must fix</b> · ' : '') +
        all.length + ' problems found';
      cnt.className = 'pill ' + (mustFix.length ? 'bad' : 'mute');
    }
    var ctl = document.getElementById('exc-ctl');
    if (ctl) {
      ctl.innerHTML = showAllControl('exc-showall', shown.length, ordered.length,
        'showAllProblems');
      wireShowAll('exc-showall');
    }

    if (!shown.length) {
      host.innerHTML = '<div class="empty">Nothing of this kind outstanding in this scenario.</div>';
      return;
    }

    var rows = shown.map(function (v) {
      var sel = v.initiative_id && App.focus === v.initiative_id;
      // Section 8 specifies type, initiative, description AND severity. The
      // initiative and severity columns had been dropped, leaving severity
      // computed on every violation but never shown, and the subject buried
      // inside the prose.
      var subject = v.initiative_id
        ? clip(App.engine.byId[v.initiative_id].name, 26)
        : (v.role ? v.role : '—');
      return '<tr class="click' + (sel ? ' sel' : '') + '"' +
        (v.initiative_id ? ' data-iid="' + v.initiative_id + '"' : '') + '>' +
        '<td>' + (v.must_fix ? '<span class="pill bad">MUST FIX</span>' : '') + '</td>' +
        '<td><span class="ty ' + v.type + '">' + TYPE_LABEL[v.type] + '</span></td>' +
        '<td>' + esc(subject) + '</td>' +
        '<td>' + esc(v.description) + '</td>' +
        '<td class="sev ' + v.severity + '">' + esc(v.severity) + '</td>' +
        // Prose carries the readable duration; this column carries the exact
        // day count, so the "worst is 716 days" claim stays checkable on screen.
        '<td class="n mono">' + (v.overlap_days ? v.overlap_days + ' days'
          : v.over_usd ? money(v.over_usd)
          : v.utilisation_pct ? Math.round(v.utilisation_pct) + '%' : '') + '</td></tr>';
    });

    host.innerHTML = '<table><thead><tr><th></th><th>Kind</th><th>Initiative</th>' +
      '<th>What is wrong</th><th>Severity</th><th class="n">Scale</th>' +
      '</tr></thead><tbody>' + rows.join('') + '</tbody></table>';

    host.querySelectorAll('tr[data-iid]').forEach(function (tr) {
      tr.addEventListener('click', function () {
        setFocus(tr.getAttribute('data-iid'));
        var g = document.querySelector('#roadmap g[data-iid="' + tr.getAttribute('data-iid') + '"]');
        if (g && g.scrollIntoView) g.scrollIntoView({ block: 'center', behavior: 'smooth' });
      });
    });
  }

  /* ======================================================================
     4. What this unblocks
     ====================================================================== */

  function renderUnblocks() {
    var host = document.getElementById('unblocks');
    if (!host) return;

    // Scenario-aware throughout: an initiative this scenario has cut is not in
    // the plan, and what the rest hold up is counted over funded work only.
    var en = App.result._enabled;
    var full = App.engine.initiatives.filter(function (i) { return en[i.initiative_id].funded; })
      .sort(function (a, b) {
        return en[b.initiative_id].value - en[a.initiative_id].value ||
          en[b.initiative_id].count - en[a.initiative_id].count;
      });
    var list = App.showAllUnblocks ? full
      : full.filter(function (i) { return en[i.initiative_id].is_enabler; });
    var maxBen = full.length ? (en[full[0].initiative_id].value || 1) : 1,
        rankOf = {};
    full.forEach(function (i, n) { rankOf[i.initiative_id] = n + 1; });

    // The enablers panel leads with the rule, so the word is earned on screen.
    var note = document.getElementById('enabler-note');
    if (note) {
      note.innerHTML = '<b>' + en._enabler_count + ' of ' + en._funded_count +
        ' funded</b> hold up ' + ENABLER_MULTIPLE + '&times; their own value or more';
    }
    var ctl = document.getElementById('unblock-ctl');
    if (ctl) {
      ctl.innerHTML = showAllControl('unblock-showall', list.length, full.length,
        'showAllUnblocks');
      wireShowAll('unblock-showall');
    }

    var rows = list.map(function (i) {
      var e = en[i.initiative_id],
          w = Math.max(1, Math.round(200 * e.value / maxBen)),
          sel = App.focus === i.initiative_id,
          move = e.standalone_rank - e.enabled_rank;
      return '<tr class="click' + (sel ? ' sel' : '') + '" data-iid="' + i.initiative_id + '">' +
        '<td class="n muted">' + rankOf[i.initiative_id] + '</td>' +
        '<td>' + esc(clip(i.name, 38)) +
          (e.is_enabler ? ' <span class="pill bad">' + Math.round(e.multiple) +
            '&times;</span>' : '') +
          (i.is_regulatory ? ' <span class="pill warn">regulatory</span>' : '') + '</td>' +
        '<td class="n">' + e.count + '</td>' +
        '<td class="n">' +
          '<svg width="208" height="12" style="display:inline-block;vertical-align:middle">' +
          '<rect x="0" y="2" width="' + w + '" height="8" rx="2" fill="' +
          pillarColour(i) + '" opacity=".85"/></svg></td>' +
        '<td class="n"><b>' + money(e.value) + '</b></td>' +
        '<td class="n mono">' + money(i.total_budget) + '</td>' +
        '<td class="n mono">' + money(i.annual_benefit_target) + '</td>' +
        '<td class="n mono">' + e.standalone_rank + '</td>' +
        '<td class="n mono">' + e.enabled_rank + '</td>' +
        '<td class="n mono" style="color:' + (move > 0 ? '#15803d' : move < 0 ? '#b91c1c' : '#8494a8') + '">' +
          (move > 0 ? '+' + move : move === 0 ? '—' : move) + '</td></tr>';
    });

    host.innerHTML = '<table><thead><tr><th class="n">#</th><th>Initiative</th>' +
      '<th class="n">Holds up</th><th class="n">Enabled value</th><th class="n"></th>' +
      '<th class="n">Cost</th><th class="n">Standalone return</th>' +
      '<th class="n">Rank —<br>standalone</th><th class="n">Rank —<br>dependency-adjusted</th>' +
      '<th class="n">Change</th></tr></thead><tbody>' +
      rows.join('') + '</tbody></table>';

    host.querySelectorAll('tr[data-iid]').forEach(function (tr) {
      tr.addEventListener('click', function () { setFocus(tr.getAttribute('data-iid')); });
    });
  }

  /* ======================================================================
     2. VALUE - the two rankings side by side
     ======================================================================
     BUILD-BRIEF.md section 9. Left column: ranked by what each initiative
     returns on its own. Right column: ranked by what it holds up. Lines join
     the same initiative across both, so the movement is visible rather than
     described.

     The argument is not "we made a chart". It is "your existing ranking method
     would have cut the one thing everything else needs" - and that only lands
     if both rankings are on screen at once, which is why these are one view and
     not two.
     ====================================================================== */

  /* ======================================================================
     2a. VALUE REALISATION - when benefit actually reaches the P&L
     ======================================================================
     The fourth deliverable, and the board's third question. A stacked area over
     the full realisation horizon, four bands bottom to top in the order section
     6 sets: cost_reduction, cost_avoidance, revenue_growth, non_financial.

     Two things this has to be honest about, because both are findings rather
     than blemishes:
       * the gap is a RUN-RATE gap, not an actuals gap: $84.3m promised at
         steady state against the annual rate the plan has actually reached by
         the end of the window. Both are annual figures, so they compare
         directly. See _exit_run_rate for why the older actuals framing was
         retired.
       * the source data only carries 24 months of plan (to 2027-12) while the
         plans themselves run to 2029-2030. The boundary is marked so nobody
         reads the tail as measured rather than modelled.
     ====================================================================== */

  function renderValueRealisation() {
    var host = document.getElementById('valuecurve');
    if (!host) return;

    var r = App.result,
        curve = r._benefit_curve_full,
        asOfI = monthIndexOfKey(App.data.meta.as_of_month),
        dataEndI = App.engine.windowStartIndex + App.engine.windowMonths - 1,
        startI = monthIndexOfKey(curve[0].month);

    // Peak stacked height sets the scale.
    var peak = 0;
    curve.forEach(function (p) {
      var t = 0;
      BANDS.forEach(function (b) { t += p[b]; });
      if (t > peak) peak = t;
    });
    if (peak <= 0) peak = 1;

    var PAD_L = 74, PAD_R = 18, PAD_T = 18, PAD_B = 40,
        MW = 15,
        plotW = curve.length * MW,
        plotH = 232,
        W = PAD_L + plotW + PAD_R,
        H = PAD_T + plotH + PAD_B,
        p = [];

    function x(idx) { return PAD_L + idx * MW; }
    function y(v) { return PAD_T + plotH - (v / peak) * plotH; }

    // ---- y gridlines and money labels
    var steps = 4;
    for (var g = 0; g <= steps; g++) {
      var val = peak * g / steps, gy = y(val);
      p.push('<line class="gridline" x1="' + PAD_L + '" y1="' + gy + '" x2="' +
        (PAD_L + plotW) + '" y2="' + gy + '"/>');
      p.push('<text class="axis-t" x="' + (PAD_L - 8) + '" y="' + (gy + 3.5) +
        '" text-anchor="end">' + money(val) + '</text>');
    }

    // ---- stacked bands, bottom to top in the order section 6 specifies
    var base = curve.map(function () { return 0; });
    BANDS.forEach(function (band) {
      var top = [], d = [];
      curve.forEach(function (pt, i) { top[i] = base[i] + pt[band]; });
      d.push('M' + x(0) + ',' + y(base[0]));
      curve.forEach(function (pt, i) { d.push('L' + x(i) + ',' + y(top[i])); });
      for (var i = curve.length - 1; i >= 0; i--) d.push('L' + x(i) + ',' + y(base[i]));
      d.push('Z');
      p.push('<path d="' + d.join(' ') + '" fill="' + BAND_COLOUR[band] +
        '" opacity=".92"><title>' + esc(BAND_LABEL[band]) + '</title></path>');
      base = top;
    });

    // ---- month axis: a tick each January and July, year labels at January
    curve.forEach(function (pt, i) {
      var mm = pt.month.slice(5);
      if (mm !== '01' && mm !== '07') return;
      p.push('<line class="gridline' + (mm === '01' ? ' year' : '') + '" x1="' + x(i) +
        '" y1="' + PAD_T + '" x2="' + x(i) + '" y2="' + (PAD_T + plotH) + '"/>');
      p.push('<text class="axis-t" x="' + x(i) + '" y="' + (PAD_T + plotH + 13) +
        '" text-anchor="middle">' + (mm === '01' ? pt.month.slice(0, 4) : 'Jul') + '</text>');
    });

    // ---- the as-of boundary: everything right of it is plan, not measured
    var ax = x(asOfI - startI);
    p.push('<line class="today" x1="' + ax + '" y1="' + PAD_T + '" x2="' + ax +
      '" y2="' + (PAD_T + plotH) + '"/>');
    p.push('<text class="today-t" x="' + (ax + 4) + '" y="' + (PAD_T + 11) + '">TODAY</text>');

    // ---- the run-rate gap, drawn as two levels
    //
    // Deliberately NOT the $507-banked line that used to sit here. Drawing $507
    // on an axis scaled in millions renders it as zero and makes the same
    // retired claim visually that the text was corrected to stop making. What
    // matters is the gap between the monthly run rate this plan reaches and the
    // one it promises - both annual rates, directly comparable.
    var promisedMonthly = r._finance.benefit_promised / 12;
    if (promisedMonthly > 0 && promisedMonthly <= peak * 1.4) {
      p.push('<line x1="' + PAD_L + '" y1="' + y(promisedMonthly) + '" x2="' +
        (PAD_L + plotW) + '" y2="' + y(promisedMonthly) +
        '" stroke="#b91c1c" stroke-width="1.5" stroke-dasharray="5 3"/>');
      p.push('<text class="axis-t" x="' + (PAD_L + plotW - 4) + '" y="' +
        (y(promisedMonthly) - 5) + '" text-anchor="end" ' +
        'style="fill:#b91c1c;font-weight:700">promised run rate &mdash; ' +
        money(r._finance.benefit_promised) + ' a year</text>');
    }

    // ---- where the source data stops and the model takes over
    if (dataEndI < startI + curve.length - 1) {
      var dx = x(dataEndI - startI);
      p.push('<line x1="' + dx + '" y1="' + PAD_T + '" x2="' + dx + '" y2="' +
        (PAD_T + plotH) + '" stroke="#8494a8" stroke-width="1.5" stroke-dasharray="2 3"/>');
      p.push('<text class="axis-t" x="' + (dx + 4) + '" y="' + (PAD_T + plotH - 6) +
        '" style="font-weight:700">source data ends</text>');
    }

    host.innerHTML = svgWrap(W, H, p);

    // ---- legend
    var lg = document.getElementById('band-legend');
    if (lg) {
      lg.innerHTML = BANDS.slice().reverse().map(function (b) {
        return '<span><i style="background:' + BAND_COLOUR[b] + '"></i>' +
          esc(BAND_LABEL[b]) + '</span>';
      }).join('');
    }

    // ---- the numbers underneath
    //
    // Everything below is CUMULATIVE benefit to a stated date, except
    // `promised`, which is an annual run rate. Mixing the two is the easiest
    // way to mislead here: summing a monthly series over six years gives a
    // number several times the annual figure, and putting the two in one
    // sentence invites the reader to treat the larger as the bigger prize.
    var t = r.totals,
        promised = r._finance.benefit_promised,   // per YEAR at steady state
        inWindow = r._benefit_in_window,          // cumulative to 2027-12
        next12 = r._benefit_next_12,              // cumulative, 12 months
        steadyMonthly = promised / 12,
        steadyFrom = null;

    // The month the plan first reaches its promised run rate.
    for (var ci = 0; ci < curve.length; ci++) {
      var mt = 0;
      BANDS.forEach(function (b) { mt += curve[ci][b]; });
      if (mt >= steadyMonthly * 0.99) { steadyFrom = curve[ci].month; break; }
    }

    var why = document.getElementById('realise-why');
    if (why) {
      why.textContent = 'Planned benefit by month, stacked by type. ' +
        'Everything right of TODAY is forecast, not banked.';
    }

    var ro = document.getElementById('realise-readout');
    if (ro) {
      var exit = r._exit_run_rate,
          pct = promised ? Math.round(100 * exit / promised) : 0;
      ro.innerHTML =
        'The portfolio promises <b>' + money(promised) + ' a year</b> at steady state. ' +
        'By ' + fmtMonthYear(monthKeyOfIndex(dataEndI) + '-01') + ' this plan has ' +
        'reached an annual run rate of <b style="color:#b91c1c">' + money(exit) +
        '</b> &mdash; <b>' + pct + '% of the promise</b>' +
        (steadyFrom ? ', and does not reach the full rate until <b>' +
          fmtMonthYear(steadyFrom + '-01') + '</b>' : '') + '. ' +
        'Cumulative benefit landing inside the window is <b>' + money(inWindow) +
        '</b>, of which <b>' + money(next12) + '</b> falls in the next twelve months. ' +
        '<span class="muted">The board asked to see value inside twelve months.</span>';
    }

    // ---- band subtotals, so the mix is readable as numbers too
    var tail = document.getElementById('valuecurve-tail');
    if (tail) {
      var sub = [
        ['cost_reduction', t.benefit_cash_backed, 'cash-backed'],
        ['cost_avoidance', t.benefit_cost_avoidance, 'non-cash'],
        ['revenue_growth', t.benefit_revenue, 'cash-backed'],
        ['non_financial', t.benefit_non_financial, 'no P&amp;L line']
      ];
      tail.innerHTML = '<table><thead><tr><th>Value type</th>' +
        '<th class="n">A year at steady state</th><th class="n">Share</th>' +
        '<th>Reaches the P&amp;L?</th></tr></thead><tbody>' +
        sub.map(function (s) {
          return '<tr><td><span class="dot" style="background:' + BAND_COLOUR[s[0]] +
            '"></span> ' + esc(BAND_LABEL[s[0]]) + '</td>' +
            '<td class="n mono">' + money(s[1]) + '</td>' +
            '<td class="n mono">' + (promised ? Math.round(100 * s[1] / promised) : 0) + '%</td>' +
            '<td>' + (s[2] === 'cash-backed'
              ? '<span class="pill ok">yes, as cash</span>'
              : s[2] === 'non-cash'
                ? '<span class="pill warn">avoided, not banked</span>'
                : '<span class="pill mute">no</span>') + '</td></tr>';
        }).join('') +
        '<tr><td><b>Total promised</b></td><td class="n mono"><b>' + money(promised) +
        '</b></td><td class="n mono">100%</td><td class="muted">of which ' +
        money(t.benefit_cash_backed + t.benefit_revenue) + ' is cash</td></tr>' +
        '</tbody></table>';
    }
  }

  function renderValueChart() {
    var host = document.getElementById('valuechart');
    if (!host) return;

    // Only what this scenario funds: an initiative that has been cut is not in
    // the plan and does not belong in a ranking of the plan.
    var en = App.result._enabled;
    var funded = App.engine.initiatives.filter(function (i) {
      return en[i.initiative_id].funded;
    });

    var byOwn = funded.slice().sort(function (a, b) {
      return b.naive_roi - a.naive_roi || (a.initiative_id < b.initiative_id ? -1 : 1);
    });
    var byEnabled = funded.slice().sort(function (a, b) {
      return en[b.initiative_id].value - en[a.initiative_id].value ||
        en[b.initiative_id].count - en[a.initiative_id].count ||
        (a.initiative_id < b.initiative_id ? -1 : 1);
    });

    var leftRank = {}, rightRank = {};
    byOwn.forEach(function (i, n) { leftRank[i.initiative_id] = n; });
    byEnabled.forEach(function (i, n) { rightRank[i.initiative_id] = n; });

    var ROW = 15, PAD_T = 46, COL_W = 268, GAP = 236,
        W = COL_W * 2 + GAP + 40,
        H = PAD_T + byOwn.length * ROW + 26,
        xL = 20, xR = xL + COL_W + GAP,
        p = [];

    p.push('<text class="col-h" x="' + xL + '" y="22">RANKED BY WHAT IT RETURNS ON ITS OWN</text>');
    p.push('<text class="col-h" x="' + xL + '" y="36">best at the top &middot; ' +
      funded.length + ' funded in this scenario</text>');
    p.push('<text class="col-h" x="' + xR + '" y="22">RANKED BY WHAT IT HOLDS UP</text>');
    p.push('<text class="col-h" x="' + xR + '" y="36">most at the top &middot; ' +
      'counts only work this scenario still funds</text>');

    function yOf(rank) { return PAD_T + rank * ROW + ROW / 2; }

    // Movement lines first, so the labels sit on top of them.
    byOwn.forEach(function (i) {
      var y1 = yOf(leftRank[i.initiative_id]),
          y2 = yOf(rightRank[i.initiative_id]),
          isE = en[i.initiative_id].is_enabler,
          focus = App.focus === i.initiative_id,
          x1 = xL + COL_W - 4, x2 = xR + 4,
          mx = (x1 + x2) / 2;
      p.push('<path d="M' + x1 + ',' + y1 + ' C' + mx + ',' + y1 + ' ' + mx + ',' + y2 +
        ' ' + x2 + ',' + y2 + '" fill="none" stroke="' +
        (focus ? '#16202e' : isE ? '#dc2626' : '#c3ccd8') +
        '" stroke-width="' + (focus ? 2.4 : isE ? 1.8 : 0.8) + '" opacity="' +
        (focus ? 1 : isE ? 0.85 : (App.focus ? 0.12 : 0.4)) + '"/>');
    });

    function label(i, x, rank, right) {
      var e = en[i.initiative_id],
          y = yOf(rank), isE = e.is_enabler, focus = App.focus === i.initiative_id,
          dim = App.focus && !focus;
      var g = '<g class="dep-node" data-iid="' + i.initiative_id + '"' +
        (dim ? ' opacity=".3"' : '') + '>';
      g += '<rect x="' + x + '" y="' + (y - 6.5) + '" width="' + COL_W + '" height="13" rx="2" fill="' +
        (focus ? '#eaf0fb' : isE ? '#fdecec' : 'transparent') + '"/>';
      g += '<rect x="' + x + '" y="' + (y - 6.5) + '" width="3" height="13" fill="' +
        pillarColour(i) + '"/>';
      g += '<text class="slope-t' + (isE ? ' e' : '') + '" x="' + (x + 8) + '" y="' + (y + 3.5) + '">' +
        (rank + 1) + '. ' + esc(clip(i.name, right ? 28 : 26)) + '</text>';
      g += '<text class="slope-v" x="' + (x + COL_W - 5) + '" y="' + (y + 3.5) +
        '" text-anchor="end">' +
        (right ? money(e.value) : money(i.annual_benefit_target)) + '</text>';
      g += '<title>' + esc(i.name + '\nreturns ' + money(i.annual_benefit_target) +
        ' a year on its own\nholds up ' + e.count + ' initiatives worth ' + money(e.value) +
        ' in this scenario' +
        (e.is_enabler ? '\nENABLER - holds up ' + Math.round(e.multiple) +
          'x its own value' : '')) + '</title>';
      return g + '</g>';
    }

    byOwn.forEach(function (i) { p.push(label(i, xL, leftRank[i.initiative_id], false)); });
    byEnabled.forEach(function (i) { p.push(label(i, xR, rightRank[i.initiative_id], true)); });

    host.innerHTML = svgWrap(W, H, p);
    host.querySelectorAll('g[data-iid]').forEach(function (g) {
      g.addEventListener('click', function () { setFocus(g.getAttribute('data-iid')); });
    });

    var lg = document.getElementById('value-legend');
    if (lg) {
      lg.innerHTML = '<span><i style="background:#dc2626"></i>enabler</span>' +
        '<span><i style="background:#c3ccd8"></i>everything else</span>';
    }

    var vw = document.getElementById('value-why');
    if (vw) {
      vw.innerHTML = 'The ' + funded.length + ' initiatives this scenario funds, ranked ' +
        'two ways. The lines show how far each one moves between them.';
    }

    var ro = document.getElementById('value-readout');
    if (ro) {
      var worst = byOwn[byOwn.length - 1], we = en[worst.initiative_id],
          dropped = 60 - funded.length;
      ro.innerHTML = '<b>' + esc(worst.name) + '</b> is <b>last of ' + funded.length +
        '</b> on what it returns on its own &mdash; ' + money(worst.total_budget) +
        ' spent for ' + money(worst.annual_benefit_target) + ' a year. Any spreadsheet ' +
        'cuts it first. It holds up <b>' + we.count + ' initiatives carrying ' +
        money(we.value) + '</b>, which moves it to <b>' +
        ordinal(rightRank[worst.initiative_id] + 1) + '</b>. ' +
        (dropped ? '<span class="muted">' + dropped + ' initiatives are not funded in ' +
          'this scenario, so they are absent from both columns and no longer counted in ' +
          'what anything holds up.</span> ' : '') +
        '<span class="muted">Red lines are enablers. Click any row to trace one.</span>';
    }
  }

  function ordinal(n) {
    var s = ['th', 'st', 'nd', 'rd'], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  /* ======================================================================
     3. RISK
     ====================================================================== */

  function renderRiskTable() {
    var host = document.getElementById('risktable');
    if (!host) return;

    // Only initiatives this scenario funds. Three of the 27 in trouble are not
    // funded under SC-02, and listing work that has been cut as needing
    // attention would send someone to fix something that no longer exists.
    var mf = mustFixIds();
    var list = inTroubleList().sort(function (a, b) {
      return (b.rollup.max_risk_score - a.rollup.max_risk_score) ||
        (b.rollup.total_risk_exposure - a.rollup.total_risk_exposure);
    });

    var note = document.getElementById('risk-note');
    if (note) {
      var exposed = list.reduce(function (a, i) { return a + i.rollup.total_risk_exposure; }, 0);
      note.innerHTML = list.length + ' initiatives &middot; ' + money(exposed) + ' exposed';
    }

    if (!list.length) {
      host.innerHTML = '<div class="empty">Nothing rated in trouble in this scenario.</div>';
      return;
    }

    var rows = list.map(function (i) {
      var r = i.rollup, sel = App.focus === i.initiative_id;
      return '<tr class="click' + (sel ? ' sel' : '') + '" data-iid="' + i.initiative_id + '">' +
        '<td><span class="dot" style="background:' + (RAG_COLOUR[i.rag_status] || '#94a3b8') +
          '"></span> ' + esc(statusWord(i.rag_status)) + '</td>' +
        '<td>' + esc(clip(i.name, 38)) +
          (i.is_regulatory ? ' <span class="pill bad">regulatory</span>' : '') +
          (enOf(i.initiative_id).is_enabler ? ' <span class="pill warn">enabler</span>' : '') + '</td>' +
        '<td>' + esc(i.stage) + '</td>' +
        '<td class="n">' + i.percent_complete + '%</td>' +
        '<td class="n mono">' + r.max_risk_score + ' / 25</td>' +
        '<td class="n mono">' + money(r.total_risk_exposure) + '</td>' +
        '<td class="n">' + (r.open_issue_count || '—') + '</td>' +
        '<td class="n mono">' + (r.total_slip_days > 0 ? r.total_slip_days + ' days' : '—') + '</td>' +
        '<td class="n mono">' + money(i.forecast_at_completion - i.total_budget) + '</td>' +
        '<td>' + (mf[i.initiative_id] ? '<span class="pill bad">MUST FIX</span>' : '') + '</td></tr>';
    });

    host.innerHTML = '<table><thead><tr><th>Health</th><th>Initiative</th><th>Stage</th>' +
      '<th class="n">Done</th><th class="n">Worst risk</th><th class="n">Exposed</th>' +
      '<th class="n">Open issues</th><th class="n">Slipped</th><th class="n">Over budget</th>' +
      '<th></th></tr></thead><tbody>' + rows.join('') + '</tbody></table>';

    host.querySelectorAll('tr[data-iid]').forEach(function (tr) {
      tr.addEventListener('click', function () { setFocus(tr.getAttribute('data-iid')); });
    });
  }

  /* ======================================================================
     4. COMPLIANCE & REGULATORY
     ====================================================================== */

  function renderComplianceView() {
    var host = document.getElementById('regtable'),
        riskHost = document.getElementById('regrisktable');
    if (!host) return;

    var reg = App.engine.initiatives.filter(function (i) { return i.is_regulatory; });
    var breaches = {};
    App.result.violations.forEach(function (v) {
      if (v.type === 'compliance') breaches[v.initiative_id] = v;
    });
    var seq = App.result._seq, included = App.result._selection.included;

    var note = document.getElementById('reg-note');
    if (note) {
      var n = Object.keys(breaches).length;
      note.innerHTML = reg.length + ' regulatory initiatives &middot; <b>' + n +
        ' in breach</b>';
      note.className = 'pill ' + (n ? 'bad' : 'ok');
    }

    var ro = document.getElementById('reg-readout');
    if (ro) {
      var deferredReg = reg.filter(function (i) { return !included[i.initiative_id]; }).length;
      ro.innerHTML = '<b>' + Object.keys(breaches).length + ' of ' + reg.length +
        '</b> regulatory initiatives are in breach in this scenario. <b>' + deferredReg +
        '</b> have been dropped &mdash; regulatory work is locked and cannot be traded ' +
        'away to meet a spending ceiling, so a ceiling that only works by cutting it is ' +
        'reported as unworkable instead. <span class="muted">Breaches always sort above ' +
        'every other kind of problem, however large.</span>';
    }

    var rows = reg.sort(function (a, b) {
      return (breaches[b.initiative_id] ? 1 : 0) - (breaches[a.initiative_id] ? 1 : 0) ||
        (b.rollup.open_regulatory_risk_exposure - a.rollup.open_regulatory_risk_exposure) ||
        (a.initiative_id < b.initiative_id ? -1 : 1);
    }).map(function (i) {
      var b = breaches[i.initiative_id], row = seq[i.initiative_id],
          sel = App.focus === i.initiative_id;
      return '<tr class="click' + (sel ? ' sel' : '') + '" data-iid="' + i.initiative_id + '">' +
        // "No breach" rather than "compliant": it means this initiative trips
        // none of the four rules in section 7, not that all is well with it.
        // INIT-016 is regulatory, in flight and rated in trouble - no breach,
        // but nobody should read that as healthy. Its health shows two columns
        // along, and it appears in the Risk view.
        '<td>' + (b ? '<span class="pill bad">IN BREACH</span>'
                    : '<span class="pill ok">no breach</span>') + '</td>' +
        '<td>' + esc(clip(i.name, 36)) +
          (enOf(i.initiative_id).is_enabler ? ' <span class="pill warn">enabler</span>' : '') + '</td>' +
        '<td>' + esc(i.stage) + '</td>' +
        '<td><span class="dot" style="background:' + (RAG_COLOUR[i.rag_status] || '#94a3b8') +
          '"></span> ' + esc(statusWord(i.rag_status)) + '</td>' +
        '<td class="n">' + enOf(i.initiative_id).count + '</td>' +
        '<td class="n mono">' + fmtMonthYear(i.end_date) + '</td>' +
        '<td class="n mono' + (row.end > i.end_date ? ' late' : '') + '">' +
          fmtMonthYear(row.end) + '</td>' +
        '<td>' + (b ? esc(b.rules.join(', ')) : '—') + '</td>' +
        '<td class="n mono">' + (i.rollup.open_regulatory_risk_exposure
          ? money(i.rollup.open_regulatory_risk_exposure) : '—') + '</td></tr>';
    });

    host.innerHTML = '<table><thead><tr><th>Status</th><th>Initiative</th><th>Stage</th>' +
      '<th>Health</th><th class="n">Holds up</th><th class="n">Committed</th>' +
      '<th class="n">Now finishes</th><th>Why it is in breach</th>' +
      '<th class="n">Own regulatory exposure</th></tr></thead><tbody>' +
      rows.join('') + '</tbody></table>';

    host.querySelectorAll('tr[data-iid]').forEach(function (tr) {
      tr.addEventListener('click', function () { setFocus(tr.getAttribute('data-iid')); });
    });

    // ---- where the regulatory exposure actually sits ---------------------
    if (!riskHost) return;
    var regRisks = App.data.risks.filter(function (r) { return r.category === 'Regulatory'; })
      .sort(function (a, b) { return b.exposure_usd - a.exposure_usd; });
    var open = regRisks.filter(function (r) { return r.status !== 'Closed'; });
    var onRegulatory = regRisks.filter(function (r) {
      return App.engine.byId[r.initiative_id].is_regulatory;
    });

    // The register itself is a property of the business, not of a funding
    // choice - the same 14 risks exist whichever scenario is picked. What DOES
    // move is how much of that exposure sits on work the scenario has cut,
    // which is the scenario-relevant fact and the reason this panel responds.
    var onUnfunded = regRisks.filter(function (r) {
      return !included[r.initiative_id];
    });
    var unfundedExposure = onUnfunded.reduce(function (a, r) { return a + r.exposure_usd; }, 0);
    // Distinct initiatives, not risk rows - several risks can sit on one.
    var unfundedCarriers = {};
    onUnfunded.forEach(function (r) { unfundedCarriers[r.initiative_id] = 1; });
    var carrierCount = Object.keys(unfundedCarriers).length;

    var rn = document.getElementById('regrisk-note');
    if (rn) {
      rn.innerHTML = regRisks.length + ' regulatory risks &middot; ' +
        money(regRisks.reduce(function (a, r) { return a + r.exposure_usd; }, 0)) +
        ' &middot; <b>' + open.length + ' still open</b>' +
        (onUnfunded.length ? ' &middot; <b>' + money(unfundedExposure) +
          ' on unfunded work</b>' : '');
      rn.className = 'pill ' + (onUnfunded.length ? 'bad' : 'mute');
    }

    riskHost.innerHTML =
      '<div class="finding">Only <b>' + onRegulatory.length + ' of ' + regRisks.length +
      '</b> regulatory risks sit on an initiative anyone has classified as regulatory. ' +
      'The other <b>' + (regRisks.length - onRegulatory.length) + '</b> are being carried by ' +
      'work nobody is treating as a compliance obligation &mdash; which is a finding in ' +
      'its own right.</div>' +
      (onUnfunded.length
        ? '<div class="finding">In this scenario <b>' + money(unfundedExposure) +
          '</b> of regulatory exposure across <b>' + onUnfunded.length + ' risk' +
          (onUnfunded.length === 1 ? '' : 's') + '</b> sits on <b>' + carrierCount +
          '</b> initiative' + (carrierCount === 1 ? '' : 's') +
          ' this scenario does not fund. Cutting the work does not cut the ' +
          'obligation.</div>'
        : '') +
      '<table><thead><tr><th>Risk</th><th>Sits on</th><th class="n">Score</th>' +
      '<th class="n">Exposed</th><th>Status</th><th>Classified regulatory?</th>' +
      '<th>Funded here?</th></tr></thead><tbody>' + regRisks.map(function (r) {
        var i = App.engine.byId[r.initiative_id], isFunded = !!included[r.initiative_id];
        return '<tr class="click" data-iid="' + r.initiative_id + '">' +
          '<td>' + esc(clip(r.title, 42)) + '</td>' +
          '<td>' + esc(clip(i.name, 30)) + '</td>' +
          '<td class="n mono">' + r.score + ' / 25</td>' +
          '<td class="n mono">' + money(r.exposure_usd) + '</td>' +
          '<td>' + esc(r.status) + '</td>' +
          '<td>' + (i.is_regulatory ? '<span class="pill ok">yes</span>'
                                    : '<span class="pill bad">no</span>') + '</td>' +
          '<td>' + (isFunded ? '<span class="pill ok">yes</span>'
                             : '<span class="pill bad">not funded</span>') + '</td></tr>';
      }).join('') + '</tbody></table>';

    riskHost.querySelectorAll('tr[data-iid]').forEach(function (tr) {
      tr.addEventListener('click', function () { setFocus(tr.getAttribute('data-iid')); });
    });
  }

  /* ======================================================================
     Headline figures - BUILD-BRIEF.md section 11
     ====================================================================== */

  function renderKpis() {
    var host = document.getElementById('kpis');
    if (!host) return;
    var t = App.data.totals, d = App.result._dependency_summary,
        s = App.result._schedule, r = App.result;

    function kpi(k, v, sub, cls) {
      return '<div class="kpi' + (cls ? ' ' + cls : '') + '"><div class="k">' + k +
        '</div><div class="v">' + v + '</div><div class="s">' + sub + '</div></div>';
    }

    // Five tiles. Each answers ONE question an executive actually asks, with the
    // answer as the headline number and one line saying why it matters. The
    // previous version showed eight measurements and made the reader work out
    // which mattered - the overspend was grey small print under the budget.
    var fin = r._finance, pinch = pinchRoles();

    host.innerHTML = [
      kpi('Budget vs spend',
        fin.overspend > 0 ? money(fin.overspend) + ' over' : money(-fin.overspend) + ' under',
        money(fin.budget) + ' approved &middot; ' + money(fin.forecast) + ' now forecast' +
        (r._included_count < 60
          ? '<br>' + (60 - r._included_count) + ' of 60 initiatives not funded' : ''),
        fin.overspend > 0 ? 'warn' : ''),

      // Like-for-like: an annual run rate against an annual promise. Never the
      // promise against benefit banked to date - see _exit_run_rate.
      kpi('Benefits promised', money(fin.benefit_promised) + ' a year',
        'By ' + fmtMonthYear(monthKeyOfIndex(App.engine.windowStartIndex +
          App.engine.windowMonths - 1) + '-01') + ' the plan reaches <b>' +
        money(r._exit_run_rate) + ' a year</b> &mdash; ' +
        (fin.benefit_promised
          ? Math.round(100 * r._exit_run_rate / fin.benefit_promised) : 0) +
        '% of the promise.',
        r._exit_run_rate < fin.benefit_promised * 0.6 ? 'warn' : ''),

      kpi('Finish date', fmtMonthYear(s.latest_end),
        s.breaches_deadline
          ? '<b>' + humanDuration(s.days_past_deadline) + ' past</b> the ' +
            fmtMonthYear(s.must_finish_by) + ' deadline'
          : 'inside the ' + fmtMonthYear(s.must_finish_by) + ' deadline',
        s.breaches_deadline ? 'warn' : ''),

      kpi('Work out of order', d.violated + ' of ' + d.edges,
        d.blocking
          ? '<b>' + d.blocking + ' cannot be worked around.</b> Worst starts ' +
            humanDuration(d.worst_blocking) + ' too early.'
          : 'None of them on a link that cannot be broken',
        d.blocking ? 'warn' : ''),

      kpi('People needed', people(r.totals.peak_fte) + ' at peak',
        pinch.length
          ? '<b>' + pinch.length + ' roles oversubscribed</b> &middot; worst is ' +
            pinch[0].role + ' at ' + Math.round(pinch[0].pct) + '%'
          : 'every role inside capacity',
        pinch.length ? 'warn' : '')
    ].join('');

    renderHealthBar();
  }

  /* The roles that cannot staff the plan as sequenced, worst first. */
  function pinchRoles() {
    var u = App.result._resource.utilisation, worst = {}, k, role, pct;
    for (k in u) {
      if (!Object.prototype.hasOwnProperty.call(u, k)) continue;
      if (u[k] <= 100) continue;
      role = k.split('|')[0];
      pct = u[k];
      if (!worst[role] || pct > worst[role]) worst[role] = pct;
    }
    return Object.keys(worst).map(function (r) { return { role: r, pct: worst[r] }; })
      .sort(function (a, b) { return b.pct - a.pct; });
  }

  /* Health as a slim bar rather than a tile - it is context, not a decision.
     "RAG" never reaches the screen. */
  function renderHealthBar() {
    var el = document.getElementById('healthbar');
    if (!el) return;
    var c = App.data.totals.rag_counts, total = c.Green + c.Amber + c.Red;
    var seg = [['Green', 'On track'], ['Amber', 'At risk'], ['Red', 'In trouble']];

    el.innerHTML = '<div class="hb-label">Initiative health</div>' +
      '<div class="hb-track">' + seg.map(function (s) {
        return '<span class="hb-seg" style="width:' + (100 * c[s[0]] / total) +
          '%;background:' + RAG_COLOUR[s[0]] + '" title="' + s[1] + ': ' +
          c[s[0]] + '"></span>';
      }).join('') + '</div>' +
      '<div class="hb-keys">' + seg.map(function (s) {
        return '<span><i style="background:' + RAG_COLOUR[s[0]] + '"></i>' +
          s[1] + ' <b>' + c[s[0]] + '</b></span>';
      }).join('') + '</div>';
  }

  /* ======================================================================
     Scenario comparison strip (the toggle)
     ====================================================================== */

  function renderCompare() {
    var host = document.getElementById('cmp-body'),
        panel = document.getElementById('compare');
    if (!host || !panel) return;
    panel.hidden = !App.compare;

    // The content is always rebuilt, even while the panel is collapsed. Bailing
    // out early here would leave the previous scenario's numbers sitting in the
    // DOM, so switching scenario with the panel shut and then reopening it would
    // show stale figures. Rebuilding is cheap - the results are cached.

    var ids = App.engine.scenarios.map(function (s) { return s.scenario_id; });

    host.innerHTML = ids.map(function (id) {
      var r = resultFor(id), c = r._scenario.constraints, t = r.totals,
          d = r._dependency_summary, s = r._schedule, vc = r._violation_counts,
          inWindow = 0;
      r.benefit_curve.forEach(function (p) {
        BANDS.forEach(function (b) { inWindow += p[b]; });
      });

      function row(k, v, cls) {
        return '<div class="cmp-row"><dt>' + k + '</dt><dd' +
          (cls ? ' class="' + cls + '"' : '') + '>' + v + '</dd></div>';
      }
      function head(k) { return '<div class="cmp-row head"><dt>' + k + '</dt><dd></dd></div>'; }

      return '<div class="cmp-col' + (id === App.scenarioId ? ' active' : '') + '">' +
        '<h3>' + esc(r._scenario.name) +
        '<small>' + esc(clip(r._scenario.description, 96)) + '</small></h3><dl>' +
        head('What is in it') +
        row('Initiatives funded', r._included_count + ' of 60') +
        row('Moved to fix order', c.allow_resequencing
          ? s.resequenced_count + ' initiatives' : 'not allowed to move') +
        head('What it costs') +
        row('Total spend', money(t.budget) + (c.budget_cap_usd
          ? ' <span class="muted">of ' + money(c.budget_cap_usd) + '</span>' : ''),
          c.budget_cap_usd && t.budget > c.budget_cap_usd ? 'bad' : 'ok') +
        row('Capital', money(t.capex) + (c.capex_cap_usd
          ? ' <span class="muted">of ' + money(c.capex_cap_usd) + '</span>' : ''),
          c.capex_cap_usd && t.capex > c.capex_cap_usd ? 'bad' : 'ok') +
        row('People at peak', people(t.peak_fte) + (c.peak_fte_cap
          ? (unreconciledFteCap(c.peak_fte_cap, t.peak_fte)
              ? ' <span class="muted">ceiling says ' + c.peak_fte_cap + ' &mdash; not reconciled</span>'
              : ' <span class="muted">of ' + c.peak_fte_cap + '</span>')
          : ''),
          c.peak_fte_cap && t.peak_fte > c.peak_fte_cap ? 'bad' : 'ok') +
        head('What it returns, a year') +
        row('Cash savings', money(t.benefit_cash_backed)) +
        row('Costs avoided (not cash)', money(t.benefit_cost_avoidance)) +
        row('New revenue', money(t.benefit_revenue)) +
        row('Capability &amp; risk (no P&amp;L line)', money(t.benefit_non_financial)) +
        head('When the value lands') +
        row('Run rate reached by 2027', money(r._exit_run_rate) +
          ' <span class="muted">of ' + money(r._finance.benefit_promised) + '</span>',
          r._exit_run_rate < r._finance.benefit_promised * 0.6 ? 'bad' : 'ok') +
        row('Next twelve months', money(r._benefit_next_12),
          r._benefit_next_12 < 3000000 ? 'bad' : 'ok') +
        row('Cumulative inside two years', money(inWindow)) +
        head('What it breaks') +
        row('Dependencies out of order', d.violated + (d.blocking
          ? ' <span class="muted">(' + d.blocking + ' unfixable)</span>' : ''),
          d.blocking ? 'bad' : 'ok') +
        row('Worst that cannot be moved', d.worst_blocking
          ? humanDuration(d.worst_blocking) : 'none', d.worst_blocking ? 'bad' : 'ok') +
        row('Roles oversubscribed', vc.resource || 0) +
        row('Initiatives overspending', vc.budget || 0) +
        row('Finishes', fmtMonthYear(s.latest_end) + (s.breaches_deadline
          ? ' <span class="muted">(' + humanDuration(s.days_past_deadline) + ' late)</span>'
          : ''), s.breaches_deadline ? 'bad' : 'ok') +
        '</dl></div>';
    }).join('');
  }

  /* ======================================================================
     Legends, chrome, wiring
     ====================================================================== */

  function renderLegends() {
    // The pillar legend carries the client's own board-approved wording,
    // including the strategic-objective number, so every bar on screen traces
    // back to an objective the board already signed off.
    var pillarHtml = PILLAR_META.map(function (p) {
      return '<span title="' + esc(p.so + ' - ' + p.meaning) + '"><i style="background:' +
        p.colour + '"></i>' + esc(p.so + ' ' + p.key) +
        ' <span class="muted">' + esc(p.meaning) + '</span></span>';
    }).join('');

    ['fn-legend', 'pillar-legend'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = pillarHtml;
    });

    var dl = document.getElementById('dep-legend');
    if (dl) {
      dl.innerHTML =
        '<span><i style="background:#dc2626"></i>out of order, cannot be fixed by moving</span>' +
        '<span><i style="background:#f0a742"></i>out of order, could be broken</span>' +
        '<span><i style="background:#c3ccd8"></i>correctly ordered</span>' +
        '<span><i style="background:#e2e8f0;border:1px dashed #c3ccd8"></i>not funded</span>' +
        '<span><i style="background:#6d28d9;box-shadow:inset 0 0 0 1.4px #fff"></i>regulatory</span>';
    }
  }

  function renderChrome() {
    var asof = document.getElementById('asof');
    if (asof) {
      asof.innerHTML = 'As at <b>' + App.data.meta.as_of_month + '</b> &middot; all figures <b>USD</b><br>' +
        'Blank months after ' + App.data.meta.as_of_month +
        ' are future, not missing &mdash; nothing is imputed.';
    }

    var pick = document.getElementById('scenario-pick');
    if (pick && !pick.dataset.built) {
      pick.innerHTML = App.engine.scenarios.map(function (s) {
        return '<button data-sid="' + s.scenario_id + '" aria-pressed="' +
          (s.scenario_id === App.scenarioId ? 'true' : 'false') + '" title="' +
          esc(s.description) + '">' + s.scenario_id + ' ' + esc(s.name) + '</button>';
      }).join('');
      pick.dataset.built = '1';
      pick.querySelectorAll('button').forEach(function (b) {
        b.addEventListener('click', function () { setScenario(b.getAttribute('data-sid')); });
      });
    }
    if (pick) {
      pick.querySelectorAll('button').forEach(function (b) {
        b.setAttribute('aria-pressed', b.getAttribute('data-sid') === App.scenarioId ? 'true' : 'false');
      });
    }

    var ct = document.getElementById('cmp-toggle');
    if (ct && !ct.dataset.wired) {
      ct.dataset.wired = '1';
      ct.addEventListener('click', function () {
        App.compare = !App.compare;
        ct.setAttribute('aria-pressed', App.compare ? 'true' : 'false');
        renderCompare();
        if (App.compare) document.getElementById('compare')
          .scrollIntoView({ block: 'start', behavior: 'smooth' });
      });
    }

    // The leader / board tab pair is gone in the prototype. Navigation is now
    // the four view buttons alone, and the scenario comparison strip covers the
    // board-level question of which scenario to pick.
  }

  /* ---- scenario switch: re-render everything from the same engine, no reload */

  function setScenario(id) {
    App.scenarioId = id;
    App.result = resultFor(id);
    render();
  }

  function renderViewSwitcher() {
    var nav = document.getElementById('views');
    if (!nav) return;
    var counts = viewCounts();

    nav.innerHTML = VIEWS.map(function (v) {
      var c = counts[v.key];
      return '<button role="tab" data-view="' + v.key + '" aria-selected="' +
        (App.view === v.key ? 'true' : 'false') + '" title="' + esc(v.hint) + '">' +
        esc(v.label) +
        (c ? ' <span class="n' + (c.bad ? ' bad' : '') + '">' + c.n + '</span>' : '') +
        '</button>';
    }).join('');

    nav.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        App.view = b.getAttribute('data-view');
        render();
      });
    });

    VIEWS.forEach(function (v) {
      var el = document.getElementById(v.id);
      if (el) el.hidden = App.view !== v.key;
    });
  }

  /* The badge on each view button: the number that tells you whether the view
     needs you. Red when it does.

     Every badge is derived from the CURRENT SCENARIO. An earlier version read
     the portfolio-wide enabler count here, so the Value badge sat at 11 in all
     three scenarios while the view beneath it showed 9 - the exact mismatch
     that makes a reader stop trusting a screen.

     Risk counts initiatives in trouble rather than must-fix problems, because
     must-fix includes the compliance items and the Risk and Compliance badges
     would then show the same 8 twice over. */

  function viewCounts() {
    var r = App.result, vc = r._violation_counts,
        inTrouble = inTroubleList().length,
        enablers = r._enabled._enabler_count;
    return {
      current: { n: r._included_count, bad: false },
      value:   { n: enablers, bad: false },
      risk:    { n: inTrouble, bad: inTrouble > 0 },
      compliance: { n: vc.compliance || 0, bad: (vc.compliance || 0) > 0 }
    };
  }

  /* Funded initiatives rated in trouble, at risk, or paused. Shared by the Risk
     view and its badge so the two can never disagree. */
  function inTroubleList() {
    var included = App.result._selection.included;
    return App.engine.initiatives.filter(function (i) {
      return included[i.initiative_id] &&
        (i.rag_status === 'Red' || i.stage === 'At Risk' || i.stage === 'Paused');
    });
  }

  function render() {
    renderChrome();
    renderViewSwitcher();
    renderLegends();
    renderKpis();
    renderCompare();

    // Only the active view is rendered. Building all four every time would draw
    // several thousand SVG nodes for panels nobody is looking at.
    if (App.view === 'current') {
      renderRoadmap();
      renderDependencyGraph();
    } else if (App.view === 'value') {
      renderValueRealisation();
      renderValueChart();
      renderUnblocks();
    } else if (App.view === 'risk') {
      renderRiskTable();
      renderExceptions();
    } else if (App.view === 'compliance') {
      renderComplianceView();
    }
  }

  function boot(url) {
    return loadPortfolio(url).then(function (data) {
      App.data = data;
      App.engine = new Engine(data);
      App.result = resultFor(App.scenarioId);
      render();
      console.log('Roadmap ready: ' + data.initiatives.length + ' initiatives, ' +
        data.dependencies.length + ' dependencies, scenario ' + App.scenarioId);
      return App;
    });
  }

  global.Roadmap = {
    Engine: Engine,
    loadPortfolio: loadPortfolio,
    boot: boot,
    App: App,
    setScenario: setScenario,
    setFocus: setFocus,
    PILLAR_META: PILLAR_META,
    PILLAR_COLOUR: PILLAR_COLOUR,
    RAG_COLOUR: RAG_COLOUR,
    BAND_COLOUR: BAND_COLOUR,
    TYPE_LABEL: TYPE_LABEL,
    fmtMonthYear: fmtMonthYear,
    humanDuration: humanDuration,
    // helpers the views and the self-test need
    BANDS: BANDS,
    BAND_LABEL: BAND_LABEL,
    BAND_BY_BENEFIT_TYPE: BAND_BY_BENEFIT_TYPE,
    BAND_BY_PNL_TYPE: BAND_BY_PNL_TYPE,
    PNL_BY_BENEFIT_TYPE: PNL_BY_BENEFIT_TYPE,
    TYPE_ORDER: TYPE_ORDER,
    sortViolations: sortViolations,
    sCurveWeights: sCurveWeights,
    benefitRampFraction: benefitRampFraction,
    pyRound: pyRound,
    monthIndexOfISO: monthIndexOfISO,
    monthIndexOfKey: monthIndexOfKey,
    monthKeyOfIndex: monthKeyOfIndex,
    quarterOfKey: quarterOfKey,
    addDaysISO: addDaysISO,
    daysBetweenISO: daysBetweenISO,
    parseISO: parseISO,
    isoOf: isoOf,
    fmtInt: fmtInt,
    money: money
  };

}(typeof window !== 'undefined' ? window : globalThis));
