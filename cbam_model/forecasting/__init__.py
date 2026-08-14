"""Statistical forecasting of the carbon price, kept out of the cost model.

Nothing here feeds a headline corridor verdict. The three carbon price
scenarios in `config/scenarios.py` are sourced anchors and remain the basis of
every published result. This package exists to answer a separate question:
what does the price history on its own support, and how does that compare with
the institutional consensus the study already relies on.

The dependency runs one way. This package reads `market_data` and `config`.
Neither imports back.
"""
