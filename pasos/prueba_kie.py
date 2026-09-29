"""
Prueba del motor de imagen de kie.ai y de como se engancha al Estudio.

No sale a la red: la API de kie.ai se sustituye por un doble que contesta como
se espera que conteste (tarea creada, en cola, generando, lista). Lo que se
comprueba es lo que se puede romper en silencio al anadir un segundo proveedor:

  - que un proyecto de OpenAI no se entere de nada: la misma huella de cache,
    las mismas referencias y el mismo prompt que antes
  - que el motor de kie.ai cumpla el contrato del de OpenAI (png, meta)
  - que las referencias se suban UNA vez aunque las pidan cien planos
  - que el recorte de referencias lo haga p6 y por papel, nunca el motor
  - que quedarse sin creditos se distinga de un fallo que se arregla esperando
  - que el gasto se apunte como kie.ai, con su tarifa plana, y no como OpenAI
  - que un proyecto nuevo solo lleve `motor_imagen` si el ajuste lo pide

    python pasos/prueba_kie.py
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types

# TODO LO QUE ESCRIBE, A UNA CARPETA DE PRUEBA: claves, ajustes, subidas, gasto.
TEMPORAL = tempfile.mkdtemp(prefix="estudio_prueba_kie_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(TEMPORAL, "secretos")
os.environ["ESTUDIO_AJUSTES"] = os.path.join(TEMPORAL, "ajustes.json")
os.environ["ESTUDIO_KIE_SUBIDAS"] = os.path.join(TEMPORAL, "subidas.json")
os.environ["ESTUDIO_COSTE_GLOBAL"] = os.path.join(TEMPORAL, "coste_global.jsonl")
os.environ.pop("KIE_API_KEY", None)
os.makedirs(os.environ["ESTUDIO_SECRETOS"], exist_ok=True)
with open(os.path.join(os.environ["ESTUDIO_SECRETOS"], "claves.json"), "w",
          encoding="utf-8") as fh:
    json.dump({"kie": {"clave": "kie-prueba-9876"}}, fh)

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)

from PIL import Image  # noqa: E402

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


def falla(funcion, excepcion, trozo, texto):
    try:
        funcion()
    except excepcion as fallo:
        comprobar(trozo.lower() in str(fallo).lower(),
                  f"{texto} -> {str(fallo)[:90]}")
        return
    except Exception as fallo:                              # noqa: BLE001
        comprobar(False, f"{texto} (fallo con otra cosa: {type(fallo).__name__}: {fallo})")
        return
    comprobar(False, f"{texto} (no fallo)")


def seccion(titulo):
    print(f"\n[{titulo}]")


def cargar_motor():
    ruta = os.path.join(RAIZ, "motores", "imagen_kie", "imagen.py")
    spec = importlib.util.spec_from_file_location("imagen_kie_prueba", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    # sin esperas de verdad: el doble contesta al momento
    modulo.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time,
                                        monotonic=time.monotonic)
    return modulo


def png_de(ancho, alto, color=(200, 40, 40)):
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(salida, "PNG")
    return salida.getvalue()


def referencia(nombre, color):
    ruta = os.path.join(TEMPORAL, "refs", f"{nombre}.png")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    Image.new("RGB", (64, 64), color).save(ruta, "PNG")
    return ruta


# ------------------------------------------------------------ el doble de kie

class Respuesta:
    def __init__(self, cuerpo=None, estado=200, contenido=b""):
        self.status_code = estado
        self._cuerpo = cuerpo
        self.text = json.dumps(cuerpo) if cuerpo is not None else ""
        self.content = contenido
        self.headers = {}

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class KieFalso:
    """Contesta como kie.ai: subidas, tareas y consultas. Apunta lo que le piden."""

    class RequestException(Exception):
        pass

    def __init__(self, motor, resultado=(1200, 900)):
        self.motor = motor
        self.subidas = []
        self.tareas = {}
        self.creadas = []
        self.guion_crear = []          # codigos que devolvera createTask, en orden
        self.guion_estados = []        # por tarea: estados que ira diciendo
        self.resultado = resultado

    def post(self, url, headers=None, data=None, files=None, json=None, timeout=None):
        if url == self.motor.URL_SUBIR:
            self.subidas.append(data.get("fileName"))
            return Respuesta({"success": True, "code": 200,
                              "data": {"downloadUrl": f"https://ficheros/{data['fileName']}"}})
        if url == self.motor.URL_CREAR:
            if self.guion_crear:
                codigo, mensaje = self.guion_crear.pop(0)
                if codigo != 200:
                    return Respuesta({"code": codigo, "msg": mensaje})
            tarea = f"t{len(self.creadas) + 1}"
            self.creadas.append(json)
            estados = list(self.guion_estados.pop(0)) if self.guion_estados \
                else ["waiting", "generating", "success"]
            self.tareas[tarea] = estados
            return Respuesta({"code": 200, "msg": "success", "data": {"taskId": tarea}})
        return Respuesta({"code": 404, "msg": "no existe"}, 404)

    def get(self, url, headers=None, params=None, timeout=None):
        if url == self.motor.URL_CONSULTAR:
            tarea = params["taskId"]
            estados = self.tareas[tarea]
            estado = estados.pop(0) if len(estados) > 1 else estados[0]
            datos = {"taskId": tarea, "state": estado}
            if estado == "success":
                datos["resultJson"] = json.dumps({"resultUrls": [f"https://salida/{tarea}.png"]})
            if estado == "fail":
                datos.update(failCode="501", failMsg="generation failed")
            return Respuesta({"code": 200, "data": datos})
        if url == self.motor.URL_SALDO:
            return Respuesta({"code": 200, "msg": "success", "data": 123.5})
        if url.startswith("https://salida/"):
            return Respuesta(None, 200, png_de(*self.resultado))
        return Respuesta({"code": 404}, 404)


# ------------------------------------------------------------------ pruebas

def prueba_contrato():
    seccion("el motor de kie.ai cumple el contrato del de OpenAI")
    motor = cargar_motor()
    falso = KieFalso(motor)
    motor.requests = falso
    estilo = referencia("estilo", (10, 120, 200))
    reparto = referencia("reparto", (240, 200, 10))

    png, meta = motor.generar("un puerto al amanecer", [estilo, reparto],
                              quality="low", tamano="apaisado")
    imagen = Image.open(io.BytesIO(png))
    igual(imagen.format, "PNG", "devuelve bytes de un PNG, como el de OpenAI")
    igual(round(imagen.width / imagen.height, 3), round(3 / 2, 3),
          "y con la proporcion EXACTA de 'apaisado' aunque el modelo de otra (4:3 -> 3:2)")
    igual(imagen.width, 1200, "recortando al centro, sin reescalar: el zoom del render lee pixeles reales")
    igual(meta["tamano"], "1536x1024", "meta.tamano es el mismo texto que da el de OpenAI")
    igual(meta["proveedor"], "kie", "y dice quien la ha generado")
    igual(meta["modelo"], motor.modelo_por_defecto(), "con el modelo por defecto de modelos.json")
    igual(meta["refs"], 2, "y cuantas referencias llevaba")
    igual(meta["usage"], {}, "sin tokens: kie.ai cobra por imagen")
    igual(meta["coste"], motor.precio(motor.modelo_por_defecto(), "low"),
          "el coste sale de tarifas.json, no de una constante del motor")

    pedida = falso.creadas[-1]
    igual(pedida["model"], "google/nano-banana-edit", "crea la tarea con el modelo de la ficha")
    igual(pedida["input"]["image_urls"],
          [f"https://ficheros/{n}" for n in falso.subidas],
          "las referencias viajan por URL, en el MISMO orden en que llegaron")
    igual(pedida["input"]["image_size"], "3:2", "y la proporcion en el campo de ese modelo")

    seccion("las referencias se suben una vez")
    antes = len(falso.subidas)
    motor.generar("otro plano", [estilo, reparto])
    igual(len(falso.subidas), antes, "el segundo plano con las mismas referencias no sube nada")
    otra = referencia("continuidad", (0, 0, 0))
    motor.generar("otro plano mas", [estilo, otra])
    igual(len(falso.subidas), antes + 1, "solo se sube la que no se habia visto")
    with open(os.environ["ESTUDIO_KIE_SUBIDAS"], encoding="utf-8") as fh:
        recordadas = json.load(fh)
    igual(len(recordadas), 3, "y se recuerdan en disco para la proxima tanda")

    seccion("vertical y cuadrado")
    falso.resultado = (900, 1200)
    png, meta = motor.generar("retrato", [estilo], tamano="vertical")
    imagen = Image.open(io.BytesIO(png))
    igual(round(imagen.width / imagen.height, 3), round(2 / 3, 3), "vertical sale en 2:3")
    igual(falso.creadas[-1]["input"]["image_size"], "2:3", "y se pide en 2:3")
    falla(lambda: motor.generar("x", [estilo], tamano="panoramico"), ValueError,
          "tamano desconocido", "un tamano que no existe se rechaza antes de pagar")


def prueba_limites():
    seccion("lo que el motor NO hace por su cuenta")
    motor = cargar_motor()
    motor.requests = KieFalso(motor)
    refs = [referencia(f"r{i}", (i * 20, 0, 0)) for i in range(11)]
    falla(lambda: motor.generar("x", refs), ValueError, "admite 10",
          "con mas referencias de las que admite el modelo levanta: no recorta a ciegas")
    falla(lambda: motor.generar("x", [os.path.join(TEMPORAL, "no_existe.png")]),
          ValueError, "no existen", "una referencia que no existe se dice antes de pagar")
    falla(lambda: motor.generar("x", [refs[0]], modelo="modelo-inventado"),
          ValueError, "desconocido", "un modelo que no esta en modelos.json se rechaza")

    seccion("sin referencias: el modelo de texto a imagen de la ficha")
    falso = KieFalso(motor)
    motor.requests = falso
    png, meta = motor.generar("una lamina de estilo", [])
    igual(falso.creadas[-1]["model"], "google/nano-banana",
          "se llama al modelo de 'sin_referencias'")
    comprobar("image_urls" not in falso.creadas[-1]["input"],
              "y sin el campo de referencias")
    igual(meta["modelo"], "google/nano-banana-edit",
          "pero se cobra con la tarifa del modelo elegido")


def prueba_errores():
    seccion("sin creditos no se reintenta; lo que se arregla esperando, si")
    motor = cargar_motor()
    estilo = referencia("estilo_err", (1, 2, 3))

    falso = KieFalso(motor)
    falso.guion_crear = [(402, "Insufficient credits")]
    motor.requests = falso
    falla(lambda: motor.generar("x", [estilo]), motor.SinSaldo, "sin creditos",
          "un 402 es SinSaldo, con el aviso de recargar")
    igual(len(falso.creadas), 0, "y no se ha creado ninguna tarea")
    comprobar(motor.cuentas_para_la_pantalla()[0]["sin_saldo"],
              "la pantalla ve la cuenta sin saldo")

    falso = KieFalso(motor)
    falso.guion_crear = [(429, "too many requests"), (500, "server error")]
    motor.requests = falso
    png, meta = motor.generar("x", [estilo])
    igual(len(falso.creadas), 1, "un 429 y un 500 se esperan y la tarea sale a la tercera")
    comprobar(not motor.cuentas_para_la_pantalla()[0]["sin_saldo"],
              "y una imagen buena quita la marca de sin saldo")

    falso = KieFalso(motor)
    falso.guion_crear = [(401, "Unauthorized")]
    motor.requests = falso
    falla(lambda: motor.generar("x", [estilo]), motor.ErrorKie, "clave",
          "un 401 dice que mires la clave")

    seccion("una tarea que falla se intenta UNA vez mas")
    falso = KieFalso(motor)
    falso.guion_estados = [["generating", "fail"], ["success"]]
    motor.requests = falso
    png, meta = motor.generar("x", [estilo])
    igual(len(falso.creadas), 2, "el segundo intento sale y la imagen llega")
    falso = KieFalso(motor)
    falso.guion_estados = [["fail"], ["fail"]]
    motor.requests = falso
    falla(lambda: motor.generar("x", [estilo]), motor.ErrorKie, "dos veces",
          "dos fallos seguidos suben el motivo, sin seguir pagando")

    seccion("el saldo se consulta gratis")
    motor.requests = KieFalso(motor)
    igual(motor.saldo(), 123.5, "saldo() devuelve los creditos de la cuenta")


def prueba_p6_sin_cambios_para_openai():
    seccion("un proyecto de OpenAI no se entera de nada")
    import p6_assets

    estilo = referencia("estilo_p6", (5, 5, 5))
    p = {"calidad": "low", "motor_imagen": "openai"}
    heredada = {"prompt": "hola", "calidad": "low", "tamano": None,
                "refs": [p6_assets.medios.huella_fichero(estilo)]}
    igual(p6_assets.medios.huella(p6_assets._huella_de_imagen("hola", [estilo], p, "apaisado")),
          p6_assets.medios.huella(heredada),
          "la huella de cache es la de siempre: el banco sigue acertando")
    igual(p6_assets.medios.huella(p6_assets._huella_de_imagen("hola", [estilo], {"calidad": "low"}, "apaisado")),
          p6_assets.medios.huella(heredada),
          "tambien en un proyecto que nunca escribio motor_imagen")
    refs = [{"papel": "lamina", "ruta": "a"}] + [
        {"papel": "continuidad", "ruta": str(i)} for i in range(20)]
    comprobar(p6_assets._referencias_para_el_motor(refs, p) is refs,
              "y las referencias salen intactas, por muchas que sean")
    igual(p6_assets._motor_generador(p).__file__.replace("\\", "/").split("/")[-2],
          "imagen_openai", "el que genera es el de OpenAI")

    seccion("un proyecto de kie.ai")
    kie = {"calidad": "low", "motor_imagen": "kie"}
    comprobar(p6_assets.medios.huella(p6_assets._huella_de_imagen("hola", [estilo], kie, "apaisado"))
              != p6_assets.medios.huella(heredada),
              "la misma escena con kie.ai es OTRA entrada de cache")
    con_modelo = dict(kie, modelo_imagen="bytedance/seedream-v4-edit")
    comprobar(p6_assets.medios.huella(p6_assets._huella_de_imagen("hola", [estilo], con_modelo, "apaisado"))
              != p6_assets.medios.huella(p6_assets._huella_de_imagen("hola", [estilo], kie, "apaisado")),
              "y con otro modelo, otra")
    igual(p6_assets._motor_generador(kie).__file__.replace("\\", "/").split("/")[-2],
          "imagen_kie", "el que genera es el de kie.ai")

    seccion("el recorte es de p6 y va por papel")
    refs = ([{"papel": "lamina", "ruta": "lamina"}]
            + [{"papel": "reparto", "ruta": f"hoja{i}"} for i in range(3)]
            + [{"papel": "parecido", "ruta": f"real{i}"} for i in range(4)]
            + [{"papel": "continuidad", "ruta": f"prev{i}"} for i in range(3)]
            + [{"papel": "adjunta", "ruta": "nota"}])
    quedan = p6_assets._referencias_para_el_motor(refs, kie)
    igual(len(quedan), 10, "doce referencias contra un modelo de diez: se quedan diez")
    rutas = [r["ruta"] for r in quedan]
    comprobar("lamina" in rutas and "nota" in rutas,
              "la lamina de estilo y la adjunta de la nota no se sueltan nunca")
    igual(rutas.count("real0") + rutas.count("real1") + rutas.count("real2") + rutas.count("real3"),
          2, "se sueltan primero los parecidos, y los ultimos")
    igual([r for r in rutas if r.startswith("prev")], ["prev0", "prev1", "prev2"],
          "la continuidad se queda entera mientras sobren otras")
    igual(rutas, [r["ruta"] for r in refs if r["ruta"] in rutas],
          "y el orden es el de la lista original: el prompt las cita por posicion")
    pro = dict(kie, modelo_imagen="nano-banana-pro")
    quedan = p6_assets._referencias_para_el_motor(refs, pro)
    igual(len(quedan), 8, "con Nano Banana Pro (ocho) sigue recortando")
    comprobar(not any(r["papel"] == "parecido" for r in quedan)
              and sum(r["papel"] == "continuidad" for r in quedan) == 3,
              "fuera los cuatro parecidos antes de tocar la continuidad")


def prueba_coste():
    seccion("el gasto se apunta como kie.ai")
    from nucleo import coste
    igual(coste.tarifa_kie("google/nano-banana-edit"), 0.02,
          "4 creditos a 0,005 $ son 0,02 $ por imagen")
    igual(coste.tarifa_kie("nano-banana-pro", "4K"), 0.12,
          "un modelo con precio por resolucion mira la resolucion")
    igual(coste.tarifa_kie("modelo-sin-tarifa"), None,
          "sin tarifa, un hueco: no un numero inventado")
    comprobar("kie" in coste.PROVEEDORES, "kie.ai es un proveedor del medidor")

    vacio = coste.agregar([])
    comprobar("kie.ai" not in vacio["cabecera"],
              "sin haberlo usado, la cabecera es la de siempre")
    agregado = coste.agregar([
        {"proveedor": "kie", "usd": 0.02, "cantidad": {"imagenes": 1}},
        {"proveedor": "kie", "usd": 0.02, "cantidad": {"imagenes": 1}},
        {"proveedor": "tts", "usd": 0.5, "cantidad": {"caracteres": 1000}}])
    igual(agregado["total_usd"], 0.54, "y entra en el total")
    comprobar("kie.ai  $0.04 · 2 img" in agregado["cabecera"],
              f"y se ve en la cabecera: {agregado['cabecera']}")

    seccion("el medidor envuelve el motor de kie.ai por el mismo sitio")
    from nucleo.proyecto import Proyecto
    proyecto = Proyecto.crear(os.path.join(TEMPORAL, "proyectos"), "prueba kie")

    def generar_falso(prompt, referencias, **kw):
        return b"png", {"proveedor": "kie", "modelo": "google/nano-banana-edit",
                        "resolucion": None, "refs": len(referencias), "coste": 0.0,
                        "tamano": "1536x1024", "segundos": 1.0, "tarea": "t9"}
    medido = coste._medir_imagen(generar_falso)
    with coste.contexto(proyecto, "assets"):
        _, meta = medido("hola", ["a", "b"], quality="low")
    total = coste.Medidor(proyecto).total()
    igual(total["proveedores"]["kie"]["cantidad"]["imagenes"], 1, "se anota una imagen de kie.ai")
    igual(total["proveedores"]["openai"]["eventos"], 0, "y ninguna de OpenAI")
    igual(meta["coste"], 0.02, "y el importe vuelve en meta, como con OpenAI")


def prueba_ajustes_y_claves():
    seccion("un proyecto nuevo solo lleva motor_imagen si el ajuste lo pide")
    import ajustes
    igual(ajustes.params_de_imagen_nuevos(), {"calidad": "low"},
          "con el ajuste de fabrica se escribe lo mismo que antes: solo la calidad")
    ajustes.guardar({"motor_imagen": "kie"})
    igual(ajustes.params_de_imagen_nuevos(), {"calidad": "low", "motor_imagen": "kie"},
          "con kie.ai se escribe el motor")
    ajustes.guardar({"modelo_imagen": "bytedance/seedream-v4-edit"})
    igual(ajustes.params_de_imagen_nuevos()["modelo_imagen"], "bytedance/seedream-v4-edit",
          "y el modelo, si se eligio")
    falla(lambda: ajustes.guardar({"motor_imagen": "midjourney"}), ValueError,
          "solo", "un motor que no existe no se guarda")
    falla(lambda: ajustes.guardar({"modelo_imagen": "inventado"}), ValueError,
          "los que hay", "ni un modelo que no esta en modelos.json")
    comprobar("google/nano-banana-edit" in ajustes.modelos_kie(),
              "la pantalla puede listar los modelos")
    igual(ajustes.coste_imagen_kie("high", "nano-banana-pro"), 0.12,
          "y saber lo que cuesta cada calidad con cada modelo")
    ajustes.guardar({"motor_imagen": "openai", "modelo_imagen": ""})

    seccion("la clave de kie.ai en el almacen")
    import claves
    igual(claves.kie(), "kie-prueba-9876", "se lee del almacen")
    resumen = claves.resumen()
    igual(resumen["kie"], {"puesta": True, "cola": "…9876"},
          "y a la pantalla solo baja la cola")
    guardado = claves.guardar({"kie": {"clave": claves.CONSERVAR},
                               "cartesia": {"clave": "cart-nueva"}})
    igual(claves.kie(), "kie-prueba-9876",
          "editar otra clave no borra la de kie.ai (CONSERVAR)")
    comprobar(guardado is not None, "y guardar sigue funcionando")

    seccion("probar la clave no cuesta nada")
    import comprobar_claves

    class Pedido:
        def __init__(self, cuerpo, estado=200):
            self.cuerpo, self.status_code, self.text = cuerpo, estado, json.dumps(cuerpo)

        def json(self):
            return self.cuerpo

    original = comprobar_claves._pedir
    try:
        comprobar_claves._pedir = lambda *a, **k: (Pedido({"code": 200, "data": 55}), "")
        ficha = comprobar_claves.probar_kie("clave")
        igual((ficha["estado"], ficha.get("creditos")), ("ok", 55.0), "con saldo: ok y cuantos creditos")
        comprobar_claves._pedir = lambda *a, **k: (Pedido({"code": 200, "data": 0}), "")
        igual(comprobar_claves.probar_kie("clave")["estado"], "mal",
              "sin creditos es MAL: pararia la tanda igual que una clave mala")
        comprobar_claves._pedir = lambda *a, **k: (Pedido({"code": 401, "msg": "no"}), "")
        igual(comprobar_claves.probar_kie("clave")["estado"], "mal", "un 401 es MAL")
        igual(comprobar_claves.probar_kie("")["estado"], "sin_clave", "sin clave lo dice")
    finally:
        comprobar_claves._pedir = original


def main():
    try:
        prueba_contrato()
        prueba_limites()
        prueba_errores()
        prueba_p6_sin_cambios_para_openai()
        prueba_coste()
        prueba_ajustes_y_claves()
    finally:
        shutil.rmtree(TEMPORAL, ignore_errors=True)
    print()
    if FALLOS:
        print(f"PRUEBA KIE: FALLAN {len(FALLOS)}")
        for texto in FALLOS:
            print(f"  - {texto}")
        return 1
    print("PRUEBA KIE OK: todas las comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())
