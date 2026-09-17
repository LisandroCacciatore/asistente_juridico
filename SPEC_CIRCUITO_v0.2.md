# SPEC — Circuito del Asistente Jurídico · v0.2 (DECISIONES CERRADAS)

**Base:** `SPEC_CIRCUITO_v0.1.md` (revisión del 16/09/2026).
**Estado:** decisiones aprobadas el 16/09/2026 ("dale con las recomendaciones").
**Regla de este documento:** lo que dice acá es lo que se construye. Si algo se
cambia, se cambia acá primero.

---

## 1. Decisiones cerradas

| # | Decisión | Quedó así |
|---|---|---|
| **D1** | Orden del circuito | **Meta Jurídico SALE del circuito** (decidido el 16/09/2026). Queda: texto → cédula PDF → **firma** (FirmAr) → **SISFE** (Nueva Cédula → descripción → adjuntar la firmada → Partes → notificar). `meta_juridico.py` queda **guardado y dormido** en el repo: no se borra, no se usa. |
| **D2** | "Proveyendo escrito" | ❌ **No es un tipo de cédula** (corregido el 16/09/2026). Es lo que dictó el juzgado — un proveído al escrito presentado. La cédula que lo notifica es la **común**: no hay plantilla nueva **ni subtipo que configurar**. |
| **D3** | Crear expediente en Meta | **No se hace** (16/09/2026): Meta salió del circuito (ver D1). |
| **D4** | Alta de Cliente ART | **Se elimina la tarjeta**; la skill queda y se dispara **desde la carpeta de documentación del cliente**. |
| **D5** | Multiagente: cuenta | **Cuenta por persona** (es la única forma de saber *quién* hizo qué). Si en el camino SISFE/Firma no lo permiten por usuario, se documenta la limitación y el log registra la máquina. |
| **D6** | Multiagente: cuándo | **Después** de cerrar el circuito de una sola persona. |
| **D7** | FirmAr vs SISFE | **[A CONFIRMAR EN VIVO]** ¿mismas claves o cuentas distintas de la misma persona? El código se escribe para **elegir la identidad una vez por corrida** y usarla en las dos, con las claves que cada portal pida. |
| **D8** | Varios destinatarios | **Mostrar la lista antes de generar**, todos tildados; el abogado destilda. Una cédula y una firma por destinatario. |
| **D9** | Partes en SISFE | **Cajas fijas** (Seg. Social de Abogados CS01 + Caja Forense Rosario CF02) por regla; **representantes desde el expediente**, mostrados para confirmar antes de notificar. **Verificado contra la pantalla real el 16/09/2026** (las 4 filas están en la Fase 6). El código entre paréntesis es la matrícula de caja, y es el mismo dato que ya usa la skill de boletas. |
| **D10** | Correo de la parte | **Solo si existe**; si no, queda vacío (notificación solo en el sistema). |
| **D11** | Log | **Usuario + máquina en cada entrada** (el usuario depende de D5; hasta entonces, el de Windows). |
| **D12** | Mail interactivo | **Abrir hilo · responder como borrador · descartar borrador.** La regla "el envío es del abogado" no se toca. |
| **D13** | Refresco | **Monitor de SISFE: 10 min.** Dashboard: 60 s. |
| **D14** | Tarjetas | **Se sacan las 5 tarjetas**; las skills **quedan** y se siguen pudiendo invocar. |
| **D15** | Partes en SISFE (confirmado) | **16/09/2026, contra la pantalla real.** La tabla trae 4 filas: 2 **cajas fijas** (CS01, CF02) + los **representantes del expediente**. El sistema **las lee del portal y las muestra**; el abogado destilda lo que no va. **Ninguna parte se fija en el código.** |
| **D16** | El correo de las partes | **Lo trae cargado el SISFE.** Se lee y se muestra tal cual; no se completa ni se inventa (coherente con D10: va solo donde existe — en la tabla real, solo Pereyra). |
| **D17** | El clic en NOTIFICAR | **Es del abogado.** El sistema deja todo cargado (descripción, adjunto, partes tildadas) y **se detiene**. Está blindado: un test lee el código y **falla si alguien agrega un clic en Notificar / Presentar / Confirmar / Enviar**, y otro test corre el flujo contra una pantalla de mentira y comprueba que el botón quedó sin apretar. Misma regla que el mail. |
| **D18** | Dos identidades | El sistema registra **operador** (quién maneja el asistente) y **identidad del acto** (con qué matrícula/sesión y con qué firma se ejecutó). Son **independientes a propósito**: el operador puede usar sus claves **o las de un compañero** — eso está permitido y es normal, no es una excepción. Lo que los une es la regla de la cadena (**D25**). Las dos van en cada línea del log, más `usuario_windows` como control cruzado. |
| **D19** | La puerta de identidad | **Al abrir el asistente**, obligatoria una vez por jornada y cambiable. Se ve siempre en la barra de arriba. **Antes del portal no se vuelve a preguntar**: se confirma en pantalla en la pausa que ya existe ("vas a actuar con la identidad de Santiago"). |
| **D20** | Quiénes | **Santiago, Jr y Socio** *(«Socio» es provisorio: Santiago no tiene el nombre todavía — está marcado en `config.py` para reemplazar)*. Cada uno con **su ingreso propio al asistente** y **su propio acceso al SISFE y a FirmAr**. La identidad del acto es, por defecto, **la del operador**. |
| **D25** | **La regla de la cadena** | *"Del SISFE que bajé, es el mismo que tiene que firmar."* Una cédula pertenece a **una sola identidad**, y no se puede cruzar: **la sesión con la que se leyó el expediente, la firma que se le pone y la sesión con la que se notifica son la misma persona.** El operador puede ser cualquiera y puede usar sus claves o las de un compañero; lo que no puede es mezclar. La identidad **se fija en el primer acto del portal** y queda grabada en la cédula; los actos siguientes la respetan **o el sistema los frena y dice por qué**. |
| **D26** | El ingreso: por mail | Cada uno entra al asistente **con su mail** (o con su nombre, mientras no tenga el mail cargado: el campo vacío no bloquea). Hoy eso es una declaración con más fricción y deja el registro; cuando el panel se sirva desde el hub (D23) el mismo campo pasa a ser **un login de verdad** — cambia la validación, no el diseño. |
| **D21** | Qué se centraliza | **Los datos sí, las sesiones no.** Una sola fuente de verdad para estado, log y ficha del cliente. Los perfiles de Chrome, las sesiones de los portales, la firma, la generación de PDF y las rutas **quedan en cada máquina**: centralizar una sesión sería centralizar credenciales. |
| **D22** | El anti-duplicado es central | Con dos máquinas y el estado local, **dos personas pueden notificar la misma cédula dos veces** y ninguna se entera. El control de duplicados tiene que vivir donde vive el estado. |
| **D23** | El ingreso al asistente | Mientras el asistente es **local**, el ingreso es la **declaración** (D19). Cuando el panel se sirva desde el hub (Fase 10b), el ingreso pasa a ser un **login de verdad** — y ahí la declaración se vuelve **identidad autenticada**: recién entonces el log deja de ser "lo que alguien dijo ser". Se hace en ese orden a propósito: primero el registro, después el candado sobre el registro. |
| **D24** | Un perfil de Chrome por persona | Cada uno entra a los portales con **su** perfil (`chrome_profile_<persona>`), porque la sesión de SISFE y la de FirmAr son personales. El paso de firma y el de SISFE usan el perfil de la **identidad elegida**, no el de la máquina. *Santiago sigue con el perfil que ya existe, para no perder la sesión que ya tiene abierta.* |

---

## 2. Criterios de aceptación por fase

### Fase 1 — Cédula completa (sin portal)
- [x] El PDF puede mostrar **juez, secretario y prosecretario**, cada uno con su cargo.
      Si un dato no está, **la línea no se imprime** (no sale "____" ni "None",
      ni queda una coma colgando). *(hecho — `_autoridad()`)*
- [x] La **ciudad** del juzgado se puede fijar explícitamente (Rosario, Rafaela, …)
      y se usa en el encabezado. *(hecho — `extraer_ciudad()` + campo `ciudad`)*
- [x] ~~Destinatario **persona jurídica** → el domicilio **no** se imprime (va por SISFE).~~
      **CORREGIDO el 16/09/2026 contra una cédula real del SISFE:** el domicilio se
      imprime **siempre que lo tengamos**, sea persona física o jurídica — la muestra
      real imprime el de una S.R.L., y en el Art. 51 ese domicilio no es decorativo
      (el artículo manda citar a las partes *"en el real, además del procesal"*). Lo
      que sigue prohibido es **inventarlo**: si no está, no se imprime. Se eliminó
      `_es_juridica()` y el flag `destinatario_es_juridica`.
- [x] ~~**La cédula de Audiencia Art. 51 sigue el modelo del SISFE**~~ → **CORREGIDO el
      16/09/2026: las tres cédulas son LA MISMA, cambiando los artículos que transcriben.**

      Santiago lo definió así (16/09/2026) y lo confirman tres cédulas reales del SISFE
      (una común de contestación de demanda, una de designación de perito y una de
      audiencia del Art. 51):

      | Cédula | Es la común… | …más |
      |---|---|---|
      | **Común** (estándar) | — | — |
      | **Peritos** | ✔ | la intimación a aceptar el cargo + arts. **78 y 79** |
      | **Audiencia Art. 51** | ✔ | arts. **51, 52 y 66** |

      En código: una sola base (`_cuerpo_comun()`) y cada plantilla le agrega su bloque
      de transcripciones. El encabezado, el `Señor:`, el `Domicilio:`, la frase del
      `Hago saber` con la carátula y el CUIJ adentro y el cierre son idénticos en las tres.
- [x] **La cédula de peritos** (16/09/2026): la común + la intimación + los arts. 78 y 79.
      Tipo propio (`peritos`) en las reglas, en el motor y en el selector del panel.
      La regla de detección pide la designación efectiva (`resulta sorteado…`), **no** la
      mención del sorteo: un decreto que ordena oficiar a la Cámara *"a los fines del
      sorteo de perito"* es una común y quedó verificado que no se confunde.
- [x] **El destinatario de la cédula de peritos es el perito**, no las partes: los
      nombres salen del acta del sorteo (puede haber más de uno, y va una cédula por
      cada uno). Antes de esto, la cédula habría salido a nombre de la demandada.
- [x] **El encabezado usa el nombre del juzgado del expediente si viene** (`juzgado_header`).
      Los juzgados no se nombran todos igual y el SISFE copia el nombre que cada uno tiene
      cargado: el Juzgado Laboral Nº 8 escribe `JUZGADO EN LO LABORAL Nº 8 DISTRITO
      JUDICIAL NRO. 2 - ROSARIO`, mientras la 5ª/10ª Nom. escribe `JUZGADO DE PRIMERA
      INSTANCIA DE DISTRITO EN LO LABORAL DE LA 5 NOMINACIÓN DE ROSARIO`. Cuando no viene
      el nombre, se compone la segunda forma (y `DE LA LOCALIDAD DE X` si el juzgado no
      se numera, como Reconquista). El número de distrito **no se deduce de la ciudad**.
- [x] **Correcciones contra las cédulas reales** (todas verificadas documento contra
      documento): el destinatario dice `Señor:` (no `Señor/a:`); la carátula y el CUIJ van
      dentro de la frase (se sacaron las líneas `Por: / Contra: / Sobre: / Expte. N°`);
      el decreto se imprime tal cual, sin comillas y sin repetirle la fecha si ya la trae;
      y **se sacó el bloque `Firma y sello`** de la común, la de peritos y la del Art. 51
      — ninguna de las tres cédulas reales lo trae (se firman digitalmente). El bloque
      queda **solo** en la Bus Federal, que es la única que se diligencia a mano y la
      necesita para el oficial notificador.
- [x] **La Bus Federal (Ley 22.172) se alineó al modelo del portal** (16/09/2026). La
      nuestra era otro documento. Ahora es el formulario del SISFE: tribunal exhortante,
      domicilio del tribunal, jueza, secretaría, **clave de acceso al expediente**,
      tribunal receptor, carátula, destinatario con su CUIT, el objeto (una resolución por
      párrafo, con la fecha en negrita) y al final el recuadro **PARA EL OFICIAL
      NOTIFICADOR** con las dos firmas y el pie de la Ley 22.172.
      Lo que no venga en los datos sale con el renglón en blanco (la clave de acceso la
      genera el SISFE): no se inventa nada. Datos nuevos: `clave_acceso` y
      `destinatario_cuit`. El domicilio del tribunal se verifica por ciudad (Rosario =
      Balcarce 1651, del Mapa Judicial del Poder Judicial), no se supone.
- [x] **La autoridad queda con nuestra redacción** — decisión del 16/09/2026. Las cédulas
      reales dicen *"a cargo de la DRA. X (JUEZA) Y DE LA DRA. Y (PROSECRETARÍA)"* y
      nosotros *"a cargo del/la DR./DRA. … (JUEZ), SECRETARIO DR./DRA. …"*. **No se
      cambia**: es wording distinto y queda como está a propósito.
- [x] **El fuero del encabezado ya no está escrito a mano.** Estaba fijo en
      "EN LO LABORAL" en la plantilla, así que una cédula de Civil o Comercial
      salía con el fuero equivocado. *(hallazgo + arreglo de esta fase)*
- [x] Tests nuevos cubriendo cada punto, y los 33 existentes siguen pasando.
      *(40 nuevos, 73 en total, todos verdes)*
- [x] **Tipo "Peritos"**: es un tipo propio, con una cédula por perito designado.
      *(hecho el 16/09/2026 con la muestra real de Santiago — ver más abajo)*
- ~~**Subtipo de decreto** (audiencia / prueba / "proveyendo escrito") fijable a mano.~~
      **Descartado el 16/09/2026: "proveyendo escrito" no es una cédula** (ver D2).
      Los subtipos de decreto que **sí** cambian la cédula ya los detectan las
      reglas (`aud51`, `bus_federal`, `traslado`); el resto sale como común y no
      hay nada que configurar.

### Fase 2 — Destinatarios (sin portal)
- [x] Antes de generar, el dashboard lista los destinatarios detectados, **todos tildados**.
      *(hecho — paso previo `POST /api/destinatarios`: no genera ni registra nada)*
- [x] Se genera **una cédula por destinatario tildado**, y ninguna por los destildados.
      *(hecho — el motor ya recorría `destinatarios`; ahora la lista la decide el abogado)*

**De dónde sale la lista** (y de dónde NO): la parte **demandada** y la **actora** de la
carátula, más los nombres que el decreto manda notificar (*"notifíquese a la Dra. X"*).
Lo que no esté en esos dos lugares **no se inventa**: queda vacío y el abogado lo agrega
a mano en la misma pantalla. Se muestra **qué interpretó** (carátula, CUIJ, fuero, ciudad,
juzgado, si es sentencia) para que confirme sobre datos concretos.

### Fase 3 — Panel (sin portal)
- [x] Se eliminan las 5 tarjetas; queda **Cédula desde texto**.
- [x] Las skills siguen en `skills/` y siguen siendo invocables
      (`/api/skill/<accion>` sigue vivo; el panel explica dónde se corren ahora).
- [x] `INTERVALO_MINUTOS = 10` y el dashboard sigue refrescando cada 60 s.

### Fase 4 — Log con usuario y máquina (sin portal)
- [x] Cada entrada de `log_acciones.jsonl` lleva **usuario** y **máquina**.
- [x] Las entradas viejas (sin esos campos) se siguen leyendo sin romper el dashboard
      (se completan vacías al leer, así ningún consumidor tiene que acordarse).

### Fase 5 — Meta Jurídico → **ELIMINADA** (16/09/2026)

Sale del circuito: una vez que la cédula está firmada, va directo al SISFE. No hay
contacto, no hay expediente en Meta, no hay confirmación previa que pedir.

### Fase 6 — SISFE: subir la cédula firmada (con portal, con Santiago)

La secuencia es la que dictó Santiago el 16/09/2026:

1. **Entrar al expediente por CUIJ.** El buscador del SISFE resuelve el CUIJ en una URL
   propia del portal — `.../buscar-notificacion-expediente/<id>` — donde `<id>` es de
   SISFE y **no** es el CUIJ (caso real: `10067855763` para el CUIJ `21-04253894-6`).
   Se busca por CUIJ; el id no se adivina. Verificar **carátula + CUIJ** antes de seguir.
2. **Nueva Cédula.**
3. **Descripción genérica** — texto libre; la convención es la fecha.
4. **Adjuntar** la cédula **firmada** (la que baja de `firma.py` / FirmAr).
5. **Partes** — la tabla que trae el expediente, tildando:

   | Carácter | Parte | Correo |
   |---|---|---|
   | AUXILIAR DE JUSTICIA | CAJA DE SEG.SOCIAL DE ABOGADOS Y PROCURA (CS01) | — |
   | AUXILIAR DE JUSTICIA | CAJA FORENSE-ROSARIO (CF02) | — |
   | REPRESENTANTE | LAMAS, ERICA GISELA (6372) | — |
   | REPRESENTANTE | PEREYRA, FABIAN CARLOS (XXI100) | FCPEREYRA@GMAIL.COM |

   Las **dos cajas son fijas** (D9). Los **representantes se leen del expediente**
   (no se fijan a mano: son los que el SISFE muestra). El correo va **solo donde
   existe** (D10) — en esta tabla lo tiene únicamente Pereyra.
6. **Notificar.**

Mismo `_navegador.py` (perfil de Chrome persistente) que ya usan `firma.py` y
`meta_juridico.py`. **Toda puerta humana (login, 2FA) corta con aviso**, como el
`input()` del monitor: el script no sigue solo.

**Estado: construido (16/09/2026), falta la pasada en vivo.** Las tres preguntas que
estaban abiertas ya se respondieron y quedaron como D15/D16/D17 — no se programó
nada a ciegas:

| Pregunta | Respuesta |
|---|---|
| ¿Las 4 partes se tildan siempre? | Se **leen del portal y se muestran**; ninguna se fija (D15) |
| ¿El correo lo trae el SISFE? | Sí, **lo trae cargado** (D16) |
| ¿Notificar lo aprieta el abogado? | Sí, y está blindado por test (D17) |

Lo que queda para la pasada en vivo es **una sola cosa: los selectores**. Todo el
paso intenta el camino automático y, cuando no encuentra un campo, **frena y te
pide que lo hagas a mano** (nunca sigue a ciegas). Los que hay que confirmar contra
el portal: la caja de búsqueda del CUIJ, el botón «Nueva Cédula», el campo de la
Descripción genérica, el input de archivo, y la tabla de Partes. Están todos
marcados y en un solo lugar de `sisfe_notificar.py`.

Y si no puede verificar el expediente, **no sigue**: el CUIJ de la pantalla tiene
que coincidir con el de la cédula (la carátula distinta solo avisa, porque el
portal la escribe a su manera, y quien decide ahí es el abogado).

- [x] El paso construido: `sisfe_notificar.py` + la acción `notificar_sisfe` y el
      cierre `marcar_notificada` (que sí da la cédula por presentada, y lo dispara
      una persona después de apretar Notificar en el portal).
- [x] Que **no** toque el botón final, verificado de dos maneras (ver D17).
- [x] Que cargar la cédula en el SISFE **no la saque de la pantalla**: el estado
      sigue siendo `firmada` y el paso queda en el log (`cargada_en_sisfe`). Un
      estado nuevo la habría hecho desaparecer de todas las secciones del panel.
- [x] Que no se pueda subir **la cédula sin firmar**: si no hay firmado, la acción
      se corta. *(Lo encontró un test: la primera versión caía al PDF sin firmar
      cuando todavía no se había firmado.)*
- [ ] La pasada en vivo con Santiago: confirmar los selectores de arriba.
- [ ] Firma en lote (Fase 7): la identidad elegida en SISFE es la que firma.

### Fase 8 — El monitor aguanta una jornada (16/09/2026)

Lo que había que resolver: que no acumule memoria ni deje Chromes huérfanos entre
ciclos, y que si la sesión de SISFE expira la vuelva a pedir en vez de colgarse.

- [x] **La puerta del login tiene tope** (`ESPERA_LOGIN_MINUTOS`, 20 por defecto).
      Sin esto, un `input()` esperando a una persona que no está dejaba la jornada
      entera colgada. Si nadie contesta, el ciclo se pierde y el próximo lo pide
      otra vez.
- [x] **Si el login no se completó, el ciclo corta limpio** en vez de arrancar la
      búsqueda y fallar con un error confuso.
- [x] **Chromes huérfanos: se pregunta por el proceso.** Al cerrar cada ciclo se
      revisa si quedó algún navegador con ese perfil y se reporta con los PIDs.
      *(Ojo con esto: la primera versión buscaba un archivo de bloqueo dentro del
      perfil; se probó contra el navegador real y **ese archivo no existe**. Lo que
      existe es el proceso, con el perfil en su línea de comando. Queda un test que
      lo verifica abriendo un Chromium de verdad.)*
- [x] **La decisión de horario se puede probar**: era un `if` adentro del
      `__main__`; ahora es una función pura con tests (bordes de apertura y cierre,
      fin de semana, días configurables).
- [x] `--limite-ciclos N`: corta después de N ciclos, para dejar una corrida
      acotada y revisar después que no quedó nada colgado.
- [ ] La corrida real de una jornada completa, sin supervisión.

### Fase 10 — Multiagente: identidad, auditoría y datos centralizados

Tres personas (Santiago, Jr y el socio), cada una en su máquina. El asistente tiene
que poder decir **quién hizo qué y con qué identidad**, y el estado y la información
del cliente tienen que estar en **un solo lugar**.

#### Fase 10a — Quién entra y con qué identidad *(se puede hacer ya, sin hub)*

El log ya sella `usuario` (el de Windows) y `maquina` (D11). Lo que falta es lo que
importa de verdad cuando hay más de una persona: **son dos identidades distintas**.

| | Qué es | Ejemplo |
|---|---|---|
| **Operador** | Quién está manejando el asistente | Jr |
| **Identidad del acto** | Con qué matrícula/sesión y con qué firma se ejecutó | Santiago — LV029, firma de Santiago |

La cédula que se firma y se notifica queda **legalmente en cabeza de la identidad
usada**, aunque la haya movido otra persona. Por eso el registro las separa: es lo
que protege a los dos.

**Cómo funciona la puerta (D19):**

1. **Al abrir el asistente, una vez por jornada:** ¿Quién está trabajando? (lista de
   personas de `config.py`). Queda en `sesion.json` con la hora de inicio y la
   máquina, y **se ve siempre en la barra de arriba** — *"Trabajando: Jr"*. Un dato
   que no se ve, no se controla.
2. **Se puede cambiar** (se sienta otro). La declaración **vence al cerrar el día**
   o después de X horas sin actividad: al vencer, vuelve a preguntar.
3. **Antes de tocar el portal no se pregunta de nuevo**: se **confirma en pantalla**,
   en la pausa que ya existe:

   > Vas a actuar con la identidad de **Santiago** (LV029) en el SISFE.
   > Operador registrado: **Jr**. ¿Seguimos?

4. Cada línea del log queda con: `operador`, `usuario_windows` (el de la máquina, que
   la interfaz no puede falsear → **control cruzado**), `maquina`, `identidad`, `firma`.

**Lo que este registro NO es** (para no venderlo como algo que no es): **no prueba
quién apretó FIRMAR.** Eso lo prueba FirmAr, con su matrícula y su OTP — el acuerdo
que ya tienen Santiago y Jr, y que **no se toca**. El log aporta el contexto
alrededor: quién operó, desde qué máquina, con qué identidad declarada.

**Estado: hecho el 16/09/2026** (falta lo que depende del hub y dos cosas que no
se decidieron todavía — ver abajo).

- [x] `sesion.py`: la jornada (operador + inicio + máquina), con vencimiento por
      cambio de día y por inactividad (12 h). *(hecho)*
- [x] La puerta al abrir el panel + *"Trabajando: X"* en la barra de estado
      (y se cambia haciendo clic ahí). *(hecho)*
- [x] `registrar_log` sella `operador` e `identidad`, además del `usuario` de
      Windows y la máquina. *(hecho)*
- [x] Las pausas de firma y de SISFE confirman la identidad antes de seguir, y el
      aviso se dice una sola vez por trabajo. *(hecho)*
- [x] La lista de personas, su matrícula y **su perfil de Chrome** salen de
      `config.py` (D24), no cableadas. *(hecho)*
- [x] Un nombre que no está en la lista **no entra**: el log no se puede firmar
      con cualquier nombre. *(hecho)*
- [x] **La regla de la cadena (D25)**, en los tres lugares donde se puede cruzar:
      **al generar** (la cédula nace con la identidad de quien la generó, y el
      monitor la marca con la matrícula de la máquina, que es la sesión de la que
      bajó los decretos), **al firmar** y **al notificar**. Si se intenta cruzar,
      **frena y dice por qué**; y el candado no se puede corregir por atrás: una
      vez que la cédula es de alguien, es de esa persona. *(hecho)*
- [x] **El ingreso con el mail (D26)**: se entra con el mail o con el nombre, y el
      que no está en la lista no entra (con el motivo **en la puerta**, no en un
      aviso que se pierde). *(hecho)*
- [ ] **La firma en lote**: hoy el lote entero usa la identidad de la jornada, y el
      servidor verifica una por una que ninguna cédula sea de otra persona (si lo
      es, frena). Falta poder **elegir la identidad del lote** desde el panel.
- [ ] **La casilla de mail por persona**: no se decidió si cada uno usa la suya o
      siguen con una del estudio. Hoy la capa de mail es del estudio.
- [ ] **El monitor**: corre con la matrícula configurada en la máquina
      (`SISFE_USUARIO`), no con la identidad de una persona. Es correcto mientras
      el monitor sea "de la máquina" y no de alguien; si el estudio quiere que el
      monitor corra con la sesión de una persona, es una decisión aparte.

#### Fase 10b — El almacén central (el hub)

El problema no es el espacio en disco: es que **cada máquina tiene su propia verdad**.

- El anti-duplicado es por máquina → **dos personas pueden notificar la misma cédula
  dos veces** y ninguna se entera. Ese es el riesgo real (D22).
- El log partido en dos **no es auditoría**: para reconstruir un expediente hay que
  juntar los dos archivos.
- La carpeta del cliente copiada en cada máquina no es redundancia, es
  **divergencia**: dos versiones del mismo caso y nadie sabe cuál vale.

**Qué se centraliza y qué no (D21).** Centralizar una sesión sería centralizar
credenciales: eso no se hace. El que tiene la sesión es la máquina.

| Se centraliza (una sola fuente de verdad) | Queda local (es de la máquina) |
|---|---|
| El estado de las cédulas **y el anti-duplicado** | Los perfiles de Chrome y las sesiones de los portales |
| El log / la auditoría | La firma (FirmAr, con su OTP) |
| La ficha del cliente: expediente, carátula, CUIJ, documentos, notas | La generación de los PDF |
| La lista de personas e identidades | La matrícula del perfil y las rutas de cada máquina |

**El contrato antes del motor.** Cuatro operaciones: *leer estado · escribir estado ·
agregar al log · leer/escribir la ficha del cliente*. Con el contrato fijo, dónde vive
el almacén pasa a ser configuración:

- **Hub en la oficina** (una máquina del estudio o una VM): los datos no salen del
  estudio. Contra: depende de que esa máquina esté prendida.
- **VM en la nube**: no depende de ninguna máquina del estudio y permite trabajar de
  cualquier lado. Contra: **los datos de los clientes salen del país** — no es una
  decisión técnica, **la decide Santiago** (secreto profesional).
- **Git como sincronización:** descartado. Dos personas a la vez sobre el mismo JSON
  son conflictos de merge, y no hay concurrencia de verdad.

**Recomendación, en orden:**

1. Escribir el contrato y correr el hub **en local**, en una carpeta: valida el diseño
   con cero infraestructura.
2. Moverlo a una máquina del estudio — **que no sea la de trabajo**: mezclar el
   "cerebro" con la máquina que corre Chrome hace que cada cierre de Chrome sea una
   caída del hub para todos.
3. Si hace falta trabajar de afuera, recién ahí la VM.

**Las VMs gratis, con los números verificados (16/09/2026):**

| | Google Cloud free tier | Oracle always free |
|---|---|---|
| Máquina | 1 × e2-micro, 30 GB de disco | 2 OCPU / 12 GB ARM (bajó de 4/24 en 2026) |
| Salida | **1 GB por mes** | — |
| Región | **solo 3 de EE.UU.** | admite **São Paulo** (los datos quedan en Sudamérica) |
| Contra | los datos quedan en EE.UU. | la capacidad ARM gratis se agota; el alta es engorrosa |

Para nuestro tráfico (JSON chico) **cualquiera de las dos alcanza de sobra**. Y ninguna
de las dos es para *servir* el asistente: el navegador, la firma y la generación siguen
en la máquina de cada uno. **La VM es un almacén, nada más.**

- [ ] El contrato del almacén (las 4 operaciones) + una implementación local.
- [ ] `estado.py` y `registrar_log` detrás del contrato.
- [ ] El anti-duplicado central: dos máquinas no pueden notificar lo mismo.
- [ ] La ficha del cliente (expediente por CUIJ), con quién la tocó por última vez.
- [ ] Prueba de fuego: dos personas trabajando a la vez, sin pisarse.

---

## 3. Datos que hay que conseguir (no se inventan)

| Dato | Para qué | Quién lo tiene |
|---|---|---|
| **Nombres de prosecretarios por juzgado** | Fase 1 | Santiago (o los decretos reales) |
| **Una cédula de peritos real** | Fase 1 | ✅ **Recibida** el 16/09/2026 (Reconquista) |
| **El nombre del juzgado cuando se llama distinto** | Encabezado de las cédulas | Sale de la cédula real de ese juzgado y se pasa en `datos["juzgado_header"]`. El número de distrito judicial **no se deduce de la ciudad**: distrito judicial no es la circunscripción y los numeran sin orden (San Jorge es el Nº 11) |
| **¿FirmAr y SISFE comparten claves?** | Fase 7 | Santiago |
| ~~Tipos de expediente de Meta Jurídico~~ | ~~Fase 5~~ | **ya no hace falta**: Meta salió del circuito (D1) |
| **Lista real de partes de SISFE** | Fase 6 | ✅ **Recibida** el 16/09/2026 — las 4 filas están en la Fase 6 |
| **El correo de los representantes** | Fase 6 | ✅ **Contestado**: lo trae cargado el SISFE (D16) |
| **El nombre del socio** | Fase 10a | Santiago (para que la lista de operadores esté completa) |
| **Si los tres actúan con la identidad de Santiago o alguno tiene la suya** | Fase 10a | Santiago. No cambia el diseño (la identidad es un dato por acto); cambia la lista |

Mientras un dato no esté, el código queda listo y **el campo se muestra vacío**
(nunca con un valor inventado).

---

## 4. Fuera de alcance (decidido el 16/09/2026)

| Tema | Por qué queda afuera |
|---|---|
| **Formularios SRT (Anexos I a IV)** | Santiago **usa la SRT directo desde Claude**. La skill `cliente-art-nuevo` ya tiene los 4 Anexos y el mapeo verificado (commit `a7da75e`), así que no falta nada — pero **no se sigue invirtiendo ahí**. Lo único que sigue valiendo es controlar que los formularios no queden sin vigencia. |
| **Meta Jurídico** | Sale del circuito (16/09/2026): la cédula firmada va directo al SISFE. `meta_juridico.py`, `_navegador.py` y la parte de `config_portales.py` quedan **guardados y dormidos** en el repo — no se borran ni se usan. |
| **Las 4 skills del secretario** (art, boletas, raeo, transferencia) | Santiago las va a usar **desde Claude**. Quedan **guardadas** en `skills/` y siguen invocables por `/api/skill/<id>`; no se desarrollan más desde el dashboard. |
