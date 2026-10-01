# Un módulo para estudiar lo que funciona: qué construir y qué no

Análisis del 01-10-2026, pedido para «ver los mejores canales del nicho, revisar
sus vídeos, extraer el guion y saber cuánto monetizan».

## Lo primero: ya pagas una herramienta que hace la mitad de esto

FoziQ (foziscribe.ai) ya da Spy Video, Spy Channel, Spy Competitors, Outliers,
Trends y Keyword Research, con el plan Growth activo. **Construir eso dentro del
Estudio es reinventar la rueda, que es justo lo que no se quería hacer.**

Lo que FoziQ NO hace, y nadie más va a hacer, es **unir lo que descubres con lo
que produces**. Te dice que un vídeo hizo 10 M; no te ayuda a escribir el tuyo
con lo que aprendiste. Ese es el hueco, y es pequeño de construir.

## Lo que ya está hecho en el repo (y abarata todo)

- **`p3_guion` digiere transcripciones con tiempos.** Lee
  `[{t_in, t_out, texto}]`, las formatea como `[00:12] texto` y aguanta 120.000
  caracteres (`max_caracteres_transcript`). Es exactamente el formato de unos
  subtítulos de YouTube.
- **`p1_ingesta` tiene el sitio reservado**: su docstring explica que el formato
  `transcript` existe y que aquí se escribe con tiempos a cero porque el
  material es texto. Rellenarlos es rellenar un hueco que ya está dibujado.
- **La receta todavía anuncia** «baja el vídeo y los subtítulos» (`recetas.py`),
  texto que quedó de cuando esto existía.

## Lo que NO se puede saber, por mucho que se construya

**Los ingresos reales de un canal ajeno no los publica nadie.** Todas las
estimaciones —incluida la de FoziQ— son `visitas × un RPM supuesto`. Por eso su
propia pantalla dice «$2.0K – $56K» con la nota de que la banda es ancha porque
«the rate a video actually earns is not published». Un rango de 28x no es un
dato, es una forma elegante de no saber.

**Nosotros podemos estimar mejor que eso**, y es el único sitio donde tiene
sentido competir con una herramienta de pago: tenemos
[NICHOS-Y-CPM.md](NICHOS-Y-CPM.md), con RPM medianos leídos de YouTube Studio
en 300 canales reales y su rango P25–P75. Multiplicar las visitas por el RPM
mediano del nicho, y enseñar la banda P25–P75 en vez de un número, da una
estimación con procedencia. Sigue siendo una estimación, pero se sabe de dónde
sale.

## El riesgo de «copiarnos», que es de negocio y no moral

Copiar la **estructura** —el tipo de gancho, cada cuánto re-enganchan, cómo
ordenan la información, qué prometen en los primeros quince segundos— es lo que
hace todo el mundo y es de donde sale el aprendizaje.

Copiar el **guion literal** es otra cosa: YouTube lo trata como contenido
reutilizado y es causa de desmonetización, además del problema de derechos. El
canal es el activo; no vale la pena.

**Consecuencia de diseño:** el módulo NO guarda el guion ajeno para reescribirlo.
Guarda una RECETA destilada —estructura, ritmo, tipo de gancho— y tira el texto.
Es más útil y además evita la tentación.

## Qué construir, por fases

### Fase 1 — «Analizar un vídeo de referencia» (lo que de verdad hace falta)

Pegas una URL de YouTube y el Estudio:

1. Baja metadatos con la **YouTube Data API v3** (oficial y gratis).
2. Baja los **subtítulos** (son el guion, dichos por el propio canal).
3. Un paso nuevo llama al CLI —**gratis, por suscripción**— y destila la receta:
   dónde está el gancho y qué promete, cuándo lo cumple, cada cuántos segundos
   cambia de tema, cuánto dura una frase, dónde re-engancha, cómo cierra.
4. Guarda esa receta en el banco y permite **inyectarla en
   `guion.prompt_general`** del proyecto que estés escribiendo.

Ese último punto es el que no tiene FoziQ y es el que convierte la
investigación en producción.

### Fase 2 — Biblioteca por nicho y estimación con procedencia

Varias recetas guardadas por nicho, y la estimación de ingresos cruzando las
visitas con la tabla de RPM medianos.

### Fase 3 — Descubrimiento de canales: NO

Buscar los mejores canales de un nicho es exactamente FoziQ. Mientras el plan
esté pagado, se pega la URL y listo.

## Lo técnico, sin sorpresas

| Pieza | Cómo | Límite |
|---|---|---|
| Metadatos del vídeo y del canal | YouTube Data API v3, `videos.list` | 1 unidad por llamada, 10.000/día gratis |
| Buscar | `search.list` | **100 unidades** por llamada: solo 100 búsquedas/día |
| Subtítulos | `youtube-transcript-api` (pip) o `yt-dlp` | No es API oficial: puede romperse |

La cuota gratuita da de sobra: 10.000 vídeos consultados al día.

**Dos avisos:**

- **Scrapear la web de YouTube viola sus condiciones.** La Data API no. Todo lo
  que se construya debe ir por la API oficial, con su clave de Google Cloud.
- **Los subtítulos no van por API oficial.** Conviene aislar esa pieza detrás de
  una función para que, el día que rompa, se cambie en un solo sitio.

## Esfuerzo

La Fase 1 es un paso nuevo, una ruta y una tarjeta en la pantalla. Reutiliza la
digestión de transcripciones que ya existe y no toca el grafo: **la receta no es
un paso del grafo**, es un dato del banco que se inyecta en `prompt_general`,
igual que la memoria del canal o la ficha de publicación.

No cuesta dinero de generación: metadatos y subtítulos son gratis, y el análisis
va por la suscripción del CLI.
