# 🧾 COBOL Payroll System for Small Businesses

This project implements a payroll system in COBOL designed for small enterprises. It calculates net salaries based on base salary, overtime hours, taxes, and deductions. The application reads employee data from flat files and generates detailed payment reports.

## 🎯 Objective

To automate the payroll calculation process using COBOL, demonstrating file handling, arithmetic operations, and structured programming logic applied to real business rules.

## 🧠 Techniques Used

- File I/O with fixed-width `.txt` files
- Structured PERFORM loops for modular design
- Arithmetic operations and conditional evaluation
- Tabular employee data management
- Report generation with salary breakdown

## 🛠️ Technologies

- COBOL (compatible with OpenCOBOL/GnuCOBOL)
- Text editor or IDE (Visual Studio Code + COBOL extension)
- Flat file format (.txt)

## 📁 Project Structure

payroll-cobol-system/  
├── employees.txt               # Master table with employee data  
├── payroll_report.txt          # Generated payroll report  
├── payroll.cob                # Main COBOL program  
├── README.md                   # Project documentation

## 📊 Inputs

**employees.txt**

1001|Ana López|7500|10
1002|Luis Pérez|9500|5
1003|Sofía Ruiz|12000|0

markdown
Copiar
Editar

- Format: `ID|Name|Base Salary|Overtime Hours`

## 🚀 Execution Pipeline

1. Read employee records from `employees.txt`  
2. Calculate:
   - Overtime pay (at 2x hourly rate)
   - IMSS (6.5%)
   - ISR (15%)
   - Other fixed deductions (500 MXN)
3. Compute net salary and generate per-employee breakdown
4. Write results to `payroll_report.txt`

## 📄 Output Example (payroll_report.txt)

Employee ID: 1001
Name: Ana López
Base Salary: 7500.00
Overtime Pay: 3750.00
IMSS: -731.25
ISR: -1687.50
Deductions: -500.00
Net Salary: 8331.25
markdown
Copiar
Editar

## 📌 Future Enhancements

- Add UI or terminal menu to manage employee entries  
- Export reports in CSV format  
- Support progressive tax brackets and bonuses  

## 📄 License

MIT License
