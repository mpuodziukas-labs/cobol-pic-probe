# COBOL PIC 9(7)V99 Truncation Probe

Proves: legacy COBOL numeric correctness testing and modernization evals. Verify in 60s: `python3 probe.py --records 47312`.

![CI](https://github.com/mpuodziukas-labs/cobol-pic-probe/actions/workflows/ci.yml/badge.svg)

**Synthetic demonstration of a COBOL fixed-point truncation failure class.
No real or client data is used anywhere in this repository.**

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

## License

MIT, see [LICENSE](LICENSE).
