# 🔥 Smart Fire Suppression Network Prototype

This project implements a functional prototype of a smart fire suppression network using mist and directional foam systems for protecting the perimeter of residential zones. The simulation demonstrates fire propagation and automated system activation in a grid environment.

## 🎯 Objective

To simulate a fire scenario and validate the effectiveness of perimeter-based suppression systems using mist and foam as a reactive defense against dynamic fire spread.

## 🧠 Techniques Used

- Cellular automata-based grid simulation
- Conditional activation of suppression zones
- Temporal progression tracking via simulation ticks
- Visualization of fire containment using heatmaps

## 🛠️ Technologies

- Python 3.x
- NumPy
- matplotlib

## 📁 Project Structure

smart-fire-suppression-network/
├── smart_fire_suppression_simulation.py    # Simulation engine for fire spread and suppression response  
├── fire_suppression_simulation.png         # 5x5 grid snapshots showing the fire control process over time  
└── README.md                               # Full documentation and simulation logic

## 🚀 Pipeline

1. Initialize a 20x20 grid with fire ignition points  
2. Define perimeter zones equipped with smart mist/foam systems  
3. Simulate fire spread across neighboring cells per tick  
4. Activate suppression when fire reaches boundary zones  
5. Record simulation snapshots over 50 ticks  
6. Export a multi-frame heatmap of fire and suppression progression

## 📊 Outputs

- `fire_suppression_simulation.png`: visualization grid showing fire containment over time  
- Internal fire matrix with cell state codes:  
  - 0 = Free  
  - 1 = Fire  
  - 2 = Suppression (foam/mist)

## 📌 Future Enhancements

- Integrate sensor-driven decision systems and temperature thresholds  
- Expand to 3D or real-world map overlays  
- Connect with IoT control systems for dynamic actuator testing
