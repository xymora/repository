# 🏧 ATM Simulator in C

This project simulates a basic ATM (Automated Teller Machine) system written in C. It includes core banking functionalities like account authentication, balance inquiry, deposits, withdrawals, and transaction history, all managed through modular C files and persistent file storage.

## 🎯 Objective

To create a realistic ATM simulator that mimics basic banking operations with multiple user accounts, secure PIN access, and persistent transaction data, suitable for academic or learning purposes in systems programming.

## 🧠 Features

- PIN-based user authentication
- Multiple user accounts stored in binary file
- Balance inquiry, deposit, withdrawal operations
- Transaction history logging
- Input validation and error handling
- Modular structure with reusable components

## 🛠️ Technologies Used

- C (GCC-compatible)
- Binary file handling (`.dat` file)
- Modular programming with headers and source files

## 📁 Project Structure

atm-simulator-c/  
├── main.c              # Entry point and main menu  
├── atm.c               # Business logic (ATM operations)  
├── utils.c             # Helper functions and validation  
├── atm.h               # Header file for ATM module  
├── utils.h             # Header file for utilities  
├── accounts.dat        # Binary file containing user data  
├── transactions.dat    # Binary file logging all transactions  
└── README.md           # Documentation and compilation guide

## 🚀 How to Compile and Run

1. Compile the code:

```bash
gcc main.c atm.c utils.c -o atm_simulator
Run the executable:

bash
Copiar
Editar
./atm_simulator
If no users exist, the system will create the data file with sample accounts.

🧾 File Descriptions
accounts.dat: stores user credentials (account number, PIN, balance)

transactions.dat: stores each operation per account with timestamp

main.c: handles the UI and flow

atm.c: implements core ATM functions

utils.c: validation functions (PIN, input format, etc.)

📊 Sample Functionalities
Check balance

Make a deposit (with validation)

Withdraw (with overdraft prevention)

View transaction history

📌 Future Enhancements
Encrypt PINs and secure files

Add admin interface to manage accounts

Extend to simulate card locking after failed attempts

📄 License
MIT License — For academic and learning purposes.
