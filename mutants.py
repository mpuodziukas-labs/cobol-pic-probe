"""Mutation check: remove each defense in a scratch copy, the matching tests must go RED.
A control copy must pass first. A mutant that hangs past TIMEOUT counts as killed.
Usage: python3 mutants.py [repo_dir]   (default: the directory holding this file)"""
import pathlib, shutil, subprocess, sys, tempfile
ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent
TIMEOUT = 40                                            # seconds per test run; the 47 312 record replays need more than 8
H = "tests/test_hostile.py"
R = "tests/test_redteam.py"
C = "cobol_semantics.py"
P = "probe.py"
# (name, file, text to remove, text to put in, test file that must fail)
MUTANTS = [
    ("literal: a bool is taken as a number", C, "    if isinstance(value, bool):\n        raise", "    if False:\n        raise", R),
    ("literal: any string is parsed", C, "if not _LITERAL.fullmatch(value):", "if False:", R),
    ("width: the 38 digit ceiling raised tenfold", C, "MAX_DIGITS = 38", "MAX_DIGITS = 380", H),
    ("width: a PIC of any size is allowed", C, "if not 1 <= int_digits + frac_digits <= MAX_DIGITS:", "if False:", H),
    ("width: digit counts are not type checked", C, "if isinstance(n, bool) or not isinstance(n, int) or n < 0:", "if False:", R),
    ("width: signed flag is not type checked", C, "if type(signed) is not bool:", "if False:", H),
    ("truncate: fractions are rounded, not cut", C, "rounding=ROUND_DOWN", 'rounding="ROUND_HALF_UP"', R),
    ("truncate: high-order digits are kept", C, "n %= 10 ** (self._int_d + self._frac_d)", "n = n", R),
    ("truncate: an unsigned field keeps the sign", C, "if self._signed and sign and n:", "if sign and n:", R),
    ("probe: record cap raised tenfold", P, "MAX_RECORDS = 999_998", "MAX_RECORDS = 9_999_998", R),
    ("probe: record range is not checked", P, "if not 1 <= n_records <= MAX_RECORDS:", "if False:", R),
    ("probe: record type is not checked", P, "if isinstance(n_records, bool) or not isinstance(n_records, int):", "if False:", R),
    ("probe: rate keeps its third decimal", P, "rate_b  = PicDecimal(rec.rate_str,  int_digits=4, frac_digits=2)", "rate_b  = PicDecimal(rec.rate_str,  int_digits=4, frac_digits=3)", R),
    ("probe: hours keep their second decimal", P, "hours_b = PicDecimal(rec.hours_str, int_digits=3, frac_digits=1)", "hours_b = PicDecimal(rec.hours_str, int_digits=3, frac_digits=2)", R),
    ("cli: a rejected record count exits 0", P, "sys.exit(1)\n    print_report(results)", "sys.exit(0)\n    print_report(results)", R),
    ("attribute: the loss split drops the hours step", P, "s_hours += a * b - a * b1", "s_hours += 0", H),
    ("attribute: the worst record is never tracked", P, "if a * b - g > worst_e:", "if False:", H),
]


def pytest_rc(tree, test):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", test],
                           cwd=tree, capture_output=True, timeout=TIMEOUT,
                           env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    except subprocess.TimeoutExpired:
        return 124                                      # a mutant that hangs the tests is caught
    return r.returncode


def fresh(tmp, name):
    dst = pathlib.Path(tmp) / name
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    return dst


def main():
    killed = 0
    tests = sorted({m[4] for m in MUTANTS})
    with tempfile.TemporaryDirectory() as tmp:
        for t in tests:
            if pytest_rc(fresh(tmp, "control-" + pathlib.Path(t).stem), t) != 0:
                print(f"control FAIL {t}"); return 1
        print(f"control {len(tests)}/{len(tests)} test files pass unmodified")
        for i, (name, f, old, new, test) in enumerate(MUTANTS):
            tree = fresh(tmp, f"m{i}")
            src = (tree / f).read_text()
            if src.count(old) != 1:
                print(f"mutant {name}: pattern matched {src.count(old)} times, want 1"); return 1
            (tree / f).write_text(src.replace(old, new))
            red = pytest_rc(tree, test) != 0
            killed += red
            print(f"{'RED ' if red else 'LIVE'} {name}")
    print(f"mutants killed {killed}/{len(MUTANTS)}")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
