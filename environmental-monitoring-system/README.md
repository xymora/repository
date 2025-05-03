# Proyecto: environmental-monitoring-system/README.md

```markdown
# 🌱 Environmental Monitoring System with ESP32, DHT11, MQTT and ML

This repository contains a complete professional IoT system for environmental monitoring using ESP32, DHT11 sensor (temperature and humidity), and a simple machine learning model (K-Means clustering) deployed on a Raspberry Pi. It also includes MQTT data transmission, real-time visualization, and detailed documentation.

## 🎯 Objective
To build an end-to-end embedded system that:
- Captures real-time temperature and humidity data
- Transmits data via MQTT
- Performs onboard or edge ML inference
- Displays real-time readings with environmental classification

## 🧠 Techniques Used
- Real-time data capture using DHT11
- Serial-to-MQTT data transmission (ESP32 to Raspberry Pi)
- K-Means clustering for air status categorization
- Streamlit dashboard for visualization
- Professional hardware documentation and testing

## 🛠️ Technologies
- Microcontroller: ESP32
- Sensor: DHT11
- Protocol: MQTT (Mosquitto broker)
- ML: KMeans (scikit-learn)
- Data visualization: Streamlit
- Languages: MicroPython (ESP32), Python (Raspberry Pi)

## 📁 Project Structure

environmental-monitoring-system/
├── firmware/
│   └── main.py                  # ESP32 code to read DHT11 and publish to MQTT
├── electronics/
│   └── schematic.png            # Diagram of ESP32 + DHT11 wiring
├── edge_processing/
│   ├── mqtt_subscriber.py      # MQTT client receiving sensor data
│   ├── model.pkl               # Pre-trained KMeans clustering model
│   └── classify_and_store.py   # Logic to classify data and store results
├── dashboard/
│   └── app.py                  # Streamlit app for real-time data view
├── notebooks/
│   └── clustering_training.ipynb # ML model development and evaluation
├── data/
│   └── sensor_data.csv         # Real collected data for training
├── requirements.txt            # Python dependencies
└── README.md                   # Full documentation

## 🚀 Pipeline Overview
1. ESP32 reads temperature/humidity from DHT11 every 10s
2. Publishes data to MQTT broker (Mosquitto)
3. Raspberry Pi receives and processes data with KMeans
4. Results stored and visualized in real time

## 📊 Outputs
- Real-time clustered environmental states
- Logs of historical data
- Visual plots in Streamlit dashboard

## 📌 Future Enhancements
- Integrate anomaly detection
- Deploy ML model directly on ESP32 using TensorFlow Lite
- Include air quality or CO2 sensors

## 📄 License
MIT License
