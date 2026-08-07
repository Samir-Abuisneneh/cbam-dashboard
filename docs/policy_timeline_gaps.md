# Policy timeline: what is structured, and what Alex still needs to fill

Alex's timeline was converted to `cbam_model/data/policy_events.csv` on
6 August 2026, 50 events across Canada, the UK, the EU and China. Load it with
`data_io.load_policy_events()`.

## What the conversion added

Frano asked for two parallel tracks rather than one narrative timeline.

**Track A, the events themselves.** Alex's version had dates, descriptions and
some links, but no classification by legal instrument. Every row now carries
`instrument_type` (primary legislation, regulation, implementing regulation,
treaty, court ruling, plan, consultation, proposal, procedural, market event)
and `status` (in force, superseded, proposed, pending, historic, not law).
That distinction is the whole point of Frano's ask: an Act of Parliament and a
consultation that closed without a decision are not the same kind of fact, and
the write-up cannot treat them the same way.

**Track B, the quantified translation.** `quantified_effect` holds the number
and date each event translates into. `model_parameter` names the constant or
input column it bears on, and `affects_model` separates events that set a
modelled value from those that only justify a sensitivity or supply context.

## The good news

A test cross-checks the timeline against the model, and **every quantified
event agrees with what the code implements**: the Canadian price path, the CBAM
factor ramp, the revised EU benchmarks, UK ETS voyage coverage, the proposed
expansion and its not-law status, and the UK CBAM start year. Nothing has
drifted.

## What is still missing

`quantified_effect` is empty on 27 of 50 rows. Most of those are genuinely
context rather than inputs, but **eight events marked as affecting the model
carry no number**, and those are the gaps worth closing:

| Event | What is needed |
|---|---|
| CA-01 | The Act creates the origin carbon price, but the timeline gives no figure for 2018-2025. Only needed if a pre-2026 baseline is reported |
| CA-07 | Bill C-4 leaves the industrial system in place. State explicitly that the industrial price is unchanged by it, so the reader knows the repeal did not touch the modelled input |
| UK-10 | The July 2025 confirmation that shipping enters UK ETS. Needs the coverage percentage, which UK-15 later gives, so this row can probably just cross-reference it |
| UK-14 | The consultation closing with no decision. Needs no number, but should state the decision date if one has since been announced |
| EU-02 | CBAM entry into force. Needs the transitional-versus-definitive split, which EU-04 and EU-10 cover between them |
| EU-03 | FuelEU adoption. Needs the intensity target trajectory and penalty rate, both already in `regulatory_constants` but not in the timeline |
| EU-05 | EU ETS maritime phase-in. Needs the 40/70/100 percent schedule for 2024/2025/2026 |
| EU-08 | The default emissions values. Needs the actual per-country figures, which are in the emissions table but not cross-referenced here |

None of these change a result. They are completeness items so the appendix
table stands on its own.

## The UK CBAM direct-only rule: real, but far smaller than first thought

**UK CBAM charges direct emissions only until 2029 at the earliest, and the
model does not represent that.** See row UK-16. The model applies the full
embedded figure on the Ningbo-Felixstowe corridor from 2027, which overstates
UK CBAM liability in 2027 and 2028, precisely the two years the lock-in
reversal turns on.

An earlier version of this note said the effect was "pathway-dependent and
probably large", reasoning that Chinese green electrolysis is mostly grid
electricity. **That was wrong for the study's primary scenario**, and the
correction came from reading the Commission's own numbers.

The adopted default values workbook publishes direct and indirect separately
(Annex I and Annex II of IR 2025/2621). For the two goods here:

| Country | Good | Direct | Indirect | Total |
|---|---|---|---|---|
| Canada | Anhydrous ammonia (CN 28141000) | 1.91 | 0.07 | 1.98 |
| China | Anhydrous ammonia | 4.17 | 0.19 | 4.36 |
| Canada | Hydrogen (CN 2804 10 00) | 10.82 | **N/A** | 10.82 |
| China | Hydrogen | 26.64 | **N/A** | 26.64 |

**Hydrogen has no indirect default value at all.** So on the primary
`cbam_default` pathway the UK direct-only rule changes hydrogen by exactly
nothing, and ammonia by 3.5% (Canada) or 4.4% (China) in two years only.

The "probably large" reasoning does still apply to the *literature* pathways,
where green electrolysis carries its grid electricity explicitly. But those are
sensitivity brackets, not the headline scenario. So this is now a documented
limitation rather than a correction worth making, and it is no longer a request
to Riya.

Sources: the Commission's adopted workbook for the values, and law-firm
briefings plus the Deloitte UK tax policy map for the direct-only rule itself.
The primary HMRC or HM Treasury text has **not** been read, so the rule should
be confirmed there before anything is built on it.

## The other thing the workbook turned up: a mark-up bug

The same workbook publishes each default value both before and after the
IR 2025/2621 mark-up, which makes the mark-up schedule directly checkable.
Dividing one by the other:

| Good | 2026 | 2027 | 2028+ |
|---|---|---|---|
| Ammonia, nitric acid, urea | 1% | 1% | 1% |
| Hydrogen, iron, steel | 10% | 20% | 30% |

The model applied 10/20/30 to **everything**. Fertiliser goods carry a flat 1%,
and ammonia is a fertiliser good for CBAM purposes (CN 2814) while hydrogen is
not (CN 2804). Ammonia's default emissions were therefore overstated by 8.9% in
2026, rising to 28.7% from 2028, on the study's primary scenario and on the EU
corridor.

Fixed 7 August 2026. `default_value_markup` now takes the product and refuses
to run without it, because defaulting it would silently reinstate a bug that
produces a plausible number rather than an obviously wrong one.

Two consequences worth knowing:

1. **The lock-in finding gets stronger.** Ammonia's EU corridor cost falls, so
   committing to the UK corridor in 2026 looks worse, not better. Lock-in
   regret rises from 95% to 146%, and the breakeven switching cost from
   GBP 75.36 to GBP 91.60.
2. **The open CBAM mechanism decision narrows to hydrogen.** Before the fix,
   switching mechanism inverted the corridor ordering for both products. With
   ammonia's mark-up corrected, both mechanisms now agree on ammonia and only
   hydrogen still flips. Frano's decision still has to be taken, but it now
   affects one product rather than two.

## Events added that were not in Alex's version

- **EU-13**, Commission Implementing Regulation (EU) 2026/1412 of 26 June 2026,
  setting the revised 2026-2030 free allocation benchmarks. Sourced from the
  Official Journal on 6 August 2026. Ammonia 1.570 to 1.522, hydrogen 6.84 to
  7.98.
