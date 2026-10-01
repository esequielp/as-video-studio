# Estilos del canal de historias bíblicas — qué se creó y por qué

**Fecha:** 29-09-2026. Cuatro estilos pensados para un mismo canal de historias
bíblicas, cada uno para una audiencia o un formato distinto. Las imágenes de
referencia de los cuatro se generaron con kie.ai (`google/nano-banana`, modo
texto a imagen, calidad `low`, 4 créditos = 0,02 $ por imagen — precio medido
de verdad, ver «kie.ai» en `CLAUDE.md`).

No son un catálogo cerrado: cada estilo se puede corregir eje por eje sin
rehacerlo entero (Configuración del estilo → Regenerar), y nada impide crear
un quinto si un formato nuevo lo pide.

**Actualización del mismo día:** las cuatro imágenes de referencia se
generaron con `google/nano-banana`. Comparado luego contra
`gpt-image-2-image-to-image` (el modelo de OpenAI **revendido por kie.ai**, no
la vía directa) con el mismo prompt, GPT Image 2 sale con mucha más ropa,
fondo y expresión de la que nano-banana entrega — y se parece bastante más a
referencias reales del género (capturas de canales como los que citan la
sección 4). Cuesta 0,03 $/imagen (6 créditos, verificado contra la cuenta
real) frente a 0,02 $ de nano-banana — un 50 % más, pero sigue siendo **36 %
más barato que llamar a OpenAI directamente** (0,047 $/imagen a calidad
`low`, por el recargo de las referencias que kie.ai no cobra). Ver la
sección 4 para el detalle y las imágenes de la comparación.

---

## 1. Por qué un cuarto estilo: lo que dice la investigación

El primer encargo fue "niños / jóvenes / adultos" — tres tonos narrativos
sobre el mismo tipo de vídeo (una historia contada de principio a fin). El
cuarto estilo, **Parábolas en Trazo**, no es una cuarta audiencia: es un
**formato distinto**, copiado a propósito de lo que ahora mismo funciona
mejor en YouTube fuera del nicho religioso.

**Lo que se investigó (29-09-2026):**

- Los canales de finanzas "sin cara" que usan animación de **figuras de palo
  (stick figure)** sobre fondo plano crecen con fuerza en 2026 — el ejemplo
  citado en las búsquedas es **Casual Finance**. El formato funciona porque el
  espectador sigue la explicación, no a quien la cuenta: la animación simple
  no resta autoridad.
- El nicho de finanzas "faceless" mueve un **RPM de 10-15 $ y un CPM de
  15-22 $**, muy por encima de la media de YouTube — la referencia es que a
  100.000 suscriptores puede suponer 5.000-10.000 $/mes solo de AdSense.
- El minimalismo no es un ahorro de producción disfrazado de estética: **es
  lo que sostiene la retención** — sin detalle que distraiga, la atención va
  al concepto. Encaja además con la regla de coste de este repo (menos
  detalle por plano, mismo precio plano de kie.ai).
- El otro extremo del mismo fenómeno son las **motion graphics** (formas,
  iconos y tipografía sin personajes), que se perciben "serias" sin ser
  solemnes — está más para contenido tipo fintech/B2B que para narrar una
  historia, así que no se copió para este canal.

**Fuentes:**
- [Best Faceless Finance YouTube Channels 2026: 7 Examples](https://shortsfast.com/blog/best-faceless-finance-youtube-channels-2026/)
- [15 Faceless stick figure animation channels: Examples and video ideas](https://facelesslist.com/categories/stick-figure-animations/)
- [20 Popular Styles of Video Animation | Breadnbeyond](https://breadnbeyond.com/articles/creative-video-animation-styles/)
- [Explainer Video Styles: A Complete Guide for 2026 | Pexo](https://pexo.ai/blog/explainer-video-styles-3897)

**La aplicación al canal:** un formato "esto no lo sabías de..." corto y
directo, bueno para Shorts y para captar audiencia que nunca buscaría
"historias bíblicas" pero sí se detiene ante un dato contado rápido y claro.
No sustituye a los otros tres — es la puerta de entrada.

---

## 2. Los cuatro estilos

### Arca y Belén (niños)
- **Para quién:** niños de 6-8 años.
- **Dirección visual:** cuento ilustrado infantil, formas redondeadas,
  colores planos muy saturados y cálidos, ojos grandes y expresivos, sin
  sombras duras ni violencia visible, luz suave de mañana.
- **Tono:** como quien le cuenta la historia a un niño sentado en las
  rodillas — frases cortas, alguna pregunta retórica, repetición cariñosa; el
  miedo se nombra pero nunca se detalla, y siempre cierra con calma.
- **Ritmo:** Lento (~4,3 s/plano).
- **Voz elegida:** Liliana - Doting Mother.
- **Estado:** listo, con sus 6 muestras.

### Génesis Urbano (jóvenes)
- **Para quién:** adolescentes / veinteañeros.
- **Dirección visual:** novela gráfica semi-realista, alto contraste, luces
  dramáticas (contraluces, neón sutil), composiciones dinámicas en diagonal,
  proporciones estilizadas.
- **Tono:** directo y sin condescendencia — plantea el conflicto humano antes
  que la moraleja, conecta con identidad, presión social, miedo a fallar: la
  fe como decisión difícil, no como respuesta automática.
- **Ritmo:** Rápido.
- **Voz elegida:** Alonso - Podcast Explainer.
- **Estado:** listo, con sus 6 muestras — costó 9 intentos y dos arreglos de
  código (apartado 3) hasta que salió bien.

### Escrituras (adultos)
- **Para quién:** adultos.
- **Dirección visual:** pintura al óleo de aire cinematográfico, pinceladas
  visibles, paleta terrosa (ocres, sienas, azules profundos), claroscuro de
  una sola fuente de luz, composiciones quietas y contemplativas, detalle
  histórico en vestuario y arquitectura.
- **Tono:** reflexivo y literario — reconoce la complejidad moral del relato
  en vez de simplificarla, aporta contexto histórico y cultural, invita a
  pensar más que a concluir.
- **Ritmo:** Documental (7-12 s/plano) — el más barato, y el que mejor casa
  con un tono contemplativo.
- **Voz elegida:** Alejandro - Calm Mentor.
- **Estado:** listo, con sus 6 muestras. (Tuvo un bug de codificación en la
  vista previa, corregido — ver apartado 3.)

### Parábolas en Trazo (explicador)
- **Para quién:** audiencia general / formato Shorts, puerta de entrada al
  canal.
- **Dirección visual:** vector plano minimalista tipo explicador (motion
  graphics): personajes stickman de cabeza redonda y cuerpo simple, sin
  rasgos faciales detallados, colores planos sin degradados, contorno fino
  oscuro, paleta apagada (azul marino, oliva, mostaza dorado) sobre fondo
  beige cálido liso. Iconos limpios y reconocibles al instante.
- **Tono:** formato "esto no lo sabías" — gancho en los primeros 2 segundos,
  frases cortas y declarativas, un dato o giro por bloque, sin rodeos
  narrativos. Respetuoso con el tema, nunca sensacionalista.
- **Ritmo:** Rápido.
- **Voz elegida:** Alonso - Podcast Explainer.
- **Estado:** listo, con sus 6 muestras.

---

## 3. Fallos encontrados en el camino, y qué se hizo

- **Mojibake en la vista previa de un estilo** (`pasos/p7_callouts.py`,
  `previsualizar`): el HTML compuesto para las muestras de un estilo no
  declaraba `<meta charset="utf-8">`, así que Edge a veces adivinaba mal la
  codificación y una tilde salía como "Ã³" en vez de "ó" — visto en
  "Escrituras", 29-09. El render REAL del vídeo (`p8_render.PAGINA`) ya
  declaraba la codificación, así que ningún vídeo terminado tuvo este fallo,
  solo la pantalla de revisión. **Corregido**: se añadió el `<meta charset>`
  y además se envolvió el par `rasterizar` + `_comprobar_previa` en el mismo
  reintento que ya usa `rasterizar` (`medios.INTENTOS_RASTERIZAR`), porque
  antes un fallo de ESTE tipo (Edge "acierta" pero deja su página de error)
  no se beneficiaba de ningún reintento. Verificado con `prueba_pasos_visuales.py`
  (229/229) y con una reproducción manual de la escena exacta que falló.
- **Un taller que no terminaba** (`taller_genesis_urbano_jovenes`): el paso
  gratuito de montar la vista previa falló 8 veces seguidas, el mismo punto
  del progreso cada vez, incluso reiniciando el servidor. Terminó saliendo
  bien con el arreglo de abajo (falso positivo del guardián) más el reintento
  ya descrito arriba — no hizo falta tocar nada más específico de este
  taller. Si algún día vuelve a pasar algo parecido y ESTO no lo explica,
  sigue siendo sospechoso cómo `GestorTrabajos` lanza la tarea (hilo propio,
  no el principal) y si eso le afecta a `subprocess` en Windows.
- **El guardián contra la página en blanco daba falsos positivos con un
  estilo de fondo claro** (`pasos/p7_callouts.py`, `_comprobar_previa`): el
  chivato miraba SOLO el color del píxel [5,5] — si salía casi blanco
  (`min(rgb) > 200`), lo daba por la página de error de Edge. Con un estilo
  de fondo oscuro o de ilustración detallada eso basta, pero **"Parábolas en
  Trazo" tiene fondo beige de punta a punta**, así que su esquina real
  (230-243 de media) caía dentro del mismo umbral que una página de error de
  verdad (~254) — tumbaba una muestra perfectamente buena. Medido: las seis
  láminas del estilo tienen la esquina por encima de 200 en al menos cuatro
  de los seis casos.
  **Corregido**: en vez de un píxel, se mide la varianza de TODA la imagen
  (`numpy`, ya es dependencia del repo). Una página de error de Edge es casi
  perfectamente plana de punta a punta (variación por debajo de 5 medida a
  mano); un cuadro real SIEMPRE varía en algún punto —la cartela, el
  subtítulo, el propio dibujo— sin importar lo claro que sea el fondo. El
  umbral nuevo (`UMBRAL_VARIACION_PREVIA = 15.0`) tiene de sobra margen: los
  fondos planos de este estilo miden 45-56 de variación total. Verificado
  regenerando las 6 muestras reales de "Parábolas en Trazo" (antes fallaban
  siempre; con el arreglo, 6/6 a la primera) y las de "Génesis Urbano" (antes
  fallaban 8/8; con el arreglo, a la primera). `prueba_pasos_visuales.py`
  sigue en 229/229.

**Importante para quien retome esto:** los dos arreglos de
`pasos/p7_callouts.py` solo se cargan al **reiniciar** `app.py` — Python no
recarga un módulo en caliente. Si un estilo con fondo claro sigue fallando
igual que antes, lo primero es comprobar que el servidor arrancó DESPUÉS de
este cambio.

---

## 4. GPT Image 2 vía kie.ai: se añadió como modelo, y gana en escenas narrativas

Las imágenes de referencia de los cuatro estilos se generaron con
`google/nano-banana` (kie.ai). Al comparar el resultado con capturas reales
del género que se quiere imitar (vídeos cortos de "esto no sabías de..." con
personajes de cara simple pero ropa y escena completas), el parecido no era
bueno: nano-banana entrega una cara más plana, sin ropa detallada, con fondos
pobres. El motivo no es que kie.ai en sí sea peor: es que **nano-banana no es
el único modelo bueno que kie.ai revende**, y no se había probado ningún otro
para este tipo de escena.

**Se añadió `gpt-image-2-image-to-image` a `motores/imagen_kie/modelos.json`**
(y su precio a `tarifas.json`) — es el **mismo GPT Image 2 de OpenAI, pero
revendido por kie.ai a tarifa plana**, no la vía directa a OpenAI que ya usa
`motores/imagen_openai`. El contrato (`campo_referencias: input_urls`, hasta
16 referencias, `aspect_ratio` con los mismos valores `3:2`/`2:3`/`1:1` que ya
usa el resto del Estudio, `resolution` 1K/2K/4K) sale de
`docs.kie.ai/market/gpt/gpt-image-2-{text,image}-to-image`, y **se probó
contra la cuenta real**: 6 créditos (0,03 $) por imagen a 1K, exactos en las
dos llamadas de prueba — coincide con lo que dice `kie.ai/gpt-image-2`.

**La comparación** (mismo prompt exacto, un joven en un patio soleado y un
anciano preocupado en una puerta, calidad `low`, sin referencias):

| | nano-banana | GPT Image 2 (kie.ai) |
|---|---|---|
| Precio | 0,02 $/imagen | 0,03 $/imagen (+50 %) |
| Cara | simple, casi sin rasgos | expresiva, con cejas y mirada reales |
| Ropa | plana, poco detalle de pliegues | túnica con pliegues, sombreado real |
| Fondo | ilustración plana | escena completa (columnas, plantas, luz) |
| Parecido al género buscado | bajo | alto — el del anciano casi calca la referencia real que trajo el usuario |

**Conclusión: para los estilos narrativos de este canal (niños, jóvenes,
adultos — cualquiera que cuente una escena con personajes vestidos, no solo
iconos), `gpt-image-2-image-to-image` es la mejor opción dentro de kie.ai.**
Sigue siendo **36 % más barato que llamar a OpenAI directamente**
(0,047 $/imagen a `low`, con el recargo de referencias que kie.ai no cobra) y
sale mucho más parecido a la referencia real que nano-banana. Para
"Parábolas en Trazo" (el explicador de iconos planos) nano-banana probablemente
sigue bastando, porque ahí el objetivo es justo la simplicidad — no se ha
comparado ese caso todavía.

**Pendiente:** las cuatro imágenes de referencia de los cuatro estilos
existentes se generaron con nano-banana, antes de esta comparación. Si el
resultado no convence al mirarlas con ojo crítico, se pueden regenerar con
`gpt-image-2-image-to-image` (mismo procedimiento, cuesta 0,03 $ x 4 imágenes
por estilo en vez de 0,02 $). No se ha hecho todavía porque implica volver a
generar y aprobar cada estilo — se deja anotado para decidir con el usuario.

---

## 5. El rehacer con personaje fijo "stickman", y la duda que dejó abierta

**Qué se hizo (30-09-2026):** los tres estilos narrativos se rehicieron desde
cero con un PERSONAJE RECURRENTE FIJO por audiencia, en vez de tres estéticas
distintas. El diseño salió del prompt maestro del usuario ("HISTORIAS
BÍBLICAS"), que define tres personajes —El Curioso (niño), El Buscador (joven),
El Guía (adulto)— compartiendo lenguaje visual: cabeza redonda enorme, ojos
ovalados negros, manos de manopla negra, extremidades finas, cel shading.

El procedimiento que funcionó, y que conviene repetir:

1. Generar UNA hoja de personajes con el prompt maestro completo
   (`gpt-image-2-image-to-image`, calidad `medium`, 0,05 $).
2. Con esa hoja **como imagen de referencia** (`--ref`), sacar las 4 láminas
   individuales de cada personaje (cara, cuerpo, escena, objeto). Esto es lo
   que da consistencia real: describir el estilo otra vez con palabras deriva,
   pasar la imagen no.
3. Subir esas 4 al buzón y crear el estilo.

Presets resultantes: niños `pr1a0f3232df6`, jóvenes `pr1a0f32b55f5`,
adultos `pr1a0f3315203`.

**LA DUDA, Y ES DE PRODUCTO, NO DE CÓDIGO.** Lo que salió no es un stickman:
es una CARICATURA INFANTIL. El propio prompt maestro pide "premium 2D
animated", "clean cel shading", "anime-inspired eyes", "charming",
"family-friendly", y solo menciona *stickman-like bodies* — así que el modelo
hizo lo correcto con lo que se le pidió. El efecto es que **los tres estilos se
leen como contenido para niños**: un adulto ve ojos enormes y cara redonda y lo
clasifica ahí, por muy adulto que sea el guion ("reflexivo y literario").

Un stickman DE VERDAD (figura de línea, sin sombreado, cara mínima) es
age-neutral precisamente porque es abstracto: no tiene ternura que señale edad.
Es la razón por la que los canales de finanzas para adultos lo usan (ver
sección 1). Si se toma ese camino, la diferencia entre audiencias no la lleva
el dibujo sino el tono, el ritmo, la paleta y el fondo — que es donde de verdad
se nota.

Queda por decidir. Los tres presets actuales sirven de comparación y se
descartan sin coste si se cambia de rumbo.

---

## 6. Dos trampas operativas que cuestan una tarde

- **El buzón de imágenes es de UN SOLO USO.** `_sembrar_aportadas` copia las
  imágenes subidas dentro del taller y **las borra del buzón**
  (`proyectos/_imagenes_aportadas/`). Si el intento falla y se reintenta con
  los MISMOS nombres, ya no existen: `_rutas_aportadas` devuelve vacío y el
  paso de la guía muere con «hacen falta al menos 3 fotogramas para escribir
  una guia de estilo». **Hay que volver a subirlas antes de cada reintento.**
- **«Retomar» no detecta que cambiaron las imágenes de origen.**
  `_light_hecha` da por hecha la tarea `referencias` si en los params hay
  cualquier ruta con «dibujadas» dentro — mira el RESULTADO, no la ENTRADA.
  Así que retomar un taller con imágenes nuevas deja aportadas nuevas y
  moodboard viejo, y termina en 0,1 s diciendo «listo». Para rehacer un estilo
  con otro material hay que **crear un preset nuevo** y descartar el viejo
  (`POST /api/presets-light` sin `taller`). El endpoint `regenerar` con
  `parte: "estilo"` y `origen` sí lo hace bien, pero **solo si el taller sigue
  en el disco** — y el taller se limpia al promocionarse a preset, así que
  para un preset ya terminado devuelve 409.
- **Restaurar un preset apartado**: `POST /api/presets-canal/papelera/{pid}/restaurar`.
  Útil porque un preset puede acabar en la papelera sin que nadie lo borre a
  mano (pasó con dos, al rehacer talleres con el mismo nombre).

## El moodboard se dibuja a `medium`, no a la calidad de Configuración

Medido el 2026-09-30 creando «Arca y Belén (jóvenes y adultos)»: con
Configuración en `low` y kie/gpt-image-2, la tanda de 6 láminas gastó **60
créditos (0,30 $)**, no los 36 que salen de multiplicar 6 × la tarifa de `low`.

La causa es que `pasos/moodboard.py:441` fija `calidad="medium"` y no lee el
ajuste. **Es correcto y no hay que "arreglarlo"**: las seis láminas son la
referencia que después copia CADA plano del vídeo, así que se dibujan a 2K
aunque los planos salgan a 1K. Una referencia borrosa se paga en los 126 planos
que la copian.

Lo que sí engaña es la previsión: `/api/presets-light/plan` devuelve
`imagenes: 6` sin decir a qué calidad, y quien las multiplique por la tarifa de
Configuración se queda corto casi el doble. **Un estilo nuevo cuesta 0,30 $ con
kie/gpt-image-2**, y esa cifra no se mueve al bajar la calidad del proyecto.

El propio Estudio sí lo apunta bien: la bitácora del taller deja
`estilo_dibujado` con su `coste_usd` real.
