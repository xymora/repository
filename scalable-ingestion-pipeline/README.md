# 🔄 Scalable Data Ingestion and Transformation Pipeline

This project implements a scalable data ingestion and transformation system using parallel processing and simulated distributed storage. It is designed to handle high-volume transactional datasets and produce structured analytical outputs.

## 🎯 Objective

To simulate and demonstrate a horizontally scalable data pipeline capable of ingesting and transforming multiple large data files in parallel, while producing summarized insights suitable for business intelligence or downstream processing.

## 🧠 Techniques Used

- Parallel file ingestion with ThreadPoolExecutor
- Date-time feature engineering (hour, weekday)
- Categorical bucketing for numerical fields
- Aggregation and group-wise summarization

## 🛠️ Technologies

- Python 3.x
- pandas
- glob
- concurrent.futures

## 📁 Project Structure

scalable-ingestion-pipeline/
├── data_part_1.csv                    # Simulated distributed data part 1  
├── data_part_2.csv                    # Simulated distributed data part 2  
├── data_part_3.csv                    # Simulated distributed data part 3  
├── data_part_4.csv                    # Simulated distributed data part 4  
├── data_part_5.csv                    # Simulated distributed data part 5  
├── data_pipeline_transform.py        # Python pipeline script for ingestion and processing  
├── processed_transactions.csv         # Final unified and enriched dataset  
├── summary_by_category_day.csv        # Aggregated summary table for insights  
└── README.md                          # Full documentation and project setup

## 🚀 Pipeline

1. Ingest multiple CSV data files from distributed sources  
2. Parse timestamps and extract time-based features (Hour, DayOfWeek)  
3. Categorize transactions into buckets based on amount  
4. Process all files in parallel using thread-based concurrency  
5. Concatenate results and save unified, transformed dataset  
6. Generate summary aggregations grouped by category and day

## 📊 Outputs

- `processed_transactions.csv`: enriched dataset with time and category features  
- `summary_by_category_day.csv`: summary of volume, mean, and sum by category/day  
- Printed summary in console for quick inspection

## 📌 Future Enhancements

- Replace file ingestion with distributed SQL (e.g. Spark, BigQuery)  
- Add anomaly detection and schema validation  
- Deploy as a batch job or cloud function for real-time ETL
