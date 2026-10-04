"""
cobol_semantics.py - Faithful Python model of COBOL fixed-point PIC arithmetic

SYNTHETIC DEMONSTRATION - No real or client data.

Models one COBOL concept that causes silent payroll errors:

    PIC 9(7)V99 style truncation (not rounding):
    COBOL MULTIPLY with a result field narrower than the intermediate
    product silently truncates the excess fractional digits.  There is
    no "rounding" by default; the low-order digits vanish.  A field's
    USAGE (DISPLAY or COMP-3) does not change this; storage
    representation is not modeled (see README Limitations).

This module exposes:
    PicDecimal(value, integer_digits, frac_digits) - a fixed-point type
    that truncates on every operation, exactly as COBOL does.

Usage (standalone sanity check):
    python cobol_semantics.py
"""

from __future__ import annotations
import re
from decimal import Decimal, ROUND_DOWN, localcontext


# COBOL numeric items hold at most 38 digits (ISO 2002 limit; GnuCOBOL's maximum).
MAX_DIGITS = 38

_LITERAL = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)")


def _coerce(value) -> Decimal:
    """Turn a literal into a finite Decimal or raise ValueError."""
    if isinstance(value, bool):
        raise ValueError("bool is not a numeric literal")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(repr(value))
    elif isinstance(value, str):
        if not _LITERAL.fullmatch(value):
            raise ValueError(f"not a numeric literal: {value!r}")
        d = Decimal(value)
    else:
        raise ValueError(f"unsupported literal type: {type(value).__name__}")
    if not d.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    return d



class PicDecimal:
    """
    Models a COBOL COMP-3 / DISPLAY numeric field with truncating
    fixed-point arithmetic.

    Parameters
    ----------
    value        : numeric literal or string  (initial value)
    int_digits   : number of digits left of implied decimal (V)
    frac_digits  : number of digits right of implied decimal (V)

    Arithmetic is performed with enough internal precision to avoid
    Python rounding, then the result is *truncated* (not rounded) to
    frac_digits decimal places - exactly as COBOL MULTIPLY/ADD/COMPUTE
    behaves when no ROUNDED clause is present.
    """

    def __init__(self, value, int_digits: int, frac_digits: int,
                 signed: bool = False):
        for name, n in (("int_digits", int_digits), ("frac_digits", frac_digits)):
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                raise ValueError(f"{name} must be an int >= 0, got {n!r}")
        if not 1 <= int_digits + frac_digits <= MAX_DIGITS:
            raise ValueError(
                f"a PIC needs 1 to {MAX_DIGITS} digits, got {int_digits + frac_digits}")
        if type(signed) is not bool:
            raise ValueError(f"signed must be a bool, got {signed!r}")
        self._int_d = int_digits
        self._frac_d = frac_digits
        self._signed = signed
        self._quantize_mask = Decimal(10) ** -frac_digits
        self._value = self._truncate(_coerce(value))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _truncate(self, d: Decimal) -> Decimal:
        """Store d as a COBOL field would, no ROUNDED and no ON SIZE ERROR.

        - extra fractional digits are cut off (toward zero), never rounded
        - high-order digits beyond the integer width are dropped
        - an unsigned field keeps the absolute value
        - there is no negative zero
        """
        sign, digits, exp = d.as_tuple()
        need = len(digits) + abs(exp) + self._frac_d + 10
        with localcontext() as ctx:
            ctx.prec = max(50, need)
            n = int(abs(d).scaleb(self._frac_d, ctx).to_integral_value(rounding=ROUND_DOWN))
            n %= 10 ** (self._int_d + self._frac_d)
            out = Decimal(n).scaleb(-self._frac_d, ctx)
            if self._signed and sign and n:
                out = -out
            return out

    def _wide(self, other: "PicDecimal") -> int:
        return 2 * (self._int_d + other._int_d + self._frac_d + other._frac_d) + 10

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def value(self) -> Decimal:
        return self._value

    def assign(self, other_decimal) -> "PicDecimal":
        """
        Simulate COBOL GIVING / MOVE assignment:
        truncate then store.  Returns self for chaining.
        """
        self._value = self._truncate(_coerce(other_decimal))
        return self

    def __add__(self, other: "PicDecimal") -> Decimal:
        """Returns the raw (full-precision) sum as Decimal."""
        with localcontext() as ctx:
            ctx.prec = max(50, self._wide(other))
            return self._value + other._value

    def __mul__(self, other: "PicDecimal") -> Decimal:
        """
        Returns the raw intermediate product.
        Caller must assign() to a PicDecimal to get truncation.
        This mirrors how COBOL MULTIPLY works: the intermediate is
        widened internally, then the *result field* determines precision.
        """
        with localcontext() as ctx:
            ctx.prec = max(50, self._wide(other))
            return self._value * other._value

    def __repr__(self) -> str:
        return f"PicDecimal(9({self._int_d})V{self._frac_d}, value={self._value})"

    def __float__(self) -> float:
        return float(self._value)


# ---------------------------------------------------------------------------
# Standalone sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== PicDecimal truncation demonstration ===\n")

    # Simulate one payroll record
    rate_buggy    = PicDecimal("23.573", int_digits=4, frac_digits=2)  # PIC 9(4)V99
    hours_buggy   = PicDecimal("40.350", int_digits=3, frac_digits=1)  # PIC 9(3)V9
    gross_buggy   = PicDecimal("0",      int_digits=7, frac_digits=2)  # PIC 9(7)V99

    # MULTIPLY WS-RATE BY WS-HOURS GIVING WS-GROSS
    intermediate = rate_buggy * hours_buggy
    gross_buggy.assign(intermediate)

    exact = Decimal("23.573") * Decimal("40.350")
    print(f"  Rate input           : 23.573")
    print(f"  Hours input          : 40.350")
    print(f"  Exact product        : {exact}")
    print(f"  Buggy  gross (2 dp)  : {gross_buggy.value}")
    print(f"  Single-record loss   : {exact - gross_buggy.value}")
    print()
    print("For the batch total and its attribution by field, run:")
    print("    python3 probe.py --attribute")
