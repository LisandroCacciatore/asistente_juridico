# Asistente Jurídico — Pendientes reales (Gherkin)

Generado contra el repo real (https://github.com/LisandroCacciatore/asistente_juridico),
commit `beb7f72`, verificado con `git log`, `git ls-files`, chequeo de sintaxis
de los 40 `.py` del repo, y lectura de `skills/LEEME_MIGRACION.md`,
`acciones.py`, `mail_gmail.py`, `servidor.py`.

**Antes de tocar nada:** la migración de las 6 skills ya está hecha (ver
`LEEME_MIGRACION.md`), la unificación de `cedula-sisfe` al motor del repo
ya está hecha, el dashboard con mail y panel de acciones ya está hecho
(1398 líneas, no la versión vieja). Estos escenarios son **solo lo que
sigue sin validar o sin resolver** — no dupliques trabajo ya hecho.

Cada `Feature` es independiente; el agente puede tomarlas en el orden que
prefiera, salvo donde se indica una dependencia explícita.

---

```gherkin
# ============================================================
Feature: Selectores de SISFE sin confirmar en vivo
  Como responsable de mantener el Asistente Jurídico
  Quiero que los selectores marcados ⬅ VALIDAR se confirmen contra el
  portal real
  Para que el login y la búsqueda no fallen silenciosamente en producción

  Background:
    Dado que "monitor_playwright.py" selecciona "#circunscripcion" con
      valor "2" y "#colegio" con valor "0" en el login de SISFE
    Y estos valores nunca se confirmaron contra el HTML real del portal

  Scenario: Confirmar los valores del formulario de login
    Dado que Santiago (o quien tenga matrícula) puede loguearse en SISFE
    Cuando se inspeccionan los <select> "#circunscripcion" y "#colegio"
      en la página de login real
    Entonces se documenta el valor real de cada <option> seleccionada
    Y si "2" y "0" no coinciden, se corrige "monitor_playwright.py" con
      el valor correcto
    Y se deja un comentario con la fecha de verificación, reemplazando
      la marca "⬅ VALIDAR"

  Scenario: Confirmar el selector de búsqueda por CUIJ en apertura de cuenta
    Dado que "skills/apertura-cuenta-judicial-banco-municipal/scripts/
      apertura_cuenta_judicial.py" tiene el campo CUIJ marcado
      "⬅ VALIDAR" (línea 133) y un selector "que no sea el de días"
      marcado igual (línea 142)
    Cuando se corre el script contra un CUIJ real de un expediente que
      SÍ tenga cuenta judicial abierta en el Banco Municipal
    Entonces el script debe encontrar el campo, completar la búsqueda,
      y tomar las dos capturas (ficha del expediente + pantalla de
      "Ver cuenta judicial") sin caer a ningún selector de respaldo
    Y si falla, se corrige el selector con el valor real visto en el
      inspector, no con una nueva conjetura

# ============================================================
Feature: Circuito de Meta Jurídico de punta a punta, sin cortes
  Como Santiago
  Quiero subir una cédula real a Meta Jurídico sin que el sistema caiga
  a "Solicita Revisión" ni a ningún mensaje de error
  Para confiar en automatizar la presentación, no solo la búsqueda

  Background:
    Dado que "meta_juridico.py" tiene los prints de progreso
      ("→ yendo a Expedientes...", etc.) para diagnóstico
    Y la última evidencia disponible es una búsqueda exitosa aislada,
      no un circuito completo firma→subida→presentación sin intervención
      manual

  Scenario: Subida real, de punta a punta, sin caer al modo manual
    Dado una cédula ya firmada de un caso real que SÍ existe en Meta
      Jurídico (confirmado por búsqueda manual previa del apellido)
    Cuando se ejecuta "Subir a Meta Jurídico" desde el dashboard
    Entonces el sistema debe encontrar el expediente, adjuntar el PDF, y
      llegar a la pantalla de confirmación sin ningún "⚠ No pude
      completar la carga automática"
    Y se registra en "log_acciones.jsonl" el resultado completo, con el
      tiempo que tardó cada paso (útil para detectar cuál es lento)

  Scenario: Repetir la subida tres veces seguidas con casos distintos
    Dado que una sola corrida exitosa no prueba estabilidad
    Cuando se repite el escenario anterior con tres cédulas de casos
      reales distintos, en la misma sesión
    Entonces las tres deben completarse sin intervención manual
    Y si alguna falla, se anota el paso exacto donde falló (usando los
      prints de progreso ya existentes) antes de tocar el código

# ============================================================
Feature: Firma en lote con documentos reales
  Como Santiago
  Quiero firmar varias cédulas en una sola sesión de FirmAr
  Para no repetir login y adjuntar uno por uno

  Background:
    Dado que "firmar_lote" en "firma.py" y "/api/firmar_lote" en
      "servidor.py" existen y están wireados al dashboard
    Y toda la evidencia de que funciona es contra dummies, nunca contra
      FirmAr real con documentos reales

  Scenario: Firmar dos cédulas reales en una sola sesión
    Dado dos cédulas reales, generadas y pendientes de firma
    Cuando se dispara "Firmar todas las pendientes" desde el dashboard
    Entonces FirmAr debe pedir login una sola vez
    Y debe adjuntar cada documento automáticamente, pidiendo PIN por
      cada uno
    Y las dos deben terminar con "estado: firmada" y su
      "fecha_firmada" en "estado.json"
    Y si el paso "volver a Firmar documento" (entre un documento y el
      siguiente) falla, debe caer al mensaje de respaldo ya escrito en
      "firma.py", no romper el lote entero

# ============================================================
Feature: Modo continuo del monitor sostenido en el tiempo
  Como Santiago
  Quiero dejar "monitor_playwright.py" corriendo sin supervisión durante
  la jornada
  Para no tener que re-lanzarlo cada vez que quiero novedades

  Background:
    Dado que el modo continuo (sin "--una-vez") ya existe, usa
      "INTERVALO_MINUTOS", "HORARIO_INICIO/FIN" y "DIAS_HABILES"
    Y solo se probó la lógica de horario en aislado (4 casos), nunca una
      corrida real sostenida

  Scenario: Corrida sostenida de una jornada completa
    Dado el monitor arrancado a primera hora, con login ya resuelto
    Cuando pasan varias horas dentro del horario laboral configurado
    Entonces debe seguir revisando cada "INTERVALO_MINUTOS" sin pedir
      login de nuevo (mientras la sesión de SISFE no expire)
    Y no debe crecer sin límite en uso de memoria ni dejar procesos de
      Chrome huérfanos entre ciclos
    Y al llegar "HORARIO_FIN" debe pasar a modo de espera sin hacer
      nada, y retomar al otro día hábil dentro de "HORARIO_INICIO"

  Scenario: La sesión de SISFE expira a mitad de una corrida continua
    Dado el monitor corriendo hace varias horas
    Cuando la sesión de SISFE expira (por inactividad o por el propio
      portal)
    Entonces el próximo ciclo debe detectarlo y pedir login de nuevo
      (puerta humana), no quedarse trabado ni fallar en silencio

# ============================================================
Feature: Vigencia de los formularios SRT (cliente-art-nuevo)
  Como Santiago
  Quiero que los Anexos que genera el sistema sean la versión vigente
  Para no presentar un formulario dado de baja por la SRT

  Background:
    Dado que "skills/cliente-art-nuevo/assets/" tiene los Anexos I, II y
      III descargados de argentina.gob.ar, con el mapeo de campos
      verificado y test funcional PASS
    Y CONFIRMADO contra la fuente primaria (Boletín Oficial, Resolución
      SRT 5/2026, RESOL-2026-5-APN-SRT#MCH, publicada 29/01/2026,
      vigente desde el 02/02/2026, art. 4): los formularios vigentes y
      OBLIGATORIOS son CUATRO — Anexo I, II, III y **Anexo IV**
      (IF-2026-09572607-APN-SRT#MCH) — para los mismos trámites de las
      Resoluciones 179/15 y 298/17 que ya cubre esta skill
    Y el Anexo IV (reingreso, divergencia en el alta médica, divergencia
      en las prestaciones) tampoco estaba en "assets/" al escribir esto
      — faltaba directamente, no era una duda de vigencia
      (✅ agregado en a7da75e; ver la nota bajo el scenario)

  # ✅ HECHA en a7da75e (16/09/2026). El Anexo IV está en assets/ con sus 27
  # campos mapeados en FIELD_MAPS["IV"], verificado por geometría (el rect de
  # cada campo contra la caja de cada texto) y después contra el render.
  #
  # ALCANCE CERRADO (16/09/2026): no se sigue invirtiendo acá. Santiago usa la
  # SRT directo desde Claude, así que el formulario se resuelve fuera del repo.
  # Lo que sigue valiendo es el control de vigencia (el scenario de abajo): si
  # la SRT publica un formulario nuevo, hay que enterarse. El mapeo ya hecho no
  # se toca "para mejorarlo" — se verificó, y cada campo tocado se vuelve a
  # verificar contra el PDF oficial o no se toca.
  Scenario: Agregar el Anexo IV que falta
    Dado el formulario oficial "Anexo IV" (IF-2026-09572607-APN-SRT#MCH)
      publicado junto a la Resolución 5/2026 en la edición web del BORA
    Cuando se descarga desde el sitio oficial (argentina.gob.ar/srt o el
      propio Boletín Oficial, que aloja los anexos de la resolución)
    Entonces se agrega a "skills/cliente-art-nuevo/assets/" con el mismo
      criterio que los otros tres (nombre descriptivo, verificación de
      campos contra el script si corresponde)
    Y se actualiza "fill_srt_form.py" y "SKILL.md" para contemplar el
      caso que resuelve el Anexo IV (reingreso / divergencia en el alta
      / divergencia en las prestaciones), que hoy no tiene ningún
      formulario asociado en la skill

  Scenario: Confirmar que los Anexos I, II y III son la versión post-Res. 5/2026
    Dado que la resolución identifica cada anexo por su número de IF
      (ej. Anexo I = IF-2026-09572121-APN-SRT#MCH), no por nombre de
      archivo
    Cuando se descargan de nuevo los tres Anexos desde el sitio oficial
    Entonces se comparan contra los que ya están en "assets/" (por
      contenido, no solo por nombre — el nombre de archivo del repo no
      coincide con el que usa hoy argentina.gob.ar, así que el nombre
      solo no alcanza para confirmar la versión)
    Y si difieren, se reemplazan y se vuelve a correr la verificación de
      campos (FIELD_MAPS) antes de tocar nada más
    Y se anota en "LEEME_MIGRACION.md" la fecha de esta confirmación,
      junto con el número de resolución vigente (Res. SRT 5/2026)

# ============================================================
Feature: Capa de mail del secretario (Gmail vía Hermes)
  Como Santiago
  Quiero leer y responder mail relacionado a los casos desde el
  dashboard, sin que el sistema envíe nada solo
  Para no tener que salir del panel para gestionar la bandeja

  Background:
    Dado que "mail_gmail.py" usa el token OAuth que ya administra
      Hermes ("~/AppData/Local/hermes/google_token.json")
    Y "servidor.py" expone "GET /api/mail/bandeja" y
      "GET /api/mail/borradores"
    Y la regla explícita en el código es "SIEMPRE borradores, nunca
      envío directo"

  Scenario: Leer la bandeja real desde el dashboard
    Dado el token OAuth de Hermes ya autorizado contra la cuenta real
      de Gmail del estudio
    Cuando se abre la sección de mail del dashboard
    Entonces debe listar los mensajes reales de la bandeja, no datos de
      prueba
    Y si el token expiró o no está autorizado, debe mostrar un mensaje
      claro (no un error genérico) explicando qué hacer

  Scenario: Un borrador armado por el secretario nunca se envía solo
    Dado un caso donde el secretario arma una respuesta (por ejemplo,
      el modelo del RAEO que devuelve un juzgado)
    Cuando el borrador se genera vía "mail_gmail.py draft"
    Entonces debe quedar visible en "borradores" de Gmail y en
      "/api/mail/borradores"
    Y bajo ninguna circunstancia debe existir un camino de código que
      lo envíe sin un clic explícito del abogado en el dashboard
    Y este escenario se verifica leyendo el código de "acciones.py" y
      "mail_gmail.py" en busca de cualquier llamada a enviar/send que
      no dependa de una acción humana explícita

# ============================================================
Feature: Las 4 skills del secretario (art, boletas, raeo, transferencia),
  de punta a punta
  Como Santiago
  Quiero disparar cada skill desde el dashboard y obtener el resultado
  real
  Para no tener que volver al chat de Claude para estos trámites

  Background:
    Dado que "acciones.py" registra las 4 skills en "secretario()":
      "art" → cliente-art-nuevo, "boletas" → oficio-incumplimiento-
      boletas, "raeo" → oficio-raeo, "transferencia" →
      transferencia-de-capital
    Y el endpoint real es "POST /api/skill/{accion}"
    Y cada una corre Hermes en un proceso aparte con timeout, matando
      el árbol completo de procesos si se cuelga (crítico en Windows,
      donde los nietos de Chrome/Playwright sobreviven si solo se mata
      el padre)

  Scenario Outline: Disparar cada skill con un caso real y verificar la salida
    Dado un caso real que corresponda al trámite "<skill>"
    Cuando se llama "POST /api/skill/<accion>" con los datos del caso
    Entonces el proceso de Hermes debe terminar dentro del timeout
      configurado
    Y debe producir los archivos de salida esperados por esa skill
      (ver su SKILL.md para el detalle exacto)
    Y si la skill genera un borrador de mail, debe aparecer en
      "/api/mail/borradores", nunca enviado

    Examples:
      | accion        | skill                          |
      | art           | cliente-art-nuevo               |
      | boletas       | oficio-incumplimiento-boletas   |
      | raeo          | oficio-raeo                     |
      | transferencia | transferencia-de-capital        |

  Scenario: Un proceso de Hermes que se cuelga no deja procesos huérfanos
    Dado una skill que por algún motivo no termina dentro del timeout
    Cuando "_correr()" en "acciones.py" mata el proceso por timeout
    Entonces no debe quedar ningún proceso hijo (Chrome, node,
      Playwright) corriendo en el Administrador de Tareas después de
      matar el padre

# ============================================================
# ✅ HECHA en 0140f77: tests/ existe y corre (33/33 en 0,46 s, sin portal).
#    Ver tests/README.md. Se deja el texto original abajo como registro de
#    qué se pidió, pero NO hay que reimplementarla.
Feature: Suite de pruebas automatizada (HECHA en 0140f77 — ver nota)
  Como quien mantenga este repo de acá en adelante
  Quiero un conjunto de pruebas que se puedan correr con un solo
  comando
  Para no depender de que cada agente redescubra a mano si algo se
  rompió

  Background:
    Dado que al escribir esto (contra `beb7f72`) el único archivo de
      prueba en todo el repo era "dev/test_rail.js" (riel visual del
      dashboard)
    Y en `0140f77` se agregó "tests/" con 33 pruebas que pasan sin
      portal ni login (estado.py y cedula_desde_texto.py)
    Y toda la validación de "estado.py", "generar_cedula.py",
      "meta_juridico.py", "firma.py", el modo continuo, y las 4 skills
      del secretario se hizo con dummies ad-hoc durante sesiones de
      desarrollo, sin quedar guardada como prueba repetible

  Scenario: Armar una carpeta de pruebas mínima, sin navegador real
    Dado la lógica pura de "estado.py" (agregar_pendiente, marcar_
      presentada + borrado automático, log de acciones) y de
      "cedula_desde_texto.py" (extraer_caratula/cuij/fecha,
      es_sentencia, recortar_sentencia)
    Cuando se crea una carpeta "tests/" con casos que no necesiten
      Playwright ni un portal real (son funciones puras sobre texto)
    Entonces correr esas pruebas debe confirmar, sin tocar ningún
      portal, que las reglas de negocio siguen funcionando después de
      cualquier cambio futuro

  Scenario: Documentar cuáles pruebas SÍ necesitan un portal real
    Dado que buena parte de este sistema no se puede probar sin SISFE,
      FirmAr o Meta Jurídico real
    Cuando se arma la suite de pruebas
    Entonces se separan claramente las pruebas "sin portal" (rápidas,
      correr siempre) de las "con portal real" (manuales, correr antes
      de cada entrega grande) — sin fingir que las segundas se pueden
      automatizar del todo
```

---

## Notas para quien tome este archivo

- **No re-implementar nada que ya esté en `LEEME_MIGRACION.md` como
  completo.** Ese archivo es la fuente de verdad de qué se migró y qué
  falta dentro de cada skill.
- **`config.py` no está en el repo** (a propósito). Para correr
  cualquiera de estos escenarios hace falta copiar `config.example.py`
  a `config.py` y completarlo — ahí están documentadas todas las claves
  que el código realmente importa.
- **El repo puede estar en privado.** Si no se puede clonar, es porque
  Lisandro lo puso en privado a propósito (dato de esta sesión) — pedir
  que lo pase a público un rato, no asumir que el repo dejó de existir.
- Los escenarios de "Meta Jurídico sin cortes" y "firma en lote real"
  son los de mayor impacto si hay que priorizar: son los dos únicos
  tramos del circuito principal (no de las skills satélite) que
  todavía no se vieron funcionar de punta a punta con casos reales.
- **Hallazgo confirmado en esta vuelta, no una duda:** falta el
  **Anexo IV** de la SRT (Resolución 5/2026, vigente desde 02/02/2026).
  No es "hay que validar si cambió" — es "falta directamente, hay que
  agregarlo". Ver el detalle en la Feature de vigencia SRT.
