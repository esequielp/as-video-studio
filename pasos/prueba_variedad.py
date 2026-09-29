"""
Prueba de la variedad entre videos de un canal y de la ficha de publicacion.

No llama a ningun modelo. Lo que se comprueba es lo que se puede romper sin que
nada lo diga:

  - que dos videos seguidos del mismo canal no reciban el mismo gancho ni la
    misma estructura, y que un mismo video reciba siempre lo mismo
  - que la memoria viva al lado de los proyectos y no en el repo
  - que una primera frase copiada de otro video del canal sea un motivo para
    pedir el guion otra vez
  - que la memoria NO entre en la firma del guion
  - que los capitulos de la ficha cumplan lo que exige YouTube (0:00, tres,
    diez segundos) y salgan del minuto real de la voz

    python pasos/prueba_variedad.py
"""
import os
import shutil
import sys
import tempfile

TEMPORAL = tempfile.mkdtemp(prefix="estudio_prueba_variedad_")
os.environ.setdefault("ESTUDIO_SECRETOS", os.path.join(TEMPORAL, "secretos"))

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)

import publicacion  # noqa: E402
import variedad  # noqa: E402
from nucleo.proyecto import Proyecto  # noqa: E402

FALLOS = []


def comprobar(condicion, texto):
    if condicion:
        print(f"  ok   {texto}")
    else:
        print(f"  FALLO {texto}")
        FALLOS.append(texto)


def igual(obtenido, esperado, texto):
    comprobar(obtenido == esperado,
              texto if obtenido == esperado
              else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def seccion(titulo):
    print(f"\n[{titulo}]")


def proyecto(nombre, canal="canal_prueba"):
    nuevo = Proyecto.crear(os.path.join(TEMPORAL, "proyectos"), nombre)
    nuevo.config["estilo_light"] = canal
    return nuevo


def prueba_eleccion():
    seccion("cada video del canal recibe otro gancho y otra estructura")
    uno = proyecto("video uno")
    eleccion = variedad.elegir(uno)
    comprobar(eleccion["gancho"] in variedad.GANCHOS_POR_ID
              and eleccion["estructura"] in variedad.ESTRUCTURAS_POR_ID,
              f"el primero recibe un gancho y una estructura del catalogo: {eleccion}")
    igual(variedad.elegir(uno), eleccion, "y el mismo proyecto recibe siempre lo mismo")
    variedad.registrar(uno, eleccion["gancho"], eleccion["estructura"],
                       "El puerto que desaparecio", "Nadie sabe donde esta el puerto.")
    ruta = variedad.ruta_de(uno)
    igual(os.path.dirname(ruta), os.path.dirname(uno.raiz),
          "la memoria vive en la carpeta de los proyectos, no en el repo")
    comprobar(os.path.exists(ruta), "y se ha escrito")
    igual(variedad.elegir(uno), eleccion,
          "despues de apuntarlo, el proyecto sigue recibiendo lo suyo (un reintento no cambia de gancho)")

    vistos_g, vistos_e = [eleccion["gancho"]], [eleccion["estructura"]]
    for indice in range(2, 7):
        otro = proyecto(f"video {indice}")
        suya = variedad.elegir(otro)
        comprobar(suya["gancho"] not in vistos_g,
                  f"el video {indice} no repite gancho ({suya['gancho']} no esta en {vistos_g})")
        comprobar(suya["estructura"] not in vistos_e[-(len(variedad.ESTRUCTURAS) - 1):],
                  f"ni estructura mientras queden sin usar ({suya['estructura']})")
        variedad.registrar(otro, suya["gancho"], suya["estructura"],
                           f"Titulo {indice}", f"Primera frase del video {indice}.")
        vistos_g.append(suya["gancho"])
        vistos_e.append(suya["estructura"])

    seccion("otro canal no se entera")
    ajeno = proyecto("video de otro canal", canal="otro_canal")
    igual(variedad.recordados(ajeno), [], "la memoria es POR CANAL")

    seccion("la seccion de la instruccion")
    nuevo = proyecto("video nuevo")
    texto = variedad.bloque_para_guion(nuevo, variedad.elegir(nuevo))
    comprobar("El puerto que desaparecio" in texto,
              "ensena los titulos de los ultimos videos del canal")
    comprobar("NO repitas" in texto, "y pide no repetirlos")
    igual(variedad.bloque_para_guion(nuevo, None), "", "sin eleccion no hay seccion")


def prueba_revision():
    seccion("una primera frase copiada es un motivo para pedirlo otra vez")
    base = proyecto("revision base", canal="canal_revision")
    variedad.registrar(base, "dato", "cronologica", "La caida del banco",
                       "En mil novecientos treinta, el banco mas grande del pais cerro sus puertas.")
    nuevo = proyecto("revision nuevo", canal="canal_revision")
    motivos = variedad.revisar(nuevo, "Otro titulo",
                               "En mil novecientos treinta el banco mas grande del pais cerro sus puertas para siempre.")
    igual(len(motivos), 1, "casi la misma frase: un motivo")
    comprobar("OTRO gancho" in (motivos or [""])[0], "y dice que hay que escribir otro gancho")
    igual(variedad.revisar(nuevo, "Otro titulo",
                           "Un pescador encontro una moneda que no deberia existir."),
          [], "una frase distinta pasa")
    comprobar(variedad.revisar(nuevo, "La caida del banco", "Algo totalmente distinto."),
              "un titulo repetido tambien es motivo")
    igual(variedad.revisar(base, "La caida del banco",
                           "En mil novecientos treinta, el banco mas grande del pais cerro sus puertas."),
          [], "un video no se compara consigo mismo (regenerar su guion no es repetirse)")
    comprobar(variedad.avisos(" ".join(["palabra"] * 20)),
              "un gancho de veinte palabras se avisa: no se dice en tres segundos")
    igual(variedad.avisos("Nadie lo vio venir."), [], "uno corto no")
    igual(variedad.primera_frase('El gancho.<break time="900ms"/> Y lo demas.'),
          "El gancho.", "la primera frase se lee sin las anotaciones de voz")


def prueba_sin_firma():
    seccion("la memoria no entra en la firma del guion")
    import p3_guion
    comprobar(not any("variedad" in clave or "memoria" in clave
                      for clave in p3_guion.PARAMS_POR_DEFECTO),
              "ningun param del guion habla de la memoria: no puede mover su firma")


def prueba_capitulos():
    seccion("los capitulos salen del minuto real de la voz")
    guion = {"guion": [
        {"id": "B001", "texto": "El gancho.", "abre_seccion": True},
        {"id": "B002", "texto": "Sigue.", "abre_seccion": False},
        {"id": "B003", "texto": "La segunda parte empieza aqui.", "abre_seccion": True},
        {"id": "B004", "texto": "Una seccion corta.", "abre_seccion": True},
        {"id": "B005", "texto": "La tercera parte.", "abre_seccion": True},
        {"id": "B006", "texto": "El final.", "abre_seccion": True},
    ]}
    meta = {"bloques": [{"id": "B001", "t_in": 0.4}, {"id": "B002", "t_in": 5.0},
                        {"id": "B003", "t_in": 31.2}, {"id": "B004", "t_in": 36.0},
                        {"id": "B005", "t_in": 75.5}, {"id": "B006", "t_in": 130.0}]}
    caps = publicacion.capitulos(guion, meta)
    igual(caps[0]["t"], 0.0, "el primero en 0:00, como exige YouTube")
    igual([c["id"] for c in caps], ["B001", "B003", "B005", "B006"],
          "una seccion a menos de diez segundos de la anterior se junta con ella")
    ficha = publicacion.componer("Titulo", caps, None)
    igual([c["reloj"] for c in ficha["capitulos"]], ["0:00", "0:31", "1:15", "2:10"],
          "con su minuto escrito como lo lee YouTube")
    igual(ficha["capitulos"][1]["titulo"], "La segunda parte empieza aqui.",
          "sin modelo, cada capitulo se llama por su primera frase")
    igual(publicacion.capitulos(guion, {"bloques": meta["bloques"][:3]}), [],
          "con menos de tres capitulos no se ponen: YouTube no los aceptaria")
    igual(publicacion.capitulos(guion, {}), [], "sin voz no hay minutos, y no se inventan")

    seccion("lo que diga el modelo se limpia")
    datos = {"titulos": ["Uno", "Uno", "x" * 200, "Tres", "Cuatro"],
             "descripcion": " Texto. ",
             "capitulos": [{"id": "B003", "titulo": "La segunda"}],
             "etiquetas": ["a", "b"], "hashtags": ["#uno", "dos", "tres palabras"]}
    ficha = publicacion.componer("Titulo", caps, datos)
    igual(len(ficha["titulos"]), 3, "tres titulos, sin repetidos")
    comprobar(all(len(t) <= publicacion.MAX_TITULO for t in ficha["titulos"]),
              "ninguno pasa del largo de un titulo de YouTube")
    igual(ficha["capitulos"][1]["titulo"], "La segunda", "el nombre del modelo manda")
    igual(ficha["capitulos"][2]["titulo"], "La tercera parte.",
          "y el que no nombra se queda con su primera frase")
    igual(ficha["hashtags"], ["#uno", "#dos"], "los hashtags llevan # y no llevan espacios")
    texto = publicacion.texto_de(ficha)
    comprobar("0:31 La segunda" in texto and "Contenido alterado" in texto,
              "el texto para pegar lleva los capitulos y el aviso de contenido sintetico")


def main():
    try:
        prueba_eleccion()
        prueba_revision()
        prueba_sin_firma()
        prueba_capitulos()
    finally:
        shutil.rmtree(TEMPORAL, ignore_errors=True)
    print()
    if FALLOS:
        print(f"PRUEBA VARIEDAD: FALLAN {len(FALLOS)}")
        for texto in FALLOS:
            print(f"  - {texto}")
        return 1
    print("PRUEBA VARIEDAD OK: todas las comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
