       IDENTIFICATION DIVISION.
       PROGRAM-ID. GESTION-INVENTARIO.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INVENTARIO ASSIGN TO 'inventario.txt'
               ORGANIZATION IS LINE SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD INVENTARIO.
       01 REGISTRO-INVENTARIO.
           05 CODIGO          PIC X(6).
           05 NOMBRE          PIC X(20).
           05 CANTIDAD        PIC 9(4).
           05 STOCK-MIN       PIC 9(2).

       WORKING-STORAGE SECTION.
       01 OPCION              PIC 9 VALUE 0.
       01 FIN                 PIC X VALUE 'N'.

       PROCEDURE DIVISION.
       INICIO.
           DISPLAY "MENU INVENTARIO"
           DISPLAY "1. CONSULTAR STOCK"
           DISPLAY "2. BUSCAR PRODUCTO"
           DISPLAY "3. SALIR"
           ACCEPT OPCION
           EVALUATE OPCION
              WHEN 1
                 PERFORM CONSULTAR-STOCK
              WHEN 2
                 PERFORM BUSCAR-PRODUCTO
              WHEN 3
                 MOVE 'S' TO FIN
              WHEN OTHER
                 DISPLAY "OPCION INVALIDA"
           END-EVALUATE
           IF FIN = 'N'
              GO TO INICIO
           END-IF
           STOP RUN.

       CONSULTAR-STOCK.
           OPEN INPUT INVENTARIO
           PERFORM UNTIL EOF
              READ INVENTARIO INTO REGISTRO-INVENTARIO
                 AT END MOVE 'Y' TO EOF
              NOT AT END
                 IF CANTIDAD < STOCK-MIN
                    DISPLAY "STOCK BAJO: " CODIGO SPACE NOMBRE
                 END-IF
           END-PERFORM
           CLOSE INVENTARIO.

       BUSCAR-PRODUCTO.
           DISPLAY "Ingrese código:"
           ACCEPT CODIGO
           OPEN INPUT INVENTARIO
           PERFORM UNTIL EOF
              READ INVENTARIO INTO REGISTRO-INVENTARIO
                 AT END MOVE 'Y' TO EOF
              NOT AT END
                 IF CODIGO = REGISTRO-INVENTARIO(1:6)
                    DISPLAY "Producto: " NOMBRE " Stock: " CANTIDAD
                 END-IF
           END-PERFORM
           CLOSE INVENTARIO.
