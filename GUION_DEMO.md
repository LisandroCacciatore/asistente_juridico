# Guion de la demo (Estudio Segovia)

Probado de punta a punta el 13/10/2026 contra `4e1b4b2`, en Chromium real.
Todo lo que dice acá **se corrió**, no es lo que debería pasar.

---

## 0. Antes de que llegue (5 minutos)

```bash
cd ~/asistente_juridico
rm -f sesion.json          # si no, D19 no vuelve a preguntar quién trabaja
```

**Arrancar con el `.bat`, no a mano:** doble clic en `Iniciar_Asistente.bat`
(desde la terminal también sirve: `./Iniciar_Asistente.bat`).

Hace dos cosas: levanta `python servidor.py` en su propia ventana (esa ventana es
el log) y abre `http://localhost:8000` en el navegador.

> ⚠️ **Abrilo en Chrome, nunca en el panel de Hermes.** El webview de Hermes
> bloquea los POST: los botones no hacen nada y la demo se cae sola.

**Decidí qué cédulas querés que se vean.** `estado.json` hoy tiene 8, y **tres
son casos reales** (con su CUIJ y el nombre del cliente):

```bash
cp estado.json estado.json.bak     # antes de tocar nada
python reset_registros.py          # deja las 3 listas vacías
```

Si reseteás, el panel arranca vacío y el recorrido es "pego un decreto y se
genera la cédula" — que es la mejor historia. Ojo: `reset_registros.py` **no
borra `log_acciones.jsonl`**, así que la Actividad sigue con historial (queda
bien: muestra que el log es acumulativo).

**Si querés mostrar la bandeja de mail**, hay que reautorizar el token de Google
(hoy está vencido, ver §4). Es un acto tuyo, con consentimiento en el navegador:

```bash
python "C:/Users/Torso/AppData/Local/hermes/skills/productivity/google-workspace/scripts/setup.py"
```

---

## 1. El recorrido (10 minutos)

### 1.1 La puerta: quién está trabajando (D19 · D26)

Al abrir, **el modal aparece solo** y no se puede saltear. Es lo primero que
conviene mostrar, porque es el argumento del sistema: *"el registro no es un
adorno, es la puerta de entrada"*.

- Pide el mail. Mientras no tenga el mail cargado, están los atajos
  **Santiago / Jr / Socio** (tocás uno, se llena, "Entrar").
- Queda en la barra de arriba: **`Trabajando: Santiago`**, y ahí se cambia
  (si se sienta otro).
- Vence al cambiar el día o a las 12 h sin actividad. No se vuelve a preguntar
  en la misma jornada.

### 1.2 La bienvenida y el panel

Al entrar arranca una **secuencia de bienvenida**: fondo azul tinta, *"Buenos
días, Santiago"* y cuatro líneas que se van tildando solas — sesión iniciada
(perfil de Chrome), expedientes con novedades, decretos clasificados, cédulas
listas para revisar. Dura unos segundos, se puede cortar con **"Saltar →"**, y
**vale la pena dejarla correr**: es el momento en que el sistema lo recibe a él,
y usa el nombre que acaba de declarar en la puerta.

Después queda el panel:

- **"Revisé 8 expedientes esta mañana."** y el resumen en una línea (*"5 esperan
  tu firma, 1 para subir al SISFE, 1 decreto para clasificar y 1 requiere
  atención."*)
- las **cuatro tarjetas de métricas**: Listas para firmar · Listas para presentar
  · Pendientes de clasificar · Requieren atención
- **Acciones del secretario** (Cédula desde texto, y la aclaración de que las
  otras cuatro se corren desde la carpeta del cliente)
- **Listas para firmar** con las cédulas y, más abajo, **Listas para presentar**,
  **Pendientes de clasificar**, **Requiere revisión**
- al final, **Mail** y **Actividad del secretario**

Cada cédula es una tarjeta con **su riel de 6 pasos** (Detectado · Generado ·
Firma · Firmado · Subida · Presentado), la barra de AVANCE (ej. 2/6), los
PRÓXIMOS pasos y el botón **"Revisar y firmar"**.

La barra de estado ahora dice la verdad:

```
Trabajando: Santiago | Servidor: conectado | Datos: reales | SISFE y FirmAr: los abrís vos
```

Los dos primeros dependen de si el panel habló con el servidor (por eso, si
apagás `servidor.py` y recargás, cambian a "sin conexión" / "Datos: demo").
El tercero no es un estado: es la puerta humana, dicha como tal.

### 1.3 Revisar la cédula y ver el PDF de verdad  ← **el momento fuerte**

En una cédula, **"Revisar y firmar"**. El modal muestra primero **los datos**
(qué se interpretó: juzgado, juez, CUIJ, destinatarios, el decreto).

> *"Antes acá decía «vista previa del PDF» y era mentira: el navegador no puede
> abrir una ruta del disco. Ahora hay un botón que te lo muestra de verdad."*

Apretá **"📄 Ver el PDF"**: se carga el visor de Chrome con la cédula tal como se
va a firmar, y el epígrafe aclara si es la generada o la ya firmada.

Dos detalles que valen la pena decir en voz alta:

- El visor carga **sólo cuando lo pedís**: si cargara al abrir el modal, cada
  mirada a una cédula bajaría un PDF entero.
- La ruta del archivo **sale siempre del registro**, nunca de lo que manda el
  navegador: no hay forma de pedir un archivo que no sea de una cédula tuya.

### 1.4 Firmar todas en una sola ventana (la identidad del lote)

Con dos o más cédulas listas aparece el botón **"🔒 Firmar todas en una sola
ventana"**. Aprietalo y aparece:

> **¿Con qué identidad se firman las 4?**
> Una sola ventana de firma para las 4: podés usar tus claves o las de un
> compañero. La que elijas vale para todo el lote.
> `Santiago` · `Jr` · `Socio`

Es la regla de la cadena (D25). Y si las cédulas del lote vinieran de sesiones
del SISFE de personas **distintas**, el panel no ofrece nada: avisa que un lote
es una sola sesión de FirmAr, que se firmen por separado, y **no abre nada**.

> ⚠️ **En la demo, cerrá ese modal con "Cancelar".** Elegir una identidad abre
> FirmAr de verdad y te pide contraseña, OTP y PIN — no es un simulacro.

### 1.5 De texto a cédula

**"📄 Cédula desde texto"**: pegás el decreto y el panel te muestra **antes de
generar** qué interpretó (carátula, CUIJ, fuero, ciudad, juzgado y **a quién
notificar**, con todos tildados). Destildás lo que no va y generás.

> *"Nada se inventa: lo que no está en la carátula ni en el decreto queda vacío
> y lo agregás a mano. Y la lista de destinatarios la confirmás vos, no el
> sistema."*

### 1.6 Acciones del secretario y Mail

**Acciones del secretario**: raeo, boletas, transferencia, alta de ART. Cada una
corre en su propio proceso, con timeout, y **deja el mail como borrador**.

**Mail**: va a mostrar *"La sesión de Gmail venció: hay que volver a autorizar la
casilla."* — y ese es el punto: **un mensaje que te dice qué hacer**, no un error
genérico. Ver §4 si querés que funcione.

### 1.7 Actividad del secretario

Cada línea del log lleva **operador**, **identidad**, **usuario de Windows** y
**máquina**. El caso interesante: si alguien opera con las claves de un
compañero, se ve marcado *"actuó con la identidad de X"*.

> *"FirmAr prueba quién apretó FIRMAR, con su matrícula y su OTP. Esto no
> reemplaza eso: agrega el contexto alrededor — quién operó, desde qué máquina,
> con qué identidad declarada."*

---

## 2. Las puertas humanas (el argumento de confianza)

Decilo explícito, en este orden, porque es lo que hace vendible el sistema:

| Dónde | Qué hacés vos | Por qué no se automatiza |
|---|---|---|
| SISFE | reCAPTCHA | Seguridad del acceso matriculado |
| FirmAr | CUIL + contraseña + OTP + PIN + FIRMAR | Es tu firma, con tu responsabilidad |
| SISFE | Clic final en **NOTIFICAR** | Acto irreversible |
| Gmail | Enviar | El sistema **nunca** manda solo |

Y el respaldo: **hay un test que lee el código y falla si alguien agrega un clic
en Notificar**, y otro que corre el flujo contra una pantalla de mentira y
comprueba que el botón quedó sin apretar. No es una promesa, es un candado.

---

## 3. Lo que NO va a andar (y no hay que intentar)

| Qué | Por qué | Cómo se ve |
|---|---|---|
| **Firmar de verdad** | Falta su CUIL/OTP/PIN, y es un acto real | No lo toques: mostrá el modal y Cancelá |
| **Notificar en el SISFE** | Los 5 selectores están `⬅ VALIDAR`: nunca se vio el portal | Si lo dispara, frena y pide que lo hagas a mano |
| **El monitor de SISFE** | Los selectores del login sin validar | No arrancarlo |
| **La bandeja de mail** | Token de Google vencido (§4) | Muestra el mensaje claro |
| **La firma en lote real** | Código listo, nunca corrido contra FirmAr | Mostrar sólo la puerta de identidad |

Nada de esto se rompe ni queda colgado: **frena y avisa**. Ese es el diseño.

---

## 4. Las 4 decisiones y los 5 datos

### Decisiones (son suyas, no técnicas)

1. **¿FirmAr y SISFE comparten claves?** Es lo que falta para D7/Fase 7.
2. **El nombre del socio**: hoy dice "Socio" en `config.py` y en la lista de
   operadores.
3. **¿Los tres actúan con la identidad de Santiago, o alguno tiene la suya?**
   No cambia el diseño (la identidad es un dato por acto); cambia la lista.
4. **¿Cada uno con su casilla de mail, o siguen con una del estudio?**

### Datos / accesos

5. **La casilla de Gmail del estudio**: autorizar el token en su máquina (es un
   clic suyo con su cuenta de Google; los pasos están en §0).
6. **Los nombres de los prosecretarios por juzgado** (o los decretos reales).
7. **Su primera corrida del monitor**, con la guía `INSTRUCCIONES_PLAYWRIGHT.md`.
8. **Un expediente real para la pasada en vivo del SISFE**: hace falta un CUIJ
   que exista de verdad, para confirmar los 5 selectores.
9. **La matrícula del SISFE por persona** (si Jr o el socio van a operar solos).

---

## 5. Si algo sale mal

```bash
# ¿quedó un servidor viejo colgado? (es la causa de la mitad de los males)
netstat -ano | grep ":8000"

# Chrome sueltos que no dejó nadie
taskkill //IM chrome.exe //F
```

Y si el panel no responde: cerrá la ventana "Asistente (servidor)" y volvé a
correr `Iniciar_Asistente.bat`. **El estado no se pierde**: vive en
`estado.json`, no en la memoria del servidor.
