# Instalación — Asistente Jurídico

Guía para dejar andando el asistente en una máquina nueva (la de Santiago, o
cualquier otra). Probada sobre un paquete recién descomprimido, sin nada
instalado antes.

---

## Lo que hace falta

| | Para qué | ¿Obligatorio? |
|---|---|---|
| **Windows 10/11** | es donde corre | sí |
| **Python 3.11** (sirve 3.10+) | el programa | sí |
| **Google Chrome** | los portales (SISFE, FirmAr) se abren en tu Chrome de verdad, con tu sesión | sí |
| **Hermes** | sólo las 4 acciones del secretario (ART, boletas, RAEO, transferencia) y la bandeja de mail | no |

**Sin Hermes el resto funciona igual**: generar cédulas, el panel, la firma, el
visor de PDF y las métricas. Lo único que no anda es lo que corre por Hermes.

---

## Paso a paso

### 1. Descomprimir

En una carpeta tuya, por ejemplo:

```
C:\AsistenteJuridico
```

> ⚠️ **Dos cosas que importan:**
> - **Que no esté en OneDrive ni en una carpeta sincronizada.** El asistente
>   guarda ahí el perfil de Chrome con la sesión del SISFE; si OneDrive lo
>   sincroniza, se corrompe la sesión.
> - **Que la ruta no tenga espacios** (o si los tiene, que sea corta). Chrome es
>   sensible a los perfiles con espacios en la ruta.

### 2. Instalar las dependencias

Abrí la terminal **en esa carpeta** (en el explorador: clic en la barra de
direcciones, escribí `cmd` y Enter) y corré:

```bat
python -m pip install -r requirements.txt
python -m playwright install chromium
```

La segunda baja el Chromium de Playwright (~190 MB). Es el respaldo: si el
Chrome real no está, se usa ese.

Si `python` no se reconoce, instalá Python desde python.org y **marcá la casilla
"Add Python to PATH"** en el instalador.

### 3. Preparar la máquina

Esto crea tu configuración (`config.py`) con tu matrícula del SISFE:

```bat
python preparar_maquina.py --matricula LV029
```

Te dice si falta algo. `config.py` **no viene en el paquete a propósito**: tiene
los datos de cada máquina y no se comparte.

### 4. Arrancar

Doble clic en **`Iniciar_Asistente.bat`**. Hace dos cosas: levanta el servidor
en su propia ventana (esa ventana *es* el log, no la cierres) y abre el panel.

Si no se abre solo, andá a mano a:

```
http://localhost:8000
```

**Abrilo en Chrome, no en el panel de otro programa.** Los visores embebidos de
otras apps bloquean los botones y parece que el sistema no responde.

### 5. El primer día

1. **Se declara quién está trabajando.** Es lo primero que aparece y no se puede
   saltear: se entra con el mail (o con el nombre, mientras no esté cargado).
2. **Cuando toque un portal, el sistema te lo pide y espera.** Se abre tu Chrome
   con tu perfil; te logueás vos (SISFE pide reCAPTCHA, FirmAr pide CUIL,
   contraseña, OTP y PIN). El sistema **nunca** escribe tus claves.
3. **El clic final es tuyo**: NOTIFICAR en el SISFE, FIRMAR en FirmAr, ENVIAR en
   el mail. El sistema deja todo cargado y se detiene.

Arrancás **sin cédulas**: el registro viene vacío a propósito, porque los datos
de un estudio no viajan en el paquete.

---

## Qué NO viene en el paquete (y por qué)

| | Por qué |
|---|---|
| `config.py` | son los datos de la máquina: matrícula, nombres, rutas. Se crea con el paso 3 |
| `estado.json`, `log_acciones.jsonl` | las cédulas y el registro del estudio. Arranca vacío |
| `chrome_profile_*` | las sesiones de los portales. **Centralizar una sesión sería centralizar credenciales** |
| `cedulas_temp/` | los PDF generados. Son transitorios: se borran al cerrar cada cédula |
| `ESTUDIO JURIDICO/` | la carpeta de documentación de los clientes |
| El historial de cambios (`.git`) | el paquete es el programa, no su historia |

---

## Para que anden las 4 acciones del secretario y el mail

Necesita **Hermes** instalado y en el PATH. Se verifica así:

```bat
python preparar_maquina.py --matricula LV029
```

Si dice `'hermes' no está en el PATH`, las acciones del secretario no van a
correr (el resto sí). Para el **mail** hace falta además autorizar la casilla de
Gmail **en esa máquina** (es un permiso por máquina, con consentimiento en el
navegador).

---

## Si algo no anda

| Síntoma | Qué pasa |
|---|---|
| El panel no carga | ¿Quedó un servidor viejo colgado? `netstat -ano \| findstr :8000`. Si hay uno, matalo y volvé a correr el `.bat` |
| Los botones no hacen nada | Estás viendo el panel dentro de otra app. Abrilo en Chrome |
| "El PDF no está en el disco" (o el botón no aparece) | El PDF es transitorio: se borró al cerrar la cédula. Se ve mientras la cédula está abierta |
| La bandeja de mail dice que hay que reautorizar | El permiso de Google venció (o nunca se dio en esta máquina). Se reautoriza una vez, con tu cuenta |
| Chrome queda abierto después de un error | `taskkill /IM chrome.exe /F` y volver a empezar. **El estado no se pierde**: vive en `estado.json`, no en la memoria del programa |

---

## Lo que este paquete todavía no hace

Para que no sorprenda: **nunca se corrió de punta a punta contra los portales
reales.** Firmar en FirmAr sí se probó. **Notificar en el SISFE no, todavía**:
los selectores de ese portal están marcados para confirmar en la primera corrida
en vivo (`⬅ VALIDAR`). Cuando el sistema no encuentra un campo, **frena y te pide
que lo hagas a mano** — nunca sigue a ciegas.
