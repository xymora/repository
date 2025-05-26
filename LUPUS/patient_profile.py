# Archivo: patient_profile.py
# Descripción: Genera un perfil clínico simulado para un paciente con LES.

import random

# Genera un diccionario con datos clínicos simulados del paciente.
# Los valores están basados en rangos reportados en la literatura médica.
def generate_patient_profile():
    profile = {
        "edad": random.randint(18, 55),                     # Edad entre 18 y 55 años
        "sexo": random.choices(["femenino", "masculino"], weights=[0.9, 0.1])[0],  # 90% probabilidad de mujer
        "IMC": round(random.uniform(18, 32), 1),            # Índice de masa corporal
        "SLEDAI": random.randint(6, 20),                    # Índice de actividad de LES (0–105, normalmente 0–20)
        "años_con_LES": random.randint(1, 15),              # Tiempo desde el diagnóstico
        "nivel_C3": round(random.uniform(60, 90), 1),       # mg/dL, normal entre 90-180, bajo en LES activo
        "nivel_C4": round(random.uniform(10, 20), 1),       # mg/dL, normal entre 10-40
    }
    return profile
