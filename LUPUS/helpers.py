"""
Archivo: helpers.py
Descripción: Funciones auxiliares comunes al modelo.
"""

def clamp(value, min_value, max_value):
    """Limita el valor entre un mínimo y un máximo."""
    return max(min_value, min(value, max_value))

def linear_decay(initial, rate, day):
    """Calcula una reducción lineal."""
    return max(0, initial - rate * day)

def logistic_growth(L, k, x0, t):
    """Modelo de crecimiento logístico."""
    from math import exp
    return L / (1 + exp(-k * (t - x0)))
