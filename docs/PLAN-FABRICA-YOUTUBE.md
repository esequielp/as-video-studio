# Plan: fábrica de vídeos para YouTube (largos + Shorts) sobre AS Video Studio

**Fecha:** 29-09-2026 · **Estado:** implementado en la rama
`claude/eloquent-hamilton-i1f2gu` salvo la verificación contra kie.ai (ver
«Estado de cada fase» justo debajo).

## Estado de cada fase (29-09-2026, noche)

| Fase | Estado | Dónde |
|---|---|---|
| 0 — Prueba de kie.ai | **Pendiente, y es lo primero**: la herramienta está hecha, falta correrla con la cuenta real (desde el entorno de desarrollo no se llegaba a kie.ai) | `herramientas/probar_kie.py` |
| 1 — Motor kie.ai | Hecho y probado con un doble de la API (tareas, subidas, errores, sin saldo, recorte). Selector por proyecto, clave en Configuración, prueba de la clave por su saldo, tarifa, coste en pantalla, aviso antes de lanzar sin clave | `motores/imagen_kie/`, `pasos/p6_assets.py`, `pasos/ajustes.py`, `nucleo/coste.py` |
| 2 — Ritmos | Hecho: ritmo «Documental» (7-12 s, media estimada 7,5 s hasta medirla) | `pasos/presets_light.py` |
| 3 — Variedad | Hecho y probado **con el CLI real**: dos guiones seguidos del mismo canal obedecen ganchos y estructuras distintos | `pasos/variedad.py`, `pasos/p3_guion.py` |
| 4 — Producir todo | Hecho: tanda `produccion` y botón «Producir el vídeo»; ficha de publicación probada con el CLI real | `app.py`, `web/app.js`, `pasos/publicacion.py` |
| 5 — Shorts de un largo | Hecho y probado con el CLI real, **con un cambio respecto al plan**: el Short no reutiliza las imágenes del largo (en vertical son otras: el tamaño entra en la huella), reutiliza material y estilo y escribe su propio guion | `crear_short` en `app.py` |
| 6 — Opcional | Sin empezar: voz por kie.ai/ElevenLabs (hay que ver si da marcas por palabra) y un clip de vídeo IA para el gancho de los Shorts | — |

**Cómo usarlo, en cuatro pasos:** Configuración → kie.ai → pega la clave y elige
«kie.ai» para los vídeos nuevos (y el modelo) · crea el vídeo con su estilo y,
si es largo, el ritmo «Documental» · revisa el guion y pulsa «Producir el
vídeo» · debajo del MP4, «Escribir la ficha» y, si quieres, «Sacar un Short».
**Entrada:** `BRIEF-VIDEO-FACTORY-YOUTUBE.md` (v3.0), `PROYECTO-GENERACION-DE-VIDEOS-SHORTS-Y-LARGOS.md`,
`YouTube_Shorts_Factibilidad.docx` y la lectura del código de este repo.

> Los precios de kie.ai que aparecen aquí son **aproximados y sin verificar**: desde el
> entorno donde se escribió esto no se pudo abrir `kie.ai/pricing` ni `docs.kie.ai`.
> La Fase 0 existe precisamente para medirlos contra la cuenta real antes de tocar nada.

---

## 1. Veredicto

**Factible, y adaptar este repo es claramente mejor que construir desde cero.**
El 80 % de lo que piden los documentos ya existe y está probado: guion con Claude,
voz con marcas por palabra, imágenes con estilo y reparto consistentes, movimiento de
cámara sobre imagen quieta, subtítulos, música con ducking, `loudnorm`, formato 16:9
**y 9:16** (ya está: `pasos/comun.py:FORMATOS`), y el motor de firmas que evita volver
a pagar lo que no cambió.

Lo que falta es poco y está bien delimitado:

| # | Qué | Por qué | Esfuerzo |
|---|---|---|---|
| 1 | Motor de imagen **kie.ai** junto al de OpenAI | es donde está el 90 % del gasto | 3-4 días |
| 2 | Un **ritmo "documental"** (planos más largos) para los vídeos largos | es la otra palanca de coste | ½ día |
| 3 | **Memoria del canal** + control de variedad en el guion | la política de "contenido inauténtico" de YouTube | 2-3 días |
| 4 | **"Producir todo"** tras aprobar el guion (un solo punto de revisión) | volumen sin 5 paradas | 2 días |
| 5 | Ficha de publicación (título, descripción, tags, capítulos) | YouTube | 1 día |

**Total: ~2 semanas y media** de trabajo real, frente a las 7-9 semanas del documento
de "construir desde cero" — y sin tirar el motor de firmas, que es lo más valioso.

**Qué NO haría:** reescribir en FastAPI+Next.js (Plan B), clips de vídeo IA por segmento
(ver §4), mover la voz a otro proveedor en la primera fase, ni construir concurrencia
multi-proyecto (ver §6).

---

## 2. Cómo lo hace este repo (lo que hay que entender antes de tocar)

```
ingesta → brief → guion → voz → revision_audio → assets → callouts → render
```

| Paso | Qué hace de verdad | Coste |
|---|---|---|
| `ingesta` | guarda el material (texto que escribes o pegas) | 0 |
| `brief` | cuenta determinista: duración → palabras (`pasos/cadencia.py`) | 0 |
| `guion` | CLI de Claude escribe la narración en bloques | cupo de la suscripción |
| `voz` | Cartesia sonic-3 **con marcas de tiempo por palabra** (SSE) | ~0,23 $ / 4 min |
| `revision_audio` | corta la narración en planos usando esas marcas (`motores/guion/segmentar.py`) | 0 |
| `assets` | una imagen por plano con gpt-image-2 + 8-14 imágenes de referencia | **el grueso** |
| `callouts` | rótulos/cartelas decididos por Claude, rasterizados con Edge | cupo |
| `render` | cámara sobre imagen quieta (`motores/render_video/movimiento.py`), subtítulos, música, `loudnorm`, MP4 | CPU |

**Por qué los vídeos salen bien** (y no hay que perderlo al adaptar):

1. **Sincronía real voz-imagen.** Los cortes caen en las marcas de palabra de Cartesia,
   no en estimaciones. Es lo que hace que parezca editado a mano.
2. **Consistencia visual por referencias.** Cada plano se genera adjuntando, en orden
   fijo: láminas de ESTILO, hojas de REPARTO (personajes del vídeo) y los 1-2 planos
   anteriores (CONTINUIDAD). Así no deriva la paleta ni cambia la cara del protagonista.
3. **Guardianes.** `_planos_repetidos` tumba la tanda si dos planos salen iguales; la
   cartela y los rótulos se deciden antes/después de las imágenes para no pagar de más.
4. **Firmas.** Cada unidad (plano, bloque de voz) tiene un hash de sus entradas.
   Cambiar una frase regenera solo lo que cuelga de ella.

### Dónde se va el dinero hoy (medido en el propio repo)

`CLAUDE.md` y `tarifas.json`: un vídeo de **4 minutos = ~126 imágenes ≈ 4,4 $**. Y lo
decisivo: **el 87 % de ese gasto no es la imagen, son las referencias**, que OpenAI
cobra como tokens de entrada (~5.100 tokens por imagen). La imagen en calidad `low`
cuesta 0,006 $; con sus referencias, 0,047 $.

Dos causas, dos palancas:

- **Precio por imagen con referencias** → kie.ai cobra **tarifa plana por imagen**,
  lleve 1 o 10 referencias. Esto por sí solo elimina el 87 %.
- **Cantidad de imágenes** → 126 imágenes en 4 min es un corte cada ~1,9 s (ritmo
  `medio`/`rapido` de `pasos/presets_light.py:RITMOS`). Para un vídeo largo eso
  escala a 400+ imágenes. Hace falta un ritmo más lento para largos.

---

## 3. Costes proyectados

Supuestos: kie.ai a **~0,02 $/imagen** (Nano Banana / Seedream 4 — *verificar*),
Cartesia a 0,000065 $/carácter (tarifa actual del repo), ~6 caracteres por palabra.

| Vídeo | Ritmo (media por plano) | Imágenes | Imágenes $ | Voz $ | **Total** |
|---|---|---|---|---|---|
| Largo 15 min — **hoy** (OpenAI, ritmo medio) | 2,8 s | ~320 | ~15 | 0,88 | **~16 $** |
| Largo 15 min — kie, ritmo `lento` | 4,3 s | ~210 | ~4,2 | 0,88 | **~5 $** |
| Largo 15 min — kie, ritmo **documental** (nuevo) | ~8 s | ~110 | ~2,2 | 0,88 | **~3 $** |
| Largo 15 min — kie, documental + plano largo reencuadrado | ~8 s de imagen, corte cada ~4 s | ~110 | ~2,2 | 0,88 | **~3 $** |
| Short 60 s vertical — kie, ritmo medio | 2,8 s | ~21 | ~0,42 | 0,06 | **~0,50 $** |
| Short 60 s vertical — kie, ritmo lento | 4,3 s | ~14 | ~0,28 | 0,06 | **~0,35 $** |

El guion y los rótulos van contra la suscripción de Claude (coste fijo). Música: 0 $.

**Truco que ya soporta el repo para no bajar el ritmo visual:** el render hace
`hyperframe` a 2× y mueve una ventana por encima de la imagen, así que **una imagen
puede dar dos cortes** (plano general → detalle). `_planos_repetidos` ya tiene la
excepción "continuación de un plano largo". Esto permite cortar cada 4 s pagando una
imagen cada 8 s. Para aprovecharlo, conviene generar en la resolución más alta que
dé el modelo (Seedream 4 llega a 2K-4K; Nano Banana ~1K), porque el zoom lee píxeles
reales.

**Conclusión de costes:** los objetivos (≤ 3 $ largo, ≤ 0,50 $ Short) se cumplen,
pero **solo combinando kie.ai + un ritmo más lento en largos**. Con kie.ai y el ritmo
actual el largo se queda en ~5 $.

---

## 4. Lo que corregiría de los documentos de entrada

1. **Clips de vídeo IA por segmento (PROYECTO…md, RF-12/13): descartado como base.**
   15 min a 0,05 $/s son **45 $** por vídeo, y además los clips de 5-8 s no se pueden
   sincronizar a palabra ni mantener el reparto consistente como las imágenes con
   referencias. El BRIEF v3 ya lo dejaba fuera; lo confirmo. Uso sensato y opcional
   (Fase 6): **un solo clip de 5-8 s para el gancho de un Short** (~0,30 $).
2. **"Cambiar solo la llamada HTTP" (BRIEF §10.1) es optimista.** kie.ai es distinto a
   OpenAI en tres cosas que obligan a más que un cambio de URL (ver §5).
3. **La voz no se toca en la primera fase.** No por precio (Cartesia es ~0,9 $ en un
   largo) sino porque **toda la sincronía cuelga de sus marcas por palabra**. kie.ai
   ofrece ElevenLabs (Multilingual v2, Turbo, Dialogue v3) y puede salir más barato,
   pero hay que comprobar si su API devuelve timestamps. Si no los devuelve, habría
   que añadir alineación forzada (p. ej. faster-whisper en local) — más piezas.
   Se evalúa en la Fase 6, no antes.
4. **Concurrencia multi-proyecto (BRIEF §10.6): no hace falta.** 50 vídeos/mes son
   ~2 al día. Una cola en serie de ~20-45 min por vídeo sobra. Además `CLAUDE.md`
   regla 2: **las tandas de imágenes van de una en una** (dos a la vez tardan el doble
   por imagen y pierden el registro del gasto). No lo romperíamos.
5. **El modelo de negocio (docx):** YPP pide 1.000 suscriptores + 4.000 h (largos) o
   10 M de vistas de Shorts en 90 días, y el RPM de Shorts es ~0,04 $/1.000. Los
   Shorts sirven para **atraer** al canal; el dinero de AdSense está en los largos.
   Recomiendo priorizar largos y usar Shorts como recortes/avances de ellos.

---

## 5. kie.ai: qué cambia técnicamente

| Diferencia | OpenAI (hoy) | kie.ai | Consecuencia |
|---|---|---|---|
| Modo de llamada | síncrono, devuelve PNG en base64 | **asíncrono**: `createTask` → consultar estado (o callback) → URL del resultado | el motor espera y descarga por dentro; `generar()` sigue devolviendo `(png, meta)` |
| Referencias | se suben como ficheros en la misma petición | **por URL** | subir cada referencia a su API de ficheros (temporales) y **cachear por hash**: las láminas de estilo se repiten en cada plano |
| Nº de referencias | 8-14 por plano | ~8-10 máx. según modelo (*verificar*) | recortar con prioridad: estilo (2-3) > reparto > continuidad (1) |
| Coste | tokens (refs incluidas) | tarifa plana por imagen | adaptar `pasos/ajustes.py` (`TOKENS_ENTRADA_POR_IMAGEN`) y `tarifas.json` para que la pantalla no enseñe un coste falso |
| Proporciones | 3:2 y 2:3 | 3:2 y 2:3 disponibles en Nano Banana/Seedream (*verificar*) | se mantienen: el render ya espera `generacion` 1536×1024 / 1024×1536 |

**Modelo a elegir en la Fase 0** (candidatos, precios aproximados):

- **Seedream 4** (~0,02 $): acepta varias referencias, resolución alta (bueno para el
  reencuadre). Primer candidato para largos.
- **Nano Banana** (~0,02 $): muy bueno siguiendo referencias de estilo/personaje.
- **Nano Banana Pro** (~0,09 $): más calidad; solo si los dos anteriores no sostienen
  el estilo del canal.
- **GPT Image vía kie**: el más parecido al resultado actual; útil como control.

### Cómo encaja sin romper el grafo ni las firmas

- **Motor nuevo `motores/imagen_kie/imagen.py`** con la **misma interfaz** que usa
  `pasos/p6_assets.py` y `pasos/moodboard.py`: `generar(prompt, referencias, quality=,
  tamano=)`, `generar_lote`, `normalizar`, `gasto`, `cargar_api_key`,
  `cuentas_para_la_pantalla`, excepción `SinSaldo`. Lee la clave de
  `secretos/claves.json` por contrato, como los demás motores.
- **El selector ya existe**: `p6_assets.PARAMS_POR_DEFECTO["motor_imagen"]`
  (`openai | adoptar`). Se añade `kie`, y los ~8 sitios que hacen
  `medios.motor("imagen_openai/imagen.py")` pasan por una función
  `_motor_imagen(p)` que elige según el param.
- **Regla 1 de `CLAUDE.md`:** `motor_imagen: "kie"` se escribe **al crear el proyecto**
  (igual que `calidad`), nunca como defecto retroactivo. Los proyectos existentes
  siguen en OpenAI y no se vuelven obsoletos.
- **La huella de la caché de imágenes** (`p6_assets.py:~2948`) hoy no incluye el
  motor. Se añade `"motor": motor if motor != "openai" else None` — el mismo patrón
  que ya usa `tamano` — para que la caché no confunda una imagen de OpenAI con una de
  kie y **las firmas de los proyectos viejos no se muevan**.
- **`nucleo/` no se toca.**

---

## 6. Variedad: que YouTube no lo lea como "contenido inauténtico"

Desde julio de 2025 la política castiga lo **plantillado y repetitivo a nivel de
canal**, no el uso de IA. El repo ya ayuda (tono, ritmo, reparto y estilo por vídeo;
material escrito por ti), pero no tiene memoria entre vídeos. Propuesta, sencilla:

1. **Memoria del canal** — un JSON por ESTILO (`proyectos/_canal/<estilo>.json`, fuera
   de las firmas) que al terminar cada render apunta: título, tipo de gancho,
   estructura narrativa, primera frase, sets/escenarios usados, música.
2. **Catálogo de ganchos y estructuras** (pregunta, dato, contraintuitivo, "in medias
   res", cronológico, problema→causa→solución, lista, misterio…). El guion recibe
   "los últimos 10 vídeos usaron X, Y, Z: elige otro".
3. **Pasada crítica** (el Critic del brief) **dentro del mismo paso `guion`**, no como
   paso nuevo del grafo: comprueba gancho ≤ 3 s, resets de atención cada 2-3 min en
   largos, y parecido con los últimos N vídeos. Si falla, reescribe una vez.
4. **Rotación visual**: 2-3 ESTILOS por canal que se alternan, y paleta de música
   rotativa. El repo ya soporta varios estilos.
5. **La parte humana que ningún código sustituye**: el material/ángulo lo escribes tú
   (`ingesta.texto`). Es lo que YouTube llama "perspectiva original". Un canal que
   solo pega un tema y pulsa un botón es exactamente el perfil que revisan.
6. **Divulgación**: marcar "contenido alterado o sintético" al subir cuando haya
   personas/escenas realistas. Con estilo ilustrado normalmente no aplica.
7. **Cadencia**: 2-4 largos/semana + 1 Short/día es un volumen seguro. 10+ al día,
   no.

---

## 7. Flujo propuesto: "Fábrica supervisada" (un solo punto de revisión)

```
[Tú] tema + material + ángulo  →  guion (Claude + pasada crítica)
                                       │
                          ┌── REVISAS Y EDITAS EL GUION ──┐   ← única parada obligatoria
                          │    (gasto hasta aquí ≈ 0 $)   │
                          └───────────────┬───────────────┘
                                          ▼  "Producir todo"
          voz → revision_audio → assets (kie) → callouts → render → ficha de publicación
                                          ▼
                             [Tú] ves el MP4 y lo subes
```

- No es un modo nuevo: es **un botón** que encadena las recetas que ya existen
  (`pasos/recetas.py`, "Generar lo pendiente") de las pestañas siguientes. Las
  paradas de siempre siguen ahí para quien quiera usarlas.
- Si una imagen sale mal, se regenera **solo esa** (firmas).
- **Ficha de publicación** al final del render: título (3 opciones), descripción con
  capítulos (salen gratis de los bloques del guion y de las marcas de voz), tags.
  Se escribe un `publicacion.txt` junto al MP4. Subida automática: no en esta fase
  (la API de YouTube exige auditoría para publicar en público).
- **Shorts desde un largo**: segunda fase natural — tomar un bloque de 45-60 s del
  guion de un largo, re-encuadrar en 9:16 reutilizando las MISMAS imágenes (coste de
  imagen ~0) y locución propia con gancho nuevo.

---

## 8. Plan por fases

| Fase | Entregable | Criterio de salida | Días |
|---|---|---|---|
| **0 — Prueba de kie.ai** | `herramientas/probar_kie.py`, suelto: coge 20 planos de un proyecto real (mismo prompt, mismas referencias) y los genera con 2-3 modelos de kie | coste real por imagen, latencia, límite de referencias, y **tú** decides si el estilo aguanta. Si no aguanta: se para aquí | 1 |
| **1 — Motor kie** | `motores/imagen_kie/`, selector `motor_imagen`, clave en Configuración + `comprobar_claves`, fila en `tarifas.json`, coste correcto en pantalla | un vídeo de 2 min generado de punta a punta con kie; proyectos viejos siguen `listo` | 3-4 |
| **2 — Ritmos** | ritmo `documental` (6-10 s) y ajuste del Short; generar a la resolución alta del modelo | un largo de 10 min ≤ 3 $ | ½-1 |
| **3 — Variedad** | memoria del canal + catálogo de ganchos + pasada crítica en `guion` | 5 guiones seguidos del mismo canal con ganchos y estructuras distintos | 2-3 |
| **4 — Producir todo** | botón tras el guion + ficha de publicación | del guion aprobado al MP4 sin tocar nada | 2-3 |
| **5 — Shorts de un largo** | re-encuadre 9:16 de un bloque, reutilizando imágenes | Short ≤ 0,15 $ extra | 2 |
| 6 — Opcional | ElevenLabs vía kie (si da timestamps) · clip de vídeo IA para ganchos | A/B de calidad frente a Cartesia | — |

Tras cada fase: `pruebas.ps1` en verde, herramientas de análisis limpias, y **abrir la
interfaz** (regla de `CLAUDE.md`).

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| El modelo de kie no sostiene el estilo/reparto como gpt-image-2 | Fase 0 decide antes de escribir código; OpenAI queda como motor alternativo por proyecto |
| kie.ai es intermediario (caídas, cambios de precio o de API) | el motor está aislado detrás de un contrato; volver a OpenAI es cambiar un param en proyectos nuevos |
| Menos referencias por imagen → deriva visual | prioridad fija estilo > reparto > continuidad; medir con `_planos_repetidos` y a ojo en la Fase 0 |
| Cupo de la suscripción de Claude a 50 vídeos/mes | guion + rótulos ≈ pocas llamadas por vídeo; `salud_cli` ya avisa del cupo; cadena de cuentas de respaldo existente |
| Política de YouTube | §6; y material/ángulo humano en cada vídeo |
| Precios que cambian | `tarifas.json` como única fuente, nunca en el código |
