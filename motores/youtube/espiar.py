r"""
Motor para ESTUDIAR vídeos de YouTube que ya funcionan: métricas y transcripción.

POR QUE EXISTE
--------------
Antes de escribir un guion vale más saber cómo lo hizo quien ya tiene diez
millones de visitas en ese mismo nicho. Esto baja los NUMEROS de un vídeo o un
canal, y su TRANSCRIPCION, para que `pasos/espiar.py` destile una receta: qué
promete en los primeros quince segundos, cada cuánto cambia de tema, cómo cierra.

Lo que NO hace, a propósito:

  - NO guarda el guion ajeno para reescribirlo. Quien llama destila una receta
    y tira el texto. Copiar un guion literal es contenido reutilizado para
    YouTube --causa de desmonetización-- y el canal es el activo.
  - NO estima ingresos. Eso lo hace `pasos/espiar.py` cruzando las visitas con
    la tabla de RPM por nicho de docs/NICHOS-Y-CPM.md, que son medianas leídas
    de YouTube Studio en 300 canales y no un número inventado.

LO QUE HAY QUE SABER ANTES DE TOCARLO
-------------------------------------
**YouTube LIMITA EL RITMO, y eso es el diseño entero de este fichero.** Medido
el 01-10-2026 contra el vídeo de 10 M de Ink Explainer:

  - El cliente `web` de yt-dlp devuelve «Sign in to confirm you're not a bot»;
    `ios` y `tv` devuelven «Requested format is not available». **Solo
    `android` pasa**, y por eso va fijo en CLIENTE y no es configurable: no es
    una preferencia, es el único que funciona.
  - Pedir cuatro cosas seguidas sin esperar devuelve HTTP 429. La transcripción
    es lo primero que cae.

De ahí las tres defensas, y ninguna es opcional:

  1. **ESPERA ENTRE PETICIONES** (`ESPERA_S`), contada contra el reloj de la
     última, no un sleep ciego: dos llamadas separadas por un minuto de trabajo
     no esperan nada.
  2. **REINTENTOS CON ESPERA CRECIENTE** ante 429, porque es un límite temporal
     y no un error: rendirse a la primera obliga a repetir todo el análisis.
  3. **CACHE EN DISCO** (`carpeta_cache`). Es la defensa de verdad: un vídeo
     que ya se miró no se vuelve a pedir NUNCA. Analizar diez vídeos de un
     canal y volver a abrirlos mañana son cero peticiones.

Y una cosa que no es defensa sino honestidad: **esto lee la web de YouTube, no
una API con contrato**. El día que cambien algo, se rompe. Por eso todo lo que
toca yt-dlp vive aquí dentro y quien llama solo ve `ficha()`, `buscar()` y
`transcripcion()`: cuando haya que arreglarlo, se arregla en un sitio.
"""

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

CARPETA_SECRETOS = os.environ.get("ESTUDIO_SECRETOS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "secretos")
RUTA_CLAVES = os.path.join(CARPETA_SECRETOS, "claves.json")
RUTA_ENV = os.path.join(CARPETA_SECRETOS, ".env")

API = "https://www.googleapis.com/youtube/v3"

#: Lo que cuesta cada llamada de la cuota diaria (10.000 unidades gratis).
#: BUSCAR ES CIEN VECES MAS CARO que consultar, y por eso en todas partes se
#: busca UNA vez y luego se piden los datos de todos los resultados DE GOLPE:
#: `videos.list` y `channels.list` admiten hasta 50 ids por llamada y cuestan 1.
COSTE_BUSCAR = 100
COSTE_CONSULTAR = 1
MAX_POR_LLAMADA = 50

#: El ÚNICO cliente de YouTube que responde (medido el 01-10-2026). Ver arriba.
CLIENTE = ["android"]

#: Segundos mínimos entre dos peticiones a YouTube. Cuatro seguidas sin esperar
#: dieron 429 en la medición; con esto no ha vuelto a salir.
ESPERA_S = 4.0

#: Cuántas veces se reintenta un 429 y cuánto se espera: 8 s, 16 s, 32 s. Pasado
#: eso no es un pico de ritmo, es un bloqueo, y conviene que se note.
REINTENTOS = 3
ESPERA_REINTENTO_S = 8.0

#: Idiomas de transcripción que se piden, en orden. El primero que exista gana.
IDIOMAS = ("es", "es-419", "es-ES", "en", "en-US", "en-GB")

_CANDADO = threading.Lock()
_ULTIMA = [0.0]


class ErrorYouTube(RuntimeError):
    """YouTube no ha querido contestar, y se dice por qué."""


# ------------------------------------------------------- la API oficial
#
# LA VIA BUENA, y la que se usa siempre que haya clave. yt-dlp lee la WEB de
# YouTube y por eso se bloquea (medido: tras unas pocas peticiones, «Sign in to
# confirm you're not a bot», sin recuperarse en 42 minutos). La Data API es
# oficial, no bloquea nada y da 10.000 unidades diarias gratis, que son 10.000
# videos consultados o 100 busquedas.
#
# La clave se saca habilitando «YouTube Data API v3» en el proyecto de Google
# Cloud. Si la API no esta habilitada, Google contesta un 401 que dice «API keys
# are not supported by this API» -- un mensaje que despista: no es que la clave
# este mal, es que a ese proyecto todavia no le han abierto esta puerta.

def _clave_del_almacen():
    try:
        with open(RUTA_CLAVES, "r", encoding="utf-8-sig") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return ""
    ficha = datos.get("youtube") if isinstance(datos, dict) else None
    if isinstance(ficha, dict):
        return str(ficha.get("clave") or "").strip()
    return ""


def _clave_del_env():
    if not os.path.exists(RUTA_ENV):
        return ""
    with open(RUTA_ENV, "r", encoding="utf-8-sig") as fh:
        for linea in fh:
            hallado = re.match(r"^YOUTUBE_API_KEY=(.*)$", linea.strip())
            if hallado and hallado.group(1).strip():
                return hallado.group(1).strip()
    return ""


def cargar_api_key():
    """La clave de la Data API: entorno, almacén o .env, por ese orden."""
    return ((os.environ.get("YOUTUBE_API_KEY") or "").strip()
            or _clave_del_almacen() or _clave_del_env())


def hay_api():
    """Si se puede ir por la via oficial. Sin esto se cae a yt-dlp."""
    return bool(cargar_api_key())


def _api(ruta, clave=None, **parametros):
    """Una llamada a la Data API. -> dict"""
    clave = clave or cargar_api_key()
    if not clave:
        raise ErrorYouTube(
            "Falta la clave de la YouTube Data API: ponla en Configuración > "
            "Claves (o YOUTUBE_API_KEY en secretos/.env). Se habilita en "
            "console.cloud.google.com > YouTube Data API v3.")
    parametros["key"] = clave
    url = f"{API}/{ruta}?" + urllib.parse.urlencode(parametros)
    try:
        with urllib.request.urlopen(url, timeout=60) as respuesta:
            return json.loads(respuesta.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as fallo:
        detalle = ""
        try:
            detalle = fallo.read().decode("utf-8", "replace")[:300]
        except Exception:                                   # noqa: BLE001
            pass
        if fallo.code == 403 and "quota" in detalle.lower():
            raise ErrorYouTube(
                "Se ha agotado la cuota diaria de la YouTube Data API (10.000 "
                "unidades). Una búsqueda cuesta 100 y consultar un vídeo 1; "
                "vuelve mañana.") from fallo
        if fallo.code == 401:
            raise ErrorYouTube(
                "La YouTube Data API no está habilitada en el proyecto de esa "
                "clave. Habilita «YouTube Data API v3» en "
                "console.cloud.google.com y la misma clave empezará a "
                f"funcionar. ({detalle[:120]})") from fallo
        raise ErrorYouTube(f"YouTube ha contestado {fallo.code}: {detalle}") from fallo
    except Exception as fallo:                              # noqa: BLE001
        raise ErrorYouTube(f"no se ha podido hablar con YouTube: {fallo}") from fallo


def _segundos_iso(texto):
    """La duración ISO-8601 de YouTube (`PT11M13S`) en segundos."""
    hallado = re.match(r"^P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$",
                       str(texto or ""))
    if not hallado:
        return None
    dias, horas, minutos, segundos = (int(g or 0) for g in hallado.groups())
    return dias * 86400 + horas * 3600 + minutos * 60 + segundos


def _entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _esperar_turno():
    """Deja pasar ESPERA_S desde la ÚLTIMA petición, no desde ahora.

    Contra el reloj y no con un sleep fijo: si entre dos llamadas han pasado
    treinta segundos haciendo otra cosa, no hay nada que esperar.
    """
    with _CANDADO:
        falta = ESPERA_S - (time.time() - _ULTIMA[0])
        if falta > 0:
            time.sleep(falta)
        _ULTIMA[0] = time.time()


def _es_limite(fallo):
    """Si el fallo es un límite de ritmo (reintentable) o algo peor."""
    texto = str(fallo).lower()
    return "429" in texto or "too many requests" in texto


def _yt(opciones):
    """Un YoutubeDL con el cliente que funciona y sin ruido en la salida."""
    import yt_dlp
    base = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extractor_args": {"youtube": {"player_client": CLIENTE}},
    }
    base.update(opciones or {})
    return yt_dlp.YoutubeDL(base)


def _pedir(url, opciones=None, descargar=False):
    """Una petición a YouTube, con su turno y sus reintentos. -> dict de info."""
    ultimo = None
    for intento in range(REINTENTOS):
        _esperar_turno()
        try:
            with _yt(opciones) as y:
                return y.extract_info(url, download=descargar)
        except Exception as fallo:                          # noqa: BLE001
            ultimo = fallo
            if not _es_limite(fallo) or intento == REINTENTOS - 1:
                break
            time.sleep(ESPERA_REINTENTO_S * (2 ** intento))
    if ultimo is not None and _es_limite(ultimo):
        raise ErrorYouTube(
            "YouTube está limitando el ritmo (HTTP 429). No es un fallo del "
            "Estudio ni de la URL: es que se le han pedido demasiadas cosas "
            "seguidas. Espera unos minutos y vuelve a intentarlo; lo que ya se "
            "analizó está en la caché y no se vuelve a pedir.") from ultimo
    raise ErrorYouTube(f"YouTube no ha contestado: {ultimo}") from ultimo


def id_de(url_o_id):
    """El id de once caracteres, venga como venga. -> str

    Acepta la URL larga, la corta, la de Shorts, la de embed y el id pelado,
    porque quien pega una URL la copia de donde la tenga.
    """
    texto = str(url_o_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", texto):
        return texto
    for patron in (r"[?&]v=([A-Za-z0-9_-]{11})",
                   r"youtu\.be/([A-Za-z0-9_-]{11})",
                   r"/shorts/([A-Za-z0-9_-]{11})",
                   r"/embed/([A-Za-z0-9_-]{11})",
                   r"/live/([A-Za-z0-9_-]{11})"):
        hallado = re.search(patron, texto)
        if hallado:
            return hallado.group(1)
    raise ErrorYouTube(f"no encuentro un id de vídeo de YouTube en {texto!r}")


# --------------------------------------------------------------------- caché

def _ruta_cache(carpeta, clave):
    return os.path.join(carpeta, f"{clave}.json")


def _leer_cache(carpeta, clave):
    if not carpeta:
        return None
    ruta = _ruta_cache(carpeta, clave)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                       # noqa: BLE001
        # una caché ilegible es como no tenerla: se vuelve a pedir y se pisa
        return None


def _escribir_cache(carpeta, clave, datos):
    if not carpeta:
        return
    os.makedirs(carpeta, exist_ok=True)
    tmp = _ruta_cache(carpeta, clave) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)
    os.replace(tmp, _ruta_cache(carpeta, clave))


# ------------------------------------------------------------------ métricas

def _ficha_desde_info(info):
    """Lo que nos interesa de la montaña de campos que devuelve yt-dlp."""
    return {
        "id": info.get("id"),
        "url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "titulo": info.get("title") or "",
        "descripcion": (info.get("description") or "")[:4000],
        "canal": info.get("channel") or info.get("uploader") or "",
        "canal_id": info.get("channel_id") or "",
        "canal_url": info.get("channel_url") or "",
        "suscriptores": info.get("channel_follower_count"),
        "visitas": info.get("view_count"),
        "likes": info.get("like_count"),
        "comentarios": info.get("comment_count"),
        "duracion_s": info.get("duration"),
        "fecha": info.get("upload_date") or "",
        "etiquetas": (info.get("tags") or [])[:30],
        "categoria": (info.get("categories") or [None])[0],
        "miniatura": info.get("thumbnail") or "",
        "idiomas_subtitulos": sorted(set(list(info.get("subtitles") or {})
                                         + list(info.get("automatic_captions") or {})))[:40],
        "subtitulos_propios": sorted(info.get("subtitles") or {}),
    }


def _ficha_desde_api(item):
    """Lo que nos interesa de lo que devuelve `videos.list`."""
    s = item.get("snippet") or {}
    e = item.get("statistics") or {}
    c = item.get("contentDetails") or {}
    minis = s.get("thumbnails") or {}
    mejor = (minis.get("maxres") or minis.get("standard")
             or minis.get("high") or minis.get("default") or {})
    return {
        "id": item.get("id"),
        "url": f"https://www.youtube.com/watch?v={item.get('id')}",
        "titulo": s.get("title") or "",
        "descripcion": (s.get("description") or "")[:4000],
        "canal": s.get("channelTitle") or "",
        "canal_id": s.get("channelId") or "",
        "canal_url": f"https://www.youtube.com/channel/{s.get('channelId')}"
                     if s.get("channelId") else "",
        "suscriptores": None,          # no viene aqui: es de `channels.list`
        "visitas": _entero(e.get("viewCount")),
        "likes": _entero(e.get("likeCount")),
        "comentarios": _entero(e.get("commentCount")),
        "duracion_s": _segundos_iso(c.get("duration")),
        "fecha": (s.get("publishedAt") or "")[:10].replace("-", ""),
        "etiquetas": (s.get("tags") or [])[:30],
        # La API da la categoria como NUMERO; `pasos/espiar` estima los ingresos
        # por el NOMBRE, asi que se traduce aqui y no alli: el que sabe de
        # YouTube es este fichero.
        "categoria": CATEGORIAS.get(str(s.get("categoryId") or "")),
        "miniatura": mejor.get("url") or "",
        "idiomas_subtitulos": [],
        "subtitulos_propios": [],
        "de": "api",
    }


#: Las categorias de YouTube por su numero. Solo las que pueden salir en un
#: video normal; las que no esten caen en `None` y la estimacion de ingresos usa
#: la mediana de toda la plataforma, que es lo honesto.
CATEGORIAS = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}


def ficha(url_o_id, carpeta_cache=None):
    """Los números de UN vídeo. -> dict

    POR LA API SI HAY CLAVE, y por yt-dlp si no. La API da datos en vivo y no
    se bloquea; yt-dlp da lo mismo pero leyendo la web, y acaba con la IP
    marcada. Medido el 01-10-2026 sobre el mismo vídeo: yt-dlp devolvió
    10.004.773 visitas y la API 10.057.760 unas horas después. La diferencia no
    es un fallo: es que una era de la caché de la web y la otra está viva.

    La caché se mira primero igual: para estudiar la ESTRUCTURA de un vídeo da
    lo mismo que las visitas sean las de ayer.
    """
    vid = id_de(url_o_id)
    guardado = _leer_cache(carpeta_cache, f"video_{vid}")
    if guardado:
        return guardado

    if hay_api():
        datos = _api("videos", part="snippet,statistics,contentDetails", id=vid)
        items = datos.get("items") or []
        if not items:
            raise ErrorYouTube(f"YouTube no conoce el vídeo {vid} (¿privado o borrado?)")
        ficha_video = _ficha_desde_api(items[0])
        # LOS SUSCRIPTORES SON DEL CANAL, y cuestan una unidad mas. Valen la
        # pena: `visitas / suscriptores` es lo que dice si a un video lo vio su
        # audiencia o lo empujo el algoritmo, que es lo que hay que aprender.
        if ficha_video.get("canal_id"):
            try:
                canales = _api("channels", part="statistics",
                               id=ficha_video["canal_id"]).get("items") or []
                if canales:
                    ficha_video["suscriptores"] = _entero(
                        (canales[0].get("statistics") or {}).get("subscriberCount"))
            except ErrorYouTube:
                pass        # sin suscriptores se vive; sin el video no
    else:
        info = _pedir(f"https://www.youtube.com/watch?v={vid}")
        ficha_video = _ficha_desde_info(info)
        ficha_video["de"] = "yt-dlp"

    _escribir_cache(carpeta_cache, f"video_{vid}", ficha_video)
    return ficha_video


def canales_del_nicho(consulta, cuantos=10, idioma="es", clave=None):
    """Los canales que mandan en un nicho, con sus números. -> [dict]

    ES LO QUE DE VERDAD DICE DONDE ESTAS PARADO, y por eso devuelve
    `vistas_por_video`: un canal con 142 vídeos y 322 millones de visitas hace
    2,3 millones por vídeo, y otro con 762 vídeos hace 228.000. Los dos salen
    en la misma búsqueda y no se parecen en nada. Mirar solo los suscriptores
    esconde eso.

    DOS LLAMADAS Y NO ONCE: `search` cuesta 100 unidades y se hace UNA vez;
    luego `channels.list` trae los números de los cincuenta de golpe por 1.
    """
    consulta = " ".join(str(consulta or "").split())
    if not consulta:
        raise ErrorYouTube("hace falta un nicho que buscar")
    cuantos = max(1, min(int(cuantos or 10), MAX_POR_LLAMADA))

    hallados = _api("search", clave=clave, part="snippet", q=consulta,
                    type="channel", maxResults=cuantos,
                    **({"relevanceLanguage": idioma} if idioma else {}))
    ids = [((i.get("snippet") or {}).get("channelId") or i.get("id", {}).get("channelId"))
           for i in hallados.get("items", [])]
    ids = [i for i in ids if i]
    if not ids:
        return []

    detalle = _api("channels", clave=clave, part="snippet,statistics",
                   id=",".join(ids))
    salida = []
    for c in detalle.get("items", []):
        s, e = c.get("snippet") or {}, c.get("statistics") or {}
        subs = _entero(e.get("subscriberCount")) or 0
        vistas = _entero(e.get("viewCount")) or 0
        videos = _entero(e.get("videoCount")) or 0
        salida.append({
            "id": c.get("id"),
            "canal": s.get("title") or "",
            "url": f"https://www.youtube.com/channel/{c.get('id')}",
            "descripcion": (s.get("description") or "")[:300],
            "miniatura": ((s.get("thumbnails") or {}).get("high")
                          or (s.get("thumbnails") or {}).get("default") or {}).get("url") or "",
            "pais": s.get("country") or "",
            "desde": (s.get("publishedAt") or "")[:10],
            "suscriptores": subs,
            "visitas": vistas,
            "videos": videos,
            "vistas_por_video": round(vistas / videos) if videos else None,
            "vistas_por_suscriptor": round(vistas / subs, 1) if subs else None,
        })
    salida.sort(key=lambda c: c.get("vistas_por_video") or 0, reverse=True)
    return salida


def buscar(consulta, cuantos=10, carpeta_cache=None):
    """Vídeos que responden a una búsqueda, con sus números. -> [dict]

    `extract_flat` a propósito: la búsqueda devuelve una ficha por vídeo SIN
    entrar en cada uno. Entrar sería una petición por resultado y el 429 llega
    enseguida; quien quiera el detalle de uno llama a `ficha()`.
    """
    consulta = " ".join(str(consulta or "").split())
    if not consulta:
        raise ErrorYouTube("hace falta algo que buscar")
    cuantos = max(1, min(int(cuantos or 10), 50))
    clave = "buscar_" + re.sub(r"[^a-z0-9]+", "_", consulta.lower())[:60] + f"_{cuantos}"
    guardado = _leer_cache(carpeta_cache, clave)
    if guardado:
        return guardado
    info = _pedir(f"ytsearch{cuantos}:{consulta}", {"extract_flat": True})
    salida = []
    for e in (info.get("entries") or []):
        if not e:
            continue
        salida.append({
            "id": e.get("id"),
            "url": f"https://www.youtube.com/watch?v={e.get('id')}",
            "titulo": e.get("title") or "",
            "canal": e.get("channel") or e.get("uploader") or "",
            "canal_id": e.get("channel_id") or "",
            "visitas": e.get("view_count"),
            "duracion_s": e.get("duration"),
            "miniatura": (e.get("thumbnails") or [{}])[-1].get("url") or "",
        })
    _escribir_cache(carpeta_cache, clave, salida)
    return salida


def canal(url_o_id, cuantos=30, carpeta_cache=None):
    """Los últimos vídeos de un canal, con sus visitas. -> dict

    Sirve para lo que de verdad importa de un canal: ver CUAL de sus vídeos se
    sale de su media. Un vídeo con diez veces las visitas del canal es donde
    está la lección, y eso no se ve mirando el vídeo solo.
    """
    pedido = str(url_o_id or "").strip()
    if not pedido:
        raise ErrorYouTube("hace falta un canal")
    if not pedido.startswith("http"):
        pedido = "https://www.youtube.com/" + pedido.lstrip("/")
    if not pedido.rstrip("/").endswith("/videos"):
        pedido = pedido.rstrip("/") + "/videos"
    cuantos = max(1, min(int(cuantos or 30), 100))
    clave = "canal_" + re.sub(r"[^a-z0-9]+", "_", pedido.lower())[-60:] + f"_{cuantos}"
    guardado = _leer_cache(carpeta_cache, clave)
    if guardado:
        return guardado

    info = _pedir(pedido, {"extract_flat": True, "playlistend": cuantos})
    videos = []
    for e in (info.get("entries") or [])[:cuantos]:
        if not e:
            continue
        videos.append({
            "id": e.get("id"),
            "url": f"https://www.youtube.com/watch?v={e.get('id')}",
            "titulo": e.get("title") or "",
            "visitas": e.get("view_count"),
            "duracion_s": e.get("duration"),
        })
    datos = {
        "canal": info.get("channel") or info.get("title") or "",
        "canal_id": info.get("channel_id") or "",
        "url": info.get("channel_url") or pedido,
        "suscriptores": info.get("channel_follower_count"),
        "videos": videos,
    }
    datos.update(_outliers(videos))
    _escribir_cache(carpeta_cache, clave, datos)
    return datos


def _outliers(videos):
    """Cuánto se sale cada vídeo de la MEDIANA del canal. -> dict

    Mediana y no media: un solo vídeo de diez millones sube la media de un canal
    pequeño hasta que todos los demás parecen fracasos. Con la mediana, el que
    se sale se sale de verdad.
    """
    vistas = sorted(v["visitas"] for v in videos if v.get("visitas"))
    if not vistas:
        return {"mediana_visitas": None, "mejores": []}
    mitad = len(vistas) // 2
    mediana = (vistas[mitad] if len(vistas) % 2
               else (vistas[mitad - 1] + vistas[mitad]) / 2)
    conteo = []
    for v in videos:
        if not v.get("visitas") or not mediana:
            continue
        conteo.append(dict(v, veces=round(v["visitas"] / mediana, 1)))
    conteo.sort(key=lambda v: v["veces"], reverse=True)
    return {"mediana_visitas": mediana, "mejores": conteo[:10]}


# ------------------------------------------------------------- transcripción

def transcripcion(url_o_id, idiomas=IDIOMAS, carpeta_cache=None):
    """Lo que se DICE en el vídeo, con tiempos. -> [{t_in, t_out, texto}]

    Ese es exactamente el formato que `p1_ingesta` documenta y que `p3_guion`
    sabe leer (`_transcript_legible` lo pinta como `[00:12] texto`), así que lo
    que sale de aquí entra en el Estudio sin traducir nada.

    Se prefiere el subtítulo ESCRITO por el canal sobre el automático: el
    automático no tiene puntuación y se come los nombres propios.
    """
    vid = id_de(url_o_id)
    guardado = _leer_cache(carpeta_cache, f"sub_{vid}")
    if guardado is not None:
        return guardado

    info = _pedir(f"https://www.youtube.com/watch?v={vid}")
    propios = info.get("subtitles") or {}
    automaticos = info.get("automatic_captions") or {}
    elegido = None
    for lengua in idiomas:
        if lengua in propios:
            elegido, origen = propios[lengua], "propio"
            break
    if elegido is None:
        for lengua in idiomas:
            if lengua in automaticos:
                elegido, origen = automaticos[lengua], "automatico"
                break
    if not elegido:
        raise ErrorYouTube(
            f"el vídeo {vid} no tiene subtítulos en ninguno de estos idiomas: "
            + ", ".join(idiomas))

    url = None
    for pista in elegido:
        if pista.get("ext") == "json3":
            url = pista.get("url")
            break
    if not url:
        url = (elegido[0] or {}).get("url")
    if not url:
        raise ErrorYouTube(f"el vídeo {vid} declara subtítulos pero sin dónde bajarlos")

    trozos = _bajar_json3(url)
    for t in trozos:
        t["origen"] = origen
    _escribir_cache(carpeta_cache, f"sub_{vid}", trozos)
    return trozos


def _bajar_json3(url):
    """El formato json3 de YouTube a la lista de trozos del Estudio."""
    import urllib.request
    _esperar_turno()
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            crudo = json.loads(respuesta.read().decode("utf-8", "replace"))
    except Exception as fallo:                              # noqa: BLE001
        if _es_limite(fallo):
            raise ErrorYouTube(
                "YouTube ha cortado la descarga del subtítulo por ritmo (429). "
                "Espera unos minutos: los vídeos ya analizados no se vuelven a "
                "pedir.") from fallo
        raise ErrorYouTube(f"no se ha podido bajar el subtítulo: {fallo}") from fallo

    trozos = []
    for evento in (crudo.get("events") or []):
        texto = "".join(s.get("utf8", "") for s in (evento.get("segs") or []))
        texto = " ".join(texto.split())
        if not texto:
            continue
        ini = (evento.get("tStartMs") or 0) / 1000.0
        dur = (evento.get("dDurationMs") or 0) / 1000.0
        trozos.append({"t_in": round(ini, 2),
                       "t_out": round(ini + dur, 2),
                       "texto": texto})
    return trozos


def texto_plano(trozos):
    """La transcripción como un texto corrido, para contar palabras y leerla."""
    return " ".join(t.get("texto", "") for t in trozos).strip()


#: Una línea de transcripción pegada de YouTube: el reloj delante y el texto
#: detrás, en la misma línea o en la siguiente. Acepta `1:23`, `01:23` y
#: `1:02:03`, que es lo que YouTube enseña según lo que dure el vídeo.
_RELOJ = re.compile(r"^\s*\[?((?:\d{1,2}:)?\d{1,2}:\d{2})\]?\s*(.*)$")


def _segundos_de(reloj):
    partes = [int(p) for p in reloj.split(":")]
    while len(partes) < 3:
        partes.insert(0, 0)
    return partes[0] * 3600 + partes[1] * 60 + partes[2]


def transcripcion_pegada(texto):
    """La transcripción que alguien copió de YouTube, a trozos. -> [{t_in,...}]

    ESTA VIA EXISTE PORQUE LA AUTOMATICA SE CAE. Medido el 01-10-2026: tras unas
    pocas peticiones YouTube pasa de `429` a «Sign in to confirm you're not a
    bot» y no se recupera esperando (42 minutos de esperas crecientes, sin
    suerte). Pelear eso con cookies del navegador pone en riesgo la cuenta de
    Google de quien las presta, y con proxies es una carrera que no se gana.

    Copiar la transcripción del propio YouTube --el botón «Mostrar
    transcripción» bajo el vídeo-- no infringe nada, no arriesga ninguna cuenta
    y no depende de que yt-dlp siga funcionando el mes que viene. Para analizar
    unos pocos vídeos de referencia es más que suficiente.

    Lee tanto «0:12 texto» en una línea como el reloj y el texto en líneas
    alternas, que es como lo suelta YouTube según desde dónde se copie.
    """
    lineas = [l.rstrip() for l in str(texto or "").splitlines()]
    trozos, pendiente = [], None
    for linea in lineas:
        if not linea.strip():
            continue
        hallado = _RELOJ.match(linea)
        if hallado:
            if pendiente is not None:
                # un reloj detrás de otro sin texto en medio: la línea anterior
                # se queda sin contenido y no vale la pena inventarle uno
                pendiente = None
            reloj, resto = hallado.group(1), hallado.group(2).strip()
            if resto:
                trozos.append({"t_in": float(_segundos_de(reloj)), "texto": resto})
            else:
                pendiente = _segundos_de(reloj)
            continue
        if pendiente is not None:
            trozos.append({"t_in": float(pendiente), "texto": linea.strip()})
            pendiente = None
        elif trozos:
            # continuación de la línea anterior: se pega, no se tira
            trozos[-1]["texto"] += " " + linea.strip()

    if not trozos:
        raise ErrorYouTube(
            "no encuentro marcas de tiempo en lo pegado. Copia la "
            "transcripción desde YouTube con el botón «Mostrar transcripción», "
            "que viene con el minuto delante de cada línea.")

    # EL t_out DE CADA TROZO ES EL t_in DEL SIGUIENTE. YouTube no lo da al
    # copiar, y ponerlo a cero rompería a quien lea duraciones aguas abajo.
    for i, t in enumerate(trozos):
        t["t_out"] = trozos[i + 1]["t_in"] if i + 1 < len(trozos) else t["t_in"] + 4.0
        t["t_in"] = round(t["t_in"], 2)
        t["t_out"] = round(t["t_out"], 2)
        t["origen"] = "pegado"
    return trozos
