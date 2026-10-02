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

## Gemini lee el vídeo entero, y eso cambia el módulo

Probado el 01-10-2026 contra el vídeo de 10 M de Ink Explainer. **La API de
Gemini acepta una URL de YouTube como entrada** y procesa imagen y audio:
61.158 tokens de vídeo en una sola llamada, dentro de la capa gratuita.

Resuelve de golpe los dos problemas que teníamos:

- **El bloqueo.** No hace falta yt-dlp ni bajar nada, así que da igual que la
  IP esté marcada.
- **El ritmo visual**, que con subtítulos NO se puede saber. Gemini lo ve.

### Lo que midió, y por qué importa

| | |
|---|---|
| Cortes por minuto de Ink Explainer | **18**, o sea un plano cada **3,3 s** |
| Nuestro ritmo `documental` | 8,9 s por plano |

Van **2,7 veces más rápido**. Con un matiz que decide el dinero: ellos son
ANIMACION y un corte no les cuesta nada; aquí cada cambio de plano es una
imagen pagada. Igualar su ritmo llevaría un vídeo de 10 minutos de 80 planos
(4,00 $) a 182 (9,10 $).

**La salida es Progressive Rhythm**: ritmo rápido solo en el primer minuto, que
es donde se pierde a la gente, y 7-12 s después. Unos 15 planos extra, 0,75 $.

### Y el gancho, que los subtítulos escondían

Gemini describió los primeros quince segundos: despertador, ciudad agobiada,
trabajo atado al reloj, dormir, salto de 50.000 años. Una secuencia montada,
no una frase.

Leyendo solo la transcripción, la lección parecía «abre en segunda persona».
Viendo el vídeo, la lección real es **«abre con un montaje rápido de la vida
del espectador antes de decir nada del tema»**. Esa diferencia justifica el
motor entero.

### Lo que cuesta

Capa gratuita: solo Flash y Flash-Lite, ~1.500 peticiones al día, 8 horas de
vídeo de YouTube diarias. Pro es de pago desde abril de 2026.

**Veo (generar vídeo) NO tiene capa gratuita por API**: 0,10-0,40 $ por segundo,
o sea 0,80-3,20 $ por un clip de ocho segundos, frente a 0,05 $ de una imagen
fija. Un clip cuesta entre 16 y 64 imágenes, así que solo sale a cuenta en el
GANCHO. Flow (la web) sí da créditos gratis con cada cuenta de Google: generar
ahí a mano un clip para el arranque y traerlo es la via barata.

## La API oficial de YouTube: lo que había que haber hecho desde el principio

Añadido el 01-10-2026, después de que el usuario preguntara por qué no se usaba
una clave si «una vez hice un HTML simple y con una clave veía canales por
nichos». Tenía razón.

**El módulo se construyó primero con yt-dlp** —que lee la web de YouTube— para
no pedir otra clave. Resultado: las dos funciones más útiles, buscar canales de
un nicho y mirar un canal entero, fueron las dos únicas que nunca llegaron a
funcionar, porque YouTube bloquea la IP.

**La YouTube Data API v3 no se bloquea.** Es oficial, da 10.000 unidades diarias
gratis y los datos vienen en vivo. Medido sobre el mismo vídeo con unas horas de
diferencia: yt-dlp devolvió 10.004.773 visitas y la API 10.057.760.

### Cómo se consigue la clave

Se habilita **«YouTube Data API v3»** en un proyecto de Google Cloud y vale la
misma clave del proyecto. **OJO AL MENSAJE DE ERROR**: si la API no está
habilitada, Google contesta un 401 que dice «API keys are not supported by this
API». Despista mucho — parece que la clave está mal, y lo que pasa es que a ese
proyecto todavía no le han abierto esta puerta.

### Lo que cuesta cada cosa, y cómo se ahorra

| Llamada | Unidades | De las 10.000 diarias |
|---|---|---|
| `search.list` (buscar) | **100** | 100 búsquedas |
| `videos.list` | 1 | 10.000 vídeos |
| `channels.list` | 1 | 10.000 canales |

Buscar es cien veces más caro que consultar, así que **se busca UNA vez y luego
se piden los datos de todos los resultados DE GOLPE**: las dos listas admiten
hasta 50 ids por llamada. `canales_del_nicho` gasta 101 unidades por búsqueda y
no 1.100.

### Y la métrica que hace útil todo esto

`canales_del_nicho` ordena por **vistas por vídeo**, no por suscriptores. Es lo
que de verdad dice dónde estás parado. Medido en el nicho de historias bíblicas
para niños:

| Canal | Subs | Vídeos | Por vídeo |
|---|---|---|---|
| Mi Primera Biblia | 1,21 M | **142** | **2.271.123** |
| Minno Español | 75.800 | **26** | **536.802** |
| Mi Pequeña Biblia | 688.000 | 762 | 228.098 |
| La Biblia con Abi | 19.800 | **12** | 127.206 |

**Minno tiene nueve veces menos suscriptores que Mi Pequeña Biblia y hace el
doble por vídeo.** Los dos canales más eficientes del nicho tienen 26 y 12
vídeos; el de 762 rinde menos que ambos. Mirando solo los suscriptores no se ve
nada de esto.

### El reparto final

| Pieza | Quién la hace |
|---|---|
| Números de un vídeo, nichos, canales | **YouTube Data API** (oficial, no se bloquea) |
| Ver el vídeo: gancho visual y ritmo | **Gemini** (capa gratuita) |
| Transcripción | yt-dlp, o pegada a mano |
