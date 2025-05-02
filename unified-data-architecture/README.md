# 🧩 Unified Data Architecture with ETL and Stream Processing

This project demonstrates a unified data architecture that integrates static and streaming data sources using ETL (Extract-Transform-Load) and temporal stream joins to support real-time decision systems.

## 🎯 Objective

To create a scalable and unified view by joining structured customer and transaction datasets with real-time events, allowing actionable insights to be generated in near real-time.

## 🧠 Techniques Used

- CSV-based structured data loading and cleaning
- Temporal joins using merge_asof to simulate stream enrichment
- Categorical bucketing for transaction segmentation
- Multi-source data integration pipeline

## 🛠️ Technologies

- Python 3.x
- pandas
- datetime for timestamp manipulation

## 📁 Project Structure

unified-data-architecture/
├── source_customers.csv               # Customer records with region and ID  
├── source_transactions.csv            # Transaction log with timestamps and amounts  
├── stream_events.csv                  # Simulated real-time user events (clicks, purchases, etc.)  
├── unified_data_architecture.py       # Full ETL and streaming integration script  
├── unified_customer_transactions.csv  # Merged customer-transaction dataset with transformation  
├── real_time_enriched_dataset.csv     # Temporally aligned and enriched dataset with stream events  
└── README.md                          # Complete project description and pipeline logic

## 🚀 Pipeline

1. Load customer and transaction data  
2. Merge and enrich transactions with customer regions and amount categories  
3. Load simulated event stream data (clicks, support, purchases)  
4. Apply a time-window join (±1 hour) to simulate real-time event integration  
5. Export unified datasets for analysis and operational insights

## 📊 Outputs

- `unified_customer_transactions.csv`: enriched and segmented transaction dataset  
- `real_time_enriched_dataset.csv`: result of stream-event integration with transactional context

## 📌 Future Enhancements

- Replace CSV with SQL-based or Kafka streaming ingestion  
- Add anomaly detection for fraudulent events or unusual activity  
- Integrate with real-time dashboards for monitoring
