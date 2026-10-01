r"""ESTUDIAR un vídeo que ya funciona, y quedarse con la RECETA.

Se le pega la URL de un vídeo que lo está petando en tu nicho y devuelve dos
cosas: sus NUMEROS (con una estimación de lo que gana, y de dónde sale esa
estimación) y su RECETA — qué promete en los primeros quince segundos, cada
cuánto cambia de tema, dónde vuelve a enganchar, cómo cierra.

Esa receta se puede inyectar en `guion.prompt_general` del vídeo que estés
escribiendo, y ahí está todo el valor: una herramienta de espionaje te dice QUE
funciona; esto lo mete en el sitio donde se escribe tu guion.

NO SE GUARDA EL GUION AJENO, Y ES UNA DECISION, NO UN DESCUIDO
---------------------------------------------------------------
La transcripción se lee, se destila y se tira. No se guarda en la receta ni en
el banco. Dos motivos, y el segundo pesa más que el primero:

  1. Copiar un guion literal es CONTENIDO REUTILIZADO para YouTube, que es causa
     de desmonetización. El canal es el activo.
  2. Un guion ajeno pegado en el prompt sale como un guion ajeno reescrito. Lo
     que se aprende de un vídeo que funciona no son sus frases: es su ESQUELETO.
     Guardar el esqueleto y tirar la carne da mejores guiones, no solo más
     seguros.

NO ES UN PASO DEL GRAFO
-----------------------
Como `publicacion.py` y `miniatura.py`: no produce nada de lo que dependa otro
paso. Vive en el banco y se inyecta en los params del guion cuando alguien lo
pide. Meterlo en el grafo sería una migración (ver CLAUDE.md).

DE DONDE SALE LA ESTIMACION DE INGRESOS
---------------------------------------
De multiplicar las visitas por el RPM MEDIANO del nicho, con la banda P25-P75 al
lado. Los RPM son los de `docs/NICHOS-Y-CPM.md`: medianas leídas de YouTube
Studio en 300 canales reales, no estimaciones de un tercero.

**Nadie sabe lo que gana un canal ajeno**, y cualquiera que dé un número exacto
se lo está inventando. Por eso aquí se da una banda y se dice de dónde sale.
"""
import json
import os
import re

try:
    from . import cli_claude, comun
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun

MODELO = "opus"
ESFUERZO = "high"
TIEMPO_BASE_S = 180.0

#: Cuánta transcripción se le da al modelo. Un vídeo de veinte minutos son unas
#: 3.000 palabras; esto deja sitio de sobra y corta los directos de dos horas,
#: donde además la estructura ya no es la de un vídeo escrito.
MAX_CARACTERES = 60000

#: RPM mediano por nicho y su banda P25-P75, de docs/NICHOS-Y-CPM.md (AIR
#: Media-Tech: 300 canales, 3.595 meses-canal monetizados, mayo 2025-mayo 2026,
#: leídos de YouTube Studio). La clave es la CATEGORIA que devuelve YouTube.
#:
#: Las categorías de YouTube no son las del estudio, así que varias caen en el
#: mismo sitio: «Science & Technology» y «Education» son ambas educación, que es
#: el nicho que mejor paga con diferencia.
RPM_POR_CATEGORIA = {
    "Education":              (10.22, 2.31, 19.50),
    "Science & Technology":   (10.22, 2.31, 19.50),
    "Nonprofits & Activism":  (2.60, 1.79, 3.62),
    "Autos & Vehicles":       (5.69, 3.17, 9.81),
    "Travel & Events":        (2.98, 1.77, 5.24),
    "News & Politics":        (2.60, 1.79, 3.62),
    "Entertainment":          (2.43, 0.88, 5.02),
    "Film & Animation":       (2.43, 0.88, 5.02),
    "Comedy":                 (2.43, 0.88, 5.02),
    "Howto & Style":          (2.39, 1.00, 3.90),
    "Music":                  (2.28, 1.35, 4.16),
    "Gaming":                 (2.05, 0.70, 3.62),
    "People & Blogs":         (2.98, 1.77, 5.24),
    "Sports":                 (1.23, 0.72, 1.53),
    "Pets & Animals":         (2.43, 0.88, 5.02),
}

#: Lo que se usa cuando YouTube no dice la categoría: la mediana de TODA la
#: plataforma, que el mismo estudio cifra en 2,30 $.
RPM_SIN_CATEGORIA = (2.30, 0.70, 5.17)


def estimar_ingresos(visitas, categoria):
    """Lo que ESE vídeo habrá dado, en una banda y con su procedencia. -> dict

    Devuelve también `aviso` porque el número sin el aviso engaña: la diferencia
    entre el suelo y el techo de un nicho es de ocho veces, y quien lea solo la
    cifra de en medio creerá que sabe algo que nadie sabe.
    """
    if not visitas:
        return {"estimado": None, "aviso": "sin visitas no hay nada que estimar"}
    mediano, bajo, alto = RPM_POR_CATEGORIA.get(categoria, RPM_SIN_CATEGORIA)
    miles = float(visitas) / 1000.0
    conocida = categoria in RPM_POR_CATEGORIA
    return {
        "categoria": categoria or "(sin categoría)",
        "rpm_mediano": mediano,
        "rpm_p25": bajo,
        "rpm_p75": alto,
        "usd_mediano": round(miles * mediano, 2),
        "usd_bajo": round(miles * bajo, 2),
        "usd_alto": round(miles * alto, 2),
        "fuente": ("RPM medianos de AIR Media-Tech: 300 canales y 3.595 "
                   "meses-canal leídos de YouTube Studio (may-2025 a may-2026). "
                   "Ver docs/NICHOS-Y-CPM.md."),
        "aviso": (
            "Es una ESTIMACION y la banda es ancha a propósito. Lo que gana un "
            "canal ajeno no lo publica nadie: esto es visitas x el RPM mediano "
            "de su nicho. Dentro de un mismo nicho los mejores ganan de tres a "
            "ocho veces más que los peores, así que la cifra de en medio dice "
            "poco por sí sola. Y falta el factor que más mueve el RPM y que no "
            "se puede saber desde fuera: DE DONDE ES LA AUDIENCIA. El mismo "
            "vídeo visto desde Estados Unidos o desde India no paga parecido, "
            "y eso solo lo ve el dueño del canal en su Studio."
            + ("" if conocida else
               " Además, YouTube no ha dicho la categoría de este vídeo, así "
               "que se ha usado la mediana de toda la plataforma.")),
    }


def _reloj(segundos):
    segundos = int(segundos or 0)
    return f"{segundos // 60:02d}:{segundos % 60:02d}"


def _transcript_legible(trozos, maximo=MAX_CARACTERES):
    """La transcripción con marcas de tiempo, recortada si no cabe.

    Con los tiempos delante, y no como texto corrido: la pregunta que se le hace
    al modelo es CUANDO pasan las cosas, y sin el reloj no puede contestarla.
    """
    lineas = [f"[{_reloj(t.get('t_in', 0))}] {t.get('texto', '')}" for t in trozos]
    texto = "\n".join(lineas)
    if len(texto) <= maximo:
        return texto
    return texto[:maximo] + "\n[...transcripción recortada por longitud...]"


SISTEMA = (
    "Eres un analista de formatos de YouTube. Lees la transcripción de un vídeo "
    "que ha funcionado y devuelves su ESQUELETO, nunca su contenido. No copias "
    "frases: describes decisiones."
)


def _instruccion(ficha, trozos):
    duracion = ficha.get("duracion_s") or 0
    return "\n".join([
        "Analiza este vídeo de YouTube y devuelve su RECETA de formato.",
        "",
        f"TITULO: {ficha.get('titulo', '')}",
        f"CANAL: {ficha.get('canal', '')} ({ficha.get('suscriptores') or '?'} suscriptores)",
        f"DURACION: {_reloj(duracion)}",
        f"VISITAS: {ficha.get('visitas')}",
        "",
        "TRANSCRIPCION CON TIEMPOS",
        "<<<",
        _transcript_legible(trozos),
        ">>>",
        "",
        "LO QUE TIENES QUE DEVOLVER, y cómo mirarlo:",
        "",
        "- El GANCHO: qué dice en los primeros 15 segundos, qué PROMETE al "
        "espectador y en qué segundo cumple esa promesa. Si no la cumple, dilo.",
        "- La ESTRUCTURA: los bloques del vídeo con el minuto en que empieza "
        "cada uno y qué hace cada bloque (plantear, dar contexto, girar, "
        "resolver). No resumas el contenido: di qué FUNCION cumple.",
        "- El RITMO: cada cuántos segundos cambia de tema, cuánto dura una "
        "frase de media, si acelera o frena y dónde.",
        "- Los RE-ENGANCHES: en qué minutos vuelve a picar la curiosidad y con "
        "qué recurso (una pregunta, una promesa nueva, un dato que choca).",
        "- El CIERRE: cómo termina, si deja algo abierto, si pide algo.",
        "- Lo TRASLADABLE: tres o cuatro decisiones concretas que otro canal de "
        "otro tema podría copiar sin copiar nada de este vídeo.",
        "",
        "NO devuelvas frases textuales del vídeo más allá de la del gancho. "
        "Lo que vale es la decisión, no la redacción.",
        "",
        "DEVUELVE EXACTAMENTE ESTE JSON, sin nada alrededor:",
        '{"gancho": {"que_dice": "...", "promete": "...", "cumple_en_s": 0, '
        '"cumple": true}, '
        '"estructura": [{"desde_s": 0, "funcion": "...", "que_hace": "..."}], '
        '"ritmo": {"segundos_por_tema": 0, "palabras_por_frase": 0, '
        '"donde_acelera": "...", "donde_frena": "..."}, '
        '"reenganches": [{"en_s": 0, "recurso": "...", "como": "..."}], '
        '"cierre": {"como_termina": "...", "deja_abierto": true, "pide": "..."}, '
        '"trasladable": ["...", "..."], '
        '"para_el_guion": "un párrafo de instrucciones, escrito para quien va a '
        'redactar OTRO vídeo de OTRO tema, con lo que este formato hace bien"}',
    ])


def _llamar_claude(instruccion, cwd, avance=None):
    """Se llama asi para que el medidor de coste pueda engancharla por nombre."""
    return cli_claude.ejecutar(
        instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
        tiempo_max_s=0, base_tiempo_s=TIEMPO_BASE_S, sistema=SISTEMA,
        avance=avance, para="la receta de un video de referencia")


def _json_de(texto):
    texto = str(texto or "").strip()
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fin <= inicio:
        raise ValueError("la respuesta no trae un objeto JSON")
    return json.loads(texto[inicio:fin + 1])


def estudiar(ficha, trozos, cwd=None, avisar=None, receta_gemini=None):
    """Los números y la receta de un vídeo de referencia. -> dict

    `ficha` y `trozos` vienen de `motores/youtube/espiar.py`. Aquí no se sale a
    la red: esto solo piensa.

    `receta_gemini` ES LA BUENA CUANDO LA HAY. Gemini ha VISTO el vídeo, así que
    trae lo que una transcripción no puede traer: qué se ve en los primeros
    quince segundos y cada cuánto cambia el plano. Medido contra el vídeo de
    10 M de Ink Explainer: por los subtítulos el gancho parecía «abre en segunda
    persona»; viéndolo, son doce planos de montaje y el tema no se menciona
    hasta el segundo 27. El CLI sobre la transcripción se queda de respaldo para
    cuando no hay clave de Gemini.
    """
    palabras = len((" ".join(t.get("texto", "") for t in trozos)).split())
    duracion = ficha.get("duracion_s") or 0

    receta = {}
    error = None
    if receta_gemini:
        receta = receta_gemini
    else:
        try:
            # `cli_claude.ejecutar` devuelve (texto, sobre): el sobre trae el
            # session_id y el gasto, y aqui solo interesa el texto.
            texto, _sobre = _llamar_claude(_instruccion(ficha, trozos), cwd,
                                           avance=avisar)
            receta = _json_de(texto)
        except Exception as fallo:                          # noqa: BLE001
            # SIN RECETA SE DEVUELVEN LOS NUMEROS IGUAL. Las métricas ya han
            # costado su espera a YouTube; perderlas porque el CLI tuvo un mal
            # rato sería obligar a volver a pedirlas y arriesgar otro 429.
            error = f"{type(fallo).__name__}: {fallo}"

    return {
        "video": {k: ficha.get(k) for k in
                  ("id", "url", "titulo", "canal", "canal_url", "suscriptores",
                   "visitas", "likes", "comentarios", "duracion_s", "fecha",
                   "categoria", "miniatura")},
        "medidas": {
            "palabras": palabras,
            "palabras_por_minuto": round(palabras / (duracion / 60), 1) if duracion else None,
            "ratio_likes": (round(100.0 * ficha["likes"] / ficha["visitas"], 2)
                            if ficha.get("likes") and ficha.get("visitas") else None),
            "ratio_comentarios": (round(100.0 * ficha["comentarios"] / ficha["visitas"], 3)
                                  if ficha.get("comentarios") and ficha.get("visitas") else None),
            "visitas_por_suscriptor": (round(ficha["visitas"] / ficha["suscriptores"], 1)
                                       if ficha.get("visitas") and ficha.get("suscriptores") else None),
        },
        "ingresos": estimar_ingresos(ficha.get("visitas"), ficha.get("categoria")),
        "receta": receta,
        # DE DONDE SALE LA RECETA, porque no valen lo mismo: la de Gemini ha
        # visto el video y trae el ritmo visual; la del CLI solo ha leido lo
        # que se dice. Quien mire el estudio dentro de un mes tiene que poder
        # saber cual esta leyendo.
        "receta_de": "gemini" if receta_gemini else ("cli" if receta else None),
        "error_receta": error,
    }


def para_el_guion(estudio):
    """La receta como un párrafo listo para `guion.prompt_general`. -> str

    Es lo ÚNICO que viaja al proyecto. Ni la transcripción ni el título ajeno:
    instrucciones de formato, que es lo que se puede usar sin copiar a nadie.
    """
    receta = (estudio or {}).get("receta") or {}
    suelto = str(receta.get("para_el_guion") or "").strip()
    if suelto:
        return suelto
    trozos = [str(t).strip() for t in (receta.get("trasladable") or []) if str(t).strip()]
    return (" ".join(trozos) if trozos else "")
