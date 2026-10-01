# Cómo se escribe el encargo de un estilo

Medido el 2026-09-30 creando cuatro estilos seguidos. Un estilo cuesta 0,30 $ y
lo copian después todos los planos de todos los vídeos de ese canal, así que
equivocarse en el encargo sale caro dos veces.

## 1. «Paleta contenida» se lee como MONOCROMO

El primer «Libro Mayor (finanzas)» salió entero en azul sobre crema: calles y
salones sin una gota de color. La culpa fue de esta frase del encargo:

> PALETA: muy contenida — tinta azul-negra y crema de papel — con UN SOLO
> acento de color, verde o rojo, reservado al momento del dinero.

La guía generada la tradujo a «deja edificios, muebles y suelos SIN RELLENAR» y
«la paleta es tinta y papel más exactamente un acento por fotograma». Coherente,
y mortal en una parrilla de YouTube: a 320 px una lámina beige clara desaparece
entre miniaturas negras y saturadas.

**Se escribe al revés, y en mayúsculas:** «NINGUNA imagen es monocroma. Sobre la
línea va SIEMPRE color plano y sólido, saturado, cubriendo zonas grandes. Deja
una zona oscura que ancle la composición: tiene que leerse a 320 píxeles.»

## 2. El moodboard dibuja SEIS EJES, y cuatro no piden personajes

Los ejes son `cara`, `cuerpos`, `interior`, `exterior`, `objeto` y `diagrama`.
Una instrucción como «el personaje trepa por la curva del gráfico» no se aplica
nunca en `interior` ni en `exterior`, porque esos ejes dibujan un sitio, no una
persona. El primer intento devolvió una calle vacía y un salón de catálogo.

**Hay que exigirlo:** «EN TODA ESCENA DE INTERIOR O DE EXTERIOR TIENE QUE HABER
AL MENOS UNA FIGURA haciendo algo; una habitación vacía está mal.»

## 3. Una técnica de dibujo arrastra un género entero

«Bolígrafo sobre papel cuadriculado» trae consigo el dibujo técnico de
arquitecto, y se tragó todo lo demás. Hay que nombrar el género que se quiere,
en la primera frase del encargo:

> ESTO ES UN EXPLICADOR ILUSTRADO, NO UNA LÁMINA DE ARQUITECTO. Cada imagen es
> una escena con alguien haciendo algo, nunca un decorado vacío.

## 4. La firma del estilo se pide por su nombre

Lo que distingue un canal —la gráfica como escenografía, el corte transversal—
hay que declararlo como obligatorio («ESTO ES LA FIRMA DEL ESTILO Y TIENE QUE
APARECER»), no describirlo de pasada. Lo que se menciona de pasada no sale.

## 5. Decir que el reparto es variado, o salen tres señores iguales

Sin pedirlo, la lámina `cuerpos` devolvió tres hombres blancos de mediana edad
con el mismo corte de pelo. Esa lámina es la que copian todos los planos.

## 6. Retomar un taller NO rehace el moodboard

`retomar` reutiliza las láminas ya dibujadas: termina en décimas de segundo y
mezcla las aportadas nuevas con las dibujadas viejas. Para rehacer un estilo se
crea un preset NUEVO y el viejo se manda a la papelera después, nunca antes.

Y el buzón de imágenes aportadas es **de un solo uso** (`_sembrar_aportadas`
hace `os.remove`): hay que volver a subirlas antes de cada intento.

## 7. gpt-image-2 ya escribe bien, y eso es un riesgo

En «Por Dentro (educativo)» las etiquetas salieron correctas en español y con
tildes («cimentación», «sótano», «acequia»). La regla de este repo —que un
generador de imágenes escribe letras mal, y por eso el texto se estampa después
con PIL— ya no se cumple con este modelo.

**Pero no se puede confiar en ella a escala.** Seis láminas correctas no
garantizan 126 planos correctos, y una errata en pantalla en un canal educativo
cuesta credibilidad. Si la firma del estilo lleva texto, que sea en los planos
de diagrama y se revisen antes del montaje.

## Qué modelo de kie.ai, medido con la misma escena

Comparativa del 30-09-2026: mismo prompt, misma lámina de referencia, calidad
`medium`, cuatro modelos. Coste total de averiguarlo: 0,14 $.

| Modelo | Corte transversal | Personaje fiel | Texto en español | Píxeles | Créditos | Segundos |
|---|---|---|---|---|---|---|
| **gpt-image-2-5-flare** | sí | sí | perfecto | **3,5 M** (2304x1536) | 10 | **61** |
| gpt-image-2 | sí | sí | perfecto | 2,0 M (1728x1152) | 10 | 100 |
| seedream/5-flash | **no** | **no** | bien | 3,8 M (2376x1584) | **3,24** | **28** |
| google/nano-banana-edit | sí | regular | **ilegible** | 1,0 M (1248x832) | 4 | 41 |

**Se usa `gpt-image-2-5-flare-image-to-image`.** Cuesta lo mismo que el 2 al
céntimo (6/10/16 créditos para 1K/2K/4K) y es un 39 % más rápido con 2,3 veces
más píxeles. Es mejora pura: no hay nada que decidir.

**Seedream 5 Flash es un tercio de precio y no vale.** Dibujó un interior
normal donde se pedía una sección, y perdió el personaje de la referencia
—cabeza ovalada y cuerpo de bulto en vez del muñeco de palo con ropa plana—.
Un plano que hay que regenerar cuesta el doble que uno caro bien hecho.
Lo que sí quedó medido: **cobra 3,24 créditos clavados CON referencias**, así
que no cobra por imagen de entrada como hace Seedream 5 Pro.

**Nano Banana escribe galimatías**: «Aisce dútiviar», «Seearias», «Bregreftóbo».
Para un canal con rótulos dentro de la imagen queda descartado.

### Y lo que ninguno hace: respetar `aspect_ratio`

Los cuatro devolvieron 3:2 habiéndoles pedido 16:9, porque **en
image-to-image la salida hereda la forma de la imagen de referencia**, que es
3:2. El `aspect_ratio` solo manda en text-to-image, que es como se dibuja el
moodboard (`moodboard.py` llama con la lista de referencias VACÍA, y por eso
sus láminas sí salen a 3072x2048 limpios).

Consecuencia práctica: para que los planos salgan en 16:9 habría que rehacer
las láminas del preset en 16:9, y entonces los planos lo heredarían. Mientras
tanto el render recorta ~15 % del alto, que es lo que siempre hizo.
