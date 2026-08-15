# Technical supervisor meeting notes, 13 August 2026

Present: Josh (data science / CS supervisor), Samir.

Source: meeting transcript. Where the transcript was garbled the item is marked
`[uncertain]`. This is the meeting that `supervisor_qna_2026-08-13.md` was
prepared for.

---

## 1. The headline verdict

The dashboard and visualisation were praised without qualification. The
modelling was not.

Josh's assessment, in his words as closely as the transcript supports: judged as
an MSc data science project this would be **too basic**, because what the model
does is compare values and run basic numerical analysis and EDA. He was explicit
that he is not the marker, but that this is what he would want to see if he were.

He did not dispute that the regulatory implementation is correct or that the
sourcing is hard. His point is that correctness of a deterministic calculation is
not the thing being assessed on a data science programme.

**The Q1 defence in the Q&A prep did not hold.** The prepared answer was that the
contribution is a validated computational pipeline and that there is deliberately
no learning because the data-generating process is legislation. That argument was
not accepted as sufficient on its own. Treat the "no learning is a design
decision" line as necessary but not sufficient from here.

## 2. What he wants added

A predictive model or other machine learning implementation, bolted on as a
**proof of concept**. His framing, repeatedly: it does not have to be intuitive
for the problem, and the results do not have to be good.

The standard he set is not accuracy, it is appropriateness:

> the important thing is that the results make sense for the data you feed it

So the deliverable is: here is a model class that would be appropriate for this
problem, here is it working end to end, and had the real data existed the
pipeline would produce meaningful output.

He estimated **a couple of days** of work to mock up. Note that the internal
model deadline is 16 August, so that estimate consumes the remaining time
entirely.

### Why the current data cannot support it

Stated in the meeting: roughly three datasets at around 200 rows each. Josh
agreed 200-ish rows is not enough to train on. The only thing the current data
could predict is post-2030 policy values, and those are single legislated figures
per year, not a sample.

## 3. Where the data could come from

In descending order of his preference.

**Real public shipping data.** AIS (Automatic Identification System) vessel
tracking is the standard source, and there are AIS datasets on Kaggle including
US coastal waters and energy trade data. He searched during the meeting and found
candidates. His instruction on scope:

- Do not restrict the search to ammonia or hydrogen. Any commodity shipping will
  do: bulk goods, fuel oil, gas oil, LPG.
- Do not read research papers to find data. Papers are for the literature review,
  and only for methodology, not for domain background. Search directly for
  datasets instead.

He also suggested adding a third corridor, South America or Brazil to Europe, to
widen the sample. **Pushed back in the meeting** on the grounds that adding a
corridor means re-running the multi-person research effort that took about three
weeks for the current two. He accepted that as fair.

**Synthetic data, if real data does not appear.** He was unambiguous that this is
acceptable and that generating it with a language model is a fair use of AI. The
declaration he suggested, close to verbatim:

> Due to the lack of available data, synthetic data was used. The results shown
> are therefore not representative of the real world. However, the results
> indicate X, Y and Z based on the parameters supplied, so provided the model
> were fed real-world data it would produce valid results.

He said this needs no further justification than that.

## 4. On using AI for the build

Explicitly endorsed for rapid prototyping: describe the goal, have it find or
generate the data and build the pipeline, then go back and understand, rewrite
and reimplement it yourself. Acknowledge the AI use in the report.

## 5. What is actually being marked

His closing point, and worth more than the ML advice itself:

> we just want to gauge that you have done a project well, and that you have been
> able to critically analyse the results of that project

He does not care whether the result is exciting. The analysis chapter carries the
mark. This is consistent with Frano's structural guidance that the discussion
chapter matters most.

## 6. Paper trail

Instruction, in the context of the MCG data withdrawal:

- Keep everything in writing and keep a clean communication chain.
- At marking time, make sure the primary supervisor is reminded of what happened
  and what was done in response.
- Make sure the **second marker** is aware of it too, since they will not have
  the history.

This matters because the ML component will exist on synthetic data, and the
justification for that is the data withdrawal. The evidence chain has to be
legible to someone who was not in these meetings.

## 7. Presentation scheduling

The group wants 25, 26 or 27 August. `[uncertain]`: the transcript attributes
this preference to "Joshua" but the reply comes from Josh himself, so the source
of the preferred dates is unclear.

Josh's constraints:

- 25, 26, 27 August are his last days before leave, and he already has
  presentations booked, including one or two around the 20th.
- He could possibly do **2 September**, or even the 3rd.
- It depends on the primary supervisor's availability, not his.

**Action:** email Frano, cc Josh and all group members, propose a couple of dates
and times, and lock it in.

He also mentioned a teaching assistant, Marcus `[uncertain]`, who may join.

## 8. Ideas raised and where they landed

| Idea | Raised by | Status |
| --- | --- | --- |
| Dashboard polls live AIS data by vessel ID | Josh | Explicitly out of scope. He said so himself, unprompted, and that it is not necessary. |
| Tariff and duty rates as an adjustable variable | Josh | Not currently parameterised. Deprioritised in the meeting on the grounds that the EU is stable and CBAM is legislated out to 2035. His counter-anecdote: a ship can leave port and arrive with its profitability inverted by a tariff change. |
| Green versus diesel profitability comparison | Samir | Josh liked it. Blocked on data: it needs the whole chain, production as well as shipping, not just the voyage leg. |
| Third corridor, Brazil or South America to Europe | Josh | Pushed back on cost. Accepted. |
| Suez closure and Cape of Good Hope routing | Samir | Already implemented. Josh saw it in the dashboard and was satisfied. |

## 9. Do not burn the MCG bridge

Opening exchange, and it echoes Frano's 6 August ruling. There is nothing to gain
from sending anything angry to the partner, however cathartic. Be the better
party and absorb it.

---

## Actions

1. Email Frano, cc Josh and the group, proposing presentation dates. Flag that
   Josh is unavailable 25 to 27 August and that 2 or 3 September works for him.
2. Raise the ML requirement with Frano immediately. He owns the scope decision
   and the 16 August model deadline, and this is a material change to both.
3. Search Kaggle and open data portals for AIS or commodity shipping datasets.
   Any commodity, not just ammonia and hydrogen.
4. If nothing usable turns up, generate synthetic data and build the proof of
   concept on it, with the disclaimer in section 3.
5. Whatever gets built, write the critical analysis of it properly. That is what
   is marked.

## One caution before building this

A synthetic-data model sits badly next to this project's own standard, which is
that every regulatory constant traces to a named instrument. If the ML output is
allowed anywhere near the headline corridor verdicts, it imports invented numbers
into results that are currently defensible line by line.

Recommendation: wall it off. Separate module, separate section, separate chapter,
clearly labelled as a methodological proof of concept, and no path by which its
output feeds the CBAM cost figures. That satisfies Josh's ask without weakening
the part of the project that is already strong.
