# 🟠 COBOL Inventory Management System

Este proyecto implementa un sistema completo de gestión de inventario para una tienda minorista, desarrollado en COBOL. Simula operaciones reales de almacén como entradas, salidas y consultas de stock utilizando archivos planos (.txt) como base de datos. Está orientado a sistemas legacy y demuestra cómo COBOL puede seguir siendo relevante en entornos donde se prioriza la estabilidad y el procesamiento batch.

## 🎯 Objetivo

Desarrollar un sistema funcional y eficiente que permita:

- Registrar productos nuevos en inventario.
- Gestionar entradas y salidas de mercancía.
- Consultar niveles actuales de stock.
- Emitir alertas automáticas para productos con bajo inventario.
- Realizar búsquedas por código de producto.

## 🛠️ Tecnologías utilizadas

- COBOL (OpenCOBOL / GnuCOBOL compatible)
- Archivos `.txt` como almacenamiento estructurado
- Editor recomendado: VSCode con extensión COBOL o cualquier IDE de mainframe

## 📁 Estructura del Proyecto

proyecto_inventario_cobol/
├── gestion_inventario.cbl # Código fuente principal del sistema
├── inventario.txt # Archivo plano con el inventario simulado (500 productos)
└── README.md # Documentación completa del sistema

markdown
Copiar
Editar

## ⚙️ Módulos del sistema

- **Inicialización y lectura**: Carga los registros del inventario desde `inventario.txt`.
- **Entrada de productos**: Permite registrar nuevas unidades de productos existentes o nuevos códigos.
- **Salida de productos**: Actualiza el inventario al registrar ventas o transferencias.
- **Consulta de stock**: Muestra la existencia actual de un producto por su código.
- **Alerta de stock bajo**: Emite un mensaje si el inventario cae por debajo del mínimo definido.

## 📝 Ejemplo de archivo `inventario.txt`

Cada línea contiene:

<codigo_producto> <descripcion_producto> <existencia> <stock_minimo>

makefile
Copiar
Editar

Ejemplo:

0001 TECLADO_USB 15 5
0002 MOUSE_OPTICO 8 3
...

markdown
Copiar
Editar

## 🚀 Cómo compilar y ejecutar

1. Asegúrate de tener instalado **GnuCOBOL**:
sudo apt install open-cobol

markdown
Copiar
Editar

2. Compila el archivo COBOL:
cobc -x gestion_inventario.cbl -o inventario

markdown
Copiar
Editar

3. Ejecuta el sistema:
./inventario

markdown
Copiar
Editar

## 📊 Resultados

- El sistema puede manejar cientos de registros en tiempo de ejecución.
- Simula actualizaciones y operaciones de consulta como si se tratara de una base de datos transaccional.

## 📌 Mejoras futuras

- Integración con base de datos relacional (DB2, Oracle).
- Interfaz basada en menús o web usando microservicios intermedios.
- Reportes en formato CSV o PDF.
- Sistema de autenticación básico.

## 📄 Licencia

Este proyecto es de uso libre con fines educativos y profesionales. Puedes adaptarlo, redistribuirlo o integrarlo a soluciones más grandes bajo licencia MIT.
¿Deseas que este archivo README.md también se incluya nuevamente dentro de un archivo .zip con el código fuente y los datos actualizados?






Dijiste:
pero el readme tiene que ser en ingles
ChatGPT dijo:
Perfect. Here's the full README.md rewritten in professional English, formatted cleanly for your GitHub project:

markdown
Copiar
Editar
# 🟠 COBOL Inventory Management System

This project implements a complete inventory management system for a retail store using COBOL. It simulates real-world warehouse operations such as product registration, stock updates, and inventory queries. Data is managed through plain text files (`.txt`), representing a simple yet effective legacy-style database.

## 🎯 Objective

To develop a functional inventory system capable of:

- Registering new products
- Managing product entries and withdrawals
- Querying current stock levels
- Triggering low stock alerts
- Searching by product code

## 🛠️ Technologies Used

- COBOL (OpenCOBOL / GnuCOBOL compatible)
- Text files as a flat-file database
- Recommended editor: VSCode with COBOL extension, or traditional mainframe IDEs

## 📁 Project Structure

inventory-management-cobol/
├── inventory_manager.cbl # Main COBOL program source
├── inventory.txt # Simulated inventory database (500+ products)
└── README.md # Full project documentation

markdown
Copiar
Editar

## ⚙️ System Modules

- **Initialization & File Read**: Loads inventory records from `inventory.txt`
- **Product Entry**: Adds stock for existing or new product codes
- **Product Withdrawal**: Updates inventory after sales or movements
- **Stock Query**: Displays the current stock level of any product
- **Low Stock Alerts**: Warns when stock is below the defined threshold

## 📝 Sample `inventory.txt` Format

Each line follows the format:

<product_code> <product_description> <stock_quantity> <minimum_stock>

makefile
Copiar
Editar

Example:

0001 USB_KEYBOARD 15 5
0002 OPTICAL_MOUSE 8 3
...

markdown
Copiar
Editar

## 🚀 How to Compile and Run

1. Install **GnuCOBOL**:
sudo apt install open-cobol

bash
Copiar
Editar

2. Compile the source code:
cobc -x inventory_manager.cbl -o inventory

markdown
Copiar
Editar

3. Run the program:
./inventory

pgsql
Copiar
Editar

## 📊 Output Summary

- Supports large-scale inventory operations (500+ records)
- Mimics real-time database behavior using file operations
- Console output displays updates and alerts for each operation

## 📌 Future Improvements

- Integration with relational databases (e.g., DB2, Oracle)
- Menu-based interface or web-based microservice integration
- Export reports to CSV or PDF
- Basic login or user roles support

## 📄 License

This project is open-source for educational and professional use. You may adapt, redistribute, or integrate it under the MIT License.
