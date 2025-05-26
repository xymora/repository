import os
import matplotlib.pyplot as plt

def save_figure(fig, filepath):
    fig.tight_layout()
    fig.savefig(filepath, dpi=300)
    plt.close(fig)
    print(f"[✔] Gráfica guardada en: {filepath}")

def plot_results(data, filepath="combined_response.png"):
    fig, ax = plt.subplots(figsize=(10, 6))
    for key in data:
        if key != "Día":
            ax.plot(data["Día"], data[key], label=key)
    ax.set_title("Evolución inmunológica durante la terapia combinada")
    ax.set_xlabel("Días de simulación")
    ax.set_ylabel("Nivel relativo")
    ax.grid(True)
    ax.legend()
    save_figure(fig, filepath)

def plot_individual_modules(data, output_dir):
    days = data["Día"]

    # Vacuna tolerogénica
    fig, ax = plt.subplots()
    ax.plot(days, data["IL10"], color='orange', label="IL-10")
    ax.set_title("Vacuna tolerogénica")
    ax.set_xlabel("Días")
    ax.set_ylabel("IL-10 (pg/mL)")
    ax.legend()
    save_figure(fig, os.path.join(output_dir, "vaccine_response.png"))

    # siRNA anti-BAFF
    fig, ax = plt.subplots()
    ax.plot(days, data["BAFF"], color='green', label="BAFF")
    ax.set_title("siRNA anti-BAFF")
    ax.set_xlabel("Días")
    ax.set_ylabel("BAFF (ng/mL)")
    ax.legend()
    save_figure(fig, os.path.join(output_dir, "sirna_response.png"))

    # Anticuerpo anti-IFN-α
    fig, ax = plt.subplots()
    ax.plot(days, data["IFNA"], color='blue', label="IFN-α")
    ax.set_title("Anticuerpo anti-IFN-α")
    ax.set_xlabel("Días")
    ax.set_ylabel("IFN-α (pg/mL)")
    ax.legend()
    save_figure(fig, os.path.join(output_dir, "ifna_blockade_response.png"))

    # Exosomas de MSCs
    fig, ax = plt.subplots()
    ax.plot(days, data["IL10 (Exosomas)"], color='darkorange', label="IL-10")
    ax.plot(days, data["M1/M2"], color='green', label="M1 / M2")
    ax.set_title("Exosomas de MSCs")
    ax.set_xlabel("Días")
    ax.set_ylabel("Valor relativo")
    ax.legend()
    save_figure(fig, os.path.join(output_dir, "exosomes_response.png"))
