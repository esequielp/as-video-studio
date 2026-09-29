"""La FICHA DE PUBLICACION: lo que hace falta para subir el video a YouTube.

Titulo (tres para elegir), descripcion, capitulos, etiquetas y hashtags, en el
idioma del video, y un recordatorio de lo que YouTube pide declarar. Se escribe
en `publicacion.json` y `publicacion.txt` en la carpeta del proyecto, al lado de
todo lo demas, y se lee desde la pantalla del video.

NO ES UN PASO DEL GRAFO, y no lo sera: no produce nada de lo que dependa otro
paso, y meterlo en el grafo obligaria a una migracion (ver CLAUDE.md, «El grafo,
y por que no se toca»). Es una tarea suelta que lee lo que ya existe.

LOS CAPITULOS SALEN DEL PROPIO VIDEO, no del modelo. Las secciones del guion
(`abre_seccion`) son las paradas del relato, y la voz ya dice en que segundo
empieza cada bloque (`audio_meta.json`): el minuto de cada capitulo es un
hecho. Al modelo solo se le pide el NOMBRE de cada uno. Si el CLI falla, la
ficha sale igual, con capitulos nombrados por su primera frase.

YouTube exige para los capitulos: el primero en 0:00, al menos tres, y cada uno
de diez segundos como minimo. Lo que no cumple eso se junta o no se pone.
"""
import json
import os
import re

try:
    from . import cli_claude, comun, marcas_tts
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun
    import marcas_tts

NOMBRE_JSON = "publicacion.json"
NOMBRE_TXT = "publicacion.txt"

MIN_CAPITULOS = 3
MIN_SEGUNDOS_CAPITULO = 10.0
MAX_TITULO = 70
MAX_ETIQUETAS = 15

MODELO = "sonnet"
ESFUERZO = "low"
TIEMPO_BASE_S = 240

SISTEMA = ("Responde exclusivamente con el objeto JSON pedido, sin texto "
           "alrededor, sin vallas de markdown y sin usar herramientas.")

#: Lo que YouTube pide declarar al subir, dicho en cristiano. No se puede marcar
#: desde aqui (se marca en YouTube Studio), asi que va en la ficha para no
#: olvidarlo.
AVISO_SINTETICO = (
    "Al subir: en «Contenido alterado o sintético», marca SÍ si el vídeo tiene "
    "personas, lugares o sucesos que parecen reales y no lo son, o una voz que "
    "imita a una persona real. Un estilo claramente ilustrado con voz de "
    "narrador no suele necesitarlo.")


def _reloj(segundos):
    # HACIA ABAJO y no al mas cercano: un capitulo que arranca en 1:16 cuando la
    # voz empieza en 1:15,5 se come media palabra; en 1:15 entra con aire
    segundos = int(max(0.0, float(segundos)))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}:{minutos:02d}:{segundos:02d}" if horas else f"{minutos}:{segundos:02d}"


def _primera_frase(texto, maximo=60):
    limpio = " ".join(marcas_tts.limpiar(str(texto or "")).split())
    corte = re.search(r"[.!?…](\s|$)", limpio)
    frase = limpio[:corte.start() + 1] if corte else limpio
    return frase if len(frase) <= maximo else frase[:maximo - 1].rsplit(" ", 1)[0] + "…"


def capitulos(guion, meta_voz):
    """Los capitulos con su minuto REAL. -> [{id, t, texto}] o [] si no llegan.

    `guion` es guion.json y `meta_voz` el audio_meta.json de la voz. Cada seccion
    del guion abre un capitulo en el segundo en que la voz empieza su bloque.
    """
    tiempos = {b.get("id"): b.get("t_in") for b in (meta_voz or {}).get("bloques") or []
               if isinstance(b, dict)}
    salida = []
    for bloque in (guion or {}).get("guion") or []:
        if not bloque.get("abre_seccion"):
            continue
        t = tiempos.get(bloque.get("id"))
        if t is None:
            continue
        salida.append({"id": bloque["id"], "t": float(t),
                       "texto": marcas_tts.limpiar(bloque.get("texto") or "")})
    if not salida:
        return []
    salida[0]["t"] = 0.0                     # YouTube: el primero en 0:00
    # un capitulo de menos de diez segundos se junta con el anterior
    juntos = [salida[0]]
    for capitulo in salida[1:]:
        if capitulo["t"] - juntos[-1]["t"] < MIN_SEGUNDOS_CAPITULO:
            continue
        juntos.append(capitulo)
    return juntos if len(juntos) >= MIN_CAPITULOS else []


def _instruccion(titulo, idioma, bloques, caps):
    texto = "\n".join(f"{b['id']}: {marcas_tts.limpiar(b.get('texto') or '')}"
                      for b in bloques)
    lista = "\n".join(f"  - {c['id']} (empieza en {_reloj(c['t'])}): "
                      f"{_primera_frase(c['texto'], 160)}" for c in caps)
    return "\n".join([
        "Vas a preparar la ficha de YouTube de un video documental ya terminado.",
        f"Titulo de trabajo: {titulo}",
        f"Idioma del video (escribe TODO en este idioma): {idioma}",
        "",
        "== EL GUION LOCUTADO ==",
        texto,
        "",
        "== LOS CAPITULOS (ya decididos; solo hay que nombrarlos) ==",
        lista or "  (este video no lleva capitulos)",
        "",
        "== LO QUE HAY QUE ENTREGAR ==",
        f"  - titulos: TRES titulos distintos, de {MAX_TITULO} caracteres como "
        "mucho, que prometan lo que el video cuenta de verdad. Nada de "
        "mayusculas enteras, ni clickbait que el video no cumpla.",
        "  - descripcion: dos o tres parrafos cortos. El primero, lo que va a "
        "entender quien lo vea (es lo que sale en la busqueda). Sin enlaces "
        "inventados y sin pedir que se suscriban.",
        "  - capitulos: un nombre corto (dos a seis palabras) para CADA id de "
        "la lista de arriba, en el mismo orden.",
        f"  - etiquetas: hasta {MAX_ETIQUETAS} busquedas con las que alguien "
        "encontraria este video.",
        "  - hashtags: tres, sin espacios.",
        "",
        "Responde UNICAMENTE con un objeto JSON con esta forma:",
        '{"titulos": ["...", "...", "..."], "descripcion": "...", '
        '"capitulos": [{"id": "B001", "titulo": "..."}], '
        '"etiquetas": ["..."], "hashtags": ["#..."]}',
    ])


def _llamar_claude(instruccion, cwd, avance=None):
    """Se llama asi para que el medidor de coste pueda engancharla por nombre."""
    return cli_claude.ejecutar(
        instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
        tiempo_max_s=0, base_tiempo_s=TIEMPO_BASE_S, sistema=SISTEMA,
        avance=avance, para="la ficha de publicacion")


def _json_de(texto):
    texto = str(texto or "").strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        raise ValueError("la respuesta no trae un objeto JSON")
    return json.loads(texto[inicio:fin + 1])


def _limpia(lista, maximo, largo=None):
    salida = []
    for valor in lista if isinstance(lista, list) else []:
        valor = " ".join(str(valor or "").split())
        if largo and len(valor) > largo:
            valor = valor[:largo].rsplit(" ", 1)[0]
        if valor and valor not in salida:
            salida.append(valor)
    return salida[:maximo]


def componer(titulo, caps, datos=None):
    """La ficha, con lo que haya dado el modelo o sin nada. Nunca levanta."""
    datos = datos if isinstance(datos, dict) else {}
    nombres = {str(c.get("id")): " ".join(str(c.get("titulo") or "").split())
               for c in (datos.get("capitulos") or []) if isinstance(c, dict)}
    return {
        "titulos": _limpia(datos.get("titulos"), 3, MAX_TITULO) or [titulo],
        "descripcion": str(datos.get("descripcion") or "").strip(),
        "capitulos": [{"t": c["t"], "reloj": _reloj(c["t"]),
                       "titulo": nombres.get(c["id"]) or _primera_frase(c["texto"])}
                      for c in caps],
        "etiquetas": _limpia(datos.get("etiquetas"), MAX_ETIQUETAS, 60),
        "hashtags": [h if h.startswith("#") else f"#{h}"
                     for h in _limpia(datos.get("hashtags"), 3)
                     if " " not in h],
        "aviso_sintetico": AVISO_SINTETICO,
        "del_modelo": bool(datos),
    }


def texto_de(ficha):
    """La ficha como se pega en YouTube Studio."""
    partes = ["TÍTULO (elige uno):"]
    partes += [f"  {i}. {t}" for i, t in enumerate(ficha["titulos"], start=1)]
    partes += ["", "DESCRIPCIÓN:", ficha["descripcion"] or "(escríbela tú)"]
    if ficha["capitulos"]:
        partes += ["", "CAPÍTULOS (van dentro de la descripción):"]
        partes += [f"{c['reloj']} {c['titulo']}" for c in ficha["capitulos"]]
    if ficha["hashtags"]:
        partes += ["", " ".join(ficha["hashtags"])]
    if ficha["etiquetas"]:
        partes += ["", "ETIQUETAS:", ", ".join(ficha["etiquetas"])]
    partes += ["", "ANTES DE PUBLICAR:", ficha["aviso_sintetico"]]
    return "\n".join(partes) + "\n"


def leer(proyecto):
    """La ficha guardada, o None."""
    ruta = proyecto.ruta(NOMBRE_JSON)
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def generar(proyecto, avisar=None):
    """Escribe la ficha de publicacion del proyecto. -> la ficha

    Necesita el guion; la voz es opcional (sin ella no hay capitulos). El CLI se
    llama UNA vez; si falla, la ficha sale igual con lo que se sabe sin el.
    """
    avisar = avisar or (lambda *a, **k: None)
    guion = comun.leer_salida(proyecto, "guion", "guion.json", obligatorio=False)
    if not guion or not guion.get("guion"):
        raise RuntimeError("no hay guion todavía: la ficha se escribe a partir de él")
    meta_voz = comun.leer_salida(proyecto, "voz", "audio_meta.json",
                                 obligatorio=False) or {}
    titulo = str(guion.get("titulo") or "").strip() or "Sin título"
    caps = capitulos(guion, meta_voz)

    avisar(0.1, "escribiendo el título, la descripción y los capítulos")
    datos, fallo = None, ""
    try:
        texto, _sobre = _llamar_claude(
            _instruccion(titulo, guion.get("idioma") or "es", guion["guion"], caps),
            proyecto.raiz)
        datos = _json_de(texto)
    except Exception as error:                              # noqa: BLE001
        fallo = f"{type(error).__name__}: {error}"
    ficha = componer(titulo, caps, datos)
    if fallo:
        ficha["aviso"] = (f"el modelo no ha contestado ({fallo[:200]}): la ficha "
                          f"lleva solo lo que se sabe sin él")
    comun.escribir_json(proyecto.ruta(NOMBRE_JSON), ficha)
    comun.escribir_texto(proyecto.ruta(NOMBRE_TXT), texto_de(ficha))
    avisar(1.0, "ficha de publicación lista")
    return ficha
