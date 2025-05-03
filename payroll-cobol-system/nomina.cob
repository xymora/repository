       IDENTIFICATION DIVISION.
       PROGRAM-ID. NOMINA.
       AUTHOR. GPT.
       DATA DIVISION.
       FILE SECTION.
       FD EMPLEADOS.
       01 EMP-REG.
           05 EMP-ID         PIC 9(5).
           05 EMP-NAME       PIC A(20).
           05 SALARIO        PIC 9(6).
           05 HORAS          PIC 9(3).
           05 DEDUCCION      PIC 9(5).
       WORKING-STORAGE SECTION.
       01 NETO               PIC 9(6).
       PROCEDURE DIVISION.
           DISPLAY "Procesando empleados..."
           STOP RUN.
