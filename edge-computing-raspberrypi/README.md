# 🌐 Edge Computing Solution with Raspberry Pi

This project demonstrates an edge computing solution using a Raspberry Pi (or simulated environment) that processes sensor data locally, without relying on cloud services.

## 🎯 Objective

To detect events (e.g., falls or gas leaks) by reading sensor data directly on a Raspberry Pi and running machine learning models locally.

## 🧠 Techniques Used

- Sensor interfacing with MPU6050 or gas sensors  
- Embedded ML inference for event detection  
- Local logging and alerting system (network/LED/sound)  
- Benchmarking against cloud-based inference

## 🛠️ Technologies

- Python 3.x  
- scikit-learn or tflite-runtime  
- RPi.GPIO or gpiozero  
- Local MQTT or socket for LAN alerts

## 📁 Project Structure

```
edge-computing-raspberrypi/
├── hardware/
│   └── diagram.png                # Wiring diagram for hardware setup
├── ml_model/
│   └── model.py                   # Edge-optimized ML model
├── scripts/
│   ├── sensor_reader.py           # MPU6050 or gas sensor data reader
│   └── alert_handler.py           # Trigger LEDs, sound, or LAN messages
├── logs/
│   └── events.log                 # Local log of detected events
└── README.md                      # Project documentation
```

## 🚀 Instructions

1. Connect sensor as shown in `hardware/diagram.png`  
2. Run `sensor_reader.py` to start reading sensor input  
3. Model will classify data using `ml_model/model.py`  
4. Detected events logged to `logs/events.log`  
5. Alerts sent via sound/LED or LAN broadcast

## 📊 Benchmarking

A script compares inference time of local model vs simulated cloud latency to evaluate real-time effectiveness.

## 📌 Future Enhancements

- Add GUI interface to view events  
- Include battery monitoring for mobile setups  
- Extend for multiple sensor types

## 📄 License

MIT License
