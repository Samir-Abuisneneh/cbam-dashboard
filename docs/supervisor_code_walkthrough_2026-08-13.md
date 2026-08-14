# What to show Josh, and what he is likely to ask

Companion to `supervisor_briefing_2026-08-13.md`. That one is the project and the
open questions. This one is the screen share: which files to open, in what order,
and the answers to the questions each one invites.

Have the repo open, a terminal ready, and the dashboard already running on a
second tab so you never have to wait for a cold start in front of him.

---

## Part A. What to show, in order

Six things, roughly twenty minutes. The order is deliberate: it opens on the
thing that is genuinely unusual about this codebase rather than on the CBAM
arithmetic, which is the least interesting part to a technical reader.

Do not open `analysis/outputs.py`. It is 1,656 lines and it is the weakest file
in the repo. If he asks, the honest answer is in Part B.

### 1. `config/unresolved.py`, the whole file (54 lines)

**Open first. It is short, complete, and nobody expects it.**

A sentinel object that raises on every operation, including truthiness and float
conversion. An unsourced regulatory value is not zero and not `None`, it is one
of these, so any code path that touches it dies at the line that needed it with a
message naming what to go and look up.

Point at lines 37 to 45, the block of dunder assignments.

**Say:** the reason it overrides `__bool__` and `__float__` and not just the
arithmetic is that `None` propagates quietly. `None * 3` raises, but `if price:`
does not, and a `None` out of a dict lookup can survive several frames before it
fails somewhere unrelated. This fails at the point of use.

**Say why it exists:** earlier drafts of this project got four regulatory facts
wrong by assuming rather than checking, and each one survived multiple review
rounds. This is the structural response to that, not a general defensive
programming habit.

### 2. `config/regulatory_constants.py`, lines 150 to 226

**The CBAM benchmark block. This is the strongest thing in the repo.**

Fifty lines of comment above two lines of code. It records the correction made on
8 August, the instrument it comes from, the exact Annex point, the decimal-comma
trap in the Official Journal text, why hydrogen and ammonia diverge, and one
paragraph explicitly marking an inference as an inference.

Point at the paragraph beginning "Why they diverge is not stated for hydrogen
specifically." It gives the mechanism recital 17 supplies for steel, says the
same reading is consistent with the hydrogen numbers, and then says do not
present it as the Commission's stated reason.

**Say:** that is the pattern the whole constants file follows. Every figure
carries its source, its retrieval date, and where the sourcing stops.

**Then point at lines 211 to 225**, the CSCF. Assumed at 1.0, `CBAM_CSCF_IS_SOURCED
= False`, and the flag travels into the output files. This is open question 2 from
the briefing, so it is a natural place to raise it rather than saving it for the
end.

### 3. `model/cbam.py`, lines 43 to 144

**The core formula. Now it is safe to show the arithmetic.**

Three things to point at, in this order.

**Lines 75 to 81, the unit warning.** The benchmark is defined per tonne of
product, so it can only be netted off an emissions figure that is itself per
tonne of product. Every caller passes it that way, but nothing inside the
function can detect a caller that does not, so it is stated as the caller's
contract.

**Lines 128 to 141, the benchmark branch.** The comment maps each term back to
IR 2025/2620's Equations 1 and 6, and explains that CBAM\_y is the share of free
allocation *remaining*, which is why the code says `1.0 - factor`. That sign
convention is the single easiest thing to get backwards in the whole model.

**Lines 83 to 93, the origin carbon price note.** The build spec wrote this as a
flat subtraction of the origin price from the total cost, which is a unit error:
it takes the price of one tonne of CO2 off a shipment-scale figure. Worth showing
because it is an example of catching a specification error rather than
implementing it faithfully.

**Say:** both mechanisms are still implemented. `factor_scaled` is the superseded
one and stays reachable so the results chapter can show the size of the choice
rather than asserting it.

### 4. `validation/unit_checks.py`, lines 87 to 151

**The input contract. This is the answer to "you are consuming three teammates'
spreadsheets".**

`validate_logistics_table`. It rejects a distance under 1,000 nautical miles on
the reasoning that Gayu's SeaRoute figures are 2,962 and 10,403, so anything
smaller suggests kilometres or a partial leg. It rejects a distance over 20,000
against the Cape of Good Hope routing of 14,815. It recomputes
`voyage_fuel_total_t` from distance times burn rate and rejects a drift over 1%.
It rejects port emissions greater than voyage emissions.

Point at any one of the error messages. They all name the owner: "Confirm units
with Gayu (Student 2)."

**Say:** a units error does not crash, it returns a plausible answer that is
wrong by a factor of a thousand, and a plausible wrong answer is more dangerous
than a crash. The error messages name an owner because the person reading the
failure is usually not the person who can fix it.

### 5. `model/switching.py`, docstring then lines 147 to 197

**The theory contribution. Show this if he asks what is novel.**

Read him the module docstring, lines 1 to 46. It states the Transaction Cost
Economics argument directly: asset specificity means route concessions, berthing,
insurance written against a named route and fixed shore infrastructure are not
redeployable, so the single-year cost ranking is not a decision rule.

**Then the two things that matter technically.**

Lines 33 to 45, the units section. Discounting a stream of GBP per tonne gives a
present value in GBP per tonne of *annual* volume, not per tonne shipped. A
switching cost is a one-off capital sum, so it has to be divided by annual
contracted tonnage before the comparison. Every threshold is named
`..._gbp_per_tonne_annual_volume` for that reason. Comparing a raw capital sum
against these would overstate the barrier by three to four orders of magnitude.

Lines 23 to 31, what the module does not know. No source for the switching cost
exists and none is claimed, so the output is a breakeven threshold rather than a
verdict. A threshold is defensible without a sourced cost. A point estimate would
not be.

**Say:** the finding is that ammonia's spot-cheapest corridor in 2026 is the wrong
ten-year commitment, regret 33.5%, breakeven GBP 38.72 per tonne of annual
contracted volume. It survives both beyond-horizon treatments in the same
direction, so it is not an artefact of the extrapolation.

### 6. The test suite, live

```bash
.venv/bin/python -m pytest -q
```

216 tests, about three seconds. Let him watch it.

Then open `tests/test_model.py` at lines 624 to 653. Three parametrised tests
that expand into 34 cases, each pinning one of Gayu's published figures. Change
the fuel carbon factor or the engine load and the failure names the quantity that
moved.

**Say:** the tolerance is `abs=0.51` on the vessel figures because Gayu's
notebooks round to whole tonnes at several intermediate steps, so an exact match
would be pinning her rounding rather than her arithmetic.

### If there is time: the dashboard

```bash
.venv/bin/streamlit run dashboard.py
```

It calls the same tested functions the notebook does, so it cannot drift from the
model. Anything policy-uncertain carries its status on screen. Worth thirty
seconds, not five minutes.

---

## Part B. Questions he is likely to ask

### On engineering

**"Is there CI?"**

No, and that is a real gap. Tests run locally before every commit and the ruff
config is pinned in `pyproject.toml` so `ruff check .` means the same thing on any
machine, but nothing enforces either on push. A GitHub Action running pytest and
ruff would take about ten minutes to add. If he suggests it, agree, it is a fair
hit and a cheap fix.

**"Why is `analysis/outputs.py` 1,656 lines?"**

Because it grew one output artefact at a time under deadline and was never split.
It is the file most in need of refactoring. The mitigating facts are that each
function is independent, they share only the base-case mask helpers, and the test
suite covers them, so the size is a readability problem rather than a correctness
one. Do not defend it beyond that.

**"Why a notebook? Notebooks are unreviewable."**

`run_model.ipynb` is a build artefact, not a source file. It is generated by
`build_notebooks.py` from the Python library, so nothing is hand-edited inside it
and the diffable source stays in `.py` files. The notebook exists because the
supervisors and the industry partner want a runnable narrative, not because
anything is developed in it. `README.md` section "Why the library is .py and the
entry point is .ipynb" has this written up.

**"What is your test coverage?"**

Not measured as a percentage, and it would be a misleading number here. What the
216 tests actually cover is worth stating instead: 34 cases pinning Gayu's
published figures, the reference case against a published paper, every regulatory
constant that has a citation, both CBAM mechanisms side by side, the three-state
verdict bands, and a test that fails if any of the three findings killed on
8 August ever reappears. If he wants a figure, offer to run `pytest --cov` after
the meeting rather than guessing.

**"Why plain functions and modules rather than classes?"**

Almost everything here is a pure function from numbers to a number, so there is no
state to encapsulate. The two dataclasses that exist, `MaritimeCost` and the
compliance row, are there because they carry twenty-odd fields into a DataFrame
and named fields beat positional tuples at that width. Adding a class hierarchy
over the regulatory functions would add indirection without removing any.

**"How do you know the model is right?"**

Three independent checks, and say them in this order. It reproduces Gayu's
published maritime figures exactly, 34 of them pinned. It reproduces a published
paper's burden figure through `validation/reference_case.py`. And every regulatory
constant traces to a named instrument with a retrieval date, which is checkable by
hand against the legislation. None of those is proof, and the 8 August error is
the standing evidence that the checks are not exhaustive.

### On modelling

**"Why deterministic? Why not Monte Carlo?"**

Because there are no distributions to sample. The carbon price scenarios are a
bracket of three sourced anchors, not a fitted distribution, and attaching
probabilities to them would invent precision that no source supports. What the
model does instead is a one-at-a-time sensitivity sweep, `analysis/sensitivity.py`,
which ranks inputs by how much they move the answer. If he pushes on this, the
honest position is that a probabilistic treatment would need a defensible prior on
each input and none exists.

**"Is it an optimisation model?"**

No, and be firm on this. There is no solver and nothing is being searched. Where
it picks a cheapest pathway it is ranking a handful of routes that exist in the
literature. Calling it optimisation in the write-up would overclaim.

**"What drives the answer most?"**

Embedded emissions, by a distance, and then the carbon price. By 2030 the border
charge is roughly thirty-two times the shipping charge on the worked ammonia case,
where in 2026 it is ten times. That ratio is itself a finding: any conclusion
drawn from a single year is really a conclusion about that year's position in the
phase-in schedule.

**"Why only two corridors?"**

Regulatory asymmetry, chosen deliberately. Halifax to Hamburg is live under EU
CBAM from January 2026, Ningbo to Felixstowe has no UK CBAM until January 2027, so
the same calendar year has one regulated and one unregulated corridor. The
industry partner confirmed that as the point of the study rather than a
complication. Generalising to arbitrary routes is written up as backlog, not
scope.

**"The hydrogen vessel is not real, is it?"**

No, and it is labelled as a counterfactual everywhere it appears. No commercial
liquid hydrogen fleet exists, so the hydrogen case applies an ammonia carrier's
geometry to hydrogen on purpose, to isolate what cargo density alone does to cost
per tonne. An ammonia carrier cannot physically hold liquid hydrogen. Say this
before he finds it.

### On the data and the team

**"Where do the inputs come from?"**

Three CSVs from three teammates. Riya supplies embedded emissions and production
costs, Gayu supplies voyage logistics out of her own notebooks, and the commercial
table is a declared scope boundary rather than a pending input, because conversion
and freight have no public source and no owner. Both of those terms are invariant
to production pathway, so they cancel out of every within-corridor comparison the
study actually makes.

**"What happens when a teammate changes their spreadsheet?"**

`unit_checks.py` runs first and rejects anything that breaks the agreed contract.
Beyond that, the pinned tests catch silent drift: if Gayu's figures move, 34 tests
fail by name. That is the intended workflow, the tests are the interface between
her work and mine.

**"The industry partner data never arrived?"**

Correct, that route closed on 6 August and the objective that depended on it was
dropped. Nothing in the write-up is framed as pending company data. What replaced
it is public-source regulatory work, which is where the UK CBAM primary
legislation trace and the DESNZ price path came from.

### The uncomfortable ones

**"You had a material error in the central calculation five days ago. What else is wrong?"**

Do not get defensive, this is a fair question and the answer is good.

The error was netting off the EU ETS product benchmark instead of the CBAM
benchmark. It was found by reading IR 2025/2620 directly rather than by testing,
because the code was self-consistent and no test could have caught it. It cost
three findings, all of which are recorded as dead in
`docs/findings_2026-08-08.md` and are now guarded by tests that fail if they
return.

What it says about the rest: errors of that class come from sourcing, not from
code, so the defence is the citation discipline in `regulatory_constants.py` and
reading primary text rather than summaries. The two places that discipline is
currently incomplete are the CSCF and the UK ETS price basis, and both are in the
briefing as open questions rather than hidden.

The honest closing line is that the finding it killed was the most interesting one
the model produced, and what replaced it is simpler and more defensible but less
interesting.

**"How much of this did you write?"**

Answer it straight. You used AI assistance for implementation and for docs, the
regulatory sourcing was done by reading primary instruments, and you can explain
any line in the repo. The last part is the one that matters and it is the reason
to spend tonight walking the six files above rather than rehearsing an answer.
If there is a file you could not defend line by line, do not show it.

**"Can you finish by the 16th?"**

The model is done and frozen. What remains is the methodology section and the
write-up, so the three days are writing days rather than modelling days. The five
open items in the briefing are all judgement calls that can be resolved in a
sentence each, not work packages.

---

## The two things to volunteer rather than wait for

Both are better said by you first.

1. **The 8 August benchmark error and the three findings it killed.** He will
   respect it as a correction found and documented. He will not respect finding it
   himself in the findings doc.
2. **No CI, and `outputs.py` is too big.** Naming your own weakest points early
   buys credibility for everything else you claim.
