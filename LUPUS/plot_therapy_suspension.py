import os
import numpy as np
import matplotlib.pyplot as plt

def plot_suspension_therapy(output_dir):
    dias = np.arange(0, 25, 1)
    abrupta = 5.5 * np.exp(-0.4 * dias) + 1
    escalonada = 5.5 * np.exp(-0.2 * dias) + 1.5

    fig, ax = plt.subplots(figsize=(6, 5))

    ax.plot(dias, abrupta, label="Suspensión abrupta", color="red")
    ax.plot(dias, escalonada, label="Suspensión escalonada", color="blue")

    ax.axvline(x=5, color="black", linestyle="-")
    ax.text(5.2, 4.7, "Inicio\nsuspensión\nde terapia", fontsize=10, verticalalignment='center')

    ax.set_xlabel("Días", fontsize=12)
    ax.set_ylabel("Índice inmunoregulador", fontsize=12)
    ax.legend()
    ax.set_ylim(0, 6.5)

    fig.tight_layout()
    output_path = os.path.join(output_dir, "suspension_terapia.png")
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[✔] Gráfica guardada en: {output_path}")

# Si lo usas directamente
if __name__ == "__main__":
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(folder, exist_ok=True)
    plot_suspension_therapy(folder)
