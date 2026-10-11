# Verifying this repository

Purpose: demonstrates a replay that exposes silent numeric truncation in legacy COBOL-style payroll arithmetic by comparing against exact arithmetic for teams subject to model-risk, audit or change-control review.

Verify: `python3 probe.py --records 47312`

Pass condition: exit code 0 and this exact output line (leading spaces ignored): `Compounding error (loss): $40,832.40790`

Scope: synthetic data, fixed seed, offline, under 60 seconds.

Limitations: Inputs are synthetic and the dollar amounts describe this batch only. Models one PIC and COMP-3 truncation failure class, not the full COBOL arithmetic specification. Overflow behavior follows GnuCOBOL and other compilers may differ. ROUNDED, ON SIZE ERROR, binary fields and storage representation are not modeled.

Anything else = not verified.
