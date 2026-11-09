import html
import math

URL_INSERTADO = "https://maps.google.com/maps?q={lat:.6f},{lon:.6f}&t={tipo}&z={zoom}&hl=es&ie=UTF8&iwloc=&output=embed"

PAGINA = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{{margin:0;height:100%;background:#0e1014;font-family:'Segoe UI',sans-serif;color:#e8ebf1}}
body{{display:flex;flex-direction:column}}
header{{display:flex;align-items:center;gap:10px;padding:9px 14px;background:#161920;border-bottom:1px solid #262b36}}
h1{{font:600 15px 'Segoe UI Semibold','Segoe UI',sans-serif;margin:0}}
small{{color:#8a93a6;font-size:12px}}
.esp{{flex:1}}
.seg{{display:flex;background:#262b36;padding:2px;gap:2px;border-radius:4px}}
button{{background:#1c2029;color:#8a93a6;border:0;padding:6px 13px;font:600 12px 'Segoe UI',sans-serif;cursor:pointer}}
button.sel{{background:#f5b400;color:#0e1014}}
button:hover:not(.sel){{color:#e8ebf1}}
iframe{{flex:1;border:0;width:100%;background:#0b0d10}}
</style></head><body>
<header><h1>{nombre}</h1><small>{lat:.6f}, {lon:.6f}</small><span class="esp"></span>
<div class="seg" id="tipos">
<button data-t="k" class="sel">Satélite</button><button data-t="h">Híbrido</button><button data-t="m">Mapa</button><button data-t="p">Relieve</button>
</div>
<div class="seg"><button id="menos">−</button><button id="mas">+</button></div>
</header>
<iframe id="mapa" src="{url}" allowfullscreen referrerpolicy="no-referrer-when-downgrade"></iframe>
<script>
var lat={lat:.6f}, lon={lon:.6f}, zoom={zoom}, tipo='k';
function poner(){{ document.getElementById('mapa').src='https://maps.google.com/maps?q='+lat+','+lon+'&t='+tipo+'&z='+zoom+'&hl=es&ie=UTF8&iwloc=&output=embed'; }}
document.querySelectorAll('#tipos button').forEach(function(b){{ b.onclick=function(){{
  document.querySelectorAll('#tipos button').forEach(function(x){{x.classList.remove('sel');}});
  b.classList.add('sel'); tipo=b.dataset.t; poner(); }}; }});
document.getElementById('mas').onclick=function(){{ zoom=Math.min(21,zoom+1); poner(); }};
document.getElementById('menos').onclick=function(){{ zoom=Math.max(3,zoom-1); poner(); }};
</script></body></html>"""


def zoom_para(ancho_m, lat):
    m_por_px = 156543.03 * math.cos(math.radians(lat))
    return int(max(3, min(20, math.floor(math.log2(m_por_px * 1000 / max(ancho_m, 100))))))


def abrir(lat, lon, nombre="Sitio", ancho_m=1600.0, captura=None):
    import webview
    zoom = zoom_para(ancho_m, lat)
    pagina = PAGINA.format(nombre=html.escape(nombre), lat=lat, lon=lon, zoom=zoom,
                           url=URL_INSERTADO.format(lat=lat, lon=lon, tipo="k", zoom=zoom))
    ventana = webview.create_window(f"Google Maps — {nombre}", html=pagina, width=1200, height=820, background_color="#0e1014")
    if captura:
        def tomar():
            import time
            from PIL import ImageGrab
            time.sleep(8)
            ImageGrab.grab().save(captura)
            ventana.destroy()
        webview.start(tomar)
    else:
        webview.start()
