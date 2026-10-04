"""
tests/test_hostile.py - one test per finding of the 2026-10-04 hostile review
(K1, H1-H4, M1-M6). See RED-RUN-REVIEW.txt for the findings.
SYNTHETIC DEMONSTRATION - No real or client data.
"""
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal, ROUND_DOWN

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import probe  # noqa: E402
from cobol_semantics import PicDecimal  # noqa: E402

HAVE_COBC = shutil.which("cobc") is not None
needs_cobc = pytest.mark.skipif(not HAVE_COBC, reason="GnuCOBOL (cobc) not installed")


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def _run(*args):
    return subprocess.run([sys.executable, "-B", os.path.join(ROOT, "probe.py"), *args],
                          capture_output=True, text=True, timeout=120, cwd=ROOT)


def _t(x, q):
    return x.quantize(Decimal(q), rounding=ROUND_DOWN)


# ---- independent oracle (does not use probe.attribute / probe_record) -------

def _independent(n):
    ex = bu = h = r = m = Decimal(0)
    worst = Decimal(0)
    for i in range(1, n + 1):
        a = Decimal(f"{(23570 + (i % 100) * 3) / 1000:.3f}")
        b = Decimal(f"{(4025 + (i % 7) * 5) / 100:.2f}")
        b1, a1 = _t(b, "0.1"), _t(a, "0.01")
        g = _t(a1 * b1, "0.01")
        ex += a * b
        bu += g
        h += a * b - a * b1
        r += a * b1 - a1 * b1
        m += a1 * b1 - g
        worst = max(worst, a * b - g)
    return ex, bu, h, r, m, worst


# ---- K1 ----------------------------------------------------------------------

def _attr_stdout():
    r = _run("--attribute")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_k1_attribute_matches_independent_decomposition():
    ex, bu, h, r, m, worst = _independent(47_312)
    at = probe.attribute(47_312)
    assert (at.exact, at.buggy) == (ex, bu)
    assert (at.hours_field, at.rate_field, at.multiply) == (h, r, m)
    assert at.worst_error == worst
    assert at.hours_field + at.rate_field + at.multiply == at.loss
    # the finding itself: the narrow hours field dominates, the product step is tiny
    assert at.hours_field > at.rate_field > at.multiply
    assert at.multiply / at.loss < Decimal("0.01")


def test_k1_command_prints_every_source_and_the_worst_record():
    out = _attr_stdout()
    at = probe.attribute(47_312)
    for needle in (f"${at.hours_field:,.5f}", f"${at.rate_field:,.5f}", f"${at.multiply:,.5f}",
                   f"${at.worst_error:,.5f}", f"#{at.worst_index:,}", f"${at.loss:,.5f}"):
        assert needle in out, needle


def test_k1_readme_block_and_numbers_equal_command_output():
    text = _read("README.md")
    m = re.search(r"python3 probe\.py --attribute` prints:\n\n```\n(.*?)\n```", text, re.S)
    assert m, "README must embed the --attribute output"
    assert m.group(1).strip() == _attr_stdout().strip()
    at = probe.attribute(47_312)
    cents = f"${at.loss.quantize(Decimal('0.01'), rounding=ROUND_DOWN) + Decimal('0.01'):,}"
    assert cents in text  # loss rounded to cents, quoted in the prose
    for pct in re.findall(r"\(([\d.]+%)\)", m.group(1)):
        assert pct in text


def test_k1_readme_does_not_blame_the_multiply_alone():
    text = _read("README.md")
    assert "silently drops sub-cent digits" not in text
    assert "intermediate has 3 decimal digits; the 3rd is silently dropped" not in text


# ---- H1 ----------------------------------------------------------------------

@pytest.mark.parametrize("n", [1, 7, 100, 47_312])
def test_h1_reference_total_is_the_exact_sum(n):
    ex, bu, *_ = _independent(n)
    res = probe.run_probe(n)
    assert res["cumulative_correct"] == ex
    assert res["cumulative_buggy"] == bu
    assert res["cumulative_error"] == ex - bu


def test_h1_report_labels_the_exact_total_with_all_its_digits():
    out = _run("--records", "47312").stdout
    ex = _independent(47_312)[0]
    assert f"${ex:,.5f}" in out
    assert "Correct payroll total" not in out


# ---- H2 ----------------------------------------------------------------------

_PIC = re.compile(r"\bPIC\s+([A-Z0-9()V.,+*$-]+)")


def _pic_strings():
    found = {}
    for name in ("README.md", "probe.py", "payroll.cob", "cobol_semantics.py"):
        for raw in _PIC.findall(_read(name)):
            found.setdefault(raw.rstrip(".,"), name)
    return found


def _pic_ok(p):
    """Repo PIC parser: balanced repeat counts, at most one V, at least one digit position."""
    if p.count("V") > 1 or p.count("(") != p.count(")") or not p:
        return False
    return re.fullmatch(r"(?:S?(?:[9ZX*]|\(\d+\))*(?:V(?:[9ZX*]|\(\d+\))*)?)|[-+$A-Z0-9(),.*]+", p) is not None \
        and re.search(r"[9ZX]", p) is not None


def test_h2_no_invalid_double_v_anywhere():
    for name in ("README.md", "probe.py", "payroll.cob", "cobol_semantics.py"):
        assert "V9(7)V99" not in _read(name), name


def test_h2_every_pic_string_parses_with_the_repo_parser():
    pics = _pic_strings()
    assert pics, "no PIC strings found"
    bad = [p for p in pics if not _pic_ok(p) or p.count("V") > 1]
    assert not bad, bad


@needs_cobc
def test_h2_every_pic_string_compiles_with_cobc(tmp_path):
    pics = sorted(_pic_strings())
    src = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. T.",
           "       DATA DIVISION.", "       WORKING-STORAGE SECTION."]
    src += [f"       01 X{i} PIC {p}." for i, p in enumerate(pics)]
    src += ["       PROCEDURE DIVISION.", "           STOP RUN."]
    f = tmp_path / "t.cob"
    f.write_text("\n".join(src) + "\n")
    r = subprocess.run(["cobc", "-fsyntax-only", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---- COBOL helpers -----------------------------------------------------------

@pytest.fixture(scope="module")
def cobol_exe(tmp_path_factory):
    if not HAVE_COBC:
        pytest.skip("GnuCOBOL (cobc) not installed")
    exe = tmp_path_factory.mktemp("cob") / "payroll_run"
    subprocess.run(["cobc", "-x", os.path.join(ROOT, "payroll.cob"), "-o", str(exe)],
                   check=True, capture_output=True)
    return str(exe)


_LABELS = {"count": "Records processed", "buggy": "Buggy   total ($)",
           "exact": "Exact   total ($)", "loss": "Cumulative loss($)"}


def parse_cobol(out):
    """Parse the labelled COBOL lines into exact signed Decimals."""
    vals = {}
    for key, label in _LABELS.items():
        m = re.search(re.escape(label) + r"\s*:\s*(.*?)\s*$", out, re.M)
        assert m, f"missing line {label!r} in {out!r}"
        raw = re.sub(r"[\s,]", "", m.group(1))
        assert re.fullmatch(r"-?\d+(\.\d+)?", raw), raw
        vals[key] = Decimal(raw)
    return vals


def assert_cobol_agrees(out, n):
    res = probe.run_probe(n)
    v = parse_cobol(out)
    assert v["count"] == n
    assert v["buggy"] == res["cumulative_buggy"]
    assert v["exact"] == res["cumulative_correct"]
    assert v["loss"] == res["cumulative_error"]
    assert v["loss"] > 0


# ---- H3 ----------------------------------------------------------------------

@needs_cobc
@pytest.mark.parametrize("n", [1, 7, 100, 1000, 47312])
def test_h3_cobol_agrees_by_parsed_exact_value_and_sign(cobol_exe, n):
    r = subprocess.run([cobol_exe], input=f"{n}\n", capture_output=True, text=True, timeout=120)
    assert r.returncode == 0
    assert_cobol_agrees(r.stdout, n)


def test_h3_comparison_has_teeth_on_a_wrong_sign():
    good = ("Records processed : 000007\nBuggy   total ($)  :  6,000.00\n"
            "Exact   total ($)  :  6,001.50000\nCumulative loss($) :  1.50000\n")
    probe_n = 7
    res = probe.run_probe(probe_n)
    forged = good.replace("Cumulative loss($) :  1.50000", "Cumulative loss($) : -        1.50000")
    assert parse_cobol(forged)["loss"] == Decimal("-1.50000")
    with pytest.raises(AssertionError):
        assert_cobol_agrees(forged, probe_n)
    assert res["cumulative_error"] > 0


@needs_cobc
def test_h3_flipped_sign_in_cobol_source_is_caught(tmp_path):
    src = _read("payroll.cob").replace("WS-ACCUM-CORRECT - WS-ACCUM-BUGGY",
                                       "WS-ACCUM-BUGGY - WS-ACCUM-CORRECT")
    assert src != _read("payroll.cob")
    (tmp_path / "m.cob").write_text(src)
    subprocess.run(["cobc", "-x", str(tmp_path / "m.cob"), "-o", str(tmp_path / "m")],
                   check=True, capture_output=True)
    out = subprocess.run([str(tmp_path / "m")], input="47312\n", capture_output=True,
                         text=True, timeout=60).stdout
    with pytest.raises(AssertionError):
        assert_cobol_agrees(out, 47312)


# ---- H4 ----------------------------------------------------------------------

def test_h4_default_record_count_comes_from_the_real_cli():
    out = _run().stdout
    assert "Records processed       : 47,312" in out


def test_h4_default_is_read_from_probe_py_source():
    m = re.search(r'"--records",[^)]*default=([\d_]+)', _read("probe.py"), re.S)
    assert m and int(m.group(1).replace("_", "")) == 47_312


# ---- M1 ----------------------------------------------------------------------

@needs_cobc
def test_m1_comp3_usage_does_not_change_the_totals(tmp_path):
    src = _read("payroll.cob")
    assert "COMP-3" in src
    outs = []
    for tag, text in (("comp3", src), ("display", src.replace(" COMP-3", ""))):
        (tmp_path / f"{tag}.cob").write_text(text)
        subprocess.run(["cobc", "-x", str(tmp_path / f"{tag}.cob"), "-o", str(tmp_path / tag)],
                       check=True, capture_output=True)
        outs.append(subprocess.run([str(tmp_path / tag)], input="47312\n", capture_output=True,
                                   text=True, timeout=60).stdout)
    assert outs[0] == outs[1]


def test_m1_headline_does_not_claim_comp3_matters():
    readme = _read("README.md")
    assert "COMP-3" not in readme.splitlines()[0]
    assert "COMP-3" not in probe.__doc__.splitlines()[1]
    assert "COMP-3" not in _run().stdout
    assert re.search(r"USAGE.*(does not|no effect|identical)", readme, re.S)


# ---- M2 ----------------------------------------------------------------------

def test_m2_limitations_list_what_is_not_modeled():
    readme = _read("README.md")
    lim = readme[readme.index("## Limitations"):]
    for term in ("sign nibble", "EBCDIC", "overpunch", "SIGN LEADING", "SEPARATE"):
        assert term in lim, term


# ---- M3 ----------------------------------------------------------------------

def test_m3_ci_installs_gnucobol_and_forbids_skips_and_checks_content():
    ci = _read(".github/workflows/ci.yml")
    assert "apt-get install -y gnucobol" in ci
    assert "cobc" in ci
    assert re.search(r"-rs", ci) and re.search(r"SKIPPED|skipped", ci)
    smoke = ci[ci.index("smoke"):]
    assert "grep" in smoke and "47,312" in smoke
    assert "# v4" in ci and "# v5" in ci  # pinned actions kept


def test_m3_readme_says_ci_runs_the_cobol_source():
    text = _read("README.md")
    row = [ln for ln in text.splitlines() if ln.startswith("| Does CI run the COBOL source?")]
    assert row and "**Yes" in row[0]


# ---- M4 ----------------------------------------------------------------------

@needs_cobc
@pytest.mark.parametrize("bad", ["abc", "0", "1000000", "999999", "", "-5", "1.5", "1 2",
                                 "12345678", "99999999999999999999999", "+5"])
def test_m4_cobol_refuses_bad_input_with_rc_1(cobol_exe, bad):
    r = subprocess.run([cobol_exe], input=f"{bad}\n", capture_output=True, text=True, timeout=60)
    assert r.returncode == 1, (bad, r.stdout)
    assert "ERROR" in r.stderr
    assert "Buggy" not in r.stdout


@needs_cobc
def test_m4_cobol_accepts_the_range_ends(cobol_exe):
    for n in (1, 5):
        r = subprocess.run([cobol_exe], input=f"{n}\n", capture_output=True, text=True, timeout=60)
        assert r.returncode == 0
        assert_cobol_agrees(r.stdout, n)


# ---- M5 ----------------------------------------------------------------------

@pytest.mark.parametrize("args,kw", [
    (("1", 0, 0), {}),
    (("1", 20, 19), {}),
    (("1", 1000000, 0), {}),
    (("-5", 3, 0), {"signed": "no"}),
    (("-5", 3, 0), {"signed": 1}),
    (("-5", 3, 0), {"signed": None}),
])
def test_m5_picdecimal_rejects_bad_shapes(args, kw):
    with pytest.raises(ValueError):
        PicDecimal(*args, **kw)


def test_m5_picdecimal_accepts_the_limits():
    assert PicDecimal("1", 38, 0).value == 1
    assert PicDecimal("1", 0, 1).value == Decimal("0.0")
    assert PicDecimal("-5", 3, 0, signed=True).value == -5


# ---- M6 ----------------------------------------------------------------------

def test_m6_demo_text_agrees_with_the_numbers():
    out = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "cobol_semantics.py")],
                         capture_output=True, text=True, timeout=60).stdout
    assert "hundreds" not in out
    exact = Decimal("23.573") * Decimal("40.350")
    buggy = _t(_t(Decimal("23.573"), "0.01") * _t(Decimal("40.350"), "0.1"), "0.01")
    assert f"Single-record loss   : {exact - buggy}" in out
    assert "probe.py --attribute" in out
    assert "hundreds" not in _read("payroll.cob")


# ---- review record -----------------------------------------------------------

def test_red_run_record_is_in_the_repo_without_home_paths():
    text = _read("RED-RUN-REVIEW.txt")
    assert not any(frag in text for frag in ("/Us" + "ers/", "~" + "/", "/ho" + "me/"))
    assert "Counts: kill 1, high 4, med 6, pass 3." in text


def test_readme_hostile_review_section_counts():
    text = _read("README.md")
    sec = text[text.index("## Hostile review 2026-10-04"):]
    assert "Found: 11" in sec and "Fixed: 11" in sec
    for fid in ("K1", "H1", "H2", "H3", "H4", "M1", "M2", "M3", "M4", "M5", "M6"):
        assert re.search(rf"^- {fid}\b", sec, re.M), fid
