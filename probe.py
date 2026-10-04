"""
probe.py - COBOL PIC 9(7)V99 fixed-point truncation probe
SYNTHETIC DEMONSTRATION - No real or client data.

Runs N deterministic synthetic payroll records through:
  - buggy COBOL-equivalent arithmetic  (PIC 9(4)V99  rate, PIC 9(3)V9  hours)
  - exact reference arithmetic         (unbounded Decimal, no truncation)

Reports:
  - Per-record truncation (first record where the error appears)
  - Compounding cumulative total error over all N records
  - Exact boundary record where the bug first fires
  - Summary table of worst-10 per-record errors

Usage:
    python probe.py                    # default: 47 312 records
    python probe.py --attribute        # loss broken down by source field
    python probe.py --records 100000   # larger batch
    python probe.py --records 47312 --verbose
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal, ROUND_DOWN, localcontext
from typing import Iterator, NamedTuple

# ---------------------------------------------------------------------------
# Re-use the PicDecimal primitive from cobol_semantics.py
# ---------------------------------------------------------------------------
from cobol_semantics import PicDecimal


# ---------------------------------------------------------------------------
# Synthetic record generator (fully deterministic, no random seed needed)
# ---------------------------------------------------------------------------

class PayrollRecord(NamedTuple):
    index: int
    rate_str: str    # e.g. "23.573"  - 3 decimal places (the "hidden" digit)
    hours_str: str   # e.g. "40.350"  - 2 decimal places


def generate_records(n: int) -> Iterator[PayrollRecord]:
    """
    Deterministic synthetic payroll records.

    rate  = 23.57 + (index % 100) * 0.003    ->  range [23.570 ... 23.867], 3 dp
    hours = 40.25 + (index %   7) * 0.05     ->  range [40.250 ... 40.550], 2 dp

    The third decimal of `rate` is what PIC 9(4)V99 silently drops.
    When multiplied by hours the dropped digit compounds.
    """
    for i in range(1, n + 1):
        # Use integer arithmetic to build exact decimal strings (no float drift)
        rate_cents_3dp = 23570 + (i % 100) * 3      # in thousandths
        hours_cents_2dp = 4025 + (i % 7) * 5        # in hundredths

        rate_str  = f"{rate_cents_3dp // 1000}.{rate_cents_3dp % 1000:03d}"
        hours_str = f"{hours_cents_2dp // 100}.{hours_cents_2dp % 100:02d}"
        yield PayrollRecord(index=i, rate_str=rate_str, hours_str=hours_str)


# ---------------------------------------------------------------------------
# Core probe logic
# ---------------------------------------------------------------------------

class RecordResult(NamedTuple):
    index: int
    rate_str: str
    hours_str: str
    gross_buggy: Decimal
    gross_correct: Decimal
    error: Decimal          # exact - buggy  (always >= 0 for truncation)


def probe_record(rec: PayrollRecord) -> RecordResult:
    """Compute both arithmetic paths for one record."""

    # --- Buggy path: PIC 9(4)V99 x PIC 9(3)V9 -> PIC 9(7)V99 ---
    rate_b  = PicDecimal(rec.rate_str,  int_digits=4, frac_digits=2)   # drops 3rd dp
    hours_b = PicDecimal(rec.hours_str, int_digits=3, frac_digits=1)   # drops 2nd dp
    gross_b = PicDecimal("0",           int_digits=7, frac_digits=2)
    gross_b.assign(rate_b * hours_b)

    # --- Exact path: unbounded Decimal, nothing is truncated ---
    gross_c = Decimal(rec.rate_str) * Decimal(rec.hours_str)

    error = gross_c - gross_b.value
    return RecordResult(
        index=rec.index,
        rate_str=rec.rate_str,
        hours_str=rec.hours_str,
        gross_buggy=gross_b.value,
        gross_correct=gross_c,
        error=error,
    )


# payroll.cob counts records in PIC 9(6) and its loop never ends at 999999
# (the index wraps to 0), so the probe stops one short of that.
MAX_RECORDS = 999_998


class Attribution(NamedTuple):
    n_records: int
    exact: Decimal
    buggy: Decimal
    hours_field: Decimal     # step 1: PIC 9(3)V9 drops the 2nd hours decimal
    rate_field: Decimal      # step 2: PIC 9(4)V99 drops the 3rd rate decimal
    multiply: Decimal        # step 3: GIVING PIC 9(7)V99 drops the product's extra decimals
    worst_index: int
    worst_error: Decimal

    @property
    def loss(self) -> Decimal:
        return self.exact - self.buggy


def attribute(n_records: int) -> Attribution:
    """Split the total loss by source. The three steps are applied in order
    (hours, rate, product) and sum exactly to exact - buggy."""
    run_probe(n_records)  # same validation as the probe
    exact = buggy = s_hours = s_rate = s_mul = Decimal("0")
    worst_i, worst_e = 0, Decimal("-1")
    for rec in generate_records(n_records):
        a, b = Decimal(rec.rate_str), Decimal(rec.hours_str)
        b1 = PicDecimal(rec.hours_str, int_digits=3, frac_digits=1).value
        a1 = PicDecimal(rec.rate_str, int_digits=4, frac_digits=2).value
        g = PicDecimal("0", int_digits=7, frac_digits=2).assign(a1 * b1).value
        s_hours += a * b - a * b1
        s_rate += a * b1 - a1 * b1
        s_mul += a1 * b1 - g
        exact += a * b
        buggy += g
        if a * b - g > worst_e:
            worst_i, worst_e = rec.index, a * b - g
    return Attribution(n_records, exact, buggy, s_hours, s_rate, s_mul, worst_i, worst_e)


def print_attribution(at: Attribution) -> None:
    loss = at.loss

    def share(x: Decimal) -> str:
        return f"{x / loss * 100:.2f}%"

    print(f"  Loss attribution over {at.n_records:,} records - SYNTHETIC")
    print(f"  Exact payroll total      : ${at.exact:,.5f}")
    print(f"  Buggy payroll total      : ${at.buggy:,.2f}")
    print(f"  Total loss               : ${loss:,.5f}")
    print(f"  1. hours field PIC 9(3)V9 drops 2nd decimal : "
          f"${at.hours_field:,.5f} ({share(at.hours_field)})")
    print(f"  2. rate field PIC 9(4)V99 drops 3rd decimal : "
          f"${at.rate_field:,.5f} ({share(at.rate_field)})")
    print(f"  3. MULTIPLY GIVING PIC 9(7)V99 drops product decimals : "
          f"${at.multiply:,.5f} ({share(at.multiply)})")
    print(f"  Worst single-record loss : ${at.worst_error:,.5f} at record #{at.worst_index:,}")


def run_probe(n_records: int, verbose: bool = False) -> dict:
    """
    Run the full probe over n_records synthetic records.

    Returns a results dict with all key metrics.
    Raises ValueError unless 1 <= n_records <= MAX_RECORDS.
    """
    if isinstance(n_records, bool) or not isinstance(n_records, int):
        raise TypeError("n_records must be an int")
    if not 1 <= n_records <= MAX_RECORDS:
        raise ValueError(f"--records must be between 1 and {MAX_RECORDS:,}")
    cumulative_buggy   = Decimal("0")
    cumulative_correct = Decimal("0")
    first_error_record = None
    worst_errors: list[RecordResult] = []

    for rec in generate_records(n_records):
        result = probe_record(rec)

        cumulative_buggy   += result.gross_buggy
        cumulative_correct += result.gross_correct

        if first_error_record is None and result.error > 0:
            first_error_record = result

        # Track top-10 worst single-record errors for the report
        worst_errors.append(result)
        worst_errors.sort(key=lambda r: r.error, reverse=True)
        if len(worst_errors) > 10:
            worst_errors.pop()

        if verbose and rec.index <= 5:
            print(
                f"  rec {rec.index:6d}  "
                f"rate={rec.rate_str}  hours={rec.hours_str}  "
                f"buggy={result.gross_buggy:.2f}  "
                f"exact={result.gross_correct:.5f}  "
                f"delta={result.error:.4f}"
            )

    cumulative_error = cumulative_correct - cumulative_buggy

    return {
        "n_records":         n_records,
        "cumulative_buggy":  cumulative_buggy,
        "cumulative_correct": cumulative_correct,
        "cumulative_error":  cumulative_error,
        "first_error":       first_error_record,
        "worst_errors":      worst_errors,
    }


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(results: dict) -> None:
    n   = results["n_records"]
    cb  = results["cumulative_buggy"]
    cc  = results["cumulative_correct"]
    ce  = results["cumulative_error"]
    fe  = results["first_error"]
    we  = results["worst_errors"]

    print()
    print("=" * 65)
    print("  COBOL PIC 9(7)V99 Truncation Probe - SYNTHETIC")
    print("=" * 65)
    print(f"  Records processed       : {n:,}")
    print(f"  Buggy   payroll total   : ${cb:,.2f}")
    print(f"  Exact   payroll total   : ${cc:,.5f}")
    print(f"  Compounding error (loss): ${ce:,.5f}")
    print(f"  Error as % of total     : {(ce / cc * 100):.4f}%")
    print()

    if fe:
        print(f"  First truncation at record #{fe.index}")
        print(f"    rate={fe.rate_str}  hours={fe.hours_str}")
        print(f"    buggy={fe.gross_buggy:.2f}  exact={fe.gross_correct:.5f}  "
              f"delta={fe.error:.4f}")
    print()

    print("  Top-10 worst single-record errors:")
    print(f"  {'Rec':>8}  {'Rate':>9}  {'Hours':>7}  {'Buggy':>10}  "
          f"{'Exact':>13}  {'Error':>8}")
    print("  " + "-" * 62)
    for r in sorted(we, key=lambda x: x.error, reverse=True):
        print(
            f"  {r.index:>8,}  {r.rate_str:>9}  {r.hours_str:>7}  "
            f"{r.gross_buggy:>10.2f}  {r.gross_correct:>13.5f}  "
            f"{r.error:>8.4f}"
        )
    print()
    print("  WHY STANDARD AUDITS MISS THIS:")
    print("  A reconciliation that sums the stored (truncated) fields agrees")
    print("  with itself, so the dropped digits never show up in the totals.")
    print("  Replaying the batch with exact arithmetic exposes the gap.")
    print("  Run --attribute to see which field causes the loss.")
    print("=" * 65)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="COBOL PIC 9(7)V99 truncation probe (synthetic data)"
    )
    parser.add_argument(
        "--records", type=int, default=47_312,
        help="Number of synthetic payroll records to process (default: 47312)"
    )
    parser.add_argument(
        "--attribute", action="store_true",
        help="Print the loss broken down by source (hours field, rate field, product)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print first 5 records side-by-side"
    )
    args = parser.parse_args()

    if args.attribute:
        try:
            at = attribute(args.records)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        print_attribution(at)
        return
    try:
        results = run_probe(args.records, verbose=args.verbose)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print_report(results)


if __name__ == "__main__":
    main()
