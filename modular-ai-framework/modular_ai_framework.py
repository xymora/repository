
import pandas as pd
import matplotlib.pyplot as plt

# Cargar datos
env_df = pd.read_csv("environment_inputs.csv")
dec_df = pd.read_csv("module_decision_log.csv")

# Visualizar activaciones
plt.figure(figsize=(10, 6))
plt.plot(env_df["TimeStep"], env_df["Temperature"], label="Temperature")
plt.plot(env_df["TimeStep"], env_df["Pressure"], label="Pressure")
plt.plot(env_df["TimeStep"], env_df["FlowRate"], label="FlowRate")
plt.title("Environmental Sensor Readings Over Time")
plt.xlabel("Time Step")
plt.ylabel("Value")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("sensor_trends.png")
plt.close()

# Activaciones por módulo
dec_df.set_index("TimeStep").plot(kind="bar", stacked=True, figsize=(12,6))
plt.title("Module Activation Log")
plt.xlabel("Time Step")
plt.ylabel("Activation")
plt.legend(loc="upper right")
plt.tight_layout()
plt.savefig("module_activation_log.png")
