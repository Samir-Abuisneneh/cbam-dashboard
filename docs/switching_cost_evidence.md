# Evidence on corridor switching costs

Desk research, 6 August 2026. Purpose: `model/switching.py` returns a
**breakeven switching cost** and claims no value for the real one. Without
evidence about actual sunk costs the threshold has nothing to be argued
against, which is half a finding. This file collects what a firm would
actually have to sink to move corridor, so the discussion can say which side of
the breakeven reality falls on.

Reminder of what has to be beaten, from `outputs/corridor_lock_in.csv`, under
the `benchmark_shielded` mechanism, ammonia at decision year 2026, medium
prices, 8% real:

| Beyond-horizon treatment | Breakeven switching cost | Lock-in regret |
|---|---|---|
| `truncate` | GBP 38.72 per tonne of annual contracted volume | 33.45% |
| `hold_final` | GBP 76.99 per tonne of annual contracted volume | 26.91% |

**Ammonia is the only product with a threshold to argue about.** Hydrogen's
myopic and committed corridor choices agree in every year, so it has no
reversal and no breakeven, and nothing in this file bears on it. An earlier
version of this table quoted GBP 75.36 for ammonia and GBP 491.95 for
hydrogen; both came from the superseded `factor_scaled` mechanism and neither
is quotable.

Units matter here. These are per tonne of **annual** throughput, so a terminal
handling 600,000 t/yr would justify a sunk cost of roughly GBP 23m on the
`truncate` figure and GBP 46m on `hold_final`. That is the comparison to make,
not a per-shipment one.

## 1. Terminal concessions run about 15 years

Port authorities commonly grant terminal concessions on a base term of around
**15 years**, with consecutive renewals every five years subject to defined
criteria.

Source: Notteboom, Pallis and Rodrigue, *Port Economics, Management and Policy*,
chapter 4.2, "Terminal Concessions and Land Leases".
https://porteconomicsmanagement.org/pemp/contents/part4/terminal-concessions-and-land-leases/

Why it matters: this is direct support for the ten-year contract tenor assumed
in `DEFAULT_CONTRACT_TENOR_YEARS`, and it is a textbook rather than a trade
press source, so it is citable. It also means the tenor assumption is if
anything conservative.

## 2. Throughput contracts carry take-or-pay obligations

Terminal throughput contracts typically run **two to ten years** and must be
renegotiated at expiry. Most contain a **minimum throughput provision**
obliging the customer to move a minimum volume or else pay for reserved but
unused capacity.

Source: Magellan Midstream Partners LP, Form 10-K filings (FY2002, FY2011,
FY2012), SEC EDGAR.

Why it matters: this is the transaction-cost mechanism made concrete. A
take-or-pay clause means the cost of the old corridor does not fall to zero on
exit, so switching incurs the new corridor's cost **plus** the residual
obligation on
the old one. That is precisely the non-redeployability that Williamson's asset
specificity describes, evidenced in primary corporate disclosure rather than
asserted.

## 3. Ammonia terminal capital costs are large and lumpy

An ammonia import terminal is a nine-figure asset. One Middle East reference
case is put at **US$1,160 million** capex (IEEJ, 2018, cited in METI's fuel
ammonia supply cost analysis).

Source: METI, *Fuel ammonia supply cost analysis (interim report)*, September
2022. https://www.meti.go.jp/shingikai/energy_environment/nenryo_anmonia/supply_chain_tf/pdf/20220928_e0.pdf

Real projects for scale: SET Select Energy has booked capacity at a planned
**600,000 t/yr** ammonia import terminal in Hamburg; OCI has expanded its
Rotterdam ammonia import terminal from roughly 400,000 t/yr to 1.2 Mt/yr.

Sources: gasworld, Ammonia Energy Association, Port of Rotterdam.

Why it matters: it lets the breakeven be converted into something arguable. At
600,000 t/yr the ammonia breakeven corresponds to roughly GBP 23m of justified
sunk cost on `truncate` and GBP 46m on `hold_final`. A terminal costing an
order of magnitude more than that is decisive evidence of lock-in, and the
US$1,160m reference case is two orders above the `truncate` figure. Note the
capex figure is a whole-terminal cost and a switching firm may only need
incremental berth or storage access, so the honest framing is a range, not a
point.

## 4. The LNG precedent

LNG import terminals lease capacity on a **use-or-pay** basis, e.g. Petronet
LNG to GAIL and Gujarat State Petroleum Corporation.

Why it matters: LNG is the closest mature analogue to the ammonia and hydrogen
trades being modelled, and it shows the contract form is standard practice in
the sector rather than a peculiarity of one operator.

## How to use this in the discussion

The argument the evidence supports:

1. Corridor access is not spot-purchasable. It is obtained through concessions
   of roughly 15 years and throughput contracts of 2 to 10 years.
2. Those contracts carry take-or-pay clauses, so exiting early does not
   extinguish the cost of the corridor being left.
3. The underlying assets are nine-figure and immobile.
4. Therefore real switching costs plausibly sit **above** the modelled
   breakeven, and the myopic 2026 corridor choice is not merely suboptimal but
   effectively irreversible for the tenor.

What is still missing, and should be stated as a limitation: no published
figure for the incremental cost of adding a *second* corridor to an existing
operation, which is the true counterfactual. Everything above prices building
or contracting a corridor from scratch. That biases the argument toward
lock-in, and the write-up should say so.
