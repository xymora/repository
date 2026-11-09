POKEMON_ORO_PLATA = {
    "posicion": [0xDA03, 0xDA02],
    "mapa": [0xDA00, 0xDA01],
    "equipo": 0xDA22,
    "niveles": [0xDA49 + 0x30 * i for i in range(6)],
    "experiencia": [0xDA32 + 0x30 * i for i in range(6)],
    "metas_bits": [[0xD57C, 1, 40.0, 1], [0xD57D, 1, 40.0, 1], [0xDBE4, 32, 6.0, 0], [0xDC04, 32, 1.0, 0]],
    "banderas_rango": [0xD7B0, 0xD88E],
    "vidas": None,
    "puntos": [],
}

CONOCIDOS = [
    ("POKEMON_GLD", "Pokémon Oro", POKEMON_ORO_PLATA),
    ("POKEMON_SLV", "Pokémon Plata", POKEMON_ORO_PLATA),
]


def buscar(titulo):
    for prefijo, nombre, perfil in CONOCIDOS:
        if titulo.startswith(prefijo):
            return nombre, perfil
    return None, None
