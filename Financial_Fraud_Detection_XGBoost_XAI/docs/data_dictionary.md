# 📖 Financial Data Dictionary (PaySim)

| Variable | Description | Type |
| :--- | :--- | :--- |
| `step` | Maps a unit of time in the real world (1 step = 1 hour). | Integer |
| `type` | CASH-IN, CASH-OUT, DEBIT, PAYMENT and TRANSFER. | Categorical |
| `amount` | Amount of the transaction in local currency. | Numeric |
| `oldBalanceOrig` | Initial balance before the transaction (Origin). | Numeric |
| `newBalanceOrig` | New balance after the transaction (Origin). | Numeric |
| `oldBalanceDest` | Initial balance before the transaction (Destination). | Numeric |
| `newBalanceDest` | New balance after the transaction (Destination). | Numeric |
| `isFraud` | **Target Variable** (1: Fraudulent, 0: Legitimate). | Binary |
