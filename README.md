# COBOL PIC V9(7)V99 Truncation Probe

![CI](https://github.com/mpuodziukas-labs/cobol-pic-probe/actions/workflows/ci.yml/badge.svg)

**Synthetic demonstration of a COBOL fixed-point truncation failure class.
No real or client data is used anywhere in this repository.**

This repo backs the candidate's *deterministic-replay forensics* methodology
with a verifiable, runnable artifact.  It demonstrates the failure class —
not any specific engagement.

---

## One-line replay

```bash
python probe.py --records 47312
```

Expected output (exact numbers are deterministic):

```
=================================================================
  COBOL PIC V9(7)V99 / COMP-3 Truncation Probe — SYNTHETIC
=================================================================
  Records processed       : 47,312
  Buggy   payroll total   : $45,294,763.33
  Correct payroll total   : $45,335,576.137
  Compounding error (loss): $40,812.807
  Error as % of total     : 0.0900%
  ...
```

Rounded to cents, the compounding loss is **$40,812.81** — the figure the
probe reproduces on every run at `--records 47312`.

Run the test suite:

```bash
python -m pytest tests/ -v
```

---

## What the bug is

### The COBOL arithmetic failure class

In COBOL, a numeric field declared `PIC 9(4)V99 COMP-3` stores **exactly 2
decimal digits**.  When two such fields are multiplied the intermediate
product may have 3 or more decimal places.  Without a `ROUNDED` or `ON SIZE
ERROR` clause COBOL **silently truncates** the excess digits — it does not
round.

```cobol
01 WS-RATE   PIC 9(4)V99  COMP-3.   *> stores 2 decimal places
01 WS-HOURS  PIC 9(3)V9   COMP-3.   *> stores 1 decimal place
01 WS-GROSS  PIC 9(7)V99  COMP-3.   *> result field: 2 decimal places

MULTIPLY WS-RATE BY WS-HOURS GIVING WS-GROSS
*> intermediate has 3 decimal digits; the 3rd is silently dropped
```

If `WS-RATE = 23.573` then the field stores `23.57` (third decimal lost).
One record: ~$0.12 under-paid.  47,312 records: **$40,812.81
compounding loss**.

### Why standard audits miss it

Standard reconciliation checks:

```
sum(gross_pay) == sum(payroll_debits)
```

Both sides of this equation use the *same* 2-decimal truncated values.
The discrepancy exists only at the sub-cent boundary inside the
multiplication — invisible to any check that rounds before summing.

Deterministic-replay forensics re-runs the computation with instrumented
higher-precision fields (`PIC 9(4)V999`) and compares field-by-field at
each record boundary.  The failure surfaces immediately.

---

## Repository layout

```
.
├── payroll.cob           # Annotated COBOL source (compilable with GnuCOBOL)
├── cobol_semantics.py    # Faithful Python model of COBOL PIC arithmetic
├── probe.py              # Detector: runs N records, reports error + boundary
├── tests/
│   └── test_pic_truncation.py  # 31 pytest assertions (bug exists, probe detects it)
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions: pytest on push
├── README.md
└── LICENSE               # MIT
```

---

## Running with GnuCOBOL (optional)

If `cobc` is installed:

```bash
cobc -x payroll.cob -o payroll_run
echo "47312" | ./payroll_run
```

The Python probe is the primary artifact; the `.cob` file documents the
exact PIC declarations that produce the failure class.

---

## Honest framing

| Claim | Status |
|-------|--------|
| Uses real payroll data | **No** — all inputs are synthetic deterministic formulas |
| References any specific employer or client | **No** |
| Demonstrates a real COBOL failure class | **Yes** — documented in COBOL standards |
| Results are reproducible | **Yes** — fixed seed, no randomness |
| Tests pass in CI | **Yes** — green badge above |

The purpose of this artifact is to demonstrate *methodology* — the ability
to instrument arithmetic boundaries deterministically — not to make claims
about any production system.

---

## Limitations

- Inputs are synthetic, deterministic formulas — not real or client data.
- The Python model reproduces one COBOL PIC/COMP-3 truncation failure class, not the full COBOL arithmetic spec.
- This is a methodology demonstration, not a turnkey audit tool for arbitrary codebases.

---

## License

MIT — see [LICENSE](LICENSE).
