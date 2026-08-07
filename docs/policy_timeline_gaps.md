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

## The one substantive finding from the conversion

**UK CBAM charges direct emissions only until 2029 at the earliest, and the
model does not represent that.** See row UK-16.

The model applies the full embedded emissions figure on the Ningbo-Felixstowe
corridor from 2027, which **overstates** UK CBAM liability in 2027 and 2028.
Those are precisely the two years the lock-in reversal turns on, so this is not
a cosmetic gap.

The effect is pathway-dependent and probably large. Chinese green electrolysis
at 2.34 tCO2e/t is mostly grid electricity, so most of it should fall out of
scope for 2027-2028; coal gasification is mostly direct process emissions and
would barely move. Correcting it would widen the modelled gap between green and
coal routes on the UK side, which is the comparison the abatement results rest
on.

Fixing it properly needs a direct/indirect split in the emissions table, which
is a request to Riya. Stating it as a limitation is the fallback. A test pins
that the gap stays written down until one or the other happens.

Sources consulted are law-firm briefings and the Deloitte UK tax policy map,
which agree. The primary HMRC or HM Treasury text has **not** been read, and
given this project's history with secondhand regulatory claims, it should be
before any code changes on the strength of it.

## Events added that were not in Alex's version

- **EU-13**, Commission Implementing Regulation (EU) 2026/1412 of 26 June 2026,
  setting the revised 2026-2030 free allocation benchmarks. Sourced from the
  Official Journal on 6 August 2026. Ammonia 1.570 to 1.522, hydrogen 6.84 to
  7.98.
