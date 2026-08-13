# Q&A for the technical supervisor meeting, 13 August 2026

Josh is the data science and CS supervisor, so the questions below are the ones
a technical reader asks, not the regulatory ones. Frano owns the policy side.

Answers are written to be said out loud. Where the honest answer is "that is a
fair hit", it says so, because conceding a real weakness early is what buys
credibility for the parts you are defending.

---

## Q1. Where is the data science in this?

**This is the question that decides the meeting. Have it ready cold.**

The short answer: the contribution is a validated computational pipeline over
multi-source, conflicting-provenance data, not a learned model. There is no
estimation because the data-generating process is legislation, and legislation
is not something you infer from a sample. It is something you implement exactly
and then test.

What is actually data science in it:

- **Multi-source integration under conflicting units and provenance.** Three
  contributors supply three tables with no shared schema and no shared units. The
  join between per-voyage costs and per-tonne costs did not exist in anyone's
  data and had to be constructed from a cargo capacity figure.
- **A data contract enforced in code.** `validation/unit_checks.py` rejects
  malformed input before it reaches a formula, on domain-specific bounds rather
  than type checks.
- **Scenario matrix generation** across six dimensions: corridor, product,
  pathway, year, price scenario, and policy variant, plus vessel class, route and
  speed on the maritime side.
- **Sensitivity analysis** ranking inputs by mean absolute percentage effect on
  the headline metric.
- **Robustness re-computation** of every headline verdict under three
  independent cost sourcings, with a test that fails if any verdict changes sign.
- **216 regression tests**, including 34 that pin a collaborator's published
  figures so her work and mine cannot silently diverge.

**What it is not, and say this yourself:** there is no learning, no inference, no
statistical estimation, and no uncertainty quantification beyond a scenario
bracket. If he wants that, see Q3, where there is a concrete and honest offer.

## Q2. Why is it deterministic? Why no Monte Carlo?

Because there are no distributions to sample from. The three carbon price
scenarios are sourced anchors, not a fitted distribution, and attaching
probabilities to them would manufacture precision no source supports. Same for
the emissions inputs: they are regulatory default values and single-study LCA
figures, neither of which comes with a variance.

A Monte Carlo over invented priors would produce confidence intervals that look
rigorous and mean nothing. That is a worse failure than not having them.

**If he pushes**, the defensible middle ground is that the scenario bracket is a
crude interval and the sensitivity sweep tells you which input the interval
should be widest on. Offer that rather than defending the absence.

## Q3. Your sensitivity analysis is one-at-a-time. That misses interactions.

**Correct, and concede it immediately.** Carbon price and embedded emissions
enter multiplicatively, so their joint effect exceeds the sum of their individual
effects, and an OAT sweep cannot see that. It is stated as a limitation in the
module docstring.

The honest offer, and it is a good one to make in the room: a variance-based
global method, Sobol or Morris, over the same parameter set would capture
interactions and give first-order and total-effect indices. The input space is
about eight parameters and the whole scenario matrix builds in 30 milliseconds,
so the compute is free. It is roughly a day of work.

**Ask him whether that is worth doing before the 16th or whether it belongs in
the limitations chapter.** That converts your weakest methodological point into a
question he gets to answer, which is a much better position than defending it.

## Q4. Which sensitivity results should I actually look at?

There are two sweeps and only one of them ranks the headline metric. Be precise
here, because the module docstring was wrong about this until 12 August.

- `sweep_corridor` / `rank_drivers` varies voyage parameters and measures cost
  **per voyage**. Maritime layer only.
- `sweep_compliance` / `rank_compliance_drivers` varies voyage parameters *and*
  the CBAM inputs, and measures **compliance cost per tonne of product**. This is
  the study's headline metric and the one to quote.

The compliance ranking on Halifax-Hamburg ammonia at 2030: carbon price 37.1%,
embedded emissions 32.1%, origin carbon price 17.3%, FuelEU intensity 1.9%, then
everything maritime below that. It defaults to 2030 rather than 2026 because the
CBAM factor is 2.5% in 2026, which would understate how much the emissions inputs
matter.

The reason this distinction matters: the maritime layer is about 3% of the 2030
ammonia cost. Quoting the voyage sweep as the model's driver ranking would be
ranking the part that does not matter.

## Q5. How big is the data? How long does it run?

Small and fast, and do not oversell it. 312 maritime rows, 273 compliance rows,
210 CBAM rows. The whole matrix builds in about 30 milliseconds and the full test
suite runs in under two seconds.

**That is a design property, not a limitation.** The scenario grid is exhaustive
over a deliberately small, fixed set of cases, because the study compares two
named corridors rather than searching a space. Speed is what makes 216 tests
runnable on every edit, which is what actually keeps the model correct.

If he expected scale, the honest framing is that the difficulty here is
provenance and correctness, not volume. Nothing about this problem gets harder
with more rows.

## Q6. What is your test strategy? What is the coverage?

Not measured as a percentage, and a percentage would be misleading here. What the
216 tests actually do, in descending order of usefulness:

- **34 parametrised cases pinning a collaborator's published figures.** If Gayu's
  fuel carbon factor or engine load changes, the failure names the quantity that
  moved. Tolerance is `abs=0.51` on the vessel figures because her notebooks round
  to whole tonnes at intermediate steps, so an exact match would be pinning her
  rounding rather than her arithmetic.
- **A reference case against a published paper**, `validation/reference_case.py`.
- **Regression tests on three dead findings.** Three results were killed by a
  calculation correction on 8 August, and there are tests that fail if any of them
  reappears.
- **Label tests.** A test fails if a new scenario variant is added without a
  status label, so a not-yet-law scenario cannot silently enter the results as
  though it were legislated.
- Unit tests on every regulatory function and every validation rule.

If he wants a number, offer to run `pytest --cov` after the meeting rather than
guessing at one.

## Q7. Is there CI?

No. That is a fair hit and a cheap fix. Tests run locally before every commit and
the ruff config is pinned in `pyproject.toml` so `ruff check .` means the same
thing on any machine, but nothing enforces either on push. A GitHub Action
running pytest and ruff is about ten minutes of work.

Agree with him rather than explaining why it did not happen.

## Q8. `analysis/outputs.py` is 1,656 lines. Why?

Because it grew one output artefact at a time under deadline and was never split.
It is the weakest file in the repo and there is no defence of the size.

What is true in mitigation: each function is independent, they share only two
base-case mask helpers, and they are covered by tests, so it is a readability
problem rather than a correctness one. The natural split is by output family,
corridor comparison, competitiveness, abatement, lock-in, charts.

Do not open this file in the meeting. If he opens it, say the above and move on.

## Q9. Why is there a notebook? Notebooks are not reviewable.

`run_model.ipynb` is a build artefact, not a source file. It is generated by
`build_notebooks.py` from the Python library, so nothing is hand-edited inside it
and the reviewable, diffable source stays in `.py` modules. The notebook exists
because the supervisors and the industry partner want a runnable narrative.

This is a genuinely good answer and it usually ends the line of questioning.

## Q10. Why plain functions rather than classes?

Almost every function here is pure, from numbers to a number, so there is no state
to encapsulate. The two dataclasses that exist carry twenty-odd fields into a
DataFrame, where named fields beat positional tuples at that width. A class
hierarchy over the regulatory functions would add indirection and remove nothing.

The architectural decision that did matter is the one-way dependency: `config`
knows nothing, `model` imports `config`, `analysis` imports `model`, and nothing
imports back up. That is what makes it possible to check any regulatory figure
against legislation in one file.

## Q11. How do you know the model is correct?

Three independent checks, and none of them is proof:

1. It reproduces a collaborator's published maritime figures exactly, 34 of them
   pinned as tests.
2. It reproduces a published paper's burden figure through
   `validation/reference_case.py`.
3. Every regulatory constant traces to a named instrument with a retrieval date,
   so it is checkable by hand against the legislation.

The standing evidence that this is not exhaustive is the 8 August error, which is
Q13.

## Q12. How do you handle missing or unsourced inputs?

`config/unresolved.py`. An unsourced value is not zero and not `None`, it is a
sentinel object that raises on every operation including truthiness and float
conversion, with a message naming what to go and look up.

The reason for overriding `__bool__` and `__float__` specifically is that `None`
propagates quietly. `None * 3` raises, but `if price:` does not, and a `None` out
of a dict lookup can survive several frames before failing somewhere unrelated.

**This is the file to show him first.** It is 54 lines, it is unusual, and it is
the clearest single artefact of the engineering argument.

## Q13. You had a material error in the central calculation five days ago. What else is wrong?

Fair question, and the answer is good. Do not get defensive.

The model was netting off the wrong benchmark in the EU CBAM free allocation
adjustment. It was found by reading the governing regulation directly, not by
testing, because the code was internally self-consistent and no test could have
caught it. It cost three findings, including the most counterintuitive result the
model had produced. All three are documented as dead and are now guarded by tests
that fail if they return.

**What it says about the rest:** errors of that class come from sourcing, not from
code, so the defence is citation discipline and reading primary text rather than
summaries, not more tests. The two places that discipline is currently incomplete
are the cross-sectoral correction factor and the UK carbon price basis, and both
are written up as open questions rather than hidden.

Close on the honest line: what replaced the dead finding is simpler and more
defensible but less interesting.

## Q14. How much of this did you write?

Answer straight. You used AI assistance for implementation and documentation, the
regulatory sourcing was done by reading primary instruments, and you can explain
any line in the repo.

The last clause is the one that matters, and it is the reason to spend tonight
walking the files in `supervisor_code_walkthrough_2026-08-13.md` rather than
rehearsing this answer. If there is a file you could not defend line by line, do
not put it on screen.

## Q15. What would you do differently?

Have one ready, it is a standard closing question and "nothing" is a bad answer.

Split `analysis/outputs.py` from the start, add CI on day one, and build the
compliance sensitivity sweep before the maritime one, since the maritime layer
turned out to be 3% of the 2030 result and got the attention first because it was
the data that arrived first.

---

## Three things to volunteer before he finds them

1. The 8 August calculation error and the three findings it killed.
2. No CI, and `outputs.py` is too big.
3. The sensitivity analysis is one-at-a-time and misses interactions, with the
   Sobol offer attached.

Each one lands better from you than from him, and the third comes with a question
he gets to answer, which is the best position you can be in.
