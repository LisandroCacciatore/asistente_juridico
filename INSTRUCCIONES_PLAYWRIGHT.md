# Firma + subida a Meta Jurídico — scripts de Playwright

Estos dos scripts cierran el circuito que faltaba: agarran la cédula ya generada,
la **firman** (con tu intervención) y la **suben a Meta Jurídico** (con tu 2FA y tu
confirmación final). Todo lo mecánico lo hace el script; los actos irreversibles
los hacés vos.

---

## 1. Qué hace cada archivo

| Archivo | Para qué |
|---|---|
| `config_portales.py` | Direcciones de los portales y rutas. **No tiene contraseñas.** |
| `_navegador.py` | Abre tu Chrome con perfil persistente. Lo usan los dos scripts. |
| `firma.py` | Abre el portal de firma, carga el PDF, frena para que firmes, guarda el firmado. |
| `meta_juridico.py` | Abre Meta Jurídico, frena para el 2FA, busca el expediente, adjunta, y frena para que confirmes. |

---

## 2. Instalación (una sola vez)

Abrí CMD y corré:

```
pip install playwright
python -m playwright install chromium
```

> Los scripts usan tu Chrome real (`channel="chrome"`), no hace falta más.
> El `install chromium` es solo por si algún día querés correrlos sin Chrome.

---

## 3. Completar los datos (una sola vez)

Abrí `config_portales.py` en Sublime y pegá las **dos URLs reales**:

- `FIRMA_URL` → la página donde firmás digitalmente.
- `META_URL` → la página de login de Meta Jurídico.

El resto ya viene configurado (perfil de Chrome, carpeta de descargas).

---

## 4. Completar los selectores (una sola vez, con ayuda)

Los scripts tienen 3-4 marcas `⬅ COMPLETAR` donde va el "selector": la forma de
señalarle al script **qué botón o campo** tocar en cada portal. Como esas páginas
son tuyas y yo no las veo, hay que capturarlos una vez. Playwright trae una
herramienta que **los graba solos mientras hacés clic**:

```
python -m playwright codegen https://LA-URL-DEL-PORTAL
```

Se abre una ventana del navegador y otra con el código. Hacés los clics normales
(elegir archivo, buscar expediente, adjuntar) y en la ventana de código aparece la
línea exacta, por ejemplo:

```
page.get_by_label("Adjuntar archivo").set_input_files("...")
page.get_by_role("button", name="Buscar").click()
```

Copiás esa línea y reemplazás la que dice `⬅ COMPLETAR` en el script. Esto es un
rato de trabajo del desarrollador (o tuyo con él al lado), y queda hecho para siempre.

---

## 5. Cómo se usan (el día a día)

**Firmar una cédula:**
```
python firma.py "C:\...\ESTUDIO JURIDICO\1) ART\GONZALEZ\cédula 21-...\cedula.pdf"
```
El script abre el portal con el PDF cargado y frena con este cartel:

```
  ┌───────────────────────────────────┐
  │  ACCIÓN TUYA                       │
  └───────────────────────────────────┘
  Firmá el documento en la ventana del navegador…
  >>> Cuando termines, presioná ENTER para continuar...
```

Firmás como firmás siempre (contraseña **o** token), volvés al CMD, ENTER, y el
PDF firmado queda guardado al lado del original como `cedula_FIRMADO.pdf`.

**Subir a Meta Jurídico:**
```
python meta_juridico.py "C:\...\cedula_FIRMADO.pdf" "21-00000001-0"
```
Frena para el 2FA, busca el expediente por CUIJ, adjunta el PDF, y frena de nuevo
para que **vos** aprietes "Presentar". El script deja todo listo; el botón final
lo tocás vos.

---

## 6. Por qué las pausas (importante)

El sistema automatiza **hasta el borde** de cada acto irreversible y frena:

- **Firma** → es tu firma, con tu responsabilidad. El script no la falsifica.
- **2FA** → por diseño no se automatiza (ese es el punto del 2FA).
- **Presentar** → la confirmación final, y su efecto legal, son tuyos.

Esto no es una limitación: es la cobertura. Si algún día se discute una
presentación, queda claro que un humano revisó y autorizó cada paso.

---

## 7. El dashboard con servidor (agente local)

Además de correr los scripts a mano, ya está armado el **agente local** que conecta
el dashboard con los scripts. Con esto trabajás desde una sola pantalla en el
navegador y **no tocás la consola**.

Archivos nuevos:

| Archivo | Para qué |
|---|---|
| `servidor.py` | Servidor local (FastAPI). Sirve el dashboard y ejecuta firma/subida. |
| `estado.py` | Lee y escribe `estado.json` (el registro de cédulas). |
| `estado.json` | La lista real de cédulas: qué son, dónde está el PDF, en qué estado. |
| `asistente_juridico.html` | El panel (ya conectado al servidor; si se abre suelto, muestra la demo). |
| `Iniciar_Asistente.bat` | Doble clic → levanta el servidor y abre el panel. |

Instalación extra (una vez):
```
pip install fastapi uvicorn
```

Día a día: doble clic a **Iniciar_Asistente.bat**. Se abre el panel en el navegador
y, atrás, una ventana de log que podés minimizar. Hacés clic en *Revisar y firmar*:
se abre la ventana real del portal, firmás, y **desde el propio dashboard** apretás
*"Ya está, continuar"*. Lo mismo para subir a Meta Jurídico. La consola negra ya no
se usa para apretar ENTER.

### El puente: estado.json

El dashboard ya no tiene datos escritos a mano: lee de `estado.json`. **La skill, al
generar cada cédula, tiene que agregar una entrada** con la ruta real del PDF y el
CUIJ. Se hace con una línea, usando el helper que ya está:

```python
import estado
estado.registrar_cedula({
    "id": "gonzalez",
    "caratula": "GONZALEZ c/ ART EJEMPLO S/ ACCIDENTE",
    "tipo": "aud", "tipoLabel": "Audiencia Art. 51 CPL", "ic": "🛡",
    "cuij": "21-00000001-0", "juzgado": "Laboral 3ª Nom. — Rosario",
    "juez": "Dra. Juez Demo",
    "dest": [{"n": "ART Ejemplo S.A.", "d": "Calle Falsa 123 — Rosario"}],
    "ruta_pdf": r"C:\...\cedula.pdf",
    "ruta_firmada": None,
    "estado": "generada",
})
```

Mientras tanto, el `estado.json` de ejemplo ya viene poblado para que el panel
muestre casos apenas arranca.

---

## 8. Qué se corrigió del plan original

Tres cosas del primer borrador de `servidor.py` que se rompían y quedaron resueltas:

1. **La ruta del PDF era inventada** (`"C:\Usuarios\Estudio\Descargas\"+id`). Ahora
   cada cédula trae su `ruta_pdf` real desde `estado.json`.
2. **La interfaz se colgaba**: el `fetch` esperaba una respuesta que no llegaba hasta
   apretar ENTER en la consola. Ahora el trabajo corre en segundo plano y la pausa se
   resuelve con un botón en el dashboard.
3. **El `.bat` compartía consola** (`start /B`), lo que trababa el ENTER. Ahora el
   servidor abre en su propia ventana y, además, ya no depende del ENTER de consola.

Con los pasos 3 y 4 hechos una vez (URLs y selectores), el circuito queda andando.
