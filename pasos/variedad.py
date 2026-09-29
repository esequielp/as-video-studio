"""La VARIEDAD entre los videos de un mismo canal.

QUE PROBLEMA RESUELVE
---------------------
YouTube no castiga que un video se haga con IA: castiga que un CANAL se vea
plantillado -- el mismo gancho, la misma estructura y la misma primera frase
video tras video (politica de «contenido inautentico», julio de 2025). Cada
video del Estudio sale bien por separado, y justo por eso el riesgo no se ve
mirando un video: se ve mirando diez seguidos. El redactor del guion no los ha
visto nunca: cada llamada al CLI es una sesion nueva.

Esto es la memoria que le falta, y tres cosas que se hacen con ella:

  1. RECORDAR. Cuando se escribe un guion se apunta que gancho y que estructura
     se le pidieron, su titulo y su primera frase. Por canal, que es el ESTILO
     del que salio el video (`config.estilo_light`).
  2. ELEGIR. El siguiente guion del mismo canal recibe el gancho y la estructura
     que MENOS se han usado ultimamente, y la lista de los ultimos titulos y
     primeras frases para no repetirlos.
  3. COMPROBAR. Una primera frase que se parece demasiado a la de otro video del
     canal es un motivo para pedir el guion otra vez, con la correccion dicha.

LO QUE NO HACE, a proposito
---------------------------
  - No toca ninguna FIRMA. La memoria no es un param del guion: si lo fuera,
    escribir un video dejaria obsoletos los guiones de todos los demas del
    canal. Entra en la instruccion (como el modelo del CLI), no en la huella.
  - No reescribe un guion que ya existe. Solo se usa en el PRIMER borrador (o al
    regenerar desde cero): sobre un guion ya escrito, cambiar el gancho seria
    rehacer la voz y las imagenes de un video que nadie pidio cambiar.
  - No sustituye a la persona. El angulo y el material los pone quien encarga
    el video, y eso es lo que YouTube llama perspectiva original.

DONDE VIVE
----------
En `_memoria_canal.json`, en la carpeta de los PROYECTOS (al lado de cada
proyecto, no dentro de ninguno). Asi es de la instalacion como lo son los
proyectos --en el servidor cada cuenta tiene la suya-- y una suite que trabaja
con proyectos de mentira en una carpeta temporal no escribe en la de verdad.
Un fichero suelto no es un proyecto: `Proyecto.listar` solo mira carpetas.
"""
import json
import os
import re
import threading
import unicodedata

NOMBRE_FICHERO = "_memoria_canal.json"

#: Cuantos videos se recuerdan por canal, y cuantos se le ensenan al redactor.
MAX_RECORDADOS = 40
EN_LA_INSTRUCCION = 8

#: A partir de que parecido dos primeras frases son «la misma». Jaccard sobre
#: las palabras con contenido: 0,6 es la misma frase con dos palabras cambiadas.
UMBRAL_PARECIDO = 0.6

#: Cuantas palabras puede tener la frase del gancho para decirse en ~3 s. A
#: 2,5 palabras por segundo (la cadencia medida del Estudio) son unas ocho; se
#: deja margen porque una frase corta y con pausa funciona igual.
PALABRAS_GANCHO = 14

_LOCK = threading.Lock()

# ---------------------------------------------------------------- los catalogos
#
# Son las dos decisiones que mas se notan cuando se repiten: como empieza el
# video y como avanza. Cada entrada es una instruccion que se puede obedecer,
# no una etiqueta: «gancho de pregunta» sin decir que pregunta no cambia nada.

GANCHOS = (
    {"id": "pregunta", "nombre": "Una pregunta que incomoda",
     "como": "Abre con UNA pregunta concreta que el espectador no sepa "
             "contestar y quiera saber. Nada de «¿te has preguntado alguna "
             "vez...?»: la pregunta tiene que salir de un hecho del material."},
    {"id": "dato", "nombre": "El dato que no cuadra",
     "como": "Abre con la cifra o el hecho del material que mas choca, dicho "
             "a pelo y sin adornos, y deja que la frase siguiente diga por que "
             "importa."},
    {"id": "contraintuitivo", "nombre": "Lo contrario de lo que crees",
     "como": "Abre afirmando algo que contradice lo que casi todo el mundo "
             "cree sobre este asunto, y que el material demuestra."},
    {"id": "escena", "nombre": "En mitad de la escena",
     "como": "Empieza DENTRO de un momento concreto del relato --un sitio, "
             "una hora, alguien haciendo algo-- sin explicar todavia de que va."},
    {"id": "final_primero", "nombre": "El final primero",
     "como": "Cuenta en una frase como acabo todo, y convierte el video en el "
             "como se llego hasta ahi."},
    {"id": "promesa", "nombre": "Una promesa concreta",
     "como": "Di en una frase que va a entender el espectador al terminar y "
             "que cambia para el. Concreto: nada de «todo lo que necesitas "
             "saber»."},
    {"id": "persona", "nombre": "Una persona",
     "como": "Abre con una persona concreta del material --con nombre si lo "
             "tiene-- y lo que hizo o lo que le paso."},
    {"id": "objeto", "nombre": "Un objeto",
     "como": "Abre describiendo un objeto, un documento o un lugar concreto "
             "que resume la historia, y tira del hilo desde ahi."},
)

ESTRUCTURAS = (
    {"id": "cronologica", "nombre": "Cronologica con una pregunta abierta",
     "como": "Los hechos en el orden en que pasaron, pero con una pregunta "
             "planteada al principio que no se contesta hasta el final."},
    {"id": "investigacion", "nombre": "Investigacion",
     "como": "Un misterio planteado al principio; cada parada aporta una pista "
             "y descarta una explicacion, hasta llegar a la respuesta."},
    {"id": "problema", "nombre": "Problema, causa, salida",
     "como": "Primero el problema y a quien afecta, despues por que pasa (la "
             "parte mas larga) y al final que se puede hacer o que se hizo."},
    {"id": "contraste", "nombre": "Dos lados",
     "como": "Dos versiones, dos personas o dos epocas enfrentadas; el video "
             "va alternando entre ellas y al final se decide o se explica la "
             "diferencia."},
    {"id": "escalada", "nombre": "De menos a mas",
     "como": "Paradas que suben de importancia, cada una mas grave o mas "
             "sorprendente que la anterior, y la mas fuerte al final."},
    {"id": "mito", "nombre": "Mito y realidad",
     "como": "Lo que se cree, por que se cree, y lo que de verdad dice el "
             "material, parada a parada."},
)

GANCHOS_POR_ID = {g["id"]: g for g in GANCHOS}
ESTRUCTURAS_POR_ID = {e["id"]: e for e in ESTRUCTURAS}


# ------------------------------------------------------------------ la memoria

def canal_de(proyecto):
    """El canal de un proyecto: el estilo del que salio. -> str

    Un proyecto hecho a mano en el editor no tiene estilo: cae en «general», que
    es un canal como otro cualquiera --mejor comparar con algo que con nada--.
    """
    config = getattr(proyecto, "config", None) or {}
    return str(config.get("estilo_light") or "general").strip() or "general"


def ruta_de(proyecto):
    """Donde vive la memoria: en la carpeta de los proyectos, al lado de este."""
    raiz = getattr(proyecto, "raiz", None)
    if not raiz:
        return None
    return os.path.join(os.path.dirname(os.path.abspath(raiz)), NOMBRE_FICHERO)


def _leer(ruta):
    if not ruta or not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _escribir(ruta, datos):
    temporal = f"{ruta}.{os.getpid()}.tmp"
    with open(temporal, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    os.replace(temporal, ruta)


def recordados(proyecto, excluir_propio=True):
    """Los ultimos videos del canal de este proyecto, del mas nuevo al mas viejo."""
    ruta = ruta_de(proyecto)
    lista = (_leer(ruta).get(canal_de(proyecto)) or [])
    propio = getattr(proyecto, "id", None)
    return [v for v in lista
            if isinstance(v, dict) and not (excluir_propio and v.get("proyecto") == propio)]


def registrar(proyecto, gancho, estructura, titulo, primera_frase):
    """Apunta el guion de este proyecto en la memoria de su canal. Nunca levanta.

    Se SUSTITUYE la entrada del proyecto si ya estaba: regenerar un guion no es
    un video mas del canal, es el mismo con otro texto.
    """
    ruta = ruta_de(proyecto)
    if not ruta:
        return False
    ficha = {"proyecto": getattr(proyecto, "id", None), "gancho": gancho,
             "estructura": estructura, "titulo": str(titulo or "")[:200],
             "primera_frase": str(primera_frase or "")[:400]}
    try:
        with _LOCK:
            datos = _leer(ruta)
            canal = canal_de(proyecto)
            lista = [v for v in (datos.get(canal) or [])
                     if isinstance(v, dict) and v.get("proyecto") != ficha["proyecto"]]
            datos[canal] = ([ficha] + lista)[:MAX_RECORDADOS]
            _escribir(ruta, datos)
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ la eleccion

def _menos_usado(catalogo, usados, semilla):
    """El id del catalogo usado hace mas tiempo (o nunca). Empates: por la semilla.

    `usados` va del mas reciente al mas viejo. Lo que no sale en la lista nunca
    se ha usado y gana; entre dos que nunca se usaron decide la semilla, que es
    el id del proyecto: el mismo proyecto recibe siempre lo mismo, y dos canales
    que empiezan a la vez no arrancan los dos por el primero del catalogo.
    """
    def antiguedad(entrada):
        try:
            return usados.index(entrada["id"])
        except ValueError:
            return len(usados) + 1
    desempate = sum(ord(c) for c in str(semilla or ""))
    ordenados = sorted(
        enumerate(catalogo),
        key=lambda par: (-antiguedad(par[1]),
                         (par[0] + desempate) % len(catalogo)))
    return ordenados[0][1]["id"]


def elegir(proyecto):
    """El gancho y la estructura para el guion de este proyecto. -> dict

    Si el proyecto ya tenia una eleccion apuntada, se respeta: un reintento o un
    «regenerar» no deben ir cambiando de gancho a cada pasada.
    """
    ruta = ruta_de(proyecto)
    previa = next((v for v in (_leer(ruta).get(canal_de(proyecto)) or [])
                   if isinstance(v, dict)
                   and v.get("proyecto") == getattr(proyecto, "id", None)), None)
    if previa and previa.get("gancho") in GANCHOS_POR_ID \
            and previa.get("estructura") in ESTRUCTURAS_POR_ID:
        return {"gancho": previa["gancho"], "estructura": previa["estructura"]}
    otros = recordados(proyecto)
    semilla = getattr(proyecto, "id", "")
    return {"gancho": _menos_usado(GANCHOS, [v.get("gancho") for v in otros], semilla),
            "estructura": _menos_usado(ESTRUCTURAS,
                                       [v.get("estructura") for v in otros], semilla)}


def bloque_para_guion(proyecto, eleccion):
    """La seccion de la instruccion del guion. -> texto, o '' si no hay nada."""
    gancho = GANCHOS_POR_ID.get((eleccion or {}).get("gancho"))
    estructura = ESTRUCTURAS_POR_ID.get((eleccion or {}).get("estructura"))
    if not gancho or not estructura:
        return ""
    lineas = [
        "== QUE ESTE VIDEO NO SE PAREZCA A LOS ANTERIORES DEL CANAL ==",
        "Este canal publica muchos videos, y si todos empiezan y avanzan igual "
        "se leen como una plantilla aunque cada uno este bien. Para ESTE video:",
        f"  - EL GANCHO: {gancho['nombre']}. {gancho['como']}",
        f"  - LA ESTRUCTURA: {estructura['nombre']}. {estructura['como']}",
        "  - El gancho se dice en unos tres segundos: su primera frase, corta. "
        "La explicacion viene despues.",
    ]
    otros = recordados(proyecto)[:EN_LA_INSTRUCCION]
    if otros:
        lineas.append("")
        lineas.append("Los ultimos videos del canal. NO repitas sus titulos, ni "
                      "su forma de empezar, ni sus primeras frases:")
        for video in otros:
            frase = " ".join(str(video.get("primera_frase") or "").split())
            lineas.append(f"  - «{video.get('titulo') or 'sin titulo'}»"
                          + (f" — empezaba: «{frase[:160]}»" if frase else ""))
    lineas.append("")
    lineas.append("Si el brief o la instruccion de esta iteracion piden otro "
                  "gancho u otra estructura, mandan ellos.")
    return "\n".join(lineas)


# ------------------------------------------------------------------ comprobar

def _palabras(texto):
    """Las palabras con contenido de un texto, sin tildes ni mayusculas."""
    limpio = unicodedata.normalize("NFKD", str(texto or "").lower())
    limpio = "".join(c for c in limpio if not unicodedata.combining(c))
    limpio = re.sub(r"<[^>]+>", " ", limpio)          # las anotaciones de voz
    return {p for p in re.findall(r"[a-z0-9]+", limpio) if len(p) > 2}


def parecido(a, b):
    """Jaccard entre las palabras con contenido de dos textos. -> 0..1"""
    uno, otro = _palabras(a), _palabras(b)
    if not uno or not otro:
        return 0.0
    return len(uno & otro) / float(len(uno | otro))


def primera_frase(texto):
    """La primera frase de un bloque, sin anotaciones de voz."""
    limpio = " ".join(re.sub(r"<[^>]+>", " ", str(texto or "")).split())
    corte = re.search(r"[.!?…](\s|$)", limpio)
    return limpio[:corte.end()].strip() if corte else limpio


def revisar(proyecto, titulo, frase):
    """Motivos para pedir el guion otra vez por parecerse a otro del canal. -> [str]"""
    motivos = []
    for video in recordados(proyecto)[:MAX_RECORDADOS]:
        previa = video.get("primera_frase") or ""
        if previa and parecido(frase, previa) >= UMBRAL_PARECIDO:
            motivos.append(
                f"la primera frase se parece demasiado a la del video "
                f"«{video.get('titulo') or 'anterior'}» del mismo canal "
                f"(«{previa[:120]}»). Escribe OTRO gancho, distinto en forma y en "
                f"palabras, y deja el resto del guion como esta")
            break
    for video in recordados(proyecto)[:MAX_RECORDADOS]:
        if titulo and parecido(titulo, video.get("titulo")) >= 0.8:
            motivos.append(
                f"el titulo es casi el mismo que el de «{video.get('titulo')}», "
                f"otro video del canal: pon otro titulo")
            break
    return motivos


def avisos(frase):
    """Lo que se le dice a la persona aunque el guion se de por bueno. -> [str]"""
    palabras = len(str(frase or "").split())
    if palabras > PALABRAS_GANCHO:
        return [f"la primera frase tiene {palabras} palabras: se tarda mas de tres "
                f"segundos en decirla, y el gancho de un video se juega ahi"]
    return []
