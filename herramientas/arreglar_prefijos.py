r"""Quita los prefijos `NN_` repetidos de las laminas de los presets.

POR QUE HIZO FALTA
------------------
`presets_canal.guardar` ponia un prefijo `NN_` al basename del origen, y en cada
edicion --nombre, idioma, ritmo, voz-- vuelve a copiar las laminas DESDE EL
BANCO, donde ya tenian el suyo. Resultado: `00_cara.png` pasaba a
`00_00_cara.png`, luego `00_00_00_cara.png`... hasta que las rutas guardadas
dejaban de cuadrar con el disco y el preset no se podia ni editar («estos
fotogramas no estan en el disco del servidor»).

El codigo ya no lo hace. Esto repara lo que quedo roto.

Sin `--aplicar` es un simulacro.
"""
import argparse
import json
import os
import re
import sys

SOBRA = re.compile(r"^(?:\d{2}_)+(?=\d{2}_)")   # todos los NN_ salvo el ultimo


def limpio(nombre):
    """`00_00_00_cara.png` -> `00_cara.png`; `00_cara.png` se queda igual."""
    return SOBRA.sub("", nombre)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("raiz", help="carpeta del Estudio (donde esta presets.json)")
    p.add_argument("--aplicar", action="store_true", help="escribir de verdad")
    args = p.parse_args()

    ruta_json = os.path.join(args.raiz, "presets.json")
    datos = json.load(open(ruta_json, encoding="utf-8"))
    renombrados = tocados = 0

    for lista in ("presets", "papelera"):
        for preset in datos.get(lista) or []:
            carpeta = os.path.dirname(preset.get("miniatura") or "")
            if not carpeta or not os.path.isdir(carpeta):
                continue
            mapa = {}
            for nombre in sorted(os.listdir(carpeta)):
                nuevo = limpio(nombre)
                if nuevo == nombre:
                    continue
                viejo_abs = os.path.join(carpeta, nombre)
                nuevo_abs = os.path.join(carpeta, nuevo)
                mapa[viejo_abs] = nuevo_abs
                print(f"  {nombre}  ->  {nuevo}")
                if args.aplicar:
                    os.replace(viejo_abs, nuevo_abs)
                renombrados += 1
            if not mapa:
                continue
            tocados += 1
            # y las rutas guardadas, que es lo que de verdad usa el Estudio
            crudo = json.dumps(preset, ensure_ascii=False)
            for viejo, nuevo in mapa.items():
                crudo = crudo.replace(json.dumps(viejo)[1:-1],
                                      json.dumps(nuevo)[1:-1])
            nuevo_preset = json.loads(crudo)
            preset.clear()
            preset.update(nuevo_preset)

    print(f"\n{'APLICADO' if args.aplicar else 'SIMULACRO'}: "
          f"{renombrados} ficheros en {tocados} presets")
    if args.aplicar and renombrados:
        tmp = ruta_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, ruta_json)
        print("presets.json actualizado")


if __name__ == "__main__":
    main()
