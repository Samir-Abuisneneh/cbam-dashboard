"""Sourcing allocation as a linear program.

The deterministic model enumerates a fixed scenario matrix and reports the cost
of each combination. It answers "what does this option cost". It cannot answer
"given a volume to source, a set of capacity limits and an emissions ceiling,
what mix of corridors and pathways is cheapest, and at what carbon price does
that mix change".

That second question is what this package adds, and it is the question the
industry partner's original brief was really asking.

Nothing here feeds a headline corridor verdict. The capacity limits are
scenario parameters chosen by the analyst, not sourced facts, so every result
in this package is conditional on assumptions that do not exist in `config/`.
See `allocation.CapacityAssumptions` for what that means in practice.
"""
