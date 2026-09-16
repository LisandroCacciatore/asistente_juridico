# Estado del proyecto — Asistente Jurídico (Estudio Segovia)

Repaso al 12/08/2026. Guardá este archivo en la carpeta; sirve de mapa cuando
retomes sin tener que releer todo el historial.

---

## 1. Qué es, en una frase

Un sistema **100% local** (sin depender de Claude para operar) que genera
cédulas, las firma en FirmAr y las presenta en Meta Jurídico — automatizando
todo lo mecánico y **frenando siempre** en los actos que tenés que hacer vos.

---

## 2. Arquitectura (4 capas)

| Capa | Archivo(s) | Rol |
|---|---|---|
| Dashboard | `asistente_juridico.html` | Panel de control. Funciona con servidor (datos reales) o solo (modo demo). |
| Servidor local | `servidor.py` | FastAPI. Orquesta firma/subida en segundo plano, pausa humana por HTTP. |
| Generación (sin IA) | `generar_cedula.py` + `cedulas.py`, `cedulas_pdf.py`, `expediente_utils.py`, `extraccion_decretos.py` | Arma el PDF y clasifica el tipo de cédula por reglas. |
| Lectura de SISFE | `monitor_playwright.py` | Detecta decretos nuevos y dispara la generación. |
| Firma | `firma.py` | Automatiza FirmAr hasta donde se puede; dos puertas humanas. |
| Notificación | `sisfe_notificar.py` | Sube la cédula **firmada** al SISFE: busca por CUIJ, verifica, describe, adjunta, tilda Partes. **No notifica**: el clic final es tuyo. |
| *(dormido)* | `meta_juridico.py` | Meta Jurídico **salió del circuito** (16/09/2026): la cédula firmada va directo al SISFE. El módulo queda guardado, no se usa. |
| Compartido | `_navegador.py`, `estado.py`, `config.py`, `config_portales.py` | Motor de navegador, registro de cédulas, configuración. |

---

## 3. Las puertas humanas (no se tocan)

| Dónde | Qué hacés vos | Por qué no se automatiza |
|---|---|---|
| SISFE | reCAPTCHA | Seguridad del acceso matriculado |
| FirmAr | CUIL + contraseña + OTP + PIN + clic en FIRMAR | Es tu firma digital, con tu responsabilidad |
| SISFE (cédula) | Contraseña + reCAPTCHA del login | Seguridad del acceso matriculado |
| SISFE (cédula) | Clic final en **NOTIFICAR** | Acto irreversible, confirmación tuya |

En el medio de esas puertas, el sistema automatiza todo lo que puede: adjuntar
el PDF en FirmAr, descargar el firmado solo, buscar el expediente en el SISFE
por CUIJ, verificar que sea el mismo (carátula + CUIJ), escribir la descripción,
adjuntar la cédula firmada y leer y tildar las Partes del expediente.

Meta Jurídico ya no está en este circuito: se sacó el 16/09/2026 (la cédula
firmada va directo al SISFE, ver `SPEC_CIRCUITO_v0.2.md`, D1). Su módulo sigue
en la carpeta, sin usar.

---

## 4. Qué está validado de verdad (probado, no solo escrito)

- ✅ **Dashboard dual** (con servidor / modo demo offline).
- ✅ **Servidor + pausa humana por HTTP** (el botón "Ya está, continuar" en vez de la consola).
- ✅ **Persistencia en `estado.json`** (registrar, marcar firmada, marcar presentada).
- ✅ **Generación de cédulas sin IA** (`generar_cedula.py`): probé clasificación automática, multi-destinatario (Provincia → 2 cédulas), deducción de juzgado/juez.
- ✅ **Firma en FirmAr — circuito real completo**: lo corriste vos mismo con la cédula PRUEBA TECNICA. Login → adjuntar automático → PIN+firmar → descarga automática del firmado. **Funcionó de punta a punta.**
- ✅ **Búsqueda en Meta Jurídico**: reescrita con tu grabación real (buscador correcto dentro de `<main>`, búsqueda por apellido, los dos casos — navegación directa y lista con clic). Probado con dummies que replican ambos escenarios. **Falta tu confirmación en el portal real.**
- ✅ **Arranque en un clic** (`Iniciar_Asistente.bat`), portable entre máquinas (rutas dinámicas, sin nada fijo a un usuario de Windows).
- ✅ **Fix de la consola de Windows** (símbolos ✓/✗ ya no crashean).

---

## 5. Qué falta (lo real, sin vueltas)

1. **Confirmar la subida a Meta Jurídico con el caso gonzalez real** — es el único eslabón sin probar en el portal de verdad. Todo lo demás del circuito de subida ya está armado y testeado en simulación.
2. **Enganchar `monitor_playwright.py` a SISFE real** — estructuralmente listo (reusa toda tu lógica de extracción probada), pero sus selectores de SISFE están marcados `⬅ VALIDAR` porque no tengo acceso al portal. Necesita tu primera corrida real (tenés la guía en `PRIMERA_CORRIDA_MONITOR.md`).
3. **Que la skill (o vos a mano) llame a `estado.registrar_cedula(...)`** para que el panel se alimente solo, en vez de generar cédulas de prueba.
4. *(Opcional, bajo la lupa)* Si algún día querés automatizar el paso de subir el documento en FirmAr (hoy es una puerta humana única con login+subida+firma juntos), hace falta grabar ese tramo puntual con `codegen`.

---

## 6. Lecciones aprendidas esta sesión (para no repetirlas)

- **Un servidor viejo colgado bloquea todo** — antes de cada prueba, si algo falla raro, chequeá `netstat -ano | findstr :8000` y matá procesos de Chrome sueltos (`taskkill /IM chrome.exe /F`) antes de reintentar.
- **El dashboard podía mentir con el tilde verde** — ya arreglado: ahora solo marca éxito si el resultado real llegó (PDF firmado, confirmación de subida).
- **Los CUIJ/carátulas de prueba deben existir de verdad** en el sistema externo (Meta) para probar algo con sentido — con datos inventados, ninguna automatización va a encontrar nada.
- **Las contraseñas no van en el chat ni en el código** — quedaron expuestas un par de veces sin querer; conviene rotarlas cuando puedas.

---

## 7. Inventario completo de archivos (deberían estar todos en la carpeta)

```
asistente_juridico.html      servidor.py                config.py
firma.py                     sisfe_notificar.py          config_portales.py
meta_juridico.py             (dormido: fuera del circuito)
_navegador.py                estado.py                   estado.json
generar_cedula.py            cedulas.py                  cedulas_pdf.py
expediente_utils.py          extraccion_decretos.py      monitor_playwright.py
Iniciar_Asistente.bat        INSTRUCCIONES_PLAYWRIGHT.md PRIMERA_CORRIDA_MONITOR.md
```

*(No debería estar: `navegador.py` sin guion bajo — es un huérfano, se puede borrar si reaparece.)*

---

## 8. Próximo paso sugerido

Terminar de confirmar la subida real a Meta Jurídico con gonzalez (punto 5.1).
Con eso cerrado, el circuito completo —generar, firmar, presentar— queda
validado de punta a punta con un caso real, y lo que resta es ampliar el uso
(más casos, el monitor de SISFE) sin cambios de arquitectura.
