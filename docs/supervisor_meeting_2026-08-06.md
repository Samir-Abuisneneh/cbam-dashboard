# Supervisor meeting notes, 6 August 2026

Present: Frano Barbic (supervisor), Samir, Riya, Gayu, Alex.

Source: meeting transcript. Where the transcript was unclear the item is marked
`[uncertain]`.

---

## 1. The MCG data is dead. Stop chasing it.

Clinton confirmed on 3 August that no company data will be shared. Frano's
ruling:

- Proceed on publicly available data only. The model already runs on it, and
  demonstrating the modelling skill is what is being assessed.
- Do not ask MCG for data again. Do not build any further deliverable *for* them.
- The research objective that depended on company-held data is dropped. Frano has
  already explained this to the programme team.
- To keep the dissertation balanced against the marking criteria, the theoretical
  chapters get correspondingly stronger. That was expected anyway.
- Do not spend Tuesday/Friday reverse-engineering the two open-source links
  Clinton sent as a substitute for data. If something in them turns out useful,
  include it because it is useful, not because he sent it.

### Vessel-details website

The site the team was looking at prohibits use of any portion of the site for
commercial or non-commercial purposes in its terms. Frano's position: then do not
use it, and arguably do not open it. Treat it as off-limits. Any vessel
characteristics need a source whose terms permit academic use.

---

## 2. Closing the MCG relationship

The university wants the partnership closed politely, not burned. Frano's
instruction: send Clinton a short, warm reply that does the following and nothing
more.

- Thanks him for the links, says they are useful.
- Acknowledges the confidentiality constraint on the data, without argument.
- States the project will be finished in three to four weeks.
- Offers to share the final dissertation and the model when done.
- Offers, optionally, a short presentation of the final work. Frano and Sam (the
  partnership contact) are willing to attend if that makes it easier.

Explicitly *not* in the message: any acknowledgement that the team owes them
validation against the two links, any commitment to deliver anything, any
reference to the process going badly.

Do not attempt to defend the earlier work or reopen the data question. The
purpose is a clean close.

### Presentation

There is no requirement to present to MCG for marks. If they want it, a 30 to 60
minute Teams session at the end is enough, and it is fine to be diplomatic about
how the collaboration went. Frano separately asked whether the team would be
comfortable presenting the finished work to him on Teams. That does not affect
the mark either.

### Why this matters beyond the dissertation

Frano's aside: "difficult stakeholder" is a standard job-interview question.
Having closed this professionally is a better answer than having a grievance.

---

## 3. The dashboard

Keep it, finish the interactive version, but reframe who it is for. It is now a
tool for the team, not a client deliverable.

Uses:
- Screenshots in the dissertation.
- The 5 to 10 minute defence video.
- A talking point for graduate job interviews.

Frano's framing on marks: a strong model plus strong theory is what earns the
grade.

---

## 4. Alex's policy timeline needs restructuring

Current state is a single combined timeline. Frano wants it split into two
parallel tracks, presented as tables or visuals, readable without narration.

**Track A, policy events.** Each entry dated, with a link to the actual policy
document, not just to a page citing a figure. For each item, classify the legal
instrument, because that determines how likely and how fast it lands:

- primary legislation / policy act
- secondary legislation or statutory instrument
- a plan or strategy with no binding force
- a procedure still requiring parliamentary approval

**Track B, quantified translation.** What each policy event means numerically and
from which date. Frano's example phrasing: "50% until this date, then a 5%
increase from that date." One quantified line per relevant policy, per
jurisdiction.

Other points:
- The new UK Prime Minister's position is not yet reflected and should be. He is
  reported as broadly pro on this agenda. `[uncertain: transcript garbled on the
  detail]`
- Analyse the key documents, do not just link them. State the main takeaways of
  each document.
- Main policies go in the body. The long tail goes in the appendix. The test for
  the body is whether the policy actually influences a price or an assumption
  inside the model.
- Anything shown to influence price should be traceable into the model.

---

## 5. Theoretical framework

Two theories, as previously set: **Transaction Cost Economics** and
**Institutional Theory**. Frano's guidance this meeting was mostly about method.

### Riya's TCE reading, endorsed as a starting point

Asset specificity applied to vessels. Low specificity assets are redeployable to
other uses; high specificity assets are purpose-built and strand if the use case
disappears. Today there are no hydrogen-fuelled carriers in service, so hydrogen
moves in ammonia form on ammonia carriers. Committing capital to a
hydrogen-specific vessel is a high-asset-specificity bet that requires long
offtake contracts and subsidy certainty to justify, which is why the market has
not made it.

### Frano's extension, and this is the part to develop

Do not stop at vessel capital. Ask what else about a corridor is *not* switchable:

- Do operators need a concession or a granted right to run that route?
- Port access, berthing rights, insurance arrangements.
- Contract tenor. These are large contracts, nobody signs a one-year deal, so
  think in terms of roughly ten-year commitments.
- Fixed shore infrastructure, pipelines and terminals, which cannot be moved if
  the regulation changes.

The point: the model produces a simple cost comparison at a point in time. TCE
plus institutional theory explain why a corridor that looks cheaper today cannot
simply be switched to, and why a regulatory change can flip the ranking. If any
of that can be pushed back into the model as a parameter, better still.

### Method for building the framework

- Do not invent a framework. Find studies doing something similar with the same
  theories and apply or adapt theirs. If a usable model exists in the literature,
  cite it and use it; do not pretend it is original.
- Read papers from management and economics angles. Engineering and pure LCA
  papers will not carry TCE.
- Minimum reading: six to eight academic articles each, and Frano called that
  the floor. His own PhD pace was 15 to 20 per week.
- Do not have ChatGPT write the literature review. Using it to suggest structure
  or to challenge your own is fine.
- Check the two theories actually fit together before committing. Frano thinks
  they do here, because the model compares corridor costs and the institutional
  layer explains why those costs move.

### On the claimed gap

Frano pushed back on "no paper connects these." Academic literature is vast; a
gap that large usually means the wrong keywords or the wrong connection between
them, not an empty field. Different research communities also use different
terminology for the same object. Find the literature that does exist and position
against it. A master's dissertation is expected to sit inside the existing body
of knowledge, not at its edge.

---

## 6. Dissertation structure and where the 8,000 words go

Frano's preferred shape, with his priority ordering.

| Chapter | Notes | Weight |
|---|---|---|
| Introduction | Short. Broad to narrow: what is known, what is not, the gap, then aim, objectives and research questions. Read published intros before writing. | Light |
| Literature review | Built from a few "building blocks", each a subtopic the reader needs before the analysis makes sense. Present both sides where authors disagree. Blocks must feed into the framework. | Substantial |
| Theoretical framework | Frano keeps this inside the literature review, with a few sentences explaining the framework diagram. Separating it is also acceptable. | With lit review |
| Methodology | Relevant here and not to be cut much. No case study, no survey: the method *is* the model build. Cover data sources, construction, assumptions. Detail goes to appendix. | Keep |
| Findings / results | Model comparisons and scenario outputs. No citations in this chapter. | High priority |
| Discussion | The most important chapter. Compare findings against the literature reviewed. Add subsections for theoretical implications and practical implications. | Highest priority |
| Conclusion | Relatively short, plus future research. Not a summary. | Light |
| Appendix | Full policy tables, per-policy detail, model detail. Everything that supports the body without consuming its word count. | Unlimited-ish |

Frano checked the assessment brief: it gives headings but no per-chapter word
counts, so the split above is his judgement, not a rule.

### What counts as a contribution

An expected, monotonic result is not a contribution. His analogy: reporting that
sunrise moved by one minute a day is nothing; finding that it jumps backwards on
a particular day, and explaining why, is the contribution. Look for the places
where the model output is counterintuitive, and explain the mechanism.

---

## 7. Action items

| Owner | Action |
|---|---|
| Samir | Reply to Clinton per section 2. Draft below. |
| Samir | Finalise the model; source any remaining inputs from public data only. |
| Samir | Finish the interactive dashboard for internal use; capture screenshots. |
| Alex | Rebuild the policy timeline as two tracks, with document links, instrument classification and quantified per-date impacts. |
| Alex | Add the new UK PM's position. |
| Riya | Develop the TCE asset-specificity argument beyond vessels, per section 5. |
| All | Six to eight academic articles each; find an existing framework to apply. |
| All | Drop the company-data objective from the write-up; strengthen theory to compensate. |

---

## 8. Draft reply to Clinton

Not sent. Review and send from your own account.

> Hi Clinton,
>
> Thanks for coming back to us, and for the links, they are useful and we will
> work through them. We completely understand that the operational data cannot be
> shared given the confidentiality involved, so no problem at all on that.
>
> We are continuing with the model on publicly available sources and expect to
> have the project finished in the next three to four weeks. Once it is done we
> would be glad to share the final report and the model with you.
>
> If it would be of interest, we would also be happy to walk you and the team
> through the finished work on a short Teams call. Our supervisor and Sam would
> be welcome to join as well if that is useful.
>
> Thanks again for your time on this.
>
> Best,
> Samir

---

## Appendix: chronology of the MCG engagement

Reconstructed live in the meeting for Frano to report to the programme team.
Several dates were checked against calendars during the call; those still
uncertain are marked.

| Date (2026) | Event |
|---|---|
| 21 May | First team meeting with Clinton (Teams). |
| 22 May | Supervisor meeting, before Frano's AI conference. Things reported as going well at this point. |
| 29 May | Second meeting with Clinton. He proposes splitting the group and building platforms. Team reports no progress pending approval. |
| 30 May | Clinton sends an article / Drive material. Described as low value. |
| early June | Giang circulates a document summarising her own call with Clinton; the team's research questions are reset from it. Company data ruled out at this point, original research questions retained. |
| 8 June | Samir emails Frano flagging scope problems with the company. |
| 12 June | Formal complaint email to all parties. |
| 18 June | PLM and Giang respond with new ground rules: email only, no WhatsApp group, no weekly meetings, revised project scope. |
| 23 June | Supervisor meeting; focus narrowed. |
| 25 June | Samir emails Clinton requesting data. Reply confirms UK CBAM not yet in force, two corridors, shipping required, hydrogen has no de minimis threshold. No access to the Viola Connect platform. Nothing internal provided. |
| 27 July | Supervisor meeting. `[uncertain: transcript also says 29]` |
| 29 July | Clinton asks for latest work; Samir sends the dashboard link; response is a thumbs-up only. |
| 3 August | Clinton replies with generic feedback and open-source links; refuses data outright. |
| 6 August | This meeting. Data route formally abandoned. |

Note: the WhatsApp group was Clinton's own suggestion, and its closure by the
programme team appears to have been taken personally.
