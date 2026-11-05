# cobol-pic-probe

Proves: legacy COBOL numeric correctness testing and modernization evals. Verify in 60s: `python3 probe.py --records 47312`.

Where this fits: NIST SP 800-53 Rev. 5 family System and Information Integrity (family name only, no control text claimed). Sources in SOURCES.md.

Title of this README before it followed the repo README standard, kept as written:

```text
# COBOL PIC 9(7)V99 Truncation Probe
```

![CI](https://github.com/mpuodziukas-labs/cobol-pic-probe/actions/workflows/ci.yml/badge.svg)

**Synthetic demonstration of a COBOL fixed-point truncation failure class.
No real or client data is used anywhere in this repository.**

## Ticket

| Field | Value |
|---|---|
| Ticket | cobol-pic-probe 2026-10-25 |
| Status | LIVE |
| Severity of a false pass | A fixed-point truncation loss in a legacy COBOL-style calculation is reported as absent or as the wrong amount because the probe printed its expected line, and a team relies on that result when it signs off a batch. |
| Scope (in) | A replay of rate times hours over N synthetic records, once with COBOL PIC truncation and once with exact decimal arithmetic, with the loss split by field; the checks are exercised by the planted edits in mutants.py. |
| Out of scope | Real or client data, other compilers, ROUNDED, ON SIZE ERROR, binary fields, storage representation (see Limitations). |
| Owner | Michael Puodziukas, michael@puodziukas.dev |
| Opened | 2026-06-12 |
| Last verified | 2026-10-25, `mutants killed 17/17` |
| Oracle | `python3 mutants.py`, last line `mutants killed 17/17`; no evaluate.py exists in this repo |
| Dependencies | Runtime: Python 3 (probe.py and cobol_semantics.py). Test: pytest. Optional: GnuCOBOL (cobc) for the COBOL source. |
| Supported platforms | macOS (mutants.py measured here, rc=0); Linux through the CI workflow in .github/workflows/ci.yml (not measured here). |

## Quick start

```bash
python3 mutants.py
python3 probe.py --records 47312
```

## Normal procedure

1. From the repo root run `python3 mutants.py`. It copies the repo to a temporary directory, runs each named test file unmodified as a control, then applies each planted edit to `cobol_semantics.py` or `probe.py` and requires the matching test file to go red.
2. Read the output. The first line reports the control run. Each `RED` line is a planted edit that a test caught. A `LIVE` line is a planted edit no test caught. The last line counts the edits caught.
3. PASS means the control line reports every test file clean, no line starts with `LIVE`, and the last line shows the same number on both sides of the slash. The end of a passing run is quoted here:

```text
RED  attribute: the worst record is never tracked
mutants killed 17/17
```

4. Run `python3 probe.py --records 47312` to see the probe itself. Its pass line is recorded in PROOF.json and was not re-run in this pass.

## Abnormal procedure

| Symptom | Cause | Action | Oracle |
|---|---|---|---|
| `mutants.py` prints a `LIVE` line | A planted edit that its test file does not detect, which is a gap in that test file | Add or tighten a test until that line prints `RED` | `python3 mutants.py` |
| `mutants.py` prints `control FAIL` or `pattern matched` | The unmodified test file fails in the scratch copy (for example pytest is missing), or the source line a planted edit targets has moved | Install pytest, or update the pattern in `mutants.py` to the new source line | `python3 mutants.py` |
| `probe.py` exits with code one | The record count is not an integer from 1 up to 999,998 | Pass a count inside that range | `python3 probe.py --records 47312` |
| The COBOL comparison tests are reported as skipped | GnuCOBOL (cobc) is not installed on this machine; CI installs it and fails on a skip | Install GnuCOBOL, then compile the source | `cobc -x payroll.cob -o payroll_run` |

## Emergency procedure

The gate printed PASS but a truncation loss in a legacy COBOL-style calculation was missed or misreported.

1. Freeze: stop relying on the probe result for that calculation, and record the repo commit, the record count and the field widths involved.
2. Replay: run `python3 probe.py --records 5 --verbose` and `python3 probe.py --attribute` on the offending case. Reduce it to a failing test in `tests/test_hostile.py`, fix `cobol_semantics.py` or `probe.py`, and add a planted edit to `mutants.py`. Then run `python3 mutants.py` and expect the same number on both sides of the slash.
3. Tell: the owner (michael@puodziukas.dev) and every team that used the result. Name the missing check and the blind spot in the Limitations section.

## Business problem

A payroll batch can reconcile to the cent against its own ledger and still be
short, because every record silently drops digits (mostly from narrow input
fields) before it is summed.
This probe replays the same arithmetic at higher precision, field by field, and
shows the loss before employees are underpaid or a regulator asks.

## Run it in 60 seconds

```bash
pip install pytest
python3 -m pytest -q
python3 probe.py --records 47312
python3 probe.py --records 5 --verbose
python3 probe.py --attribute
```

Optional, if GnuCOBOL (`cobc`) is installed, run the COBOL source itself:

```bash
cobc -x payroll.cob -o payroll_run
echo 47312 | ./payroll_run
```

Without `cobc`, skip this step: the probe is pure Python and unaffected, and the
tests that compare it with the COBOL program are skipped, not failed. CI installs
GnuCOBOL and fails if any test is skipped.

Both the probe and the COBOL program print the same totals for the same record
count, from 1 up to 999,998. The COBOL record counter is `PIC 9(6)` and its loop
never ends at 999,999, so both refuse counts above 999,998 (exit code 1). The
COBOL program also refuses input that is not digits.

## Expected output

`python3 probe.py --records 47312` prints (numbers are deterministic):

```
=================================================================
  COBOL PIC 9(7)V99 Truncation Probe - SYNTHETIC
=================================================================
  Records processed       : 47,312
  Buggy   payroll total   : $45,294,763.33
  Exact   payroll total   : $45,335,595.73790
  Compounding error (loss): $40,832.40790
  Error as % of total     : 0.0901%
```

The "Exact" total is the plain sum of rate times hours, with no truncation
anywhere. Rounded to cents, the loss is **$40,832.41**, the figure the probe
reproduces on every run at `--records 47312`. The report continues with the
first truncated record and the ten worst single-record errors.

---

## What the bug is

### Where the loss comes from

The loss comes mostly from input fields that are too narrow, not from the
multiplication. `python3 probe.py --attribute` prints:

```
  Loss attribution over 47,312 records - SYNTHETIC
  Exact payroll total      : $45,335,595.73790
  Buggy payroll total      : $45,294,763.33
  Total loss               : $40,832.40790
  1. hours field PIC 9(3)V9 drops 2nd decimal : $32,061.43490 (78.52%)
  2. rate field PIC 9(4)V99 drops 3rd decimal : $8,595.23900 (21.05%)
  3. MULTIPLY GIVING PIC 9(7)V99 drops product decimals : $175.73400 (0.43%)
  Worst single-record loss : $1.56225 at record #693
```

The three steps are applied in order (hours, rate, product) and add up exactly
to the total loss. The hours field `PIC 9(3)V9` keeps one decimal, so an hours
value of 40.35 is stored as 40.3. That step alone is 78.52% of the loss. The
rate field `PIC 9(4)V99` is 21.05%. Truncating the product into
`PIC 9(7)V99` is 0.43%. The worst single record loses $1.56225.

```cobol
01 WS-RATE   PIC 9(4)V99.   *> stores 2 decimal places
01 WS-HOURS  PIC 9(3)V9.    *> stores 1 decimal place
01 WS-GROSS  PIC 9(7)V99.   *> result field: 2 decimal places

MULTIPLY WS-RATE BY WS-HOURS GIVING WS-GROSS
```

Without a `ROUNDED` or `ON SIZE ERROR` clause COBOL silently truncates every
store into a narrow field. It does not round. `COMP-3` (packed decimal) is a
USAGE, a storage format, and does not change this: `payroll.cob` uses it, and a test
shows the totals are identical with and without it.

The probe's synthetic record 1 has rate `23.573` and hours `40.30`. It comes
out $0.1219 short (see the `--verbose` command above). Over 47,312 records the
shortfall compounds to the **$40,832.41** shown above.

### Why a total-only reconciliation misses it

A check such as:

```
sum(gross_pay) == sum(payroll_debits)
```

passes when both sides use the same truncated values. The discrepancy exists
only in the digits dropped before the store, so a check that compares
truncated totals cannot see it.

Replaying the computation with exact arithmetic and comparing field by field
at each record boundary exposes the difference. That is what `probe.py` does.

---

## Repository layout

```
.
  payroll.cob           Annotated COBOL source (compiles with GnuCOBOL, validates input)
  cobol_semantics.py    Python model of truncating COBOL PIC arithmetic
  probe.py              Runs N records, reports error + first truncation
  tests/
    test_pic_truncation.py   pytest tests (bug exists, probe detects it)
    test_redteam.py          attack cases, README drift checks, COBOL agreement
    test_hostile.py          one test per finding of the 2026-10-04 review
    test_stranger.py         clean-clone checks
  .github/workflows/ci.yml   GitHub Actions: installs GnuCOBOL, probe smoke, pytest, no skips
  RED-RUN-REVIEW.txt      hostile review findings (input to test_hostile.py)
  README.md
  LICENSE               MIT
```

---

## Honesty Statement

| Question | Answer |
|----------|--------|
| Uses real payroll data? | **No.** Every input is a deterministic formula in `probe.py` (and the same formulas in `payroll.cob`). |
| References a specific employer or client? | **No.** |
| Results reproducible? | **Yes.** No randomness and no clock; the commands above print the same numbers every time. |
| Does CI run the COBOL source? | **Yes.** CI installs GnuCOBOL, compiles `payroll.cob`, and fails if any test is skipped. Locally, without `cobc`, the COBOL comparison tests are skipped. |

The purpose is to demonstrate a *methodology* (instrumenting arithmetic
boundaries deterministically), not to make claims about any production system.

---

## Limitations

- Inputs are synthetic formulas, not real or client data. The dollar amounts
  describe this synthetic batch only.
- The Python model reproduces one COBOL PIC/COMP-3 truncation failure class,
  not the full COBOL arithmetic specification.
- The model drops high-order digits on overflow and keeps the absolute value in
  an unsigned field, as GnuCOBOL does. The COBOL standard leaves overflow
  without `ON SIZE ERROR` undefined, so other compilers may differ.
- Behavior of other compilers, `ROUNDED`, `ON SIZE ERROR` and binary (`COMP`)
  fields is not modeled or tested here.
- Not modeled: storage representation. That covers the sign nibble of packed
  decimal (C, D, F), EBCDIC versus ASCII digits, zoned-decimal overpunch signs,
  and `SIGN LEADING` / `SIGN TRAILING` with `SEPARATE`. The model works on
  numeric values only.
- Numeric items are limited to 1 to 38 digits, the GnuCOBOL maximum.
- The COBOL file was checked against the Python probe with GnuCOBOL only.
- This is a methodology demonstration, not a turnkey audit tool for arbitrary
  codebases.
- No evaluate.py exists in this repo. The measured evidence below is the last line of `mutants.py` only.
- The pytest suite and the probe were not run directly in this pass. `mutants.py` ran the two named test files inside its own scratch copies, and GnuCOBOL was not used.

---

## Hostile review 2026-10-04

Found: 11 (kill 1, high 4, med 6). Fixed: 11. Pass: 3 (no change needed).
The raw findings are in `RED-RUN-REVIEW.txt`; each fix has a test in
`tests/test_hostile.py`. Expectations changed on purpose: the "Correct" total
is now the exact total, so the headline loss moved from $40,812.81 to
the exact-total figure above, and `PicDecimal` now caps a PIC at 38 digits.

- K1 README blamed MULTIPLY; fixed with `--attribute` and a README rewritten from its output.
- H1 "Correct" total was itself truncated; fixed, the reference is an exact Decimal sum.
- H2 the headline PIC had two V characters, which cobc rejects; fixed, now `PIC 9(7)V99`, every PIC string compiled by `cobc`.
- H3 COBOL tests used a substring match; fixed, they parse exact value and sign.
- H4 default record-count test built its own parser; fixed, it runs the real CLI.
- M1 COMP-3 in the title changed nothing; fixed, dropped from the headline and a test proves no effect.
- M2 storage representation was unlisted; fixed, listed under Limitations.
- M3 CI never ran COBOL; fixed, CI installs GnuCOBOL, forbids skips, checks smoke output.
- M4 COBOL accepted bad counts with rc 0; fixed, it validates and exits 1.
- M5 `PicDecimal` accepted zero, over 38 digits and non-bool `signed`; fixed, all raise ValueError.
- M6 demo said "hundreds of dollars"; fixed, the demo points to `--attribute`.

---

## Architecture

| Path | Role | Lines |
|---|---|---|
| `probe.py` | Runs N records through the truncating model and the exact model, reports the loss and its split | 301 |
| `cobol_semantics.py` | Python model of truncating COBOL numeric storage | 179 |
| `payroll.cob` | The COBOL source that the probe is compared with | 133 |
| `mutants.py` | Mutation check: edits copies of `probe.py` and `cobol_semantics.py` and requires the matching test file to go red | 71 |
| `tests/test_pic_truncation.py` | Tests that the bug exists and the probe detects it | 332 |
| `tests/test_redteam.py` | Attack cases, README drift checks, COBOL agreement | 173 |
| `tests/test_hostile.py` | One test per hostile-review finding | 372 |
| `tests/test_stranger.py` | Clean-clone checks | 38 |
| `RED-RUN-REVIEW.txt` | Raw hostile-review findings | 21 |
| `.github/workflows/ci.yml` | CI workflow | 48 |
| `PROOF.json` | Machine-readable verify command and expected line | 11 |
| `AGENTS.md` | Verification contract (path only) | 13 |

Data flow:

1. `probe.py` builds each synthetic record from a fixed formula.
2. It stores each field through `cobol_semantics.py` (truncating) and also computes the exact product.
3. It reports the compounded difference, the first truncated record and the loss split by field.
4. `mutants.py` edits copies of the two Python files and requires the named test file to go red.

## Test and mutation evidence

Measured on 2026-10-25 on macOS by running `python3 mutants.py` from the repo root. It exited with code zero (rc=0). There is no evaluate.py in this repo, so there is no evaluate.py line to quote. Last line of `python3 mutants.py`:

```text
mutants killed 17/17
```

The same measured line, restated as a summary table:

```text
| oracle | last line measured |
|---|---|
| python3 mutants.py | mutants killed 17/17 |
```

## Change log

| Date | Change | Oracle after |
|---|---|---|
| 2026-10-25 | Additive restructuring to the README standard: sections added, no old line dropped or reworded, the former title line kept verbatim inside a fenced block | `python3 mutants.py` last line `mutants killed 17/17` |
| 2026-06-12 | First commit (date from the repo git log) | none: no oracle output was recorded for that commit |

---

## License

MIT, see [LICENSE](LICENSE).

Agent verification contract: [AGENTS.md](AGENTS.md)
