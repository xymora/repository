import os
import numpy as np
import matplotlib.pyplot as plt

def plot_article_multipanel(output_dir):
    # Simulación de días para cada intervención
    days_vaccine = np.arange(0, 31)
    days_sirna = np.arange(0, 25)
    days_ifna = np.arange(0, 31)
    days_exo = np.arange(0, 25)

    # Panel A: Vacuna tolerogénica
    il6 = 1.2 + 0.02 * days_vaccine
    il17 = 1.8 - 0.005 * days_vaccine
    treg_th = 1.35 * np.ones(len(days_vaccine))

    # Panel B: siRNA anti-IFN-γS
    v1 = -1.2 + 0.02 * days_sirna
    sirna = -0.7 - 0.025 * days_sirna
    ifna_sirna = -1.0 + 0.04 * days_sirna

    # Panel C: Anticuerpo anti-IFN-α
    ifna = 0.2 + 0.03 * days_ifna
    dcs = 0.6 - 0.015 * days_ifna
    tnf = 0.2 * np.exp(-0.1 * days_ifna)

    # Panel D: Exosomas de MSCs
    tnf_exo = 5 - 0.12 * days_exo
    il10_exo = 1 + 0.1 * days_exo
    m1_m2 = 3.0 * np.exp(-0.15 * days_exo)

    fig, axs = plt.subplots(2, 2, figsize=(12, 10))

    # Panel A
    axs[0, 0].plot(days_vaccine, il6, label="/L–6", color="red")
    axs[0, 0].plot(days_vaccine, il17, label="/L17", color="purple")
    axs[0, 0].plot(days_vaccine, treg_th, label="Treg/Th?", color="green")
    axs[0, 0].set_title("Evolución inmunológica\nbajo vacuna tolerogenica")
    axs[0, 0].set_xlabel("Time (days)")
    axs[0, 0].legend()

    # Panel B
    axs[0, 1].plot(days_sirna, v1, label="(1)* V.ućnaâ Ɉoler:", color="blue")
    axs[0, 1].plot(days_sirna, sirna, label="(2) SIRNA anti-", color="orange")
    axs[0, 1].plot(days_sirna, ifna_sirna, label="(3) IFN-α", color="green")
    axs[0, 1].set_title("Evolución inmunológica\nbajo siRNA anti-IFN-γS")
    axs[0, 1].set_xlabel("Time (days)")
    axs[0, 1].legend()

    # Panel C
    axs[1, 0].plot(days_ifna, ifna, label="IFN-α", color="blue")
    axs[1, 0].plot(days_ifna, dcs, label="DCs", color="green")
    axs[1, 0].plot(days_ifna, tnf, label="TNF-α", color="orange")
    axs[1, 0].set_title("Evolución inmunológica\nbajo anticuerpo anti-IFN−α")
    axs[1, 0].set_xlabel("Time (days)")
    axs[1, 0].legend()

    # Panel D
    axs[1, 1].plot(days_exo, tnf_exo, label="TNF-α", color="red")
    axs[1, 1].plot(days_exo, il10_exo, label="IL10", color="orange")
    axs[1, 1].plot(days_exo, m1_m2, label="M1 / M2", color="green")
    axs[1, 1].set_title("Evolución inmunológica\nbajo exosomas de MSCs")
    axs[1, 1].set_xlabel("Time (days)")
    axs[1, 1].legend()

    # Ajustar y guardar
    fig.tight_layout()
    output_path = os.path.join(output_dir, "immune_response_multipanel.png")
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"[✔] Gráfica multipanel guardada en: {output_path}")

# Para ejecución directa
if __name__ == "__main__":
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(folder, exist_ok=True)
    plot_article_multipanel(folder)
