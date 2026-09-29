"""La FASE 0 del cambio a kie.ai: antes de generar un video, medir.

Lo que decide esto no se puede decidir leyendo codigo: si un modelo de kie.ai
sostiene el ESTILO de un canal (con sus referencias delante), cuanto cobra de
verdad por imagen y cuanto tarda. Esta herramienta genera los mismos planos con
varios modelos, mira el saldo antes y despues de cada uno y deja una hoja de
contactos para comparar a ojo.

    # solo comprobar la clave y el saldo (no cuesta nada)
    python herramientas/probar_kie.py --saldo

    # 5 planos x 2 modelos, con la lamina de estilo y una hoja de reparto
    python herramientas/probar_kie.py \\
        --ref ruta/lamina_estilo.png --ref ruta/reparto.png \\
        --prompts prompts.txt --modelo google/nano-banana-edit \\
        --modelo bytedance/seedream-v4-edit --salida prueba_kie

    # y con las imagenes que ya hizo OpenAI para esos planos, al lado
    python herramientas/probar_kie.py ... --comparar carpeta_con_S001.png_etc

`prompts.txt` lleva un prompt por bloque, separados por una linea en blanco. Lo
mas util es copiar los prompts de verdad de un proyecto (los guarda p6 junto a
cada plano) para que la comparacion sea contra lo que ya se pago.

Deja en --salida: las imagenes (<modelo>/<n>.png), `informe.json` (segundos,
creditos medidos por el saldo y creditos de tarifas.json) y `hoja.html`.

CUESTA DINERO: pregunta antes de empezar cuanto va a gastar (con --si no).
"""
import argparse
import html
import importlib.util
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def motor():
    ruta = os.path.join(RAIZ, "motores", "imagen_kie", "imagen.py")
    spec = importlib.util.spec_from_file_location("imagen_kie", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def leer_prompts(ruta, uno):
    if uno:
        return [uno]
    with open(ruta, "r", encoding="utf-8") as fh:
        bloques = [b.strip() for b in fh.read().split("\n\n")]
    return [b for b in bloques if b]


def hoja(salida, filas, modelos, comparar):
    """Una tabla: una fila por prompt y una columna por modelo (y OpenAI)."""
    columnas = (["OpenAI (ya pagado)"] if comparar else []) + modelos
    partes = ["<!doctype html><meta charset='utf-8'><title>Prueba kie.ai</title>",
              "<style>body{font-family:sans-serif;margin:16px;background:#111;color:#eee}"
              "table{border-collapse:collapse}td,th{border:1px solid #333;padding:6px;"
              "vertical-align:top}img{width:360px;display:block}p{max-width:360px;"
              "font-size:12px;color:#aaa}</style>",
              "<table><tr><th>#</th>"
              + "".join(f"<th>{html.escape(c)}</th>" for c in columnas) + "</tr>"]
    for fila in filas:
        celdas = [f"<td>{fila['n']}<p>{html.escape(fila['prompt'][:400])}</p></td>"]
        if comparar:
            previa = fila.get("comparar")
            celdas.append(f"<td><img src='{html.escape(previa)}'></td>" if previa
                          else "<td>—</td>")
        for modelo in modelos:
            hecho = fila["modelos"].get(modelo) or {}
            if hecho.get("png"):
                celdas.append(f"<td><img src='{html.escape(hecho['png'])}'>"
                              f"<p>{hecho.get('segundos')} s</p></td>")
            else:
                celdas.append(f"<td><p>{html.escape(str(hecho.get('error') or '—'))}</p></td>")
        partes.append("<tr>" + "".join(celdas) + "</tr>")
    partes.append("</table>")
    ruta = os.path.join(salida, "hoja.html")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(partes))
    return ruta


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--saldo", action="store_true", help="solo comprobar clave y saldo")
    parser.add_argument("--ref", action="append", default=[], help="imagen de referencia (repetible)")
    parser.add_argument("--prompts", help="fichero con un prompt por bloque")
    parser.add_argument("--prompt", help="un solo prompt")
    parser.add_argument("--modelo", action="append", default=[], help="modelo de kie.ai (repetible)")
    parser.add_argument("--calidad", default="low", choices=("low", "medium", "high"))
    parser.add_argument("--tamano", default="apaisado", choices=("apaisado", "vertical", "cuadrado"))
    parser.add_argument("--comparar", help="carpeta con las imagenes de OpenAI de esos planos (1.png, 2.png... o S001.png...)")
    parser.add_argument("--salida", default="prueba_kie")
    parser.add_argument("--si", action="store_true", help="no preguntar antes de gastar")
    args = parser.parse_args()

    kie = motor()
    try:
        saldo_inicial = kie.saldo()
    except SystemExit as fallo:
        print(f"sin clave: {fallo}")
        return 2
    except Exception as fallo:                              # noqa: BLE001
        print(f"kie.ai no contesta al saldo: {type(fallo).__name__}: {fallo}")
        return 2
    print(f"clave de kie.ai: OK. Saldo: {saldo_inicial:g} creditos")
    if args.saldo:
        return 0

    if not (args.prompts or args.prompt):
        parser.error("hace falta --prompts o --prompt")
    prompts = leer_prompts(args.prompts, args.prompt)
    modelos = args.modelo or [kie.modelo_por_defecto()]
    previsto = 0.0
    for modelo in modelos:
        precio = kie.precio(modelo, args.calidad)
        previsto += (precio or 0.0) * len(prompts)
        print(f"  {modelo}: {len(prompts)} imagenes x "
              f"{'sin tarifa' if precio is None else f'{precio:.4f} $'}")
    print(f"Previsto (segun tarifas.json, sin verificar): {previsto:.2f} $")
    if not args.si and input("¿Seguir? [s/N] ").strip().lower() not in ("s", "si", "sí", "y"):
        return 1

    os.makedirs(args.salida, exist_ok=True)
    comparables = {}
    if args.comparar and os.path.isdir(args.comparar):
        nombres = sorted(n for n in os.listdir(args.comparar) if n.lower().endswith(".png"))
        for indice, nombre in enumerate(nombres[:len(prompts)], start=1):
            comparables[indice] = os.path.relpath(os.path.join(args.comparar, nombre), args.salida)

    filas = [{"n": i, "prompt": p, "modelos": {}, "comparar": comparables.get(i)}
             for i, p in enumerate(prompts, start=1)]
    informe = {"saldo_inicial": saldo_inicial, "calidad": args.calidad,
               "tamano": args.tamano, "referencias": args.ref, "modelos": {}}
    for modelo in modelos:
        carpeta = os.path.join(args.salida, modelo.replace("/", "_"))
        os.makedirs(carpeta, exist_ok=True)
        antes = kie.saldo()
        tiempos, fallos = [], 0
        for fila in filas:
            t0 = time.time()
            try:
                png, meta = kie.generar(fila["prompt"], args.ref, quality=args.calidad,
                                        tamano=args.tamano, modelo=modelo)
            except Exception as fallo:                      # noqa: BLE001
                fallos += 1
                fila["modelos"][modelo] = {"error": f"{type(fallo).__name__}: {fallo}"}
                print(f"  {modelo} #{fila['n']}: FALLO {fallo}")
                continue
            ruta = os.path.join(carpeta, f"{fila['n']}.png")
            with open(ruta, "wb") as fh:
                fh.write(png)
            tiempos.append(time.time() - t0)
            fila["modelos"][modelo] = {"png": os.path.relpath(ruta, args.salida),
                                       "segundos": meta.get("segundos")}
            print(f"  {modelo} #{fila['n']}: {meta.get('segundos')} s")
        despues = kie.saldo()
        hechas = len(filas) - fallos
        medidos = (antes - despues) / hechas if hechas else None
        tarifa = kie.precio(modelo, args.calidad)
        por_credito = ((kie._tarifas() or {}).get("usd_por_credito"))
        informe["modelos"][modelo] = {
            "imagenes": hechas, "fallos": fallos,
            "segundos_medios": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
            "creditos_medidos_por_imagen": round(medidos, 3) if medidos is not None else None,
            "usd_tarifa_por_imagen": tarifa,
            "usd_medido_por_imagen": (round(medidos * float(por_credito), 5)
                                      if medidos is not None and por_credito else None)}
        print(f"  => {modelo}: {informe['modelos'][modelo]}")

    informe["saldo_final"] = kie.saldo()
    with open(os.path.join(args.salida, "informe.json"), "w", encoding="utf-8") as fh:
        json.dump({"informe": informe, "filas": filas}, fh, ensure_ascii=False, indent=2)
    print(f"\nHoja de contactos: {hoja(args.salida, filas, modelos, bool(comparables))}")
    print("Si los creditos medidos no cuadran con tarifas.json, corrige el bloque "
          "'kie' de tarifas.json y pon 'verificado': true. Si un modelo falla por un "
          "campo, corrige su ficha en motores/imagen_kie/modelos.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
