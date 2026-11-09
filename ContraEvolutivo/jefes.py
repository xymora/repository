import math

NOMBRES = {
    "muro": "Muro defensor",
    "ojo": "Ojo de la base",
    "cabeza": "Cabeza alienígena",
    "gemelos": "Gemelos",
    "tanque": "Tanque blindado",
    "gigante": "Gigante de la puerta",
    "nave": "Núcleo del hangar",
    "corazon": "Corazón alienígena",
}


def _parte(sprite, x, y, w, h, hp, vital=False, mov="fijo", ataque="ninguno", periodo=60, desfase=0,
           a=0.0, s=0.0, centro=None, fase=0.0):
    return dict(sprite=sprite, x=x, y=y, w=w, h=h, hp=hp, vital=vital, mov=mov, ataque=ataque,
                periodo=periodo, desfase=desfase, a=a, s=s, centro=centro, fase=fase)


PARTES = {
    "muro": [
        _parte("sensor", 170, 128, 22, 32, 30, vital=True, ataque="apuntado", periodo=70),
        _parte("canon_muro", 196, 50, 20, 12, 14, ataque="granada", periodo=55),
        _parte("canon_muro", 196, 90, 20, 12, 14, ataque="granada", periodo=55, desfase=27),
    ],
    "ojo": [
        _parte("ojo", 176, 148, 40, 40, 40, vital=True, ataque="anillo", periodo=75),
        _parte("torreta_jefe", 120, 32, 16, 16, 12, ataque="apuntado", periodo=50),
        _parte("torreta_jefe", 150, 32, 16, 16, 12, ataque="apuntado", periodo=50, desfase=25),
    ],
    "cabeza": [
        _parte("cabeza", 104, 20, 48, 40, 45, vital=True, mov="flota", ataque="abanico", periodo=45,
               a=6, s=0.05),
        _parte("orbe", 120, 32, 16, 16, 16, mov="circulo", a=58, s=0.05, centro=(128, 40)),
        _parte("orbe", 120, 32, 16, 16, 16, mov="circulo", a=58, s=0.05, centro=(128, 40), fase=math.pi),
    ],
    "gemelos": [
        _parte("gemelo", 60, 70, 28, 28, 26, vital=True, mov="vaiven", ataque="apuntado", periodo=55,
               a=40, s=0.04),
        _parte("gemelo", 170, 70, 28, 28, 26, vital=True, mov="vaiven", ataque="apuntado", periodo=55,
               desfase=27, a=40, s=0.04, fase=math.pi),
    ],
    "tanque": [
        _parte("tanque", 150, 136, 56, 40, 45, vital=True, mov="vaiven", ataque="abanico", periodo=50,
               a=40, s=0.02),
    ],
    "gigante": [
        _parte("gigante", 170, 136, 32, 56, 50, vital=True, mov="vaiven", ataque="disco", periodo=45,
               a=50, s=0.025),
    ],
    "nave": [
        _parte("nave", 180, 120, 40, 40, 50, vital=True, ataque="anillo", periodo=80),
        _parte("canon_muro", 160, 50, 20, 12, 15, ataque="abanico", periodo=60),
        _parte("canon_muro", 160, 165, 20, 12, 15, ataque="abanico", periodo=60, desfase=30),
    ],
    "corazon": [
        _parte("corazon", 170, 120, 48, 56, 60, vital=True, ataque="apuntado", periodo=90),
        _parte("boca", 140, 40, 24, 24, 15, ataque="engendrar", periodo=80),
        _parte("boca", 205, 40, 24, 24, 15, ataque="engendrar", periodo=80, desfase=40),
    ],
}
