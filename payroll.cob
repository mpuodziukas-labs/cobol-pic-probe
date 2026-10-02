      *> ============================================================
      *> payroll.cob — SYNTHETIC DEMONSTRATION ONLY
      *>
      *> Demonstrates the PIC V9(7)V99 / COMP-3 truncation failure
      *> class that silent-accumulates rounding errors over large
      *> payroll batches.  NO real or client data used.
      *>
      *> The deliberate bug:
      *>   WS-RATE is declared PIC 9(4)V99 COMP-3  (2 decimal places)
      *>   WS-HOURS is declared PIC 9(3)V9 COMP-3  (1 decimal place)
      *>   WS-GROSS is declared PIC 9(7)V99 COMP-3 (2 decimal places)
      *>
      *>   MULTIPLY WS-RATE BY WS-HOURS GIVING WS-GROSS
      *>   produces a 3-decimal intermediate; COBOL silently truncates
      *>   the third decimal digit (no ON SIZE ERROR clause present).
      *>   Over 47 000 records the cumulative loss is non-trivial.
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
       01 WS-EMPLOYEE-COUNT     PIC 9(6) VALUE ZERO.
       01 WS-RECORD-INDEX       PIC 9(6) VALUE ZERO.

      *> --- Buggy arithmetic fields (COMP-3, limited precision) ---
       01 WS-RATE-BUGGY         PIC 9(4)V99  COMP-3.
       01 WS-HOURS-BUGGY        PIC 9(3)V9   COMP-3.
       01 WS-GROSS-BUGGY        PIC 9(7)V99  COMP-3.
       01 WS-ACCUM-BUGGY        PIC 9(11)V99 COMP-3 VALUE ZERO.

      *> --- Correct arithmetic fields (higher-precision) ---
       01 WS-RATE-CORRECT       PIC 9(4)V999 COMP-3.
       01 WS-HOURS-CORRECT      PIC 9(3)V99  COMP-3.
       01 WS-GROSS-CORRECT      PIC 9(7)V999 COMP-3.
       01 WS-ACCUM-CORRECT      PIC 9(11)V999 COMP-3 VALUE ZERO.

      *> --- Comparison ---
       01 WS-RECORD-DELTA       PIC S9(7)V999 COMP-3.
       01 WS-CUMULATIVE-DELTA   PIC S9(11)V999 COMP-3 VALUE ZERO.

      *> --- Display work ---
       01 WS-DISPLAY-BUGGY      PIC ZZZ,ZZZ,ZZ9.99.
       01 WS-DISPLAY-CORRECT    PIC ZZZ,ZZZ,ZZ9.999.
       01 WS-DISPLAY-DELTA      PIC -ZZZ,ZZZ,ZZ9.999.

       PROCEDURE DIVISION.
       MAIN-LOGIC.
           DISPLAY "Enter record count: " WITH NO ADVANCING
           ACCEPT WS-EMPLOYEE-COUNT

           PERFORM VARYING WS-RECORD-INDEX FROM 1 BY 1
               UNTIL WS-RECORD-INDEX > WS-EMPLOYEE-COUNT

      *>         Synthetic deterministic inputs:
      *>         rate   = 23.57 + (index mod 100) * 0.003   -> 3 decimals
      *>         hours  = 40.25 + (index mod 7) * 0.05     -> 2 sig decimals
      *>         The 3rd decimal in the intermediate product gets truncated
      *>         by the buggy PIC definition.

               COMPUTE WS-RATE-BUGGY =
                   23.57 + FUNCTION MOD(WS-RECORD-INDEX, 100) * 0.003
               COMPUTE WS-HOURS-BUGGY =
                   40.25 + FUNCTION MOD(WS-RECORD-INDEX, 7) * 0.05

      *>         BUG: MULTIPLY truncates the third decimal digit silently
               MULTIPLY WS-RATE-BUGGY BY WS-HOURS-BUGGY
                   GIVING WS-GROSS-BUGGY

               ADD WS-GROSS-BUGGY TO WS-ACCUM-BUGGY

      *>         CORRECT: higher-precision fields retain third decimal
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
           DISPLAY "Correct total ($)  : " WS-DISPLAY-CORRECT
           DISPLAY "Cumulative loss($) : " WS-DISPLAY-DELTA

           STOP RUN.
