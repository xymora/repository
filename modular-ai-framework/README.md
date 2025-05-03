# 🧠 Modular AI Framework for Real-Time Environmental Response

This project implements a modular artificial intelligence framework capable of dynamically adapting automation workflows based on environmental sensor input. It simulates intelligent modules that respond to temperature, pressure, and flow rate variations with rule-based decisions.

## 🎯 Objective

To simulate a system where intelligent components (cooling, pressure relief, and flow control) activate automatically depending on real-time environmental data, laying the foundation for adaptable automation systems.

## 🧠 Techniques Used

- Threshold-based rule evaluation
- Sensor input simulation
- Time-based event logging
- Multi-module decision mapping
- Visualization of activation dynamics

## 🛠️ Technologies

- Python 3.x
- pandas
- matplotlib

## 📁 Project Structure

modular-ai-framework/
├── environment_inputs.csv          # Simulated environmental sensor readings  
├── module_decision_log.csv         # Binary log of each module's activation  
├── modular_ai_framework.py         # Python script to execute logic and generate graphs  
├── sensor_trends.png               # Plot of sensor readings across time  
├── module_activation_log.png       # Bar chart showing module activations over time  
└── README.md                       # Project overview and documentation

## 🚀 Pipeline

1. Simulate environmental input for 30 time steps  
2. Apply rule-based logic to determine module activation  
3. Log activation matrix by time step  
4. Visualize sensor behavior and module activation dynamics  
5. Save analysis outputs for further evaluation or integration

## 📊 Outputs

- `sensor_trends.png`: line plot of temperature, pressure, and flow rate  
- `module_activation_log.png`: stacked bar chart of activations across time steps  
- `module_decision_log.csv`: full activation history per module  
- `environment_inputs.csv`: raw environmental data for simulation

## 📌 Future Enhancements

- Replace rule-based logic with reinforcement learning policies  
- Integrate IoT sensor input from real systems via MQTT or WebSockets  
- Extend module complexity to multi-state activation with fuzzy logic
