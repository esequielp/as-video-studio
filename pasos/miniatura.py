"""Las MINIATURAS del video: tres propuestas de 1280x720 para YouTube.

COMO SE HACEN
-------------
La IDEA sale de la ficha de publicacion (`publicacion.py`): una escena descrita
y tres textos cortos. La IMAGEN la genera el mismo motor que los planos del
video (kie.ai u OpenAI, `assets.motor_imagen`) con dos planos del propio video
como referencia, que es lo que hace que la miniatura se parezca al video que
promete: mismo dibujo, misma paleta, mismos personajes. El TEXTO se pone
despues, aqui, con una fuente de verdad: un generador de imagenes escribe letras
mal, y un texto torcido en una miniatura se lee como descuido.

Lo que se sigue de las guias de miniaturas de 2026: un sujeto dominante, dos o
tres colores con mucho contraste, y de tres a cuatro palabras como mucho, que
tienen que leerse al tamano al que se ve en un movil.

NO ES UN PASO DEL GRAFO, igual que la ficha: se pide a mano, cuesta tres
imagenes y no deja obsoleto nada. Queda en `miniaturas/` dentro del proyecto,
cada una con su version sin texto al lado por si se quiere rotular a mano.
"""
import json
import os
import time

from PIL import Image, ImageDraw

try:
    from . import comun, medios, p6_assets, publicacion, tipografia
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import comun
    import medios
    import p6_assets
    import publicacion
    import tipografia

CARPETA = "miniaturas"
INDICE = "miniaturas.json"
TAMANO = (1280, 720)
CUANTAS = 3
#: Mas calidad que los planos: es UNA imagen que decide si se pulsa el video.
CALIDAD = "medium"
MAX_REFERENCIAS = 2

PROMPT = (
    "A YouTube thumbnail, 16:9. {escena} {tipo}"
    "Match the drawing style, colour palette and characters of the reference "
    "images exactly: they are frames of the same video, and the thumbnail must "
    "show something the video really shows. One dominant subject, large in "
    "frame and readable at a very small size; two or three saturated colours "
    "with strong contrast, no large areas of mid grey; a simple, uncluttered "
    "background. Keep the left third of the frame calm and darker so a title "
    "can be written over it, and keep the bottom-right corner empty. "
    "Absolutely no text, letters, numbers or logos anywhere in the image.")

#: Lo que se le recalca al generador segun el tipo de concepto. Los tres existen
#: para la prueba A/B de YouTube: tres ideas distintas, no tres rotulos.
POR_TIPO = {
    "emocion": "Close-up: the character's face shows an exaggerated, readable "
               "emotion (surprise, fear or awe) that is obvious at thumbnail size. ",
    "curiosidad": "The subject is an intriguing object or detail that raises a "
                  "question without answering it. ",
    "momento": "A wider shot of the single most dramatic moment, frozen at its peak. ",
}


def leer(proyecto):
    """Las miniaturas hechas: {miniaturas: [{n, ruta, fondo, texto}], ...} o None."""
    ruta = proyecto.ruta(CARPETA, INDICE)
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def conceptos_de(proyecto):
    """Los conceptos de miniatura de la ficha guardada, limpios. -> [{tipo, escena, texto}]

    Pasan otra vez por `publicacion._miniatura_de` para que una ficha escrita
    antes del cambio (una escena y tres textos) siga valiendo sin reescribirla.
    """
    ficha = publicacion.leer(proyecto) or {}
    return publicacion._miniatura_de(ficha.get("miniatura")).get("conceptos") or []


def referencias_del_video(proyecto):
    """Hasta dos planos YA dibujados del video, en el orden del plan. -> [ruta]

    Los primeros del plan son los del gancho, que es de lo que suele ir la
    miniatura. Una cartela no vale de referencia: es texto sobre negro.
    """
    # EN LA VERSION Y EN LA CARPETA DE TRABAJO, como `_imagenes_ya_generadas`
    # de app.py: una pasada parcial de assets versiona los assets y deja los
    # planos en trabajo/, asi que mirar solo la version no encontraba ninguno
    carpetas = [os.path.join(proyecto.ruta_trabajo("assets", crear=False), "escenas")]
    version = proyecto.version_activa("assets")
    if version:
        carpetas.insert(0, os.path.join(proyecto.ruta_paso("assets", version), "escenas"))
    plan = p6_assets.plan_actual(proyecto, "assets") or {}
    rutas = []
    for escena in plan.get("escenas") or []:
        if escena.get("cartela"):
            continue
        ruta = next((os.path.join(c, f"{escena.get('id')}.png") for c in carpetas
                     if os.path.exists(os.path.join(c, f"{escena.get('id')}.png"))), None)
        if not ruta:
            continue
        rutas.append(ruta)
        if len(rutas) >= MAX_REFERENCIAS:
            break
    return rutas


def _recortar(png, tamano=TAMANO):
    """Bytes de una imagen -> Image de 1280x720, recortada al centro."""
    import io
    imagen = Image.open(io.BytesIO(png)).convert("RGB")
    objetivo = tamano[0] / float(tamano[1])
    ancho, alto = imagen.size
    if ancho / float(alto) > objetivo:
        nuevo = int(round(alto * objetivo))
        x = (ancho - nuevo) // 2
        imagen = imagen.crop((x, 0, x + nuevo, alto))
    else:
        nuevo = int(round(ancho / objetivo))
        y = (alto - nuevo) // 2
        imagen = imagen.crop((0, y, ancho, y + nuevo))
    return imagen.resize(tamano, Image.LANCZOS)


def _lineas(texto, fuente, ancho_max, dibujo):
    """Parte el texto en una o dos lineas que quepan en `ancho_max`."""
    palabras = texto.split()
    if len(palabras) <= 1:
        return [texto]
    mejor = None
    for corte in range(1, len(palabras)):
        uno, dos = " ".join(palabras[:corte]), " ".join(palabras[corte:])
        ancho = max(dibujo.textlength(uno, font=fuente), dibujo.textlength(dos, font=fuente))
        if mejor is None or ancho < mejor[0]:
            mejor = (ancho, [uno, dos])
    solo = dibujo.textlength(texto, font=fuente)
    return [texto] if solo <= ancho_max and len(palabras) <= 2 else mejor[1]


def _oscurecer_izquierda(imagen):
    """Un degradado negro sobre la mitad izquierda, fuerte al borde y nulo al medio.

    El texto tiene que leerse en un movil y en modo oscuro, sobre cualquier cosa
    que haya dibujado el generador: el borde negro de las letras ayuda, pero
    sobre un fondo con detalle no basta. El degradado no tapa el sujeto, que va
    en el centro o a la derecha.
    """
    ancho, alto = imagen.size
    mascara = Image.new("L", (ancho, alto), 0)
    tope = int(ancho * 0.55)
    # linear_gradient va de 0 (arriba) a 255 (abajo); girada un cuarto en el
    # sentido del reloj, va de 255 (izquierda) a 0 (derecha): fuerte en el
    # borde y nula al llegar al tope
    columnas = Image.linear_gradient("L").rotate(-90, expand=True).resize((tope, alto))
    columnas = columnas.point(lambda v: int(v * 0.62))
    mascara.paste(columnas, (0, 0))
    negro = Image.new("RGB", (ancho, alto), (0, 0, 0))
    return Image.composite(negro, imagen, mascara)


def rotular(imagen, texto):
    """El texto grande, blanco con borde negro, en el tercio izquierdo. -> Image"""
    imagen = imagen.copy()
    texto = " ".join(str(texto or "").upper().split())
    if not texto:
        return imagen
    imagen = _oscurecer_izquierda(imagen)
    dibujo = ImageDraw.Draw(imagen)
    ancho_max = int(imagen.width * 0.46)
    alto_max = int(imagen.height * 0.62)
    tam = 150
    while tam > 40:
        fuente = tipografia.fuente("arial", tam, negrita=True)
        lineas = _lineas(texto, fuente, ancho_max, dibujo)
        alto_linea = int(tam * 1.08)
        ancho = max(dibujo.textlength(l, font=fuente) for l in lineas)
        if ancho <= ancho_max and alto_linea * len(lineas) <= alto_max:
            break
        tam -= 6
    borde = max(4, tam // 14)
    x = int(imagen.width * 0.05)
    y = (imagen.height - alto_linea * len(lineas)) // 2
    for linea in lineas:
        dibujo.text((x, y), linea, font=fuente, fill=(255, 255, 255),
                    stroke_width=borde, stroke_fill=(0, 0, 0))
        y += alto_linea
    return imagen


def generar(proyecto, params_assets, avisar=None):
    """Las tres miniaturas del proyecto. -> el indice escrito

    Necesita la ficha de publicacion (la idea) y planos dibujados (el estilo).
    """
    avisar = avisar or (lambda *a, **k: None)
    conceptos = conceptos_de(proyecto)
    if not conceptos:
        raise RuntimeError("falta la idea de la miniatura: escribe (o reescribe) "
                           "antes la ficha de publicación")
    referencias = referencias_del_video(proyecto)
    if not referencias:
        raise RuntimeError("todavía no hay planos dibujados: la miniatura se hace "
                           "con el estilo de las imágenes del vídeo")
    carpeta = proyecto.ruta(CARPETA)
    os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(carpeta, "_refs")
    normalizar = medios.motor("imagen_openai/imagen.py").normalizar
    referencias = [normalizar(r, cache) for r in referencias]

    p = dict(params_assets or {})
    motor = p6_assets._motor_generador(p)
    extra = {"modelo": p6_assets._modelo_kie(p)} if p6_assets._usa_kie(p) else {}
    hechas, prompts, coste = [], [], 0.0
    sello = time.strftime("%Y%m%d_%H%M%S")
    for indice in range(CUANTAS):
        # UN CONCEPTO POR MINIATURA; si la ficha trae menos, se repiten --otra
        # tirada de la misma idea sigue siendo otra imagen--
        concepto = conceptos[indice % len(conceptos)]
        avisar(0.05 + 0.9 * indice / CUANTAS,
               f"miniatura {indice + 1} de {CUANTAS}")
        prompt = PROMPT.format(escena=concepto["escena"],
                               tipo=POR_TIPO.get(concepto.get("tipo"), ""))
        prompts.append(prompt)
        try:
            png, meta = motor.generar(prompt, referencias, quality=CALIDAD,
                                      tamano="apaisado", **extra)
        except SystemExit as fallo:
            raise RuntimeError(f"el motor de imagen aborto: {fallo}") from fallo
        fondo = _recortar(png)
        texto = concepto.get("texto") or ""
        nombre = f"{sello}_{indice + 1}"
        ruta_fondo = os.path.join(carpeta, f"fondo_{nombre}.png")
        ruta = os.path.join(carpeta, f"miniatura_{nombre}.jpg")
        fondo.save(ruta_fondo, "PNG")
        rotular(fondo, texto).save(ruta, "JPEG", quality=90, optimize=True)
        coste += float(meta.get("coste") or 0.0)
        hechas.append({"n": indice + 1, "texto": texto, "tipo": concepto.get("tipo"),
                       "ruta": os.path.relpath(ruta, proyecto.raiz).replace("\\", "/"),
                       "fondo": os.path.relpath(ruta_fondo, proyecto.raiz).replace("\\", "/")})
    indice_doc = {"miniaturas": hechas, "prompts": prompts, "coste_usd": round(coste, 4),
                  "motor": "kie" if extra else "openai", "fecha": sello}
    comun.escribir_json(proyecto.ruta(CARPETA, INDICE), indice_doc)
    avisar(1.0, f"{len(hechas)} miniaturas listas")
    return indice_doc
