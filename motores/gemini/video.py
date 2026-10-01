r"""
Motor para LEER un vídeo de YouTube entero: imagen y audio, no solo subtítulos.

POR QUE EXISTE, Y POR QUE NO LO HACE yt-dlp
-------------------------------------------
Estudiar un vídeo que funciona por su transcripción deja fuera la mitad de la
lección. Medido el 01-10-2026 contra el vídeo de 10 M de Ink Explainer:

  - Por los SUBTITULOS, el gancho parecía «abre en segunda persona».
  - VIENDO el vídeo, el gancho es un montaje: despertador, ciudad agobiada,
    trabajo atado al reloj, dormir, salto de 50.000 años. Quince segundos sin
    decir de qué va el tema.

La segunda lección es la que sirve, y no está en el texto. Lo mismo con el
RITMO VISUAL: ese vídeo corta cada 3,3 segundos (18 por minuto) y eso no se
deduce de unos subtítulos por ningún lado.

Y hay un motivo práctico encima: desde una IP que YouTube ha marcado, yt-dlp
deja de bajar nada («Sign in to confirm you're not a bot») y no se recupera
esperando. Gemini no baja el vídeo: le pasa la URL a Google, que ya lo tiene.

LO QUE HAY QUE SABER
--------------------
  - **Una URL por llamada.** La API acepta un `file_data` con la URL de YouTube
    y el vídeo tiene que ser PUBLICO (o del dueño de la cuenta).
  - **La capa gratuita da para esto de sobra**: solo modelos Flash, ~1.500
    peticiones al día y 8 horas de vídeo de YouTube diarias. Un vídeo de once
    minutos gastó 61.158 tokens de entrada, todos de la modalidad VIDEO.
  - **Tarda.** Google procesa el vídeo entero: minutos, no segundos, para uno
    de diez minutos. Quien llame tiene que ir por un trabajo en segundo plano.
  - **El modelo por defecto es Flash a propósito** (`MODELO`): Pro dejó de estar
    en la capa gratuita en abril de 2026 y aquí no hace falta.

ESTE MOTOR NO GENERA VIDEO. Veo está en la misma API y con la misma clave, pero
no tiene capa gratuita (0,10-0,40 $ por segundo, o sea 0,80-3,20 $ por un clip
de ocho segundos frente a 0,05 $ de una imagen fija). Si algún día se usa, irá
en su propio motor y con su aviso de precio delante.
"""

import json
import os
import re
import urllib.error
import urllib.request

CARPETA_SECRETOS = os.environ.get("ESTUDIO_SECRETOS") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "secretos")
RUTA_CLAVES = os.path.join(CARPETA_SECRETOS, "claves.json")
RUTA_ENV = os.path.join(CARPETA_SECRETOS, ".env")

API = "https://generativelanguage.googleapis.com/v1beta/models"

#: Flash y no Pro: Pro salió de la capa gratuita en abril de 2026 y para leer un
#: vídeo y describir su estructura no aporta nada que justifique pagarlo.
MODELO = "gemini-3.8-flash"

#: Un vídeo de diez minutos tarda minutos en procesarse. El tope es generoso a
#: propósito: quedarse corto tira el trabajo cuando ya estaba casi.
TIEMPO_MAX_S = 600


class ErrorGemini(RuntimeError):
    """Gemini no ha contestado, y se dice por qué."""


def _del_almacen():
    try:
        with open(RUTA_CLAVES, "r", encoding="utf-8-sig") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return ""
    ficha = datos.get("gemini") if isinstance(datos, dict) else None
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
            hallado = re.match(r"^GEMINI_API_KEY=(.*)$", linea.strip())
            if hallado and hallado.group(1).strip():
                return hallado.group(1).strip()
    return ""


def cargar_api_key():
    """La clave de Gemini: entorno, almacén del Estudio o .env, por ese orden.

    El mismo orden que `imagen_kie`: el entorno manda para poder probar sin
    tocar nada, y el `.env` va al final porque es donde se pega a mano antes de
    que la pantalla la conozca.
    """
    return ((os.environ.get("GEMINI_API_KEY") or "").strip()
            or _del_almacen() or _del_env())


def hay_clave():
    """Si se puede usar este motor. Quien llama cae a otra vía si no."""
    return bool(cargar_api_key())


def _pedir(modelo, cuerpo, clave, tiempo_max_s=TIEMPO_MAX_S):
    peticion = urllib.request.Request(
        f"{API}/{modelo}:generateContent",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=tiempo_max_s) as respuesta:
            return json.loads(respuesta.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as fallo:
        detalle = ""
        try:
            detalle = fallo.read().decode("utf-8", "replace")[:400]
        except Exception:                                   # noqa: BLE001
            pass
        if fallo.code == 429:
            raise ErrorGemini(
                "Gemini ha agotado la cuota de hoy (429). La capa gratuita da "
                "unas 1.500 peticiones y 8 horas de vídeo al día; vuelve "
                "mañana o pon facturación en el proyecto de Google.") from fallo
        if fallo.code in (401, 403):
            raise ErrorGemini(
                f"Gemini ha rechazado la clave ({fallo.code}). Compruébala en "
                f"Configuración > Claves. {detalle}") from fallo
        raise ErrorGemini(f"Gemini ha contestado {fallo.code}: {detalle}") from fallo
    except Exception as fallo:                              # noqa: BLE001
        raise ErrorGemini(f"no se ha podido hablar con Gemini: {fallo}") from fallo


def _texto_de(respuesta):
    """El texto de la respuesta, o un error que diga por qué no lo hay."""
    candidatos = respuesta.get("candidates") or []
    if not candidatos:
        # SIN CANDIDATOS SUELE SER UN FILTRO, y el motivo viene aparte: decirlo
        # ahorra buscar un fallo de red que no existe.
        motivo = ((respuesta.get("promptFeedback") or {}).get("blockReason")
                  or "sin motivo declarado")
        raise ErrorGemini(f"Gemini no ha devuelto nada ({motivo})")
    partes = ((candidatos[0].get("content") or {}).get("parts") or [])
    texto = "".join(p.get("text", "") for p in partes).strip()
    if not texto:
        razon = candidatos[0].get("finishReason") or "?"
        raise ErrorGemini(f"Gemini ha devuelto una respuesta vacía ({razon})")
    return texto


def _json_de(texto):
    """El objeto JSON que venga dentro del texto, con o sin ```json alrededor."""
    texto = str(texto or "").strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        raise ErrorGemini("Gemini no ha devuelto un objeto JSON")
    try:
        return json.loads(texto[inicio:fin + 1])
    except ValueError as fallo:
        raise ErrorGemini(f"el JSON de Gemini no se puede leer: {fallo}") from fallo


INSTRUCCION = """Mira este vídeo de YouTube ENTERO y devuelve cómo está hecho.

Eres un analista de formatos. NO resumas el contenido ni copies frases: describe
DECISIONES, que es lo que otro canal de otro tema puede aprovechar.

Mira sobre todo dos cosas que solo se ven VIENDO el vídeo:

- QUE SE VE en los primeros quince segundos, plano a plano, antes de que se diga
  de qué va el tema. Si es un montaje, descríbelo en orden.
- CADA CUANTO cambia el plano, y si ese ritmo es igual todo el vídeo o cambia
  entre el principio y el final. TODO en SEGUNDOS POR PLANO salvo
  `cortes_por_minuto`, que va en cortes: no mezcles las dos unidades.

DEVUELVE EXACTAMENTE ESTE JSON, en español, sin nada alrededor:
{"gancho_visual": {"planos": ["lo que se ve, en orden"], "segundos": 0,
 "dice_el_tema_en_s": 0},
 "gancho_hablado": {"que_dice": "la primera frase", "promete": "...",
 "cumple_en_s": 0, "cumple": true},
 "ritmo_visual": {"cortes_por_minuto": 0, "segundos_por_plano": 0,
 "segundos_por_plano_al_principio": 0, "segundos_por_plano_al_final": 0,
 "cambia_el_ritmo": true},
 "estructura": [{"desde_s": 0, "funcion": "plantear|contexto|girar|resolver|relanzar",
 "que_hace": "..."}],
 "recursos_visuales": ["lo que usa para sostener la atención sin hablar"],
 "reenganches": [{"en_s": 0, "recurso": "...", "como": "..."}],
 "cierre": {"como_termina": "...", "deja_abierto": true, "pide": "..."},
 "trasladable": ["tres o cuatro decisiones copiables sin copiar nada de este vídeo"],
 "para_el_guion": "un párrafo de instrucciones para quien va a redactar OTRO vídeo de OTRO tema"}"""


def analizar(url, modelo=MODELO, instruccion=INSTRUCCION, clave=None,
             tiempo_max_s=TIEMPO_MAX_S):
    """Cómo está hecho ese vídeo de YouTube. -> (dict, meta)

    Devuelve también `meta` con los tokens gastados: son de la modalidad VIDEO y
    es lo que consume la cuota diaria, así que conviene poder mirarlo.
    """
    clave = clave or cargar_api_key()
    if not clave:
        raise ErrorGemini(
            "Falta la clave de Gemini: ponla en Configuración > Claves (o "
            "GEMINI_API_KEY en secretos/.env). Se saca gratis en "
            "aistudio.google.com/apikey")
    url = str(url or "").strip()
    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={url}"

    cuerpo = {"contents": [{"parts": [
        {"file_data": {"file_uri": url}},
        {"text": instruccion},
    ]}]}
    respuesta = _pedir(modelo, cuerpo, clave, tiempo_max_s)
    datos = _json_de(_texto_de(respuesta))
    uso = respuesta.get("usageMetadata") or {}
    meta = {
        "modelo": modelo,
        "tokens_entrada": uso.get("promptTokenCount"),
        "tokens_salida": uso.get("candidatesTokenCount"),
        "tokens_video": next(
            (d.get("tokenCount") for d in (uso.get("promptTokensDetails") or [])
             if d.get("modality") == "VIDEO"), None),
    }
    return datos, meta
