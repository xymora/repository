# Archivo: helpers.py
# Descripción: Funciones auxiliares comunes al modelo.

# Limita un valor entre un mínimo y un máximo.
def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

# Calcula una disminución lineal a lo largo del tiempo.
def linear_decay(initial, rate, day):
    return max(0, initial - rate * day)

# Calcula el crecimiento logístico de una variable.
# L: valor límite superior (capacidad máxima)
# k: tasa de crecimiento
# x0: punto medio (día de mayor cambio)
# t: día actual
def logistic_growth(L, k, x0, t):
    from math import exp
    return L / (1 + exp(-k * (t - x0)))
