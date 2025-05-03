# 📡 IoT Anomaly Detection System with MQTT, InfluxDB, and Real-Time Dashboard

This project simulates an IoT system with multiple sensor nodes transmitting environmental data via MQTT to a centralized broker. Data is stored in real-time, processed for anomaly detection, and visualized on a dashboard. The goal is to demonstrate how AI can enhance decision-making through real-time monitoring.

## 🎯 Objective

To create a realistic IoT simulation that captures sensor data, stores it, applies a machine learning model for anomaly detection, and displays insights in real time, simulating an intelligent and scalable architecture.

## 🧠 Techniques Used

- MQTT protocol for lightweight real-time data transmission  
- Simulation of multiple sensor nodes  
- InfluxDB for time-series data storage  
- Isolation Forest for unsupervised anomaly detection  
- Streamlit for interactive visualization  
- Joblib for model serialization  

## 🛠️ Technologies

- Python 3.x  
- paho-mqtt  
- InfluxDB  
- scikit-learn  
- joblib  
- streamlit  
- Mosquitto MQTT broker  

## 📁 Project Structure

```
iot-anomaly-detection/
├── broker/
│   └── mosquitto.conf             # MQTT broker configuration
├── sensors/
│   ├── sensor_node_1.py           # Sensor node 1 simulation
│   ├── sensor_node_2.py           # Sensor node 2 simulation
│   └── sensor_node_3.py           # Sensor node 3 simulation
├── storage/
│   ├── influxdb_setup.sh          # Database setup script
│   └── data_schema.txt            # Schema structure
├── processing/
│   ├── anomaly_detection.py       # Anomaly detection and data ingestion
│   └── model.pkl                  # Trained ML model
├── dashboard/
│   └── app.py                     # Streamlit dashboard
├── notebooks/
│   └── model_training.ipynb       # Notebook for training and saving model
├── requirements.txt               # Python dependencies
└── README.md                      # Full project documentation
```

## 🔄 Workflow Simulation

- Simulated MQTT topics per sensor (`sensor/1`, `sensor/2`, `sensor/3`)  
- Nodes publish temperature and humidity every 5 seconds  
- Central processor subscribes, stores, and applies the model  
- Results visualized in real time  

## 🚀 How to Run

1. Start MQTT broker:
   ```bash
   mosquitto -c broker/mosquitto.conf
   ```

2. Set up InfluxDB:
   ```bash
   chmod +x storage/influxdb_setup.sh
   ./storage/influxdb_setup.sh
   ```

3. Launch sensor nodes (in separate terminals):
   ```bash
   python sensors/sensor_node_1.py
   python sensors/sensor_node_2.py
   python sensors/sensor_node_3.py
   ```

4. Run anomaly detection processor:
   ```bash
   python processing/anomaly_detection.py
   ```

5. Launch Streamlit dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```

## 📊 Outputs

- `model.pkl`: Trained Isolation Forest model  
- Live data storage in InfluxDB  
- Detected anomalies printed and visualized  
- Dashboard on `http://localhost:8501`  

## 📌 Future Enhancements

- Switch to real sensors (ESP32 + MQTT)  
- Add Grafana or InfluxDB native dashboards  
- Extend ML model to support classification and regression  
- Enable alerts on anomaly detection  

## 📄 License

This project is licensed under the MIT License.
