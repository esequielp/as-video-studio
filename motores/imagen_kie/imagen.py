"""
Motor de imagen sobre kie.ai: el mismo contrato que `imagen_openai`, otro proveedor.

POR QUE EXISTE
--------------
En `imagen_openai` el 87 % de lo que cuesta un plano no es la imagen: son las
referencias (estilo, reparto, continuidad), que OpenAI cobra como tokens de
entrada. kie.ai revende modelos de imagen (Nano Banana, Seedream...) con TARIFA
PLANA POR IMAGEN, lleve una referencia o diez. Ese es todo el ahorro, y por eso
este motor existe al lado del otro y no en su lugar: el de OpenAI se queda como
esta y un proyecto elige cual usa (`motor_imagen` en los params de assets).

EL CONTRATO, QUE NO CAMBIA
--------------------------
`generar(prompt, referencias, quality=, tamano=)` devuelve `(png_bytes, meta)`,
igual que el de OpenAI, y `generar_lote`, `gasto`, `cargar_api_key`,
`cuentas_para_la_pantalla` y `SinSaldo` existen con la misma forma. Quien llama
(`pasos/p6_assets.py`) no tiene que saber que por dentro todo es distinto:

  1. ASINCRONO. kie.ai no devuelve la imagen: devuelve una TAREA. Se crea con
     `createTask`, se pregunta por ella con `recordInfo` hasta que acaba, y el
     resultado es una URL que hay que descargar. Aqui se espera por dentro.
  2. LAS REFERENCIAS VAN POR URL. No se adjuntan a la peticion: se suben antes a
     su almacen de ficheros (temporal) y se pasa la direccion. Como la lamina de
     estilo es la MISMA en todos los planos, cada subida se recuerda por el
     contenido del fichero y no se repite mientras la URL siga viva.
  3. MENOS REFERENCIAS. Cada modelo admite un maximo (`modelos.json`). Este
     motor NO recorta: si le llegan de mas, levanta. Quien sabe que papel tiene
     cada referencia --y por tanto cual sobra-- es p6, y el prompt las cita por
     posicion: recortar aqui dejaria el prompt hablando de una imagen que no va.

LO QUE NO ESTA VERIFICADO
-------------------------
Los nombres de los endpoints, de los modelos y de sus campos se escribieron sin
poder abrir docs.kie.ai. Viven en `modelos.json` (dato, no codigo) y en las
constantes de abajo, y cada uno se puede corregir sin tocar la logica. La prueba
contra la cuenta real es `herramientas/probar_kie.py`.

Uso suelto (una imagen, para probar):
    python imagen.py --prompt "..." --ref estilo.png --out prueba.png [--modelo X]
"""
import argparse
import hashlib
import io
import json
import os
import re
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(AQUI))

#: Los tres sitios a los que se habla. Se pueden mover por entorno por si kie.ai
#: los cambia antes de que alguien toque este fichero.
API = (os.environ.get("ESTUDIO_KIE_API") or "https://api.kie.ai").rstrip("/")
API_FICHEROS = (os.environ.get("ESTUDIO_KIE_FICHEROS")
                or "https://kieai.redpandaai.co").rstrip("/")
URL_CREAR = f"{API}/api/v1/jobs/createTask"
URL_CONSULTAR = f"{API}/api/v1/jobs/recordInfo"
URL_SALDO = f"{API}/api/v1/chat/credit"
URL_SUBIR = f"{API_FICHEROS}/api/file-stream-upload"

#: Los mismos nombres de tamano que el motor de OpenAI, y en `meta["tamano"]` se
#: devuelve el mismo texto: el medidor de coste y la cache de p6 lo leen asi.
TAMANOS = {"apaisado": "1536x1024", "cuadrado": "1024x1024", "vertical": "1024x1536"}
#: La proporcion EXACTA que espera el resto del Estudio para cada tamano. Un
#: modelo que no sabe dar 3:2 (Seedream da 4:3) se recorta al centro hasta ella,
#: sin reescalar: el render hace zoom leyendo pixeles reales, y cada pixel que
#: devuelve el modelo es un zoom mas limpio.
PROPORCIONES = {"apaisado": 3 / 2, "cuadrado": 1.0, "vertical": 2 / 3}

RUTA_MODELOS = os.path.join(AQUI, "modelos.json")
RUTA_TARIFAS = (os.environ.get("ESTUDIO_TARIFAS")
                or os.path.join(RAIZ_ESTUDIO, "tarifas.json"))

#: El almacen que escribe la pantalla de configuracion. Se lee por CONTRATO --una
#: ruta y una forma--, nunca importando `pasos/claves.py`: un motor no importa
#: codigo de la aplicacion (ver motores/README.md).
CARPETA_SECRETOS = os.environ.get("ESTUDIO_SECRETOS") or os.path.join(
    RAIZ_ESTUDIO, "secretos")
RUTA_CLAVES = os.path.join(CARPETA_SECRETOS, "claves.json")
RUTA_ENV = os.path.join(CARPETA_SECRETOS, ".env")

#: Donde se recuerdan las subidas. Fuera del repo y fuera de secretos/: son URLs
#: temporales, no secretos, y perderlas solo cuesta volver a subir.
RUTA_SUBIDAS = (os.environ.get("ESTUDIO_KIE_SUBIDAS")
                or os.path.join(tempfile.gettempdir(), "estudio_kie_subidas.json"))
#: Cuanto se reutiliza una URL subida. kie.ai borra los ficheros subidos a los
#: pocos dias; se usa bastante menos para no mandar nunca una URL ya muerta.
VIDA_SUBIDA_S = 36 * 3600

#: El ritmo de creacion de tareas: kie.ai limita las peticiones nuevas por
#: ventana de segundos. Se frena ANTES de chocar, como el cubo de OpenAI.
TAREAS_POR_VENTANA = int(os.environ.get("ESTUDIO_KIE_TAREAS_POR_VENTANA") or 15)
VENTANA_S = 10.0

#: Cuanto se espera por una tarea antes de darla por perdida, y cada cuanto se
#: pregunta. Una imagen tarda de 10 a 60 s; una cola saturada, bastante mas.
ESPERA_MAXIMA_S = float(os.environ.get("ESTUDIO_KIE_ESPERA_S") or 600)
CONSULTA_INICIAL_S = 2.0
CONSULTA_MAXIMA_S = 6.0
TIEMPO_PETICION_S = 60

ESTADOS_FIN = {"success": "ok", "fail": "fallo"}

_gasto = {"usd": 0.0, "llamadas": 0}
_LOCK_SUBIDAS = threading.Lock()
_SUBIDAS = {}
_SUBIDAS_CARGADAS = [False]
_CUBO = threading.Condition()
_CREADAS = deque()
_ESTADO_CUENTA = {"sin_saldo": False, "clave_rechazada": False, "clave": None}


class SinSaldo(RuntimeError):
    """La cuenta de kie.ai no tiene creditos: reintentar no lo arregla."""


class ErrorKie(RuntimeError):
    """kie.ai ha contestado con un error que no se arregla reintentando."""


# ------------------------------------------------------------------ los datos

def modelos():
    """La tabla de `modelos.json`. Se relee siempre: es pequena y se edita a mano."""
    with open(RUTA_MODELOS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def modelo_por_defecto():
    return modelos()["por_defecto"]


def ficha_modelo(modelo=None):
    """La ficha de un modelo, o un error que dice cuales hay."""
    tabla = modelos()
    nombre = modelo or tabla["por_defecto"]
    ficha = tabla["modelos"].get(nombre)
    if ficha is None:
        raise ValueError(f"modelo de kie.ai desconocido: {nombre!r}. Los que hay "
                         f"en {RUTA_MODELOS}: {', '.join(tabla['modelos'])}")
    return dict(ficha, id=nombre)


def max_referencias(modelo=None):
    """Cuantas imagenes de referencia admite ese modelo en una llamada."""
    return int(ficha_modelo(modelo)["max_referencias"])


def resolucion_de(modelo, quality):
    """La resolucion que se pide para esa calidad, o None si el modelo no la elige."""
    ficha = ficha_modelo(modelo)
    return (ficha.get("resoluciones") or {}).get(str(quality or "low"))


def _tarifas():
    try:
        with open(RUTA_TARIFAS, "r", encoding="utf-8-sig") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return {}
    return datos.get("kie") if isinstance(datos, dict) else {}


def precio(modelo=None, quality="low"):
    """USD de UNA imagen de ese modelo a esa calidad, de tarifas.json. None si no esta.

    El precio vive en tarifas.json y no aqui por lo mismo que el de OpenAI: es
    la unica tabla de precios del Estudio y se edita sin tocar codigo.
    """
    tabla = _tarifas() or {}
    por_credito = tabla.get("usd_por_credito")
    creditos = (tabla.get("creditos_por_imagen") or {}).get(modelo or modelo_por_defecto())
    if isinstance(creditos, dict):
        creditos = creditos.get(resolucion_de(modelo, quality) or "")
    try:
        return round(float(creditos) * float(por_credito), 6)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ la clave

def _del_almacen():
    try:
        with open(RUTA_CLAVES, "r", encoding="utf-8-sig") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return ""
    ficha = datos.get("kie") if isinstance(datos, dict) else None
    if isinstance(ficha, dict):
        return str(ficha.get("clave") or "").strip()
    if isinstance(ficha, str):
        return ficha.strip()
    return ""


def _del_env():
    if not os.path.exists(RUTA_ENV):
        return ""
    with open(RUTA_ENV, "r", encoding="utf-8-sig") as fh:
        for linea in fh:
            m = re.match(r"^KIE_API_KEY=(.*)$", linea.strip())
            if m and m.group(1).strip():
                return m.group(1).strip()
    return ""


def cargar_api_key():
    """La clave de kie.ai: entorno, almacen del Estudio o .env, por ese orden."""
    clave = (os.environ.get("KIE_API_KEY") or "").strip() or _del_almacen() or _del_env()
    if not clave:
        # SystemExit como el motor de OpenAI: p6 ya lo convierte en un error
        # legible ("el motor de imagen aborto: ...") y no se cuelga el paso
        raise SystemExit("Falta la clave de kie.ai: ponla en Configuracion > "
                         "Claves (o KIE_API_KEY en el entorno)")
    if clave != _ESTADO_CUENTA["clave"]:
        # una clave nueva entra limpia: lo que se aprendio era de la otra
        _ESTADO_CUENTA.update(clave=clave, sin_saldo=False, clave_rechazada=False)
    return clave


def _cabeceras(clave):
    return {"Authorization": f"Bearer {clave}"}


def cuentas_para_la_pantalla():
    """Como esta la cuenta AHORA, sin la clave. La misma forma que la de OpenAI."""
    try:
        clave = cargar_api_key()
    except SystemExit:
        return []
    return [{"nombre": "kie.ai", "etiqueta": "", "cola": f"…{clave[-4:]}",
             "sin_saldo": bool(_ESTADO_CUENTA["sin_saldo"]),
             "clave_rechazada": bool(_ESTADO_CUENTA["clave_rechazada"]),
             "limite_por_minuto": int(TAREAS_POR_VENTANA * 60 / VENTANA_S),
             "medido": False, "espera_s": 0.0}]


def saldo(api_key=None):
    """Los creditos que le quedan a la cuenta. Consultarlo no cuesta nada."""
    clave = api_key or cargar_api_key()
    r = requests.get(URL_SALDO, headers=_cabeceras(clave), timeout=TIEMPO_PETICION_S)
    cuerpo = _cuerpo(r)
    codigo = _codigo(r, cuerpo)
    if codigo != 200:
        raise ErrorKie(f"kie.ai no da el saldo ({codigo}): {_mensaje(r, cuerpo)}")
    return float(cuerpo.get("data") or 0.0)


# ------------------------------------------------------------ las respuestas
#
# kie.ai contesta casi siempre HTTP 200 y pone el resultado de verdad en el
# campo `code` del cuerpo. Se lee de los dos sitios: el que no sea 200 manda.

def _cuerpo(respuesta):
    try:
        datos = respuesta.json()
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _codigo(respuesta, cuerpo):
    if respuesta.status_code != 200:
        return respuesta.status_code
    try:
        return int(cuerpo.get("code", 200))
    except (TypeError, ValueError):
        return 200


def _mensaje(respuesta, cuerpo):
    return str(cuerpo.get("msg") or cuerpo.get("message")
               or (respuesta.text or "")[:200]).strip()


def _es_sin_saldo(codigo, mensaje):
    texto = mensaje.lower()
    return codigo == 402 or "insufficient" in texto or "credits" in texto and "not enough" in texto


# --------------------------------------------------------------- el freno

def _pedir_turno():
    """No se crean mas de TAREAS_POR_VENTANA tareas en VENTANA_S segundos."""
    while True:
        with _CUBO:
            ahora = time.monotonic()
            while _CREADAS and ahora - _CREADAS[0] >= VENTANA_S:
                _CREADAS.popleft()
            if len(_CREADAS) < TAREAS_POR_VENTANA:
                _CREADAS.append(ahora)
                return
            espera = VENTANA_S - (ahora - _CREADAS[0]) + 0.05
        time.sleep(max(0.05, espera))


# ------------------------------------------------------------ las subidas

def _cargar_subidas():
    if _SUBIDAS_CARGADAS[0]:
        return
    try:
        with open(RUTA_SUBIDAS, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        if isinstance(datos, dict):
            _SUBIDAS.update(datos)
    except (OSError, ValueError):
        pass
    _SUBIDAS_CARGADAS[0] = True


def _guardar_subidas():
    ahora = time.time()
    vivas = {k: v for k, v in _SUBIDAS.items()
             if ahora - float(v.get("t", 0)) < VIDA_SUBIDA_S}
    temporal = f"{RUTA_SUBIDAS}.{os.getpid()}.tmp"
    try:
        with open(temporal, "w", encoding="utf-8") as fh:
            json.dump(vivas, fh)
        os.replace(temporal, RUTA_SUBIDAS)
    except OSError:
        pass                    # perder el recuerdo solo cuesta volver a subir


def _huella(ruta):
    with open(ruta, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def subir(ruta, api_key=None):
    """La URL publica de un fichero local, subiendolo solo si hace falta.

    Se recuerda por el CONTENIDO (sha1 de los bytes) y no por la ruta: la lamina
    de estilo se regenera con el mismo nombre y otro dibujo, y la continuidad
    cambia de plano en plano con rutas que se repiten.
    """
    clave = api_key or cargar_api_key()
    huella = _huella(ruta)
    with _LOCK_SUBIDAS:
        _cargar_subidas()
        previa = _SUBIDAS.get(huella)
        if previa and time.time() - float(previa.get("t", 0)) < VIDA_SUBIDA_S:
            return previa["url"]
    ultimo = ""
    for intento in range(4):
        with open(ruta, "rb") as fh:
            r = requests.post(URL_SUBIR, headers=_cabeceras(clave),
                              data={"uploadPath": "estudio",
                                    "fileName": f"{huella[:16]}{os.path.splitext(ruta)[1] or '.png'}"},
                              files={"file": (os.path.basename(ruta), fh, "image/png")},
                              timeout=TIEMPO_PETICION_S)
        cuerpo = _cuerpo(r)
        codigo = _codigo(r, cuerpo)
        datos = cuerpo.get("data") if isinstance(cuerpo.get("data"), dict) else {}
        url = datos.get("downloadUrl") or datos.get("fileUrl") or datos.get("url")
        if codigo == 200 and url:
            with _LOCK_SUBIDAS:
                _SUBIDAS[huella] = {"url": url, "t": time.time()}
                _guardar_subidas()
            return url
        ultimo = f"{codigo}: {_mensaje(r, cuerpo)}"
        if codigo == 401:
            _ESTADO_CUENTA["clave_rechazada"] = True
            raise ErrorKie(f"kie.ai rechaza la clave al subir una referencia "
                           f"(401): revisala en Configuracion > Claves. {ultimo}")
        if codigo not in (429, 500, 502, 503, 504, 455):
            break
        time.sleep(2 * (intento + 1))
    raise ErrorKie(f"no se ha podido subir la referencia {os.path.basename(ruta)} "
                   f"a kie.ai: {ultimo}")


# ------------------------------------------------------------- la imagen

def _ajustar(crudo, tamano):
    """PNG con la proporcion exacta del tamano pedido, recortando al centro."""
    img = Image.open(io.BytesIO(crudo))
    img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
    objetivo = PROPORCIONES[tamano]
    ancho, alto = img.size
    actual = ancho / float(alto)
    if abs(actual - objetivo) > 0.01:
        if actual > objetivo:                       # sobra ancho
            nuevo = int(round(alto * objetivo))
            x = (ancho - nuevo) // 2
            img = img.crop((x, 0, x + nuevo, alto))
        else:                                       # sobra alto
            nuevo = int(round(ancho / objetivo))
            y = (alto - nuevo) // 2
            img = img.crop((0, y, ancho, y + nuevo))
    salida = io.BytesIO()
    img.save(salida, "PNG")
    return salida.getvalue()


def _entrada(ficha, prompt, urls, quality, tamano):
    """El bloque `input` de createTask para ese modelo, leido de su ficha."""
    entrada = {"prompt": prompt, ficha["campo_referencias"]: urls}
    if ficha.get("campo_proporcion"):
        entrada[ficha["campo_proporcion"]] = ficha["proporciones"][tamano]
    resolucion = (ficha.get("resoluciones") or {}).get(str(quality or "low"))
    if ficha.get("campo_resolucion") and resolucion:
        entrada[ficha["campo_resolucion"]] = resolucion
    entrada.update(ficha.get("fijos") or {})
    return entrada


def _crear_tarea(clave, ficha, entrada):
    """-> id de la tarea. Reintenta lo que se arregla esperando; el resto sube."""
    ultimo = ""
    for intento in range(6):
        _pedir_turno()
        r = requests.post(URL_CREAR, headers=_cabeceras(clave),
                          json={"model": ficha["id"], "input": entrada},
                          timeout=TIEMPO_PETICION_S)
        cuerpo = _cuerpo(r)
        codigo = _codigo(r, cuerpo)
        mensaje = _mensaje(r, cuerpo)
        datos = cuerpo.get("data") if isinstance(cuerpo.get("data"), dict) else {}
        if codigo == 200 and datos.get("taskId"):
            return datos["taskId"]
        ultimo = f"{codigo}: {mensaje}"
        if _es_sin_saldo(codigo, mensaje):
            _ESTADO_CUENTA["sin_saldo"] = True
            raise SinSaldo(
                "la cuenta de kie.ai se ha quedado sin creditos, asi que no se "
                "pueden generar mas imagenes. Recarga en https://kie.ai y retoma "
                "la generacion: lo ya generado NO se pierde ni se vuelve a pagar.")
        if codigo == 401:
            _ESTADO_CUENTA["clave_rechazada"] = True
            raise ErrorKie(f"kie.ai rechaza la clave (401): revisala en "
                           f"Configuracion > Claves. {mensaje}")
        if codigo == 429:
            time.sleep(min(10.0 * (intento + 1), 60.0))
            continue
        if codigo in (455, 500, 502, 503, 504):
            time.sleep(min(3.0 * (intento + 1), 30.0))
            continue
        break
    raise ErrorKie(f"kie.ai no ha aceptado la tarea ({ficha['id']}): {ultimo}")


def _esperar_tarea(clave, tarea):
    """Pregunta hasta que acaba. -> lista de URLs del resultado."""
    t0 = time.monotonic()
    pausa = CONSULTA_INICIAL_S
    while time.monotonic() - t0 < ESPERA_MAXIMA_S:
        time.sleep(pausa)
        pausa = min(CONSULTA_MAXIMA_S, pausa * 1.5)
        try:
            r = requests.get(URL_CONSULTAR, headers=_cabeceras(clave),
                             params={"taskId": tarea}, timeout=TIEMPO_PETICION_S)
        except requests.RequestException:
            continue                # un corte al PREGUNTAR no pierde la tarea
        cuerpo = _cuerpo(r)
        if _codigo(r, cuerpo) != 200:
            continue
        datos = cuerpo.get("data") if isinstance(cuerpo.get("data"), dict) else {}
        estado = ESTADOS_FIN.get(str(datos.get("state") or "").lower())
        if estado == "ok":
            resultado = datos.get("resultJson") or {}
            if isinstance(resultado, str):
                try:
                    resultado = json.loads(resultado)
                except ValueError:
                    resultado = {}
            urls = (resultado or {}).get("resultUrls") or []
            if not urls:
                raise ErrorKie(f"la tarea {tarea} acabo bien y no trae imagen")
            return urls
        if estado == "fallo":
            raise _FalloDeTarea(f"{datos.get('failCode') or ''} "
                                f"{datos.get('failMsg') or 'sin motivo'}".strip())
    raise ErrorKie(f"la tarea {tarea} de kie.ai no ha terminado en "
                   f"{ESPERA_MAXIMA_S:.0f} s. Retoma la generacion: lo ya hecho "
                   f"no se vuelve a pagar.")


class _FalloDeTarea(RuntimeError):
    """El modelo acepto la tarea y fallo al generarla. Se reintenta UNA vez."""


def _descargar(url):
    ultimo = None
    for intento in range(4):
        try:
            r = requests.get(url, timeout=TIEMPO_PETICION_S)
            if r.status_code == 200 and r.content:
                return r.content
            ultimo = f"HTTP {r.status_code}"
        except requests.RequestException as fallo:
            ultimo = str(fallo)
        time.sleep(2 * (intento + 1))
    raise ErrorKie(f"no se ha podido descargar la imagen de kie.ai: {ultimo}")


def generar(prompt, referencias, *, quality="low", tamano="apaisado",
            api_key=None, modelo=None):
    """Una imagen. -> (png_bytes, meta). El mismo contrato que imagen_openai.

    SIN referencias tambien se puede, a diferencia del de OpenAI: se llama al
    modelo de 'sin_referencias' de la ficha (texto a imagen), que es lo que
    necesitan las laminas de un estilo descrito. Se cobra con la tarifa del
    modelo de la ficha, que es el que eligio el proyecto.
    """
    referencias = list(referencias or [])
    faltan = [r for r in referencias if not os.path.exists(r)]
    if faltan:
        raise ValueError("estas imagenes de referencia no existen: "
                         + ", ".join(str(f) for f in faltan[:5]))
    if tamano not in TAMANOS:
        raise ValueError(f"tamano desconocido: {tamano!r} ({', '.join(TAMANOS)})")
    ficha = ficha_modelo(modelo)
    if len(referencias) > int(ficha["max_referencias"]):
        raise ValueError(
            f"{ficha['id']} admite {ficha['max_referencias']} referencias y "
            f"llegan {len(referencias)}. Las recorta quien sabe cual sobra "
            f"(p6_assets._referencias_para_el_motor), no el motor: el prompt las "
            f"cita por su posicion.")

    llamado = dict(ficha)
    if not referencias:
        if not ficha.get("sin_referencias"):
            raise ValueError(f"{ficha['id']} necesita al menos una imagen de "
                             f"referencia y su ficha no dice con que modelo "
                             f"dibujar sin ninguna ('sin_referencias')")
        llamado["id"] = ficha["sin_referencias"]

    clave = api_key or cargar_api_key()
    t0 = time.time()
    urls = [subir(ruta, clave) for ruta in referencias]
    entrada = _entrada(ficha, prompt, urls, quality, tamano)
    if not referencias:
        entrada.pop(ficha["campo_referencias"], None)

    fallo_previo = None
    for _ in range(2):
        tarea = _crear_tarea(clave, llamado, entrada)
        try:
            resultado = _esperar_tarea(clave, tarea)
            break
        except _FalloDeTarea as fallo:
            if fallo_previo is not None:
                raise ErrorKie(f"kie.ai no ha podido generar la imagen dos veces "
                               f"seguidas ({ficha['id']}): {fallo}. Si habla de "
                               f"contenido o moderacion, cambia el texto del "
                               f"plano.") from fallo
            fallo_previo = fallo
            print(f"[imagen kie] la tarea fallo ({fallo}); se intenta otra vez",
                  flush=True)
    png = _ajustar(_descargar(resultado[0]), tamano)
    coste = precio(ficha["id"], quality)
    _gasto["usd"] += coste or 0.0
    _gasto["llamadas"] += 1
    _ESTADO_CUENTA["sin_saldo"] = False
    return png, {"segundos": round(time.time() - t0, 1), "quality": quality,
                 "refs": len(referencias), "coste": coste or 0.0,
                 "modelo": ficha["id"], "modelo_llamado": llamado["id"],
                 "tamano": TAMANOS[tamano],
                 "resolucion": resolucion_de(ficha["id"], quality),
                 "proveedor": "kie", "tarea": tarea,
                 # sin tokens: kie.ai cobra por imagen. Se deja la clave para
                 # que quien lea `usage` no tenga que preguntar por el proveedor
                 "usage": {}}


def generar_lote(trabajos, *, concurrencia=4, modelo=None):
    """Como el de OpenAI: trabajos en paralelo, un fallo no tumba el lote."""
    def uno(trabajo):
        try:
            png, meta = generar(trabajo["prompt"], trabajo["referencias"],
                                quality=trabajo.get("quality", "low"),
                                tamano=trabajo.get("tamano", "apaisado"),
                                modelo=trabajo.get("modelo") or modelo)
        except Exception as exc:                            # noqa: BLE001
            return {"id": trabajo.get("id"), "error": str(exc)}
        os.makedirs(os.path.dirname(trabajo["destino"]), exist_ok=True)
        with open(trabajo["destino"], "wb") as fh:
            fh.write(png)
        return {"id": trabajo.get("id"), "destino": trabajo["destino"], **meta}

    with ThreadPoolExecutor(max_workers=concurrencia) as pool:
        return list(pool.map(uno, trabajos))


def gasto():
    return dict(_gasto, usd=round(_gasto["usd"], 4))


def main():
    parser = argparse.ArgumentParser(description="Una imagen con kie.ai")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--ref", action="append", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--modelo", default=None)
    parser.add_argument("--calidad", default="low")
    parser.add_argument("--tamano", default="apaisado", choices=sorted(TAMANOS))
    args = parser.parse_args()
    png, meta = generar(args.prompt, args.ref, quality=args.calidad,
                        tamano=args.tamano, modelo=args.modelo)
    with open(args.out, "wb") as fh:
        fh.write(png)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
