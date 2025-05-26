# Archivo: sensitivity_analysis.py
# Descripción: Realiza un análisis de sensibilidad variando parámetros del modelo.

import matplotlib.pyplot as plt

# Ejecuta una función modelo con múltiples valores de un parámetro
# y retorna un diccionario de resultados por cada valor probado.
# model_func: función que recibe un valor del parámetro y devuelve un resultado (p. ej., lista).
# param_values: lista de valores a probar.
def analyze_sensitivity(model_func, param_values, variable_key):
    results = {}

    for val in param_values:
        output = model_func(val)
        if isinstance(output, dict) and variable_key in output:
            results[val] = output[variable_key]
        else:
            results[val] = output

    return results

# Genera una gráfica de sensibilidad para comparar el efecto del parámetro
# sobre una variable de interés durante varios días de simulación.
def plot_sensitivity(results, variable_name="Variable", param_name="Parámetro"):
    plt.figure(figsize=(10, 6))

    for param_val, series in results.items():
        plt.plot(series, label=f"{param_name} = {param_val}")

    plt.title(f"Análisis de sensibilidad: {variable_name}")
    plt.xlabel("Días")
    plt.ylabel(variable_name)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig("sensitivity_analysis.png")
    plt.close()
    print("[✔] Gráfica de sensibilidad guardada como sensitivity_analysis.png")
