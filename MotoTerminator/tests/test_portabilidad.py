import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRON = os.path.join(os.path.dirname(RAIZ), "DronEntregas", "datos")
MTY = "Monterrey · Centro"
CLAVE_MTY = "monterrey___centro_25p6790_m100p3070"
VIVOS = ("mejor_moto", "poblacion", "historial", "sesion", "campeones")
CHECKPOINTS = ("mejor_moto_ciudad.json", "poblacion_ciudad.npz", "historial_ciudad.csv",
               "campeones_ciudad.json")

SCRIPT = r'''
import hashlib, json, os, sys, urllib.request
COPIA = sys.argv[1]
sys.path.insert(0, COPIA)
def _sin_red(*a, **k):
    raise OSError("prueba de portabilidad: sin internet")
urllib.request.urlopen = _sin_red
import numpy as np
import config as C
import calles as K
K._descargar = _sin_red
out = {"cwd": os.getcwd(), "calles": K.__file__, "AQUI": K.AQUI, "CARPETA": K.CARPETA}

solo_red = len(sys.argv) > 2 and sys.argv[2] == "solo_red"   # original: sólo lectura
if not solo_red:
    modo, zona, ruta = K.cargar_sesion()                     # 1) sesión vieja
    out["sesion"] = {"modo": modo, "clave": zona.clave, "carpeta": zona.carpeta,
                     "ancho": zona.ancho, "alto": zona.alto, "ruta": ruta}

red = K.RedVial(K.zona_para("Monterrey · Centro"),
                avisar=lambda *a, **k: None)                 # 2) RedVial sin internet
z = red.zona
p = K.PistaCalle(red, 3, 12345, superficie="pavimento", circuito="no")
out["red"] = {"clave": z.clave, "carpeta": z.carpeta, "ancho": z.ancho, "alto": z.alto,
              "m_por_px": z.m_por_px, "nodos": len(red.pos),
              "pista": hashlib.sha256(np.ascontiguousarray(p.kappa, dtype=float).tobytes()).hexdigest()}
if solo_red:
    print("@@" + json.dumps(out, default=str))
    sys.exit(0)

import evolucion as E                                         # 3) entrenador que continúa
with np.load(E.ruta(C.ARCHIVO_POBLACION, "ciudad"), allow_pickle=False) as d:
    gen_guardada = int(d["generacion"])
e = E.Entrenador(continuar=True, modo="ciudad", red_vial=red)
out["entrenador"] = {"gen_guardada": gen_guardada, "generacion": e.generacion,
                     "dir_datos": e.dir_datos, "archivo": e.ruta(C.ARCHIVO_POBLACION)}

h = dict(e.historial[-1]) if e.historial else {}             # 4) guardar UNA generación
resumen = {"generacion": e.generacion, "nivel": e.nivel, "mejor": float(h.get("mejor", 1.0)),
           "promedio": float(h.get("promedio", 0.5)), "llegaron": float(h.get("llegaron", 0.0)),
           "terminadas_lider": int(h.get("terminadas_lider", 0)), "sigma": float(e.sigma),
           "vel_lider": float(h.get("vel_lider", 0.0)),
           "llegadas_limpias": float(h.get("llegadas_limpias", 0.0)),
           "reintentos_lider": float(h.get("reintentos_lider", 0.0)),
           "terminadas_limpias_lider": int(h.get("terminadas_limpias_lider", 0)),
           "pistas": int(C.PISTAS_POR_GENERACION)}
e._guardar_mejor(e.pob[0], resumen)
e._guardar_historial(resumen)
e._guardar_poblacion()
if hasattr(e, "_guardar_campeon"):
    e._guardar_campeon(e.pob[0], resumen, e.etapa)
e.cerrar()
K.guardar_sesion("ciudad", red.zona, ruta)
with open(K.ARCHIVO_SESION, encoding="utf-8") as f:
    out["sesion_nueva"] = json.load(f)
print("@@" + json.dumps(out, default=str))
'''


def _foto(raiz, excluir=(), ignorar_vivos=False):
    out = {}
    if not os.path.isdir(raiz):
        return out
    excluir = [os.path.normcase(os.path.abspath(x)) for x in excluir]
    for d, subdirs, archivos in os.walk(raiz):
        if os.path.normcase(os.path.abspath(d)) in excluir:
            subdirs[:] = []
            continue
        subdirs[:] = [s for s in subdirs if s != "__pycache__"
                      and os.path.normcase(os.path.abspath(os.path.join(d, s))) not in excluir]
        for a in archivos:
            if ignorar_vivos and a.startswith(VIVOS):
                continue
            p = os.path.join(d, a)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out[os.path.relpath(p, raiz)] = (st.st_mtime_ns, st.st_size)
    return out


def _foto_original():
    out = {os.path.join("datos", k): v for k, v in _foto(os.path.join(RAIZ, "datos")).items()}
    out.update({os.path.join("resultados", k): v
                for k, v in _foto(os.path.join(RAIZ, "resultados")).items()})
    for a in os.listdir(RAIZ):
        p = os.path.join(RAIZ, a)
        if os.path.isfile(p) and not a.startswith(VIVOS) and a.endswith(
                (".json", ".npz", ".csv", ".jpg", ".png", ".npy", ".tmp", ".pkl")):
            st = os.stat(p)
            out[a] = (st.st_mtime_ns, st.st_size)
    return out


def _copiar(origen, destino, intentos=5):
    for k in range(intentos):
        try:
            shutil.copy2(origen, destino)
            return
        except OSError:
            if k == intentos - 1:
                raise
            time.sleep(0.5)


def _preparar_copia(copia):
    os.makedirs(os.path.join(copia, "datos"))
    os.makedirs(os.path.join(copia, "tests"))
    for a in os.listdir(RAIZ):
        if a.endswith((".py", ".bat", ".txt")):
            _copiar(os.path.join(RAIZ, a), os.path.join(copia, a))
    for a in os.listdir(os.path.join(RAIZ, "tests")):
        if a.endswith(".py"):
            _copiar(os.path.join(RAIZ, "tests", a), os.path.join(copia, "tests", a))
    for a in os.listdir(os.path.join(RAIZ, "datos")):
        p = os.path.join(RAIZ, "datos", a)
        if os.path.isfile(p):
            _copiar(p, os.path.join(copia, "datos", a))
    for a in CHECKPOINTS:
        if os.path.exists(os.path.join(RAIZ, a)):
            _copiar(os.path.join(RAIZ, a), os.path.join(copia, a))
    with open(os.path.join(copia, "sesion.json"), "w", encoding="utf-8") as f:
        json.dump({"modo": "ciudad", "superficie": "pavimento", "circuito": "no",
                   "plan": "automatico",
                   "ruta": [[25.685106079042512, -100.32521212981435],
                            [25.683290277111503, -100.3229998103575]],
                   "zona": {"nombre": MTY, "centro": [25.679, -100.307], "ancho": 5200.0,
                            "alto": 3600.0, "m_por_px": 1.0,
                            "carpeta": r"Q:\Usuarios\Otra Máquina\ProyectosIAJ\DronEntregas\datos"}},
                  f, ensure_ascii=False, indent=1)


def _correr(copia, cwd, *extra):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("PYTHONPATH", None)
    r = subprocess.run([sys.executable, "-c", SCRIPT, copia, *extra], cwd=cwd, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600)
    assert r.returncode == 0, f"falló el subproceso:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"
    linea = [x for x in r.stdout.splitlines() if x.startswith("@@")]
    assert linea, r.stdout[-3000:] + r.stderr[-3000:]
    return json.loads(linea[-1][2:])


def _dentro(ruta, base):
    r, b = os.path.normcase(os.path.abspath(ruta)), os.path.normcase(os.path.abspath(base))
    return os.path.commonpath([r, b]) == b


def comprobar_portabilidad(verbose=False):
    if not os.path.exists(os.path.join(RAIZ, "datos", f"{CLAVE_MTY}_osm.json")) \
            and not os.path.exists(os.path.join(DRON, f"{CLAVE_MTY}_osm.json")):
        return "omitida: no hay zona de Monterrey en disco"
    if not os.path.exists(os.path.join(RAIZ, "poblacion_ciudad.npz")):
        return "omitida: no hay checkpoint de calles"
    if not os.path.exists(os.path.join(RAIZ, "datos", f"{CLAVE_MTY}_osm.json")):
        sys.path.insert(0, RAIZ)
        import calles
        calles.zona_para(MTY)

    base = tempfile.mkdtemp(prefix="MT portabilidad ")
    try:
        copia = os.path.join(base, "Mis Proyectos Ñandú", "Moto Terminátor copia (ñ á é)")
        otro_cwd = os.path.join(base, "otro cwd")
        os.makedirs(otro_cwd)
        _preparar_copia(copia)
        assert not os.path.exists(os.path.join(os.path.dirname(copia), "DronEntregas"))

        ref = _correr(RAIZ, otro_cwd, "solo_red")

        antes_copia = _foto(copia)
        antes_fuera = _foto(base, excluir=[copia])
        antes_orig = _foto_original()
        antes_dron = _foto(DRON)
        out = _correr(copia, otro_cwd)
        if verbose:
            print(json.dumps(out, ensure_ascii=False, indent=1, default=str))

        assert _dentro(out["calles"], copia) and _dentro(out["AQUI"], copia), out
        assert os.path.normcase(out["cwd"]) == os.path.normcase(os.path.abspath(otro_cwd))
        s = out["sesion"]
        assert s["modo"] == "ciudad" and s["clave"] == CLAVE_MTY, s
        assert _dentro(s["carpeta"], copia) and (s["ancho"], s["alto"]) == (5200.0, 3600.0), s
        assert s["ruta"] is not None
        r = out["red"]
        assert _dentro(r["carpeta"], copia), r
        assert (r["clave"], r["ancho"], r["alto"], r["m_por_px"]) == (CLAVE_MTY, 5200.0, 3600.0, 1.0), r
        assert (r["nodos"], r["pista"]) == (ref["red"]["nodos"], ref["red"]["pista"]), (r, ref["red"])
        en = out["entrenador"]
        assert en["generacion"] == en["gen_guardada"] + 1, en
        assert en["dir_datos"] is None and _dentro(en["archivo"], copia), en
        z = out["sesion_nueva"]["zona"]
        assert z["clave"] == CLAVE_MTY and not os.path.isabs(z.get("carpeta", "datos")), z
        texto = json.dumps(out["sesion_nueva"], ensure_ascii=False)
        assert ":\\" not in texto and ":/" not in texto, texto

        despues = _foto(copia)
        cambiados = sorted(k for k, v in despues.items() if antes_copia.get(k) != v)
        for f in ("mejor_moto_ciudad.json", "poblacion_ciudad.npz", "historial_ciudad.csv",
                  "sesion.json"):
            assert f in cambiados, (f, cambiados)
        assert not any(k.endswith(".tmp") for k in despues), cambiados
        fuera = _foto(base, excluir=[copia])
        nuevos_fuera = sorted(k for k, v in fuera.items() if antes_fuera.get(k) != v)
        assert not nuevos_fuera, nuevos_fuera
        orig = _foto_original()
        tocados = sorted(k for k, v in orig.items() if antes_orig.get(k) != v)
        assert not tocados, f"se escribió en el proyecto original: {tocados}"
        assert _foto(DRON) == antes_dron, "se escribió en DronEntregas"
        if os.name == "nt":
            bat = os.path.join(copia, "Iniciar_Simulador.bat")
            rb = subprocess.run(f'cmd /d /c ""{bat}" --help"', cwd=otro_cwd, capture_output=True,
                                timeout=180, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            txt = rb.stdout.decode("utf-8", "replace")
            assert rb.returncode == 0 and "--dir-datos" in txt, (rb.returncode, txt[-2000:],
                                                                   rb.stderr[-2000:])
            assert not os.listdir(otro_cwd), os.listdir(otro_cwd)
        return {"copia": copia, "cambiados": cambiados, "generacion": en["generacion"]}
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_portabilidad_copia_en_otra_carpeta():
    r = comprobar_portabilidad()
    if isinstance(r, str):
        import pytest
        pytest.skip(r)


if __name__ == "__main__":
    t = time.time()
    r = comprobar_portabilidad(verbose="-v" in sys.argv)
    print("Portabilidad:", "OK" if isinstance(r, dict) else r, f"({time.time() - t:.1f} s)")
    if isinstance(r, dict):
        print("  copia:", r["copia"])
        print("  archivos escritos dentro de la copia:", ", ".join(r["cambiados"]))
        print("  generación continuada:", r["generacion"])
