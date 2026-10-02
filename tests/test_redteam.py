"""Red-team regression tests. Each case was a wrong answer, a crash or a
drift between the README and the code before the fix."""

import os
import re
import subprocess
import sys
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cobol_semantics import PicDecimal  # noqa: E402
import probe  # noqa: E402
from probe import run_probe  # noqa: E402


def _run(*args, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "probe.py"), *args],
        capture_output=True, text=True, env=env, timeout=120,
    )


# --- value parsing ---------------------------------------------------------

@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN", "1_0", " ", "", "1e3", "0x10", "--1"])
def test_non_numeric_literals_rejected(bad):
    with pytest.raises(ValueError):
        PicDecimal(bad, int_digits=4, frac_digits=2)


def test_bool_rejected():
    with pytest.raises(ValueError):
        PicDecimal(True, int_digits=4, frac_digits=2)


def test_float_accepted_via_shortest_repr():
    assert PicDecimal(23.573, 4, 3).value == Decimal("23.573")
    assert PicDecimal(1e-07, 4, 9).value == Decimal("0.000000100")


def test_bad_field_widths_rejected():
    for i, f in [(-1, 2), (4, -1), (4.5, 2), (4, "2")]:
        with pytest.raises(ValueError):
            PicDecimal("1", int_digits=i, frac_digits=f)


# --- size, sign (behaviour confirmed against GnuCOBOL) -----------------------

def test_high_order_digits_are_dropped_on_overflow():
    # PIC 9(7)V99 receiving 123456789.55 keeps 3456789.55 (no ON SIZE ERROR)
    p = PicDecimal("123456789.55", int_digits=7, frac_digits=2)
    assert p.value == Decimal("3456789.55")


def test_assign_overflow_drops_high_order_digits():
    g = PicDecimal("0", 7, 2)
    g.assign(Decimal("9999.99") * Decimal("999.9"))
    assert g.value == Decimal("9998990.00")


def test_unsigned_field_stores_absolute_value():
    assert PicDecimal("-5.55", int_digits=3, frac_digits=1).value == Decimal("5.5")


def test_signed_field_keeps_sign_and_truncates_toward_zero():
    p = PicDecimal("-5.59", int_digits=3, frac_digits=1, signed=True)
    assert p.value == Decimal("-5.5")


def test_no_negative_zero():
    p = PicDecimal("-0.04", int_digits=3, frac_digits=1, signed=True)
    assert str(p.value) == "0.0"


def test_huge_value_does_not_crash():
    p = PicDecimal(10 ** 60 + 5, int_digits=70, frac_digits=2)
    assert p.value == Decimal(f"{10 ** 60 + 5}.00")
    assert p.value.as_tuple().exponent == -2


def test_assign_accepts_int_and_float():
    p = PicDecimal("0", 7, 2)
    assert p.assign(3).value == Decimal("3.00")
    assert p.assign(2.999).value == Decimal("2.99")


def test_sum_of_wide_fields_is_not_rounded():
    a = PicDecimal("1" + "0" * 29, int_digits=40, frac_digits=0)
    b = PicDecimal("1", int_digits=40, frac_digits=0)
    assert a + b == Decimal("1" + "0" * 28 + "1")


# --- probe boundaries --------------------------------------------------------

def test_zero_records_is_a_clean_error():
    with pytest.raises(ValueError):
        run_probe(0)


@pytest.mark.parametrize("bad", [-1, True, 1.5, "3"])
def test_bad_record_counts_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        run_probe(bad)


def test_record_count_capped_at_cobol_counter_limit():
    # payroll.cob counts with PIC 9(6); at 999999 its loop never ends.
    assert probe.MAX_RECORDS == 999_998
    with pytest.raises(ValueError):
        run_probe(probe.MAX_RECORDS + 1)
    r = _run("--records", "1000000")
    assert r.returncode == 1 and "must be" in r.stderr


def test_cli_exit_codes():
    assert _run("--records", "0").returncode == 1
    assert _run("--records", "abc").returncode == 2
    assert _run("--records", "3").returncode == 0


def test_report_survives_ascii_stdout():
    r = _run("--records", "5", "--verbose", env_extra={"PYTHONIOENCODING": "ascii"})
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


# --- README must match the code ----------------------------------------------

def _readme():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        return fh.read()


def test_readme_expected_output_block_is_the_real_output():
    text = _readme()
    block = re.search(r"prints \(numbers are deterministic\):\n\n```\n(.*?)\n```", text, re.S).group(1)
    out = _run("--records", "47312").stdout
    real = out.strip("\n").split("\n\n")[0]
    assert block.strip() == real.strip()


def test_readme_cent_figures_match_the_probe():
    res = run_probe(47_312)
    cents = f"${res['cumulative_error'].quantize(Decimal('0.01')):,}"
    text = _readme()
    assert text.count(cents) == 2, cents
    first = res["first_error"]
    assert first.index == 1
    assert f"${first.error} short" in text.replace("**", "") or f"${first.error.normalize()} short" in text
    assert "47,312" in text


# --- COBOL source agrees with the model at the boundaries and at the headline --

import shutil  # noqa: E402


@pytest.mark.skipif(shutil.which("cobc") is None, reason="GnuCOBOL (cobc) not installed")
@pytest.mark.parametrize("n", [1, 7, 99, 100, 101, 47312])
def test_cobol_agrees_at_boundaries(tmp_path_factory, n):
    exe = tmp_path_factory.mktemp("cob") / "payroll_run"
    subprocess.run(["cobc", "-x", os.path.join(ROOT, "payroll.cob"), "-o", str(exe)],
                   check=True, capture_output=True)
    out = subprocess.run([str(exe)], input=f"{n}\n", capture_output=True,
                         text=True, check=True, timeout=60).stdout
    res = run_probe(n)
    assert f"{res['cumulative_buggy']:,.2f}" in out
    assert f"{res['cumulative_correct']:,.3f}" in out
    assert f"{res['cumulative_error']:,.3f}" in out
