# Notes on the draft, 15 August 2026

I went through the draft against the model and checked the numbers rather than
just reading it. Most of this is structural. One thing is worth fixing before
anyone external reads it.

## First, the good news

Every figure in the Findings section is correct. I checked all of them against
the model rather than taking them on trust.

The 1,097.0 and 3,872.4 tCO2e are exactly the model's `voyage_co2e_t`, so they
include the methane and nitrous oxide on a CO2-equivalent basis, which is the
right basis for the ETS calculation. The 43,880, 13,229 and 2,936 match to the
euro and the pound. So do the distances, the voyage days, the 56,142 and 5,828
tonne cargo masses, and the 0.78 and 7.53 per tonne. Alex's Canadian price path
of 95, then 100 through 2029, then 115 is exactly what the model uses.

That is unusual and worth saying out loud. Four people, three data handovers,
and the numbers in the write-up still agree with the code.

## The one that needs fixing

Alex's methodology section describes a model we have not built.

It commits to three named scenarios, "stable, softened and accelerated". The
model has low, medium and high, and they move the carbon price only. There is no
narrative scenario dimension in the code.

It says the Article 9 deduction "is therefore varied across a low, central and
high band rather than fixed at the benchmark", after a good explanation of why
the effective price under an output-based system sits below the headline figure.
The model holds one Canadian origin price per year. The band does not exist.

It puts the IMO Net-Zero Framework in the accelerated scenario. The IMO framework
is not in the model at all. No constant, no flag.

It says the parameter ranking is reported as a tornado diagram. We have
`rank_compliance_drivers`, which produces the ranking and could be drawn as one,
but nobody has drawn it.

None of this is a mistake in the analysis. It reads like a section written while
the build was still moving, which is exactly when this happens. But we are about
to send the repo to a supervisor, and the gap between what the methodology
promises and what the code does is the sort of thing that gets found in about
ten minutes.

Two options. Build the deduction band, which is genuinely small since it is one
parameter over three values. Or rewrite the section to describe what the model
does and move the rest into further work. Given where we are in the week I would
rewrite.

## Structure

We have four literature reviews and four research gaps. Riya closes on these
areas being examined independently, Alex on regulatory uncertainty having had
little attention, Gayu on no study integrating all three schemes, and mine on
neither CBAM study covering hydrogen. Each is fine on its own. Read end to end
there is no single gap, and a reader cannot tell what the study is for. They need
to become one paragraph.

Gayu's section quotes the 57,000 euro and 2,940 pound figures and the three
times more carbon comparison. Those are our own model outputs, so they are
appearing before the methodology that produced them, and again in Findings. They
belong in Findings only.

The theoretical framework is also sitting inside Gayu's literature review.
Institutional theory and transaction cost economics are a requirement, and right
now they are buried in a paragraph about maritime carbon pricing where a marker
might not find them. They need their own subsection, or they go in the
discussion.

While we are there, I would drop first-mover advantage. Lieberman and Montgomery
is about advantage from entering a market early. Being regulated first is a cost,
not an advantage, and the sentence more or less says so. Two frameworks used
properly will read better than three used loosely.

## Findings

The biggest gap in the whole draft is that Findings contains no CBAM results.

The maritime layer is about 3% of 2030 compliance cost. Everything currently in
Findings is that 3%. The CBAM layer is the research question and the bulk of the
model, and it is not there. Neither is the price forecasting or the sourcing
optimisation, though those are new enough that nobody could have written them up
yet.

One thing to be careful about in what is already written. The 9.6 times ratio
between hydrogen and ammonia cost per tonne is arithmetically unavoidable.
Ammonia density is 682 and hydrogen is 70.8, which is a ratio of 9.63. The cargo
masses are 56,142 and 5,828, which is the same 9.63. One voyage cost divided by
two cargo masses has to give back the density ratio. It is still worth reporting
and the fleet-scale corroboration is a good addition, but we should not present
it as something the model discovered.

## Two smaller inconsistencies

Riya's section gives coal-based hydrogen with CCS as 4.92 to 10.90. The model
uses 6.28, from the unified-framework study we switched to on 4 August for
source consistency. One of the two needs updating.

Alex's section says the Canadian origin price is provincial, from Nova Scotia's
output-based system, rather than federal. The model's constant is called
`ORIGIN_CARBON_PRICE_CANADA` and carries the federal path. If the provincial
argument is the one we are making, the constant and its sourcing note should say
so.

## What is missing

Introduction, Modelling Approach, Limitations, Discussion and Conclusion are all
still empty, plus the CBAM, forecasting and optimisation findings.

Worth watching the word count. The literature review is already around 2,100
words, which is roughly a quarter of 8,000, and the discussion has not started.
Frano has said twice that the discussion carries the weight. The literature
review should not grow from here and probably needs trimming.

## Order I would go in

1. Rewrite Alex's methodology so it matches the model. Highest risk and it is a
   writing job, not a build job.
2. Write the CBAM findings. It is the research question and it is absent.
3. Turn four gap statements into one.
4. Move the results and the theory framework out of the literature review.
5. Discussion, with whatever budget is left.
