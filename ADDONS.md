# ADD ONs — Asistente Jurídico (Estudio Segovia)

**Fecha:** 13/09/2026
**Producto base:** asistente_juridio (`C:\Users\Torso\asistente_juridico\`)
**Autor:** Lisandro Cacciatore (agentic-sdlc + octalysis-core)

---

## 1. Estado actual del producto base

### 1.1. Lo que YA está construido y validado

| Componente | Estado | Evidencia |
|---|---|---|
| Dashboard HTML dual (servidor/demo) | ✅ productivo | `asistente_juridico.html` |
| Servidor local FastAPI + pausa humana HTTP | ✅ productivo | `servidor.py` |
| Generación de cédulas sin IA (multi-destinatario, clasificación) | ✅ probado | `generar_cedula.py`, `cedulas.py`, `cedulas_pdf.py` |
| Firma en FirmAr (login → adjuntar → PIN+firmar → descarga) | ✅ probado | `firma.py` (PRUEBA TÉCNICA real OK) |
| Búsqueda en Meta Jurídico (reescrita con grabación real) | ✅ probado | `meta_juridico.py` |
| Persistencia en `estado.json` + circuito completo | ✅ validado | `estado.py` |
| Arranque portable en 1 clic (`Iniciar_Asistente.bat`) | ✅ verificado | bat dinámico |
| Migración skills Claude → repo (6/6 migradas, 4 con scripts) | ✅ completo | `skills/`, `scripts/` |
| Capa Playwright (SISFE, CUIJ, decretos) | ✅ estructural | `monitor_playwright.py` |
| Capa secretario (Google Workspace → Gmail, borradores) | ⚠️ Fase 1 | `mail_gmail.py` |
| Perfil Chrome compartido + anti-huérfanos | ✅ operativo | `_navegador.py` |

### 1.2. Puertas humanas (no se automatizan por diseño)

| Dónde | Qué hace el usuario | Por qué |
|---|---|---|
| SISFE | reCAPTCHA matriculado | Seguridad externa |
| FirmAr | CUIL + contraseña + OTP + PIN + FIRMAR | Firma digital, responsabilidad civil |
| Meta Jurídico | Login + código email (2FA) | 2FA por diseño |
| Meta Jurídico | Clic final en "Presentar" | Acto irreversible |

---

## 2. Brecha — lo que FALTA vs. lo que se puede AGREGAR

### 2.1. Secretario con IA (capa Hermes)

| Add-On | Estado actual | Con el Add-On |
|---|---|---|
| **Bot de Telegram** | No existe. Todo es local, sin chat. | El estudio manda un mensaje → el bot lee el estado de cédulas, agenda, borradores. El usuario responde desde el celular sin abrir el dashboard. |
| **Triage automático de emails** | No existe. Los correos se leen manualmente. | Cada mail entrante se clasifica (caso nuevo, consulta urgente, plazo perentorio, spam), se vincula a un expediente, y se genera una tarjeta en el dashboard. El abogado solo ve lo relevante. |
| **Agenda + recordatorios proactivos** | No existe. El estudio agenda manualmente. | El bot escanea los plazos cargados, detecta vencimientos (48h, 24h, día), y manda un mensaje de Telegram al abogado responsable. Integra con Google Calendar (google-workspace). |
| **Borradores con aprobación (HG-05)** | `mail_gmail.py` es borrador (nunca envía). Falta el gate humano. | Se propone un borrador → el abogado lo revisa en el dashboard o Telegram → con un clic se envía. Si no responde en X horas, escalar. |
| **Calendario de audiencias** | No existe. Las fechas se anotan en papel/Excel. | Calendario integrado: carga automática desde notificaciones judiciales, sincronizado con Google Calendar, con avisos por Telegram. |
| **Búsqueda inteligente de jurisprudencia** | No existe. Se usa manualmente. | El bot consulta sitios (Cijarmac, SAIJ, InfoLeg) con criterios del abajo, extrae los párrafos relevantes y arma un resumen. |

### 2.2. Automatización del portal judicial

| Add-On | Estado actual | Con el Add-OF |
|---|---|---|
| **Monitor de SISFE (decretos)** | ⬅️ VALIDAR en vivo. Selectores marcados. | Una vez validados los selectores, el sistema revisa SISFE periódicamente (cada 30 min), detecta decretos nuevos, dispara la generación automática de cédula, y deja todo firmado y presentado (con las pausas humanas correspondientes). |
| **Descarga automática de cédulas presentadas** | No existe. Se busca manualmente en Meta. | Una vez que una cédula queda presentada, el sistema descarga el comprobante y lo asocia al expediente. |
| **Estado en tiempo real de un expediente** | No existe. Se pregunta al cliente. | El sistema hace raspado periódico de Meta/SISFE y reporta: "Tu expediente Gonzalez pasó a etapa X". |

### 2.3. Octalysis para el Estudio (nuevo)

| Add-On | Qué resuelve |
|---|---|
| **Auditoría de retención de clientes** | Aplica Octalysis Core Suite al vínculo estudio-cliente: ¿el cliente vuelve? ¿Recomienda? ¿Siente que pertenece? |
| **Auditoría de formularios web** | Si el estudio tiene web de captación, audita la conversión con Octalysis (Core Drives del visitante). |
| **Gamificación de la carga de casos** | Si el estudio tiene pasantes/empleados, gamifica la carga de expedientes (logros, progreso, competencia sana). |

### 2.4. Infraestructura y empaquetado (nuevo)

| Add-On | Estado actual | Con el Add-On |
|---|---|---|
| **Docker compose** | No existe. Dependencias sueltas (Python, Playwright, Chrome, Node). | `docker-compose.yml` levanta todo en un contenedor reproducible. El cliente baja un repo, corre `docker compose up`, y tiene el sistema sin instalar nada manualmente. |
| **Perfil Hermes portable** | No existe. El secretario vive en tu máquina local. | Profile Distribution del perfil "abogados-ar" (config.yaml + skills + scripts + memory + docker-compose). El cliente tiene su propia instancia aislada, con su propio bot de Telegram y su propia memoria. |
| **Telegram Bot del estudio** | No existe. | El estudio tiene su bot (@EstudioSegoviaBot, por ejemplo) que habla con su instancia de Hermes. Cada mensaje es una orden (pedir estado, pedir borrador, pedir agenda). |
| **Dashboard web remoto** | Solo existe el HTML local. | Se deploya en Vercel (como el Octalysis Board). El cliente accede desde cualquier dispositivo (celular, oficina, tribunales). |
| **Backups automáticos** | No existe. `estado.json` puede perderse. | Backup diario de `estado.json` + SQLite de expedientes → Supabase o Google Drive. |

---

## 3. Comparativa — Producto base vs. Producto completo

| Dimensión | Hoy | Con todos los ADD ONs |
|---|---|---|
| **Punto de entrada** | Dashboard HTML local | Dashboard + Bot Telegram + Bot WhatsApp |
| **Generación de documentos** | Manual desde dashboard | Automática vía email entrante / comando Telegram |
| **Firma y presentación** | Con pausas humanas | Con pausas humanas + notificaciones proactivas |
| **Agenda y plazos** | Manual (externa) | Integrada + alertas Telegram |
| **Monitor judicial** | Apagado (⬅️ VALIDAR) | Corriendo 24/7 + alertas |
| **Inteligencia artificial** | No usa IA | Secretario Hermes triagea, agenda, propone |
| **Despliegue** | 1 clic en Windows local | Docker multiplataforma |
| **Escalabilidad** | 1 máquina, 1 usuario | N instancias (cada cliente su perfil) |
| **Modelo de negocio** | Uso propio | Licencia por cliente ($50-150/mes) |

---

## 4. Roadmap sugerido (3 sprints)

### Sprint 1 — Bot + Triage + Agenda (2 semanas)

```
□ Bot de Telegram funcional (@EstudioSegoviaBot)
□ Triage automático de emails entrantes → dashboard
□ Agenda de audiencias + recordatorios proactivos
□ Gate de aprobación de borradores (HG-05)
□ Dashboard lee estado real (no demo)
```

### Sprint 2 — Monitor judicial + Docker (1 semana)

```
□ Validar selectores SISFE en vivo (con Santiago)
□ Monitor corriendo 24/7 + alertas
□ Docker compose funcional
□ Backup automático
```

### Sprint 3 — Perfil portable + 2 cliente nuevo (2 semanas)

```
□ Profile Distribution "abogados-ar"
□ Vender la primera licencia (dentista o local de ropa)
□ Documentar setup para cliente
□ Crear skills específicas del nuevo rubro
```

---

## 5. Modelo de precios propuesto

| Tier | Qué incluye | Precio sugerido |
|---|---|---|
| **Básico** | Bot Telegram + dashboard + cédulas automáticas | $50-80/mes |
| **Profesional** | Lo anterior + agenda + triage emails + recordatorios | $120-150/mes |
| **Full** | Lo anterior + monitor judicial 24/7 + soporte + backups | $200-300/mes |

---

## 6. Dependencias críticas (lo que falta validar en vivo)

1. **SISFE** → selectores del monitor (⬅️ VALIDAR). Sin esto, el monitor judicial no arranca.
2. **Meta Jurídico** → confirmar subida con caso real (gonzalez). Sin esto, la presentación no está cerrada.
3. **Firma en lote** → hoy es 1 por 1. Si el estudio sube 5 cédulas, tarda 5×. Optimizable.
4. **Credenciales** → el cliente las maneja en su `.config.py` local. Nunca viaja al servidor ni al chat.

---

*Documento vivo. Se actualiza a medida que se validan los add ons.*
