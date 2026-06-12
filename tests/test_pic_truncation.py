"""
tests/test_pic_truncation.py
SYNTHETIC DEMONSTRATION — No real or client data.

Tests that:
1. PicDecimal truncates (not rounds) exactly as COBOL does.
2. The buggy payroll arithmetic produces demonstrably wrong per-record gross.
3. The probe detects the first truncation at record #1 (confirmed output).
4. The compounding total error over 47 000 records is in the expected range.
5. The compounding math is internally consistent (correct - buggy == reported error).
"""

import sys
import os
from decimal import Decimal

# Ensure project root is on sys.path so imports work from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from cobol_semantics import PicDecimal
from probe import probe_record, run_probe, generate_records, PayrollRecord


# ---------------------------------------------------------------------------
# 1. PicDecimal: truncation behaviour
# ---------------------------------------------------------------------------

class TestPicDecimalTruncation:
    """PicDecimal must truncate, never round."""

    def test_two_dp_field_truncates_third_decimal(self):
        """PIC 9(4)V99 stores at most 2 decimal places; the third is dropped."""
        p = PicDecimal("23.579", int_digits=4, frac_digits=2)
        assert p.value == Decimal("23.57"), (
            f"Expected 23.57 (truncation), got {p.value}"
        )

    def test_truncation_not_rounding(self):
        """23.575 should truncate to 23.57, NOT round to 23.58."""
        p = PicDecimal("23.575", int_digits=4, frac_digits=2)
        assert p.value == Decimal("23.57")

    def test_one_dp_field_truncates_second_decimal(self):
        """PIC 9(3)V9 stores at most 1 decimal place."""
        p = PicDecimal("40.35", int_digits=3, frac_digits=1)
        assert p.value == Decimal("40.3")

    def test_zero_initial_value(self):
        p = PicDecimal("0", int_digits=7, frac_digits=2)
        assert p.value == Decimal("0.00")

    def test_assign_truncates(self):
        """assign() must truncate the supplied Decimal."""
        p = PicDecimal("0", int_digits=7, frac_digits=2)
        p.assign(Decimal("949.9914"))
        assert p.value == Decimal("949.99"), (
            f"Expected 949.99, got {p.value}"
        )

    def test_multiply_returns_full_precision_intermediate(self):
        """
        The * operator returns the full-precision intermediate product.
        Truncation happens only on assign().
        """
        rate  = PicDecimal("23.573", int_digits=4, frac_digits=3)
        hours = PicDecimal("40.350", int_digits=3, frac_digits=2)
        intermediate = rate * hours
        # 23.573 × 40.350 = 950.9695 (full precision)
        assert intermediate == Decimal("23.573") * Decimal("40.350")

    def test_three_dp_field_retains_third_decimal(self):
        """PIC 9(4)V999 must retain 3 decimal places."""
        p = PicDecimal("23.573", int_digits=4, frac_digits=3)
        assert p.value == Decimal("23.573")


# ---------------------------------------------------------------------------
# 2. Single-record: the bug fires on record #1
# ---------------------------------------------------------------------------

class TestSingleRecordBug:
    """The first synthetic record should produce a measurable truncation error."""

    def setup_method(self):
        recs = list(generate_records(1))
        self.rec = recs[0]
        self.result = probe_record(self.rec)

    def test_first_record_rate_input(self):
        """Record #1 rate should be 23.573 (deterministic input)."""
        assert self.rec.rate_str == "23.573"

    def test_first_record_hours_input(self):
        """Record #1 hours should be 40.30 (index=1, 1%7=1, 40.25+0.05)."""
        assert self.rec.hours_str == "40.30"

    def test_buggy_gross_is_less_than_correct(self):
        """Buggy gross must be strictly less than correct gross due to truncation."""
        assert self.result.gross_buggy < self.result.gross_correct, (
            f"Expected buggy < correct, got {self.result.gross_buggy} vs "
            f"{self.result.gross_correct}"
        )

    def test_error_is_positive(self):
        """Truncation always causes under-payment; error must be > 0."""
        assert self.result.error > Decimal("0")

    def test_error_matches_first_record_probe_output(self):
        """
        The per-record error on record #1 must match the value observed
        in verified probe output: Δ=0.1210
        """
        assert self.result.error == Decimal("0.1210"), (
            f"Expected 0.1210, got {self.result.error}"
        )

    def test_buggy_gross_matches_probe_output(self):
        """Record #1 buggy gross must equal the probe's confirmed value: 949.87"""
        assert self.result.gross_buggy == Decimal("949.87")

    def test_correct_gross_matches_probe_output(self):
        """Record #1 correct gross must equal the probe's confirmed value: 949.991"""
        assert self.result.gross_correct == Decimal("949.991")


# ---------------------------------------------------------------------------
# 3. Compounding: 47 000 record full run
# ---------------------------------------------------------------------------

class TestCompoundingError:
    """The error must compound to a substantial, reproducible total."""

    @pytest.fixture(scope="class")
    def results(self):
        return run_probe(47_000)

    def test_record_count(self, results):
        assert results["n_records"] == 47_000

    def test_buggy_total_matches_probe_output(self, results):
        """
        Verified probe output: Buggy total = $44,996,120.72
        Allow ±$0.01 for any future platform Decimal precision edge case.
        """
        expected = Decimal("44996120.72")
        diff = abs(results["cumulative_buggy"] - expected)
        assert diff <= Decimal("0.01"), (
            f"Buggy total {results['cumulative_buggy']} not within $0.01 of {expected}"
        )

    def test_correct_total_matches_probe_output(self, results):
        """Verified probe output: Correct total = $45,036,664.777"""
        expected = Decimal("45036664.777")
        diff = abs(results["cumulative_correct"] - expected)
        assert diff <= Decimal("0.01")

    def test_compounding_error_matches_probe_output(self, results):
        """
        Verified probe output: Compounding error = $40,544.057
        This is the core assertion — the bug produces ~$40.5K loss on 47 000 records.
        """
        expected = Decimal("40544.057")
        diff = abs(results["cumulative_error"] - expected)
        assert diff <= Decimal("0.01"), (
            f"Compounding error {results['cumulative_error']} not within $0.01 "
            f"of expected {expected}"
        )

    def test_compounding_error_is_positive(self, results):
        """Truncation always under-pays; total error must be positive."""
        assert results["cumulative_error"] > 0

    def test_internal_consistency(self, results):
        """correct - buggy must equal reported error exactly."""
        delta = results["cumulative_correct"] - results["cumulative_buggy"]
        assert delta == results["cumulative_error"]

    def test_error_exceeds_ten_thousand_dollars(self, results):
        """
        The compounding loss must exceed $10,000 on 47 000 records —
        a threshold that proves the failure is material, not rounding noise.
        """
        assert results["cumulative_error"] > Decimal("10000"), (
            f"Expected >$10,000 compounding error, got {results['cumulative_error']}"
        )

    def test_error_rate_below_one_percent(self, results):
        """
        The error must be <1% of total payroll — small enough to hide in
        standard reconciliation but large enough to matter forensically.
        """
        error_pct = results["cumulative_error"] / results["cumulative_correct"] * 100
        assert error_pct < Decimal("1.0"), (
            f"Expected <1% error rate, got {error_pct:.4f}%"
        )

    def test_first_error_at_record_one(self, results):
        """The truncation must fire on the very first record."""
        assert results["first_error"] is not None
        assert results["first_error"].index == 1

    def test_worst_error_list_length(self, results):
        """Probe must return exactly 10 worst-error records."""
        assert len(results["worst_errors"]) == 10


# ---------------------------------------------------------------------------
# 4. Determinism: same inputs, same outputs across runs
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Two calls to run_probe with the same N must return identical results."""

    def test_repeated_runs_are_identical(self):
        r1 = run_probe(1_000)
        r2 = run_probe(1_000)
        assert r1["cumulative_buggy"]   == r2["cumulative_buggy"]
        assert r1["cumulative_correct"] == r2["cumulative_correct"]
        assert r1["cumulative_error"]   == r2["cumulative_error"]

    def test_small_run_determinism(self):
        """10 records must always produce the same compounding error."""
        r1 = run_probe(10)
        r2 = run_probe(10)
        assert r1["cumulative_error"] == r2["cumulative_error"]


# ---------------------------------------------------------------------------
# 5. Boundary: minimum records needed to show material error
# ---------------------------------------------------------------------------

class TestBoundaryConditions:
    """Edge cases for the probe runner."""

    def test_single_record_run(self):
        r = run_probe(1)
        assert r["n_records"] == 1
        assert r["first_error"].index == 1

    def test_error_grows_with_record_count(self):
        """More records → more compounding error (monotonic growth)."""
        r_small = run_probe(100)
        r_large = run_probe(1_000)
        assert r_large["cumulative_error"] > r_small["cumulative_error"]

    def test_generate_records_count(self):
        recs = list(generate_records(50))
        assert len(recs) == 50
        assert recs[0].index == 1
        assert recs[-1].index == 50

    def test_generate_records_deterministic_rate(self):
        """Rate at index 1 must always be 23.573."""
        recs = list(generate_records(1))
        assert recs[0].rate_str == "23.573"

    def test_generate_records_deterministic_hours(self):
        """Hours at index 7 must be 40.25 + 0*0.05 = 40.25 (7%7==0)."""
        recs = list(generate_records(7))
        assert recs[6].hours_str == "40.25"
