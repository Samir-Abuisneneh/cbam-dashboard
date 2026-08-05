# Canada carbon pricing: a political-economy case study

Drafted 5 August 2026, from a timeline compiled by Alex (Student 4). Feeds
the political-economy research task set in the 27 July 2026 supervisor
meeting (see the project memory for the full brief) and the model's origin
carbon price input for the Halifax-Hamburg corridor.

## Why Canada is worth a case study of its own

The research task asked whether policy is likely to visibly change when
government changes, per country in the model, and treated the United States
and the European Union/United Kingdom/China as the two poles: the US
expected to be volatile because it has never been bound by the Paris
Agreement or the earlier Kyoto Protocol at the federal treaty level, and the
EU, UK and China expected to be stable, either because commitments sit at
treaty level (EU, UK) or because they run through multi-year state planning
rather than electoral cycles (China's Five-Year Plans). Canada was not
explicitly placed on that spectrum, and the timeline below shows it does not
sit cleanly at either end. Part of its carbon pricing system was repealed
outright. Another part survived a change of government, years of provincial
legal challenge, and a change of government's own policy platform, largely
intact.

## What actually happened, in order

Canada's carbon price began as a single law with two halves. The
Greenhouse Gas Pollution Pricing Act, in force from June 2018, set a
consumer fuel charge on petrol, diesel and heating fuel alongside an
Output-Based Pricing System (OBPS) for large industrial facilities. Only the
second half matters to this model, since it is what creates a domestic
carbon cost on Canadian hydrogen and ammonia production that Article 9 of
Regulation (EU) 2023/956 allows an EU importer to deduct from its carbon
border charge.

The law was contested from early on. Saskatchewan, Ontario and Alberta each
challenged it in provincial appeal courts between 2019 and 2020, arguing it
intruded on provincial jurisdiction over natural resources. Saskatchewan and
Ontario lost; Alberta's court found the law unconstitutional. The dispute
went to the Supreme Court of Canada, which upheld the law on 25 March 2021 by
six votes to three, ruling that setting a minimum national carbon pricing
standard was a matter of national concern under the constitution. That
ruling looked, at the time, like the end of the legal question.

It was not the end of the political one. On 1 April 2025 the federal
government set the consumer fuel charge to zero, and British Columbia and
the Northwest Territories dropped their own consumer carbon taxes the same
day. Saskatchewan paused its industrial pricing system on the same date. On
12 March 2026 the federal government went further with Bill C-4, which
permanently repealed the consumer fuel charge, backdated to April 2025. By
this point the retail half of Canada's carbon pricing system, in force for
under seven years and upheld by the country's highest court, had been
dismantled by ordinary legislation rather than another court challenge.

The industrial system was treated differently. Bill C-4 left the OBPS in
place, and on 15 May 2026 the federal government published a revised
industrial price path rather than abandoning it: 95 Canadian dollars per
tonne of CO2-equivalent (CO2e, a unit that expresses the warming effect of
different greenhouse gases in terms of an equivalent amount of CO2) in 2026,
held flat at 100 from 2027 through 2029, then rising to 115 in 2030, 130 in
2035 and 140 in 2040. This replaced the December 2020 plan, which had set a
much steeper path to 170 Canadian dollars by 2030. The revision is a real
cut in ambition compared with the abandoned plan, not a rounding change: by
2030 the new path sits 55 Canadian dollars below where the old one would
have landed.

One further complication sits underneath the federal figure. The price a
Canadian industrial facility actually pays is not uniform across the
country, because OBPS compliance credits trade provincially. By mid-2026,
credits were trading around 65 Canadian dollars in British Columbia, around
72 in Ontario, and as low as roughly 37.50 in provinces where cheaper
Alberta-linked credits are available. The federal benchmark figure this
model uses is a ceiling, not a confirmed price any specific producer pays.

## Reading the pattern

Two features of this timeline matter more than the headline price change on
its own. First, the two halves of the same law diverged sharply once
political pressure was applied to both. The consumer half, which is visible
to individual voters at the petrol pump, was repealed outright within a
single electoral cycle of the pressure appearing. The industrial half, which
is largely invisible to voters and matters mainly to exporters and trading
partners, was revised downward but not repealed, and it still exists as a
functioning price on the date this note is written. A policy mechanism with
a direct international or trade dimension appears to have survived
political pressure that a domestically visible mechanism did not.

Second, the Supreme Court ruling did not prevent this divergence, and it was
not supposed to. The Court settled a jurisdictional question, whether Ottawa
could set a national minimum standard at all, not a question about the
level that standard would be set at or how long any government would keep
it there. Judicial entrenchment secured the federal government's authority
to run a national carbon price; it did not secure any particular price path
under that authority. This is a useful distinction to carry into the
model's treatment of regulatory certainty more broadly: a legal ruling that
a policy is constitutional is not the same claim as a policy being immune
to erosion.

Set against the research task's original framing, Canada is best read as a
partial case rather than a clean example of either pole. It is not as
volatile as the US case is expected to be, since Canada's industrial carbon
price never disappeared and the underlying legal authority to run one was
tested and upheld rather than contested indefinitely. It is also plainly
not as stable as the EU, UK or China cases, since a substantial share of the
original 2018 law, the consumer half, no longer exists, and the surviving
half was cut back from its original ambition under sustained provincial and
political pressure. The Canadian pattern looks closer to selective
persistence: the parts of a climate policy regime that carry a trade or
export dimension proving more durable than the parts that are purely
domestic, even within one country's own law.

## What this means for the model

Two consequences follow for the corridor cost model itself, beyond the
numeric correction already made to `ORIGIN_CARBON_PRICE_CANADA_CAD_PER_TCO2E_BY_YEAR`
in `cbam_model/config/regulatory_constants.py`.

The origin carbon price is now modelled as a year-varying schedule rather
than a single flat figure, which is a closer match to how the underlying
policy actually behaves: it has already changed once, materially, within
the model's own 2026-2030 run window. Treating it as fixed would have
understated how much this input can move even without a change of
government, since the 15 May 2026 revision happened under the same
governing party that set the original 2020 plan.

The provincial price variation is a genuine limitation worth stating
plainly rather than resolving. The model uses the federal benchmark because
it is what Nova Scotia, EverWind's own jurisdiction, actually applies, but
the wide spread between provinces (roughly 37.50 to 72 Canadian dollars per
tonne in mid-2026, against a federal benchmark of 95) shows that even a
correctly sourced national figure can diverge from what a specific facility
pays. This is the same shape of problem as the OBPS benchmark-versus-actual
distinction already flagged in the regulatory constants module: a headline
rate that is a ceiling, not a confirmed effective price.

For the theoretical framework chapter, this case sits naturally under
Institutional Theory rather than Transaction Cost Economics: the finding is
about which parts of a regulatory regime persist under political pressure
and why, not about the cost of contracting or asset specificity between
firms. The mechanism at work resembles institutional layering, where a
newer, trade-facing rule (the industrial system) survives inside an older
statute even as a politically exposed sibling rule (the consumer charge) is
stripped out of the same law, rather than outright institutional collapse
or simple continuity.

## Sources

- Government of Canada, Greenhouse Gas Pollution Pricing Act and OBPS
  guidance: https://www.canada.ca/en/environment-climate-change/services/climate-change/pricing-pollution-how-it-will-work/carbon-pollution-pricing-federal-benchmark-information.html
- Government of Canada, "A Healthy Environment and a Healthy Economy"
  (December 2020 climate plan, superseded): https://www.canada.ca/en/services/environment/weather/climatechange/climate-plan/climate-plan-overview/healthy-environment-healthy-economy.html
- Reference to Reference re Greenhouse Gas Pollution Pricing Act, 2021 SCC
  11 (Supreme Court of Canada, 25 March 2021)
- carboncredits.com, "Canada's Carbon Pricing Reset in 2026: Will Industry
  Step Up or Stall Climate Progress?": https://carboncredits.com/canadas-carbon-pricing-reset-in-2026-will-industry-step-up-or-stall-climate-progress/

Timeline compiled by Alex (Student 4), 5 August 2026.
