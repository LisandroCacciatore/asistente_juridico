# SPEC — Circuito del Asistente Jurídico · v0.1 (para revisar)

**Origen:** revisión del 16/09/2026 (hora y media recorriendo el sistema con Santiago).
**Estado:** borrador para aprobar. **Nada de esto está implementado todavía.**
**Regla:** cada punto dice qué pide, qué existe hoy (verificado en el código) y qué falta.

---

## 0. El circuito, como lo entendí

```
decreto (texto) → cédula armada → FIRMA DIGITAL → META JURÍDICO (guardar/asociar)
                                                 → SISFE "Nueva cédula" (adjuntar + partes + notificar)
```

Hoy el sistema hace: `decreto → cédula → FirmAr → subir a Meta Jurídico`.
El cambio de fondo es que **aparece SISFE como destino de la notificación**, y
que Meta Jurídico pasa a ser (también) donde se **crea** el expediente si no existe.

**[D1] Orden a confirmar:** ¿Meta Jurídico va *antes* de SISFE (primero archivo/creo el
expediente, después notifico por SISFE), o SISFE es lo único que importa y Meta
Jurídico es archivo paralelo? Abajo trabajo con el orden del diagrama.

---

## 1. Cédula desde texto — completar las variables

### Lo que pide

| Variable | Detalle |
|---|---|
| **Juzgado** | Fuero + nominación + **ciudad** (Rosario / Rafaela / …). Ej: "Juzgado de Primera Instancia en lo Laboral de la 2da Nominación de Rosario". |
| **A quién va dirigida** | Persona física o jurídica. |
| **Domicilio** | Si es física: la dirección. Si es jurídica: **"va directo por SISFE"** (no se escribe a mano). |
| **Juez / secretario / prosecretario** | Los tres, los que correspondan. |
| **Decreto propiamente dicho** | Con su tipo: *se fija audiencia* / *se crea prueba* / *proveyendo escrito*. |
| **Tipos de cédula** | Común · Peritos · Ley 22172 · Artículo 51. |

### Lo que existe hoy (verificado)

- `cedulas_pdf.py` tiene **3 plantillas**: `generar_pdf_estandar` (común),
  `generar_pdf_audiencia_51`, `generar_pdf_bus_federal` (Ley 22.172).
- `cedulas.py` detecta `audiencia_51`, `bus_federal` y **peritos solo para elegir
  el destinatario** (`elif "perito" in texto_lower`), no como tipo de cédula.
- El PDF usa: `juez`, `secretario`, `cargo_juez`, `cargo_secretario`,
  `destinatario_nombre`, `destinatario_domicilio`, `caratula`, `cuij`, `ciudad`,
  `fecha_decreto`, `texto_decreto`.

### Lo que falta

1. **`prosecretario` no existe en el repo** (`grep` en todos los `.py` = 0 resultados).
   Hay que agregarlo a las 3 plantillas y a `config.JUZGADOS`
   (`juzgados_rosario.json` hoy solo tiene juez/secretario por juzgado).
2. **"Peritos" como tipo de cédula**: no tiene plantilla ni etiqueta propia.
3. **Ciudad**: hoy se toma del texto; hay que poder fijarla explícitamente
   (Rosario/Rafaela/…) y usarla en el encabezado del juzgado.
4. **Domicilio de persona jurídica**: hoy siempre se escribe el domicilio.
   Falta la regla "si es jurídica, va por SISFE" (dejar el campo vacío/electrónico).
5. **Subtipo de decreto** (audiencia / prueba / proveyendo escrito): hoy la
   clasificación es por reglas sobre el texto (`es_decreto_audiencia_51`, etc.).
   Falta exponerlo como elección explícita cuando las reglas no alcanzan.

**[D2]** — ¿"Proveyendo escrito" es un tipo de cédula más (una plantilla nueva) o
solo una forma de nombrar el decreto dentro de la cédula común? **Recomiendo:**
plantilla Común + un campo "subtipo de decreto" que cambia el encabezado, sin
duplicar plantillas.

---

## 2. Meta Jurídico — crear si no existe

### Lo que pide

- Si el expediente **existe** → guardar ahí (lo que ya hace).
- Si **no existe** → crearlo:
  - crear un **contacto** con nombre y los datos disponibles (DNI, dirección, tel, mail),
  - elegir **tipo de expediente** (por defecto "Sin asignar"),
  - la **carátula** sale de la cédula; el tipo se puede **inferir de la carátula**,
    y si no, "Sin Asignar".

### Lo que existe hoy (verificado)

`meta_juridico.py` → `subir(ruta_pdf, cuij, caratula)`: busca por apellido, abre el
expediente, adjunta. Si no lo encuentra, **corta a propósito** con:
*"No se encontró ningún expediente para '<X>' en Meta Jurídico"* — con un comentario
en el código que dice que no conviene crear un expediente nuevo y duplicado.

### Lo que falta

Invertir esa decisión: agregar el camino "no existe → crear contacto → crear
expediente (tipo inferido de la carátula, si no 'Sin Asignar') → adjuntar".
Esto **necesita sesión real** en el portal: los selectores del alta no se pueden
adivinar. Igual que con FirmAr, la creación es un acto con consecuencias: **[D3]**
¿queda con una confirmación humana antes de crear, o se crea y se avisa?

**[D3] recomendación:** que la cree, pero mostrando antes en el dashboard
"Voy a crear el expediente X para Y — ¿confirmás?" (una vez por expediente, no por
cédula). Crear un expediente por error es más caro que un clic.

---

## 3. Alta de Cliente ART — subir archivos y dispararla desde la carpeta

### Lo que pide

- Poder subir **distintos tipos de archivo** (jpg, img, pdf, etc.).
- Que la skill **se ejecute desde la carpeta de documentación del cliente**
  (el paquete de 5 documentos: poder, relato, telegrama, formulario SRT, convenio).

### Lo que existe hoy

La skill `cliente-art-nuevo` está completa (SKILL.md + 5 references + `fill_srt_form.py`
+ los 4 Anexos SRT) y la tarjeta del dashboard pide **texto pegado**, no archivos.

### Lo que falta

1. El formulario de la acción, para aceptar archivos (PDF y **imágenes**) y no solo texto.
2. Que la documentación subida quede en la carpeta del cliente y la skill lea de ahí.

**[D4] Ambivalencia a resolver:** en el mismo documento dice *"hay que modificarlo"*
(Alta de Cliente ART) y después, en "Todo esto se elimina", la lista de tarjetas
incluye **Alta de cliente ART**. **Recomiendo:** la tarjeta **desaparece** del panel
(lo que se elimina es el acceso, no la skill) y el paquete se dispara desde la
carpeta de documentación del cliente. Si preferís que siga como tarjeta, decime y
la dejo — pero entonces no va en la lista de eliminadas.

---

## 4. Multi-usuario (jr / socio) — **esto es Nivel 2**

### Lo que pide

- Un **jr o socio** entra desde **otra máquina**, con **las contraseñas de Santiago**.
- Entrada **multiagente**: cada uno con su usuario y contraseña, y **eligiendo a qué
  SISFE conectarse** (puedo entrar a un SISFE que no es mío).
- Cada uno tiene **su usuario de Firma Digital**; se firma y se guarda.
- En Meta Jurídico cada uno se loguea con **su cuenta** → cada usuario necesita un
  mail para conectarse a "Asistente Jurídico" (cada uno con su cuenta habilitada).
- **Log general**: quién interactuó con qué registro.

### Por qué es un proyecto aparte

Hoy el sistema es **de una sola persona en una sola máquina**: un `config.py` con una
matrícula, un perfil de Chrome, un token de Gmail. Todo eso cambia:

| Hoy | Con multiagente |
|---|---|
| `config.SISFE_USUARIO` (una matrícula) | N usuarios, cada uno con matrícula + su Firma Digital |
| Un perfil de Chrome | Un perfil por usuario (las sesiones NO se pueden mezclar) |
| Un token de Gmail | Una casilla por usuario |
| El log no dice quién | Cada entrada con usuario |

**No es un ajuste: es otra arquitectura.** Y tiene un problema práctico que hay que
decidir antes de escribir código: **"{D5} entrar con las contraseñas de Santiago"**.
Si el jr entra con la cuenta de Santiago, entonces *no hay* multi-usuario real: hay
una cuenta compartida, y el log general no puede distinguir quién hizo qué.
O cada uno entra con su propia cuenta (y entonces hay que ver si SISFE y Firma
Digital lo permiten para un jr), o se comparte la cuenta y el log registra **la
máquina**, no la persona.

**[D5] recomendación:** definir primero el objetivo real —
(a) *que otro pueda trabajar desde otra máquina* (se resuelve con la cuenta
compartida + log por máquina), o
(b) *saber quién hizo qué* (requiere cuenta propia por persona).
Son dos productos distintos y el segundo vale más.

**[D6]** — ¿esto entra ahora o después de cerrar el circuito de una sola persona?
**Recomiendo:** después. El circuito de cédula→firma→SISFE→Meta es lo que hace
útil al sistema; el multiagente multiplica algo que todavía no está cerrado.

---

## 5. Firma Digital

### Lo que pide

- Que sea **la misma cuenta que la de SISFE**: al firmar debe pedir **usuario,
  contraseña y OTP de la cuenta elegida en SISFE**.
- Firmado → **se descarga en local**.

### Lo que existe hoy

`firma.py` → `firmar(ruta_pdf)` y `firmar_lote(items)`: entran a FirmAr, adjuntan,
piden PIN y descargan el firmado. Hoy es **una cuenta fija**, no la que se eligió en
SISFE, y la firma individual **se confirmó en vivo** con la cédula PRUEBA TECNICA
(la firma en lote todavía no).

### Lo que falta

1. Que la cuenta de Firma Digital salga de la cuenta elegida en SISFE (una sola
   identidad por corrida).
2. Confirmar en vivo la **firma en lote** (varias cédulas, un login, un PIN por documento).

**[D7]** — ¿FirmAr y SISFE comparten credenciales de verdad (mismo usuario y
contraseña) o son cuentas distintas que hay que pedir por separado? Si son
distintas, "la misma cuenta" significa "la misma persona", no "las mismas claves",
y el flujo cambia.

---

## 6. Destinatarios múltiples

### Lo que pide

- Que la skill **sepa a quién mandárselo**, o **pregunte antes de generar**.
- Si hay varios destinatarios: **una cédula por destinatario** y **una firma por
  cédula** (validar si se puede firmar en lote).

### Lo que existe hoy

`cedulas.py` ya arma **una cédula por destinatario** (multi-destinatario probado), y
`firmar_lote` existe pero **nunca se corrió contra FirmAr real** (está en
`PENDIENTES.feature.md`).

**[D8]** — Cuando hay varios destinatarios, ¿siempre se genera y firma para todos, o
el abogado elige cuáles en ese momento? **Recomiendo:** mostrar la lista de
destinatarios detectados **antes** de generar, con todos tildados, y que él destilde.

---

## 7. Subir a SISFE (el tramo nuevo)

### La secuencia que describieron

1. Entrar a `sisfe.justiciasantafe.gov.ar/buscar-notificacion-expediente/<id>`
   (con el CUIJ correspondiente).
2. Clic en **Nueva cédula**.
3. Completar **Descripción genérica** (por ejemplo, la fecha).
4. **Adjuntar** la cédula firmada.
5. **Partes**: marcar la columna *Seleccionar* y completar/confirmar Caracter, Parte
   y Correo Electrónico. Ejemplo real que pasaron:

| Seleccionar | Caracter | Parte | Correo |
|---|---|---|---|
| ☐ | AUXILIAR DE JUSTICIA | CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA (CS01) | |
| ☐ | AUXILIAR DE JUSTICIA | CAJA FORENSE-ROSARIO (CF02) | |
| ☐ | REPRESENTANTE | LAMAS, ERICA GISELA (6372) | |
| ☐ | REPRESENTANTE | PEREYRA, FABIAN CARLOS (XXI100) | FCPEREYRA@GMAIL.COM |

### Lo que existe hoy

**Nada de esto.** El sistema nunca tocó SISFE para notificar: lo usaba solo para
leer decretos (`monitor_playwright.py`).

### Lo que falta

Todo el tramo, y **necesita sesión real**: los selectores de esa pantalla no se
pueden escribir a ciegas. Es el tramo de mayor riesgo de la entrega.

**[D9] — qué se tilda siempre y qué sale del expediente.** Las dos filas de
**AUXILIAR DE JUSTICIA** (Caja de Seguridad Social de Abogados y Caja Forense
Rosario) parecen fijas en todo expediente; las de **REPRESENTANTE** parecen salir
de las partes del caso. ¿Es así? **Recomiendo:** las Cajas fijas por regla, y las
partes tomadas del expediente, mostradas para confirmar antes de notificar.

**[D10]** — ¿El correo electrónico se carga solo cuando la parte lo tiene, y si no
queda vacío (notificación solo en el sistema)? El ejemplo tiene un mail en una fila
y vacío en las otras tres.

---

## 8. Log general

- **Log general de Asistente Jurídico: quién interactuó con qué registro.**
- Hoy existe `log_acciones.jsonl` (fecha, acción, id, carátula, CUIJ, detalle) **sin
  campo de usuario**. Falta agregar el usuario/máquina a cada entrada.
- **[D11]** — El campo nuevo, ¿es el usuario de Windows de la máquina, el mail con el
  que entró al dashboard, o ambos? Depende de D5 (cuenta compartida o por persona).

---

## 9. Mail y "Borradores listos" con interacción

- "Darle interacción a la casilla de Mail desde el Dashboard y lo mismo en Borradores listos."
- Hoy: se **mira** la bandeja y los borradores; el único botón es "Abrir en Gmail".
- **[D12]** — ¿Qué acciones exactamente? Las candidatas: responder (**como borrador**,
  nunca enviando), marcar leído, archivar, descartar borrador, abrir el hilo completo.
  **Recomiendo** empezar por: abrir el hilo, responder como borrador, y descartar
  borrador. La regla "el envío es del abogado" no se toca.

---

## 10. Refresco cada 10 minutos

- "El refresh de la consulta por si hay cosas nuevas debería hacerse cada 10 minutos."
- Hoy: `INTERVALO_MINUTOS = 30` en `config.py` (monitor de SISFE) y el dashboard se
  refresca cada 60 s.
- **[D13]** — **Recomiendo:** monitor de SISFE → **10 min** (es lo que piden);
  dashboard → dejarlo en 60 s (es solo lectura y hace que el panel se sienta vivo).

---

## 11. Tarjetas del panel que se eliminan

**Todo esto se elimina** (textual del pedido): Alta de cliente ART · Apertura de
cuenta judicial · Oficio por boletas impagas · Oficio RAEO · Transferencia de capital.

Quedaría **solo "Cédula desde texto"** en el panel de acciones.

**[D14]** — Ojo con una consecuencia: las skills **siguen existiendo** (están en
`skills/`, con sus `SKILL.md` y scripts). Lo que se elimina es el acceso desde el
panel. ¿Eso es lo que quieren, o hay que dar de baja también las skills?
**Recomiendo:** sacar las tarjetas y **dejar las skills** — se pueden seguir
invocando, y borrarlas es más difícil de revertir que volver a poner un botón.

---

## 12. Cómo propongo ordenar el trabajo

| Fase | Qué | ¿Necesita portal? |
|---|---|---|
| **1** | Cédula completa: prosecretario, ciudad, domicilio jurídico, tipo Peritos, subtipo de decreto | No — todo local |
| **2** | Destinatarios: confirmar antes de generar (D8) | No |
| **3** | Panel: sacar las 5 tarjetas (D14), refresh a 10 min (D13) | No |
| **4** | Log con usuario (D11) — engancha con el multiagente | No |
| **5** | Meta Jurídico: crear contacto + expediente (D3) | **Sí** |
| **6** | Subir a SISFE: nueva cédula + partes (D9, D10) | **Sí** |
| **7** | Firma: cuenta de SISFE + lote (D7) | **Sí** |
| **8** | ART: subida de archivos desde la carpeta del cliente (D4) | No |
| **9** | Mail interactivo (D12) | No |
| **10** | **Multiagente** (D5, D6) — proyecto aparte | **Sí** |

Las fases 1 a 4 **no dependen de ningún portal**: se pueden hacer y ver funcionando
hoy, con tests. Las 5 a 7 son las que necesitan sesión real (idealmente en una sola
tanda, con Santiago adelante). El 10 es aparte y conviene diseñarlo antes de tocarlo.

---

## 13. Decisiones que necesito para arrancar

1. **D1** Orden del circuito: ¿Meta Jurídico antes o después de SISFE?
2. **D2** "Proveyendo escrito": ¿plantilla nueva o subtipo de la común?
3. **D3** Crear expediente en Meta: ¿con confirmación previa o automático?
4. **D4** Alta de Cliente ART: ¿se elimina la tarjeta (y queda la skill) o se modifica?
5. **D5** Multiagente: ¿cuenta compartida (saber *desde dónde*) o cuenta por persona (saber *quién*)?
6. **D6** Multiagente: ¿ahora o después de cerrar el circuito de una persona?
7. **D7** FirmAr y SISFE: ¿mismas claves o cuentas distintas de la misma persona?
8. **D8** Varios destinatarios: ¿todos por defecto, eligiendo?
9. **D9** Partes en SISFE: ¿Cajas fijas + representantes del expediente?
10. **D10** Correo electrónico de la parte: ¿solo si existe?
11. **D11** Log: ¿usuario de Windows, mail del dashboard, o los dos?
12. **D12** Mail: ¿qué interacciones exactamente?
13. **D13** Refresco: ¿10 min en el monitor y 60 s en el dashboard?
14. **D14** Tarjetas: ¿se sacan y las skills quedan?

Con esas 14 respuestas escribo el spec v0.2 ya cerrado (con los criterios de
aceptación por fase) y arranco por las fases que no dependen de portales.
