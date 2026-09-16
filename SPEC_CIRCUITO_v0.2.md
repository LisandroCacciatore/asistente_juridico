# SPEC — Circuito del Asistente Jurídico · v0.2 (DECISIONES CERRADAS)

**Base:** `SPEC_CIRCUITO_v0.1.md` (revisión del 16/09/2026).
**Estado:** decisiones aprobadas el 16/09/2026 ("dale con las recomendaciones").
**Regla de este documento:** lo que dice acá es lo que se construye. Si algo se
cambia, se cambia acá primero.

---

## 1. Decisiones cerradas

| # | Decisión | Quedó así |
|---|---|---|
| **D1** | Orden del circuito | **Meta Jurídico primero** (guardar/asociar y crear si no existe), **SISFE después** (notificar con partes). |
| **D2** | "Proveyendo escrito" | ❌ **No es un tipo de cédula** (corregido el 16/09/2026). Es lo que dictó el juzgado — un proveído al escrito presentado. La cédula que lo notifica es la **común**: no hay plantilla nueva **ni subtipo que configurar**. |
| **D3** | Crear expediente en Meta | **Con confirmación previa** en el dashboard, una vez por expediente. |
| **D4** | Alta de Cliente ART | **Se elimina la tarjeta**; la skill queda y se dispara **desde la carpeta de documentación del cliente**. |
| **D5** | Multiagente: cuenta | **Cuenta por persona** (es la única forma de saber *quién* hizo qué). Si en el camino SISFE/Firma no lo permiten por usuario, se documenta la limitación y el log registra la máquina. |
| **D6** | Multiagente: cuándo | **Después** de cerrar el circuito de una sola persona. |
| **D7** | FirmAr vs SISFE | **[A CONFIRMAR EN VIVO]** ¿mismas claves o cuentas distintas de la misma persona? El código se escribe para **elegir la identidad una vez por corrida** y usarla en las dos, con las claves que cada portal pida. |
| **D8** | Varios destinatarios | **Mostrar la lista antes de generar**, todos tildados; el abogado destilda. Una cédula y una firma por destinatario. |
| **D9** | Partes en SISFE | **Cajas fijas** (Seg. Social de Abogados + Caja Forense Rosario) por regla; **representantes desde el expediente**, mostrados para confirmar antes de notificar. |
| **D10** | Correo de la parte | **Solo si existe**; si no, queda vacío (notificación solo en el sistema). |
| **D11** | Log | **Usuario + máquina en cada entrada** (el usuario depende de D5; hasta entonces, el de Windows). |
| **D12** | Mail interactivo | **Abrir hilo · responder como borrador · descartar borrador.** La regla "el envío es del abogado" no se toca. |
| **D13** | Refresco | **Monitor de SISFE: 10 min.** Dashboard: 60 s. |
| **D14** | Tarjetas | **Se sacan las 5 tarjetas**; las skills **quedan** y se siguen pudiendo invocar. |

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

### Fases 5 a 7 — con portal (una sola tanda, con Santiago)
- [ ] Meta Jurídico: crear contacto + expediente si no existe, **con confirmación previa**.
- [ ] SISFE: Nueva cédula → descripción → adjuntar firmada → Partes → notificar.
- [ ] Firma: la identidad elegida en SISFE es la que firma; validar **firma en lote**.

### Fase 10 — Multiagente (proyecto aparte, después)
- [ ] Un usuario = su matrícula, su Firma Digital, su perfil de Chrome, su casilla,
      su entrada en el log.

---

## 3. Datos que hay que conseguir (no se inventan)

| Dato | Para qué | Quién lo tiene |
|---|---|---|
| **Nombres de prosecretarios por juzgado** | Fase 1 | Santiago (o los decretos reales) |
| **Una cédula de peritos real** | Fase 1 | ✅ **Recibida** el 16/09/2026 (Reconquista) |
| **El nombre del juzgado cuando se llama distinto** | Encabezado de las cédulas | Sale de la cédula real de ese juzgado y se pasa en `datos["juzgado_header"]`. El número de distrito judicial **no se deduce de la ciudad**: distrito judicial no es la circunscripción y los numeran sin orden (San Jorge es el Nº 11) |
| **¿FirmAr y SISFE comparten claves?** | Fase 7 | Santiago |
| **Tipos de expediente de Meta Jurídico** | Fase 5 | la pantalla del portal |
| **Lista real de partes de SISFE** | Fase 6 | la pantalla del portal |

Mientras un dato no esté, el código queda listo y **el campo se muestra vacío**
(nunca con un valor inventado).

---

## 4. Fuera de alcance (decidido el 16/09/2026)

| Tema | Por qué queda afuera |
|---|---|
| **Formularios SRT (Anexos I a IV)** | Santiago **usa la SRT directo desde Claude**. La skill `cliente-art-nuevo` ya tiene los 4 Anexos y el mapeo verificado (commit `a7da75e`), así que no falta nada — pero **no se sigue invirtiendo ahí**. Lo único que sigue valiendo es controlar que los formularios no queden sin vigencia. |
