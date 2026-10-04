      *> ============================================================
      *> payroll.cob - SYNTHETIC DEMONSTRATION ONLY
      *>
      *> Demonstrates the PIC 9(7)V99 fixed-point truncation failure
      *> class that silently accumulates errors over large payroll
      *> batches.  NO real or client data used.
      *>
      *> The deliberate bug:
      *>   WS-RATE-BUGGY  is declared PIC 9(4)V99 (2 decimal places)
      *>   WS-HOURS-BUGGY is declared PIC 9(3)V9  (1 decimal place)
      *>   WS-GROSS-BUGGY is declared PIC 9(7)V99 (2 decimal places)
      *>
      *>   Each COMPUTE into a narrow field truncates the extra digits,
      *>   and MULTIPLY ... GIVING truncates the product.  No ROUNDED
      *>   and no ON SIZE ERROR clause is present.  The loss by source
      *>   field is printed by: python3 probe.py --attribute
      *>   USAGE COMP-3 does not change the truncation; a test shows
      *>   identical totals with and without it.
      *>
      *> The reference total is exact: the rate has 3 decimals, the
      *> hours 2, so the product has 5 and PIC 9(7)V99999 keeps it all.
      *>
      *> Input: a record count, digits only, 1 to 999998.  Anything
      *> else is refused with a message on stderr and return code 1.
      *>
      *> Compile (GnuCOBOL):
      *>   cobc -x payroll.cob -o payroll_run
      *> Run:
      *>   echo "47312" | ./payroll_run
      *> ============================================================
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL-PROBE.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *> --- Employee record fields ---
       01 WS-INPUT              PIC X(20) VALUE SPACES.
       01 WS-TEXT-LEN           PIC 9(4) VALUE ZERO.
       01 WS-COUNT-WIDE         PIC 9(7) VALUE ZERO.
       01 WS-EMPLOYEE-COUNT     PIC 9(6) VALUE ZERO.
       01 WS-RECORD-INDEX       PIC 9(6) VALUE ZERO.

      *> --- Buggy arithmetic fields (COMP-3, limited precision) ---
       01 WS-RATE-BUGGY         PIC 9(4)V99  COMP-3.
       01 WS-HOURS-BUGGY        PIC 9(3)V9   COMP-3.
       01 WS-GROSS-BUGGY        PIC 9(7)V99  COMP-3.
       01 WS-ACCUM-BUGGY        PIC 9(11)V99 COMP-3 VALUE ZERO.

      *> --- Correct arithmetic fields (wide enough to be exact) ---
       01 WS-RATE-CORRECT       PIC 9(4)V999 COMP-3.
       01 WS-HOURS-CORRECT      PIC 9(3)V99  COMP-3.
       01 WS-GROSS-CORRECT      PIC 9(7)V99999 COMP-3.
       01 WS-ACCUM-CORRECT      PIC 9(11)V99999 COMP-3 VALUE ZERO.

      *> --- Comparison ---
       01 WS-RECORD-DELTA       PIC S9(7)V99999 COMP-3.
       01 WS-CUMULATIVE-DELTA   PIC S9(11)V99999 COMP-3 VALUE ZERO.

      *> --- Display work ---
       01 WS-DISPLAY-BUGGY      PIC ZZ,ZZZ,ZZZ,ZZ9.99.
       01 WS-DISPLAY-CORRECT    PIC ZZ,ZZZ,ZZZ,ZZ9.99999.
       01 WS-DISPLAY-DELTA      PIC -ZZ,ZZZ,ZZZ,ZZ9.99999.

       PROCEDURE DIVISION.
       MAIN-LOGIC.
           DISPLAY "Enter record count: " WITH NO ADVANCING
           ACCEPT WS-INPUT
           MOVE FUNCTION LENGTH(FUNCTION TRIM(WS-INPUT))
               TO WS-TEXT-LEN
           IF WS-TEXT-LEN > 7
              OR FUNCTION TRIM(WS-INPUT) IS NOT NUMERIC
               PERFORM REFUSE-INPUT
           END-IF
           COMPUTE WS-COUNT-WIDE =
               FUNCTION NUMVAL(FUNCTION TRIM(WS-INPUT))
           IF WS-COUNT-WIDE < 1 OR WS-COUNT-WIDE > 999998
               PERFORM REFUSE-INPUT
           END-IF
           MOVE WS-COUNT-WIDE TO WS-EMPLOYEE-COUNT

           PERFORM VARYING WS-RECORD-INDEX FROM 1 BY 1
               UNTIL WS-RECORD-INDEX > WS-EMPLOYEE-COUNT

      *>         Synthetic deterministic inputs:
      *>         rate   = 23.57 + (index mod 100) * 0.003   -> 3 decimals
      *>         hours  = 40.25 + (index mod 7) * 0.05     -> 2 sig decimals
      *>         The narrow PIC definitions truncate the inputs and the
      *>         product (see: python3 probe.py --attribute).

               COMPUTE WS-RATE-BUGGY =
                   23.57 + FUNCTION MOD(WS-RECORD-INDEX, 100) * 0.003
               COMPUTE WS-HOURS-BUGGY =
                   40.25 + FUNCTION MOD(WS-RECORD-INDEX, 7) * 0.05

      *>         BUG: narrow fields and GIVING truncate silently
               MULTIPLY WS-RATE-BUGGY BY WS-HOURS-BUGGY
                   GIVING WS-GROSS-BUGGY

               ADD WS-GROSS-BUGGY TO WS-ACCUM-BUGGY

      *>         EXACT: wide fields keep every digit
               COMPUTE WS-RATE-CORRECT =
                   23.57 + FUNCTION MOD(WS-RECORD-INDEX, 100) * 0.003
               COMPUTE WS-HOURS-CORRECT =
                   40.25 + FUNCTION MOD(WS-RECORD-INDEX, 7) * 0.05

               MULTIPLY WS-RATE-CORRECT BY WS-HOURS-CORRECT
                   GIVING WS-GROSS-CORRECT

               ADD WS-GROSS-CORRECT TO WS-ACCUM-CORRECT

           END-PERFORM

           COMPUTE WS-CUMULATIVE-DELTA =
               WS-ACCUM-CORRECT - WS-ACCUM-BUGGY

           MOVE WS-ACCUM-BUGGY    TO WS-DISPLAY-BUGGY
           MOVE WS-ACCUM-CORRECT  TO WS-DISPLAY-CORRECT
           MOVE WS-CUMULATIVE-DELTA TO WS-DISPLAY-DELTA

           DISPLAY "Records processed : " WS-EMPLOYEE-COUNT
           DISPLAY "Buggy   total ($)  : " WS-DISPLAY-BUGGY
           DISPLAY "Exact   total ($)  : " WS-DISPLAY-CORRECT
           DISPLAY "Cumulative loss($) : " WS-DISPLAY-DELTA

           STOP RUN.

       REFUSE-INPUT.
           DISPLAY "ERROR: record count must be digits, 1 to 999998"
               UPON SYSERR
           MOVE 1 TO RETURN-CODE
           STOP RUN.
