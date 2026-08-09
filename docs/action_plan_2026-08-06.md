# Action plan, 6 August 2026

Written against the current code base after the supervisor meeting
(`supervisor_meeting_2026-08-06.md`). Model integration deadline is 16 August,
so this is a ten-day plan.

> **Dated document.** The counts and status below describe the repository on
> 6 August 2026 and are deliberately not kept current, so the plan can be read
> against the state it was written for. Two things have moved since and matter
> for anything in this plan: the EU CBAM mechanism was switched to
> `benchmark_shielded` on 7 August 2026 (Samir's decision, settled on the law
> rather than by a supervisor ruling), and the benchmark itself was corrected on
> 8 August, which between them removed hydrogen's corridor crossover, its
> lock-in reversal and the competitiveness divergence; and the test suite has
> grown past 200. Use `README.md`, `docs/findings_2026-08-08.md` and the test
> suite for current state.

## Where the code actually stands

- 168 tests pass. `cbam_model` is ~6,040 lines across config, model, analysis,
  validation.
- `analysis.outputs.write_all` produces 17 artefacts including
  `corridor_cost_comparison.csv`, `corridor_crossover_year.csv`,
  `pathway_cost_ranking.csv`, `marginal_abatement_cost.csv`,
  `abatement_breakeven_year.csv` and two sensitivity rankings.
- `dashboard.py` has four tabs: compliance, maritime, sensitivity, and the
  pathway/corridor choice tab added 6 August.
- The scenario matrix already carries a policy-uncertainty dimension
  (`UK_ETS_VARIANTS`, labelled as not-law in `VARIANT_LABELS`).

The model is not the weak point. The weak points are (a) two known regulatory
inaccuracies that are now sourceable from public data, and (b) nothing in the
code speaks to the theory Frano wants.

---

## P1. Fix the EU CBAM functional form

`README.md` item 1. The model computes `chargeable = embedded x CBAM_factor`.
Regulation (EU) 2023/956 Art. 31 adjusts for free allocation measured against a
product benchmark, so the correct form is
`max(0, embedded - benchmark x (1 - CBAM_factor))`. The two only converge in
2034.

This is the single largest examiner risk in the repo: a documented, known
deviation from the governing regulation, in the chapter the dissertation is
named after.

Both forms already sit side by side in `validation/reference_case.py`, and the
benchmark form reproduces Ramsook et al.'s published 22% burden at 20.7% against
14.5% for the current form. So the machinery exists. The only blocker is that the
hard-coded benchmarks (ammonia 1.570, hydrogen 6.84, from IR 2021/447) are the
2021-2025 set, and the Commission adopted revised 2026-2030 benchmarks on
29 June 2026.

**Do:** source the revised benchmarks from the Official Journal, put them in
`config/regulatory_constants.py` with the IR citation and adoption date, switch
`model/cbam.py` to the benchmark form, and keep the old form reachable as a
labelled variant so the results chapter can show both.

This is now firmly a public-data task, which is exactly the kind of work that
replaces the dead MCG data route.

**Risk if skipped:** individual CBAM figures are wrong throughout. The headline
finding (production cost gap dwarfs the CBAM differential) survives either way,
per the existing side-by-side, but "we knew and didn't fix it" is worse than
"we fixed it late."

## P2. Give the UK ETS price a real path

`README.md` item 5, and the standing open item in memory. The UK ETS price is
held flat across 2026-2030 while the EU price rises 58%. Only the 2026 figure
(GBP 49.41/tCO2e, UK ETS Authority determination) was ever sourced.

The headline result that the UK corridor overtakes the EU one by 2030 is
directionally safe because UK is the *understated* side, but a flat five-year
price on one of two compared corridors is an obvious viva target.

**Do:** source UKA December futures settlement prices per scheme year for the
low/medium/high anchors, mirroring how the EU anchors are built. If a defensible
five-year path cannot be sourced, promote the existing EU-UK linkage variant to a
labelled headline scenario rather than leaving flat as the silent default.

## P3. Put the theory into the model

This is where the marks are, and Frano said it explicitly: if the institutional
and transaction-cost layer can go into the model, it becomes more interesting.

Right now `corridor_crossover_year` answers "when does the UK corridor become
more expensive than the EU one." It implicitly assumes switching is free and
instantaneous. Frano's whole point is that it is not: route concessions and
transport rights, port access and berthing, insurance, ~10-year contract tenor,
and fixed shore infrastructure that cannot be relocated.

**Do:** add a lock-in module, e.g. `model/switching.py` plus
`analysis/outputs.corridor_switch_decision`, that takes:

- a switching cost (asset-specific sunk cost of moving corridor or pathway)
- remaining contract tenor, defaulting to 10 years
- a discount rate

and reports whether the cost crossover is actually *actionable*: does the
discounted saving over remaining tenor exceed the sunk cost? Output a
`switch_justified` / `locked_in` verdict alongside the existing crossover year.

Two reasons this is high value:

1. It operationalises TCE asset specificity directly, so the discussion chapter
   has a mechanism to explain rather than a theory bolted onto results.
2. It very plausibly produces a *counterintuitive* result: a corridor that the
   pure cost model says you should switch to, that lock-in says you should not.
   Frano defined contribution as exactly this kind of finding.

Treat the switching cost as a swept parameter with a stated range, not a single
sourced number. The finding is the threshold at which the verdict flips, which is
a defensible result even without a precise cost figure.

## P4. Wire Alex's policy timeline into the scenario matrix

Alex's Track B is quantified per-date policy impacts ("+5% from this date").
The model already has the pattern for this: `UK_ETS_VARIANTS` with
`VARIANT_LABELS` captioning it as not-law.

**Do:** generalise that one-off into a small dated policy-event table that maps
each of Alex's Track B entries onto a model parameter, an effective date and a
delta, with the instrument classification (primary legislation / statutory
instrument / non-binding plan / pending approval) carried through as a
confidence field. Then the results chapter can show cost paths under
legislated-only versus legislated-plus-proposed.

This is the join between Alex's chapter and the model, and it is currently
missing. It also makes the institutional-theory argument empirical rather than
descriptive.

Scope guard: if this looks like more than a day, do the two-scenario version
(legislated only vs legislated plus proposed) and put the full event table in
the appendix.

## P5. Decide and document the conversion and freight cost gap

`README.md` item 4, no owner assigned. These two terms are invariant to
production pathway, so they cancel out of every within-corridor comparison and
do not block the marginal abatement results.

**Do:** either source them publicly, or write them up explicitly as a stated
scope boundary in methodology. Do not leave them as an unowned open item.

**Important:** with the MCG data route closed, nothing in the write-up may be
framed as "pending company data." Sweep `README.md` and
`docs/model_overview_for_team.md` for that framing and convert it to scope
boundaries. The dropped objective needs removing from the objectives list too.

## P6. Freeze results and build the objectives map

There are 17 output artefacts and no single table mapping them to research
objectives. Discussion is the highest-weighted chapter and it needs a stable set
of numbers to argue against.

**Do:** after P1 and P2 land, run `write_all` once, tag the commit, and write
`docs/findings_2026-08-XX.md` in the existing style with one row per research
objective: objective, the artefact that answers it, the headline number, and the
verdict with its confidence. Then stop changing numbers.

Carry the existing caveats through verbatim: green ammonia on the UK corridor is
`marginal` at a 1% margin, not `justified`, and the two production-cost gaps
built across separate studies are covered by
`abatement_source_robustness.csv`.

## P7. Dashboard capture, low effort

The dashboard is already interactive and finished enough. Its audience is now
internal.

**Do:** after the results freeze, capture screenshots of all four tabs at a
sensible scenario, save to `docs/figures/`, and note which go in the
dissertation and which in the 5-10 minute defence video. The pathway/corridor
choice tab is the strongest visual. No further dashboard features.

---

## Ordering

| Day | Work |
|---|---|
| 7-9 Aug | P1 CBAM benchmarks and functional form. P2 UK ETS price path in parallel where sourcing is independent. |
| 10-12 Aug | P3 lock-in module and its sweep. This is the marks item, protect the time. |
| 13-14 Aug | P4 policy event table, two-scenario version if time is tight. P5 documentation sweep. |
| 15-16 Aug | P6 results freeze, objectives map, tag. P7 screenshots. |

Everything after 16 August is writing, and the model should not move again
except to fix an outright error.

## Explicitly not doing

- Any further deliverable for MCG, or any use of the vessel-details website.
- Reverse-engineering Clinton's two open-source links as a validation exercise.
- The free-form any-route generalisation, chokepoint-closure scenarios, or
  variable engine load. These stay backlog. The model is already past the
  complexity needed to demonstrate the skill, and Frano's steer was that
  remaining time goes to theory.
