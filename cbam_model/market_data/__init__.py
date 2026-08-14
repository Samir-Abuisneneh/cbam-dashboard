"""Market price series, kept separate from the sourced regulatory inputs.

Everything in `config/` traces to a named legal instrument with a retrieval
date. Nothing in here does. These are observed market prices, so they carry
market-data provenance instead: an exchange, a contract, and a vendor.

The separation is deliberate and matters. A regulatory constant is checkable
by hand against legislation and is either right or wrong. A price series is
neither. It is a sample, it has a vendor licence attached, and it is only
usable for the things samples are usable for.

Nothing in `model/` imports from here. The dependency runs one way, the same
as `analysis/`: this package may import from `model` and `config`, and neither
imports back.
"""
