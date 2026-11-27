# Instalación del asistente en una PC nueva

Cada persona del estudio tiene **su propia copia** del asistente, con su SISFE,
su FirmAr y su token. No comparten archivos entre máquinas.

Sin datos de clientes y sin claves en este documento.

## 1. Requisitos

- Windows 10 u 11
- Python 3.11 o superior (`python --version`)
- Google Chrome instalado
- Git (o una copia del repositorio en un pendrive)
- Usuario y clave de SISFE **de esa persona**
- Su certificado o token de FirmAr

## 2. Traer el repositorio

```bash
git clone <url-del-repo> asistente_juridico
cd asistente_juridico
pip install -r requirements.txt
python -m playwright install chromium
```

Si no hay Git, copiar la carpeta completa y ejecutar los dos últimos comandos.

## 3. Crear el `config.py` de esa PC

```bash
copy config.example.py config.py
```

Después editar `config.py` con el Bloc de notas y completar:

1. **`PERSONAS`**: dejar **sólo** la persona dueña de esa PC. Si quedan las
   otras, el asistente puede tomar el perfil equivocado y la sesión de otra.
2. **`PERFIL_CHROME`** (en `config_portales.py`): dejar el valor por defecto
   salvo que se quiera usar un perfil de Chrome ya existente.
3. **`TOKEN_ASISTENTE`**: se genera en el paso 5. Es la única clave necesaria
   en una PC donde no corre el portal.

`config.py` está en `.gitignore`: no se sube al repositorio y no se comparte.

## 4. Crear el perfil de Chrome de esa persona

El perfil guarda la sesión de SISFE y de FirmAr. **No se copia de otra PC**: si
se copia, la sesión viaja y queda en dos lugares.

1. Abrir el asistente (`Iniciar_Asistente.bat`). En el primer arranque Chrome
   crea la carpeta del perfil.
2. Desde ese Chrome, entrar a SISFE con el usuario de esa persona.
3. Entrar también a FirmAr y autorizar el token.
4. Cerrar el navegador que abrió el asistente.

Verificar que la carpeta exista:
`chrome_profile_portales\chrome_profile_<persona>`

## 5. Generar el `TOKEN_ASISTENTE` sin imprimirlo

En una PC de Jr o del Socio **no corre el portal**, así que `TOKEN_PORTAL` y
`PORTAL_SECRETO` no hacen falta: esas dos son de la máquina del estudio, donde
sí vive el portal.

La clave tiene que quedar escrita en `config.py` **sin pasar por la pantalla**.
Este comando la genera y sólo informa que terminó:

```bash
python - << 'EOF'
import re, secrets
p = "config.py"
t = open(p, encoding="utf-8").read()
for nombre in ("TOKEN_ASISTENTE",):
    valor = secrets.token_urlsafe(32)
    if re.search(rf'{nombre}\s*=\s*"[^"]*"', t):
        t = re.sub(rf'{nombre}\s*=\s*"[^"]*"', f'{nombre} = "{valor}"', t)
    else:
        t += f'\n{nombre} = "{valor}"\n'
open(p, "w", encoding="utf-8", newline="\n").write(t)
print("claves generadas y guardadas en config.py (no se muestran)")
EOF
```

Para comprobar que quedaron, sin ver el valor:

```bash
python -c "import config; print('largo:', len(config.TOKEN_ASISTENTE))"
```

Tiene que dar un número mayor a 30.

## 6. Rutas: qué es relativo y qué no

Todo cuelga de la carpeta del repositorio (`_CARPETA_BASE`):

| Qué | Ruta |
|---|---|
| Estado de las cédulas | `estado.json` |
| Base del portal | `portal.db` |
| PDFs del portal | `portal_uploads\` |
| Perfil de Chrome | `chrome_profile_portales\` |
| Cola de trabajos | `data\cola.json` |

**No hay rutas absolutas en el código.** Verificado con una búsqueda en todo el
repo (`C:\Users` y `C:/Users`): el único resultado estaba en un documento de
demo, y se corrigió. Si la carpeta está en `C:\Users\<quien>\asistente_juridico`,
funciona igual. La única excepción es reutilizar un perfil de Chrome que ya
existe en otro lado: ahí hay que apuntar `PERFIL_CHROME` a esa carpeta.

Las carpetas `portal_uploads`, `data` y `chrome_profile_portales` se crean solas.

## 7. Iniciar el asistente

```bash
Iniciar_Asistente.bat
```

Abre el navegador en `http://localhost:8000`. La ventana negra tiene que quedar
abierta: si se cierra, el asistente se apaga.

Si al arrancar avisa que hay trabajos a medias, **no reintentar a ciegas**:
primero mirar en SISFE si la acción ya se hizo.

## 8. Prueba de punta a punta (sin presentar)

Se hace una sola vez, al instalar. **No toca SISFE más que para leer.**

1. Abrir el asistente y traer las novedades. Esto **sólo lee** de SISFE.
2. Elegir una cédula de prueba —un expediente propio o de práctica— y generarla.
3. Firmarla con FirmAr usando el token de esa persona.
4. Verificar que la cédula pasó a **firmada** en el panel.
5. Abrir la carpeta `cedulas\` y comprobar que el PDF firmado está ahí y que el
   archivo tiene el mismo nombre que la cédula.
6. **PARAR ACÁ.** No apretar *Presentar*.

Presentar es un acto real sobre un expediente real. Para la prueba de la
instalación no hace falta: alcanza con que el PDF firmado exista y que el panel
lo muestre como firmado.

## 9. Si algo sale mal

| Síntoma | Qué revisar |
|---|---|
| Chrome no abre o pide login | el perfil de esa persona no está logueado en SISFE |
| Error de Playwright | `python -m playwright install chromium` |
| "No hay perfil" | el nombre en `config.PERSONAS` no coincide con `config_portales` |
| El panel no muestra cédulas | el asistente no trajo novedades todavía |
| Error al firmar | el token de FirmAr no está conectado en esa PC |

Nunca copiar `config.py` de otra PC: cada instalación tiene sus claves.
