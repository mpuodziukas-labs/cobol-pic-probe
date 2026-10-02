# COBOL PIC V9(7)V99 Truncation Probe

![CI](https://github.com/mpuodziukas-labs/cobol-pic-probe/actions/workflows/ci.yml/badge.svg)

**Synthetic demonstration of a COBOL fixed-point truncation failure class.
No real or client data is used anywhere in this repository.**

## Business problem

A payroll batch can reconcile to the cent against its own ledger and still be
short, because every record silently drops sub-cent digits before it is summed.
This probe replays the same arithmetic at higher precision, field by field, and
shows the loss before employees are underpaid or a regulator asks.

## Run it in 60 seconds

```bash
pip install pytest
python3 -m pytest -q
python3 probe.py --records 47312
python3 probe.py --records 5 --verbose
```

Optional, if GnuCOBOL (`cobc`) is installed, run the COBOL source itself:

```bash
cobc -x payroll.cob -o payroll_run
echo 47312 | ./payroll_run
```

Both the probe and the COBOL program print the same totals for the same record
count.

## Expected output

`python3 probe.py --records 47312` prints (numbers are deterministic):

```
=================================================================
  COBOL PIC V9(7)V99 / COMP-3 Truncation Probe - SYNTHETIC
=================================================================
  Records processed       : 47,312
  Buggy   payroll total   : $45,294,763.33
  Correct payroll total   : $45,335,576.137
  Compounding error (loss): $40,812.807
  Error as % of total     : 0.0900%
```

Rounded to cents, the compounding loss is **$40,812.81**, the figure the
probe reproduces on every run at `--records 47312`. The report continues with the
first truncated record and the ten worst single-record errors.

---

## What the bug is

### The COBOL arithmetic failure class

In COBOL, a numeric field declared `PIC 9(4)V99 COMP-3` stores **exactly 2
decimal digits**. When two such fields are multiplied the intermediate
product may have 3 or more decimal places. Without a `ROUNDED` or `ON SIZE
ERROR` clause COBOL **silently truncates** the excess digits. It does not
round.

```cobol
01 WS-RATE   PIC 9(4)V99  COMP-3.   *> stores 2 decimal places
01 WS-HOURS  PIC 9(3)V9   COMP-3.   *> stores 1 decimal place
01 WS-GROSS  PIC 9(7)V99  COMP-3.   *> result field: 2 decimal places

MULTIPLY WS-RATE BY WS-HOURS GIVING WS-GROSS
*> intermediate has 3 decimal digits; the 3rd is silently dropped
```

The probe's synthetic record 1 has rate `23.573` and hours `40.30`. The narrow
fields drop the third decimal of the rate, and that record comes out
$0.121 short (see the `--verbose` command above). Over 47,312 records the
shortfall compounds to the **$40,812.81** shown above.

### Why a total-only reconciliation misses it

A check such as:

```
sum(gross_pay) == sum(payroll_debits)
```

passes when both sides use the same truncated values. The discrepancy exists
only at the sub-cent boundary inside the multiplication, so a check that
compares truncated totals cannot see it.

Replaying the computation with wider fields (`PIC 9(4)V999`) and comparing
field by field at each record boundary exposes the difference. That is what
`probe.py` does.

---

## Repository layout

```
.
  payroll.cob           Annotated COBOL source (compiles with GnuCOBOL)
  cobol_semantics.py    Python model of truncating COBOL PIC arithmetic
  probe.py              Runs N records, reports error + first truncation
  tests/
    test_pic_truncation.py   pytest tests (bug exists, probe detects it)
  .github/workflows/ci.yml   GitHub Actions: probe + pytest on push
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
| Does CI run the COBOL source? | **No.** CI runs the Python probe and pytest. The COBOL-versus-Python comparison test runs only where `cobc` is installed and is skipped elsewhere. |

The purpose is to demonstrate a *methodology* (instrumenting arithmetic
boundaries deterministically), not to make claims about any production system.

---

## Limitations

- Inputs are synthetic formulas, not real or client data. The dollar amounts
  describe this synthetic batch only.
- The Python model reproduces one COBOL PIC/COMP-3 truncation failure class,
  not the full COBOL arithmetic specification.
- Behavior of other compilers, `ROUNDED`, `ON SIZE ERROR` and binary (`COMP`)
  fields is not modeled or tested here.
- The COBOL file was checked against the Python probe with GnuCOBOL only.
- This is a methodology demonstration, not a turnkey audit tool for arbitrary
  codebases.

---

## License

MIT, see [LICENSE](LICENSE).
