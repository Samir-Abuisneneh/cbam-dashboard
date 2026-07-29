"""Sentinel for regulatory values that have deliberately not been resolved.

The build spec is explicit that two constants must never be silently filled in
with a plausible-looking number: the UK CBAM phase-in factor, and the UK ETS
price scenario anchors. Both were left open because earlier drafts of this
project got three separate regulatory facts wrong by assuming rather than
checking.

An ordinary `None` would propagate quietly (`None * 3` raises, but
`if price:` does not, and a dict lookup returning None can survive several
frames before it fails). `Unresolved` raises on every operation including
truthiness and float conversion, so any code path that touches one of these
values fails at the point of use with a message saying what to go and check.
"""


class UnresolvedConstantError(RuntimeError):
    """Raised when a deliberately unresolved regulatory value is used."""


class Unresolved:
    """A value that must be sourced from primary legislation before use."""

    def __init__(self, name: str, question: str, how_to_resolve: str) -> None:
        self.name = name
        self.question = question
        self.how_to_resolve = how_to_resolve

    def _fail(self, *_args, **_kwargs):
        raise UnresolvedConstantError(
            f"\n\n  {self.name} has not been resolved.\n"
            f"  Open question: {self.question}\n"
            f"  To resolve:    {self.how_to_resolve}\n"
            f"  Do not substitute an estimate. See Verification Log in the build spec.\n"
        )

    # Any arithmetic, comparison, truth test or numeric cast fails loudly.
    __add__ = __radd__ = _fail
    __sub__ = __rsub__ = _fail
    __mul__ = __rmul__ = _fail
    __truediv__ = __rtruediv__ = _fail
    __lt__ = __le__ = __gt__ = __ge__ = _fail
    __bool__ = _fail
    __float__ = __int__ = _fail
    __call__ = _fail

    def __repr__(self) -> str:
        return f"<Unresolved: {self.name}>"


def is_unresolved(value) -> bool:
    """Check for an unresolved value without triggering the failure."""
    return isinstance(value, Unresolved)
