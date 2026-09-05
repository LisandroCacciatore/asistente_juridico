---
name: "transferencia-de-capital"
description: "Genera los dos escritos de transferencia de capital de una cuenta judicial del estudio de Santiago Segovia, en UN solo PDF (oficio en la pág. 1 y escrito al juez en la pág. 2): el OFICIO al banco donde está depositado el capital ordenando transferir, y el escrito MANIFIESTA/SOLICITA al Juez pidiendo se libre el oficio de pago de capital. Entrega dos opciones: solo los escritos, y un paquete completo que une los escritos con el informe bancario y la constancia de CBU. Usar siempre que Santiago suba o pegue un \"Informe de Saldos de Cuentas Judiciales\" (Banco Municipal de Rosario, Nuevo Banco de Santa Fe, u otro) junto con la constancia de CBU de la cuenta destino, o pida \"los escritos de transferencia\", \"transferir el capital\", \"hacer el oficio de transferencia\", \"oficio de pago de capital\", aunque no diga la palabra skill."
---

# Transferencia de capital

Genera los **dos escritos** que siguen a un cobro de capital en una cuenta judicial, en **UN solo PDF de dos páginas** (nunca se mezcla el texto de un escrito en la página del otro):

1. **Página 1 — OFICIO** al banco donde está depositado el capital (Caja de Abogados / sucursal judicial) ordenando *transferir* el capital a la cuenta del cliente.
2. **Página 2 — Escrito MANIFIESTA / SOLICITA** al Juez, pidiendo que se libre el oficio de pago de capital.

Al final se entregan **dos opciones** (ver Paso 5):
- **Opción 1 — Escritos:** solo los dos escritos.
- **Opción 2 — Paquete completo:** los escritos + el informe bancario + la constancia de CBU unidos en un único PDF, listo para descargar/adjuntar.

Formato: **cuerpo justificado**; título **OFICIO centrado**; título **MANIFIESTA / SOLICITA alineado a la derecha** (como el modelo firmado de Santiago). El script ya lo hace; no cambiar.

## Insumos (dos archivos)

- **Informe de Saldos de Cuentas Judiciales** del banco donde está el dinero → datos de la cuenta judicial de ORIGEN, el juzgado y el monto. Puede ser del **Banco Municipal de Rosario**, del **Nuevo Banco de Santa Fe**, u otro. El oficio se dirige a ESE banco.
- **Constancia de CBU** de la cuenta de DESTINO (Credicoop, Nación, Santa Fe, etc.) → datos de la cuenta a la que se transfiere y del titular.

Guardar las rutas de estos dos PDF: se usan para el paquete completo (Opción 2). Santiago normalmente sube los dos juntos. Si falta uno, pedírselo. Si la constancia es una imagen escaneada, transcribir a ojo lo que se ve.

## Paso 1 — Extraer datos de los dos archivos

**Del Informe de Saldos (banco de ORIGEN):**
- `caratula`: la del informe, **expandiendo abreviaturas** y normalizando ("C" suelto → "C/", agregar "S/ {Motivo}" si la carátula no trae el objeto; ej. "BAUER ANIBAL JOSE C PONZIO OSCAR HECTOR" + Motivo "COBRO DE PESOS" → "BAUER ANIBAL JOSE C/ PONZIO OSCAR HECTOR S/ COBRO DE PESOS").
- `cuij`: los 11 dígitos del CUIJ con formato `21-XXXXXXXX-X` (ej. `21262695821` → `21-26269582-1`).
- `cuenta_judicial`: "Nro. de cuenta".
- `cbu_origen`: el CBU del informe.
- `banco_origen_nombre`: nombre del banco del informe, tal como se escribe en el cuerpo (ej. "Banco Municipal de Rosario", "Nuevo Banco de Santa Fe S.A."). También se usa en mayúsculas como destinatario del oficio.
- `sucursal_origen_desc`: la sucursal para el cuerpo, entre paréntesis (ej. "Sucursal N° 80 – Caja de Abogados" para Banco Municipal; "Sucursal San Jorge" para Nuevo Banco de Santa Fe).
- `sucursal_origen_linea`: la línea de sucursal bajo el nombre del banco en el destinatario (normalmente igual a `sucursal_origen_desc`).
- `ciudad`: ciudad del juzgado (Rosario, San Jorge, etc.).
- `juzgado_desc`: descripción completa del juzgado para el cuerpo. Para laborales de Rosario se puede dejar vacío y pasar `nominacion` (arma "Juzgado de Primera Instancia en lo Laboral de la {nom} Nominación de {ciudad}"). Para otros, pasarla explícita (ej. "Juzgado de Primera Instancia de Distrito en lo Civil, Comercial y Laboral de San Jorge").
- `nominacion`: solo para laborales de Rosario (ej. "2da.").
- `monto_letras`: importe en letras del informe (quitar asteriscos de relleno).
- `monto_num`: saldo en números con separador de miles, sin decimales (ej. `800.000`).
- `concepto`: según el "Motivo". Ej: ART → "capital por indemnización por Accidente de Trabajo"; cobro de pesos → "capital por cobro de pesos". Ante la duda, "capital".

**De la Constancia de CBU (cuenta DESTINO):**
- `banco_destino`: se escribe después de "del Banco ..." (ej. "CREDICOOP" → "del Banco CREDICOOP"; Nación → poner "de la Nación Argentina" → "del Banco de la Nación Argentina").
- `tipo_cuenta_destino`: "Caja de ahorro" o "Cuenta corriente".
- `cuenta_destino`: nº de cuenta.
- `cbu_destino`: CBU de destino (22 dígitos).
- `titular`: titular de la cuenta (debe coincidir con el actor de la carátula; si no, avisar a Santiago antes de generar).
- `cuil`: si la constancia trae CUIL/CUIT, formatear `XX-XXXXXXXX-X`. Si solo trae DNI, dejar `cuil` en `""` (el script omite el campo CUIL).
- `dni`: con puntos (ej. `23.422.977`). Si la constancia trae "DU"/DNI con ceros a la izquierda, quitarlos.

**Verificación clave:** el titular del CBU destino debe corresponder al actor de la carátula. Si no coinciden, avisar a Santiago — transferir al CBU equivocado es un error grave.

**Datos fijos del abogado** (no preguntar): `abogado` = "SANTIAGO A. SEGOVIA", `abogado_apellido` = "Segovia", matrícula Tomo `LV`, Folio `029`.

## Paso 2 — Juez y secretario/a (biblioteca)

Si el juzgado es de **Rosario** (fuero Laboral/Civil/Familia, Circ. N°2), tomar juez, secretario/a y cargos de la tabla de más abajo, usando la clave del juzgado (ej. `LABORAL 2`). El script deduce "Dr./Dra." y "del/de la" del cargo.

Si el juzgado **no es de Rosario** o no está en la tabla (ej. San Jorge), no inventar: preguntar en el Paso 3 (o dejar en blanco, con líneas para completar a mano).

## Paso 3 — Completar lo que falte (AskUserQuestion)

Juntar en **una sola** pregunta lo que no se pudo deducir. Típicamente:

- **Juez y Secretario/a** si el juzgado no está en la biblioteca. Ofrecer "dejar en blanco" (líneas de puntos) como opción.
- **Nº de EXPTE interno**: muchos informes no lo traen (o dicen "0/0"). Opciones: pasarlo, dejar en blanco (`expte_interno: ""`, se imprime una línea), o usar solo el CUIJ (`omitir_expte: true`, no aparece el campo EXPTE).
- Si hace falta, confirmar el **concepto** (según el Motivo del informe).

No preguntar nada que ya esté en los archivos o en la tabla.

## Paso 4 — Generar los PDF (las dos opciones de una)

Escribir el script `generar_transferencia.py` (abajo) en la carpeta de trabajo, armar `datos.json`, y ejecutarlo pasando **también las rutas del informe y de la constancia** como argumentos extra:

```bash
pip install reportlab pypdf --break-system-packages -q   # si faltan
python3 generar_transferencia.py datos.json CARPETA_SALIDA "RUTA_INFORME.pdf" "RUTA_CONSTANCIA_CBU.pdf"
```

Produce dos archivos:
- `TRANSFERENCIA_{APELLIDO}_{CUIJ}.pdf` → **Opción 1** (solo escritos: oficio pág. 1, escrito al juez pág. 2).
- `TRANSFERENCIA_{APELLIDO}_{CUIJ}_COMPLETO.pdf` → **Opción 2** (escritos + informe + constancia unidos, en ese orden).

Si por algún motivo no se pasan los PDF adjuntos, el script genera solo la Opción 1.

Ejemplo de `datos.json` (caso fuera de Rosario, otro banco, sin CUIL):

```json
{
  "caratula": "BAUER ANIBAL JOSE C/ PONZIO OSCAR HECTOR S/ COBRO DE PESOS",
  "cuij": "21-26269582-1",
  "expte_interno": "", "omitir_expte": true,
  "juzgado_desc": "Juzgado de Primera Instancia de Distrito en lo Civil, Comercial y Laboral de San Jorge",
  "juez": "", "cargo_juez": "JUEZ", "secretario": "", "cargo_secretario": "SECRETARIO",
  "ciudad": "San Jorge",
  "monto_letras": "OCHOCIENTOS MIL", "monto_num": "800.000",
  "cuenta_judicial": "105346", "cbu_origen": "3300544530000001053462",
  "banco_origen_nombre": "Nuevo Banco de Santa Fe S.A.",
  "sucursal_origen_desc": "Sucursal San Jorge", "sucursal_origen_linea": "Sucursal San Jorge",
  "banco_destino": "de la Nación Argentina",
  "tipo_cuenta_destino": "Caja de ahorro",
  "cuenta_destino": "1957334314", "cbu_destino": "0110195530019573343147",
  "titular": "Bauer Anibal Jose", "dni": "23.422.977", "cuil": "",
  "concepto": "capital por cobro de pesos",
  "fecha_dia": "", "fecha_mes": "Julio", "fecha_anio": "2026",
  "abogado": "SANTIAGO A. SEGOVIA", "abogado_apellido": "Segovia",
  "abogado_matricula_tomo": "LV", "abogado_matricula_folio": "029"
}
```

Para un caso laboral clásico de Rosario/Banco Municipal: omitir `juzgado_desc` y pasar `nominacion` (ej. "2da."), `banco_origen_nombre` = "Banco Municipal de Rosario", `sucursal_origen_desc` = "Sucursal N° 80 – Caja de Abogados", juez/secretario de la tabla, `expte_interno` con el número, `cuil` completo.

## Paso 5 — Entregar (dos opciones)

Presentar con `present_files` **los dos archivos**, dejando claro cuál es cuál:
- **Opción 1 — Escritos:** `TRANSFERENCIA_..._.pdf` (los dos escritos para firmar).
- **Opción 2 — Completo:** `TRANSFERENCIA_..._COMPLETO.pdf` (escritos + informe + constancia, todo junto para descargar/adjuntar).

Resumen de una línea (actor, monto, banco destino). No transcribir el contenido en el chat. Si Santiago corrige el **texto** de un modelo (no los datos del caso), avisarle que conviene actualizar esta skill.

---

## Biblioteca de juzgados (Rosario, Circ. N°2)

Fuente: Guía Judicial oficial (misma base que la skill de cédulas). Solo Rosario. Si el juzgado no está acá, preguntar o dejar en blanco.

| Juzgado | Juez/a | Cargo | Secretario/a | Cargo |
|---|---|---|---|---|
| LABORAL 1 | BARBARA SERRAT | JUEZA | RICARDO JAVIER SULLIVAN | SECRETARIO |
| LABORAL 2 | FABIÁN NAHUEL VEGA | JUEZ | RAMIRO LUNA | SECRETARIO |
| LABORAL 3 | MARÍA SILVIA ALBERTTI | JUEZA | ANALÍA CARLA GALLUCCI | SECRETARIA |
| LABORAL 4 | RICARDO GRAMEGNA | JUEZ | GUSTAVO ANDRÉS JUKIC | SECRETARIO |
| LABORAL 5 | RINA GRACIELA BRISIGHELLI | JUEZA | LORENA BETINA SPIZZIRRI | SECRETARIA |
| LABORAL 6 | PATRICIA LILIANA OTEGUI | JUEZA | MARINA ELISA ARP | SECRETARIA |
| LABORAL 7 | MARCELO AGUSTÍN ENZO GALLUCCI | JUEZ | MARÍA TERESA HAYDEE CAUDANA | SECRETARIA |
| LABORAL 8 | SILVANA LAURA QUAGLIATTI | JUEZA | PEDRO DANIEL HERRERO | SECRETARIO |
| LABORAL 9 | GUSTAVO ALBERTO BURGIO | JUEZ | NATALIA LORENA DI GIORGIO | SECRETARIA |
| LABORAL 10 | PAULA VERÓNICA CALACE VIGO | JUEZA | PAULA NYDIA HECHEM | SECRETARIA |
| CIVIL 1 | RICARDO ALBERTO RUIZ | JUEZ | ARTURO AUDANO | SECRETARIO |
| CIVIL 2 | MÓNICA KLEBCAR | JUEZA | MARIANELA GODOY | SECRETARIA |
| CIVIL 3 | EZEQUIEL MARÍA ZABALE | JUEZ | MAYRA IBAÑEZ | SECRETARIA (S) |
| CIVIL 4 | NICOLÁS VILLANUEVA | JUEZ | DANIELA ANDREA JAIME | SECRETARIA |
| CIVIL 5 | LUCRECIA MANTELLO | JUEZA | SILVINA LEONOR RUBULOTTA | SECRETARIA |
| CIVIL 6 | FERNANDO ALEJANDRO MÉCOLI | JUEZ | SABRINA MERCEDES ROCCI | SECRETARIA |
| CIVIL 7 | MARCELO NOLBERTO QUIROGA | JUEZ | LORENA ANDREA GONZALEZ | SECRETARIA |
| CIVIL 8 | LUCIANO DANIEL JUAREZ | JUEZ | MARÍA JOSÉ CASAS | SECRETARIA |
| CIVIL 9 | MARÍA FABIANA GENESIO | JUEZA | VERÓNICA AMANDA ACCINELLI | SECRETARIA |
| CIVIL 10 | MAURO RAUL BONATO | JUEZ | MARIANELA MAULION | SECRETARIA |
| CIVIL 11 | LUCIANO DANIEL CARBAJO | JUEZ | SERGIO ANTONIO GONZÁLEZ | SECRETARIO |
| CIVIL 12 | FABIAN EDUARDO DANIEL BELLIZIA | JUEZ | ELINA GABRIELA CERLIANI | SECRETARIA |
| CIVIL 13 | VERÓNICA GOTLIEB | JUEZA | LUCAS MENOSSI | SECRETARIO |
| CIVIL 14 | MARCELO CARLOS MAURICIO QUAGLIA | JUEZ | MARÍA KARINA ARRECHE | SECRETARIA |
| CIVIL 15 | SEBASTIÁN JOSÉ RUPIL | JUEZ | MARÍA EUGENIA SAPEI | SECRETARIA |
| CIVIL 16 | SABRINA CAMPBELL | JUEZA | MARIA SOL SEDITA | SECRETARIA |
| CIVIL 17 | MARÍA SILVIA BEDUINO | JUEZA | MARÍA FLORENCIA DI RIENZO | SECRETARIA |
| CIVIL 18 | SUSANA SILVINA GUEILER | JUEZA | PATRICIA ANDREA BEADE | SECRETARIA |
| CIVIL 19 | DANIEL HUMBERTO GONZÁLEZ | JUEZ | GABRIELA MARÍA KABICHIAN | SECRETARIA |
| CIVIL 20 | EDUARDO HORACIO ARICHULUAGA | JUEZ | JAVIER MATÍAS CHENA | SECRETARIO |
| CIVIL 21 | CECILIA ANDREA CAMAÑO | JUEZA | ANA BELÉN CURÁ | SECRETARIA |
| CIVIL 22 | MAXIMILIANO NELSON GUSTAVO COSSARI | JUEZ | GABRIELA PATRICIA ALMARÁ | SECRETARIA |
| FAMILIA 1 | MARÍA JOSÉ DIANA | JUEZA | DANIA LEONELA CHIEMENTIN | SECRETARIA |
| FAMILIA 2 | SILVINA ILEANA GARCIA | JUEZA | ANALÍA DANIELA PERRULLI | SECRETARIA |
| FAMILIA 3 | MARÍA JOSÉ CAMPANELLA | JUEZA | SERGIO LUIS FUSTER | SECRETARIO |
| FAMILIA 4 | GUSTAVO ADOLFO ANTELO | JUEZ | MARCO PEDRAZA | SECRETARIO |
| FAMILIA 5 | ALICIA ANA GALLETTO | JUEZA | ANA CLARA REBOLA | SECRETARIA |
| FAMILIA 6 | MARIA PAULA MANGANI | JUEZA | MARÍA JOSÉ CAVIGLIA | SECRETARIA |
| FAMILIA 7 | SABINA MARGARITA SANSARRICQ | JUEZA | ALEJANDRA CLAUDIA WULFSON | SECRETARIA |
| FAMILIA 8 | (vacante) | JUEZ | MARÍA CECILIA NAVEIRA | SECRETARIA |
| FAMILIA 9 | MILCA MILEVA BOJANICH | JUEZA | AGUSTINA SUEIRAS MUNUCE | SECRETARIA |
| FAMILIA 10 | VALERIA VIVIANA VITTORI | JUEZA | LARA BELÉN FAVRO | SECRETARIA |
| FAMILIA 11 | ANDREA MARIEL BRUNETTI | JUEZA | MARÍA FLORENCIA MARTÍNEZ BELLI | SECRETARIA |
| FAMILIA 12 | GABRIELA ESTER TOPINO | JUEZA | MARÍA SILVIA ZAMANILLO | SECRETARIA |

Secretarios alternativos (subrogancias) están en `config.py` del SCRIPT SISFE; si el caso trae otro nombre, usar ese.

---

## Script: generar_transferencia.py

Guardar tal cual y ejecutar: `python3 generar_transferencia.py datos.json CARPETA_SALIDA [informe.pdf constancia.pdf]`.

```python
# ============================================================
#  GENERAR_TRANSFERENCIA.PY
#  Un solo PDF de escritos: OFICIO (pág. 1) + MANIFIESTA/SOLICITA (pág. 2),
#  nunca mezclados. Si se pasan PDFs adjuntos (informe, constancia) también
#  arma un _COMPLETO.pdf = escritos + adjuntos.
#  Uso: python3 generar_transferencia.py datos.json CARPETA_SALIDA [pdf1 pdf2 ...]
#  Formato: cuerpo justificado; "OFICIO" centrado; "MANIFIESTA/SOLICITA" a la derecha.
# ============================================================
import os, re, sys, json
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ESTILO_TITULO = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=12,
    alignment=TA_CENTER, spaceAfter=4, leading=15)
ESTILO_TITULO_DER = ParagraphStyle("titulo_der", fontName="Helvetica-Bold", fontSize=11,
    alignment=TA_RIGHT, spaceAfter=2, leading=14)
ESTILO_CAMPO = ParagraphStyle("campo", fontName="Helvetica", fontSize=11,
    alignment=TA_LEFT, spaceAfter=3, leading=15)
ESTILO_CUERPO = ParagraphStyle("cuerpo", fontName="Helvetica", fontSize=11,
    alignment=TA_JUSTIFY, spaceAfter=12, leading=17, firstLineIndent=0)
ESTILO_CUERPO_SANGRIA = ParagraphStyle("cuerpo_sangria", fontName="Helvetica", fontSize=11,
    alignment=TA_JUSTIFY, spaceAfter=12, leading=17, firstLineIndent=1.2 * cm)

def _esc(texto):
    if texto is None:
        return ""
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def _doc(ruta):
    return SimpleDocTemplate(ruta, pagesize=A4,
        leftMargin=3 * cm, rightMargin=2.5 * cm, topMargin=2.5 * cm, bottomMargin=2.5 * cm,
        title="Transferencia de capital", author="Estudio Jurídico Segovia")

def _trato(cargo):
    c = (cargo or "").strip().upper()
    fem = c.endswith("A") or c.endswith("A (S)") or "JUEZA" in c or "SECRETARIA" in c
    return ("de la", "Dra.") if fem else ("del", "Dr.")

def _banco_origen(d):
    return _esc(d.get("banco_origen_nombre", "Banco Municipal de Rosario"))

def _sucursal_origen(d):
    return _esc(d.get("sucursal_origen_desc", "Sucursal N&deg; 80 &ndash; Caja de Abogados"))

def _juzgado_desc(d):
    jd = d.get("juzgado_desc")
    if jd:
        return _esc(jd)
    nom = _esc(d.get("nominacion") or "____")
    ciudad = _esc(d.get("ciudad", "Rosario"))
    return f"Juzgado de Primera Instancia en lo Laboral de la {nom} Nominación de {ciudad}"

def _bloque_transferencia(d):
    cuil = _esc(d.get("cuil", ""))
    frag_cuil = f", CUIL N&deg; {cuil}" if cuil else ""
    return (
        f"la suma de Pesos {_esc(d.get('monto_letras',''))} "
        f"(${_esc(d.get('monto_num',''))},00.-), que se encuentra depositada en la "
        f"Cuenta Judicial N&ordm; {_esc(d.get('cuenta_judicial',''))}, "
        f"CBU: {_esc(d.get('cbu_origen',''))}, del {_banco_origen(d)} "
        f"({_sucursal_origen(d)}) "
        f"a la Cuenta {_esc(d.get('tipo_cuenta_destino','Caja de ahorro'))} "
        f"N&deg; {_esc(d.get('cuenta_destino',''))} "
        f"CBU {_esc(d.get('cbu_destino',''))}, del Banco {_esc(d.get('banco_destino',''))}, "
        f"a favor de la parte actora, {_esc(d.get('titular',''))}, "
        f"titular del DNI N&ordm; {_esc(d.get('dni',''))}{frag_cuil}, "
        f"en concepto de {_esc(d.get('concepto','capital'))}."
    )

def _ref_autos(d):
    cuij = _esc(d.get("cuij", ""))
    expte = d.get("expte_interno")
    if expte:
        return f"EXPTE N&ordm; {_esc(expte)} - CUIJ {cuij}"
    if d.get("omitir_expte"):
        return f"CUIJ {cuij}"
    return f"EXPTE N&ordm; ____________ - CUIJ {cuij}"

def elementos_oficio(d):
    ciudad = _esc(d.get("ciudad", "Rosario"))
    dia = _esc(d.get("fecha_dia", "")) or "____"
    mes = _esc(d.get("fecha_mes", "")); anio = _esc(d.get("fecha_anio", ""))
    cargo_j = _esc(d.get("cargo_juez", "JUEZ")); cargo_s = _esc(d.get("cargo_secretario", "SECRETARIO"))
    juez = _esc(d.get("juez") or "________________"); sec = _esc(d.get("secretario") or "________________")
    tomo = _esc(d.get("abogado_matricula_tomo", "LV")); folio = _esc(d.get("abogado_matricula_folio", "029"))
    apellido_abog = _esc(d.get("abogado_apellido", "Segovia"))
    art_j, trato_j = _trato(d.get("cargo_juez", "JUEZ"))
    art_s, trato_s = _trato(d.get("cargo_secretario", "SECRETARIO"))
    banco_dest = _esc(d.get("banco_origen_nombre", "Banco Municipal de Rosario")).upper()
    suc_linea = _esc(d.get("sucursal_origen_linea", d.get("sucursal_origen_desc", "Sucursal 80 &ndash; Caja de Abogados")))
    return [
        Paragraph("OFICIO", ESTILO_TITULO),
        Spacer(1, 10),
        Paragraph(f"N&ordm; ..............&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                  f"&nbsp;&nbsp;&nbsp;{ciudad}, {dia} de {mes} de {anio}", ESTILO_CAMPO),
        Spacer(1, 14),
        Paragraph("Señores", ESTILO_CAMPO),
        Paragraph(f"<b>{banco_dest}</b>", ESTILO_CAMPO),
        Paragraph(suc_linea, ESTILO_CAMPO),
        Paragraph("<b>Presente</b>", ESTILO_CAMPO),
        Spacer(1, 14),
        Paragraph(
            f"En los autos caratulados &ldquo;{_esc(d.get('caratula',''))}&rdquo; "
            f"{_ref_autos(d)}, que tramitan por ante este {_juzgado_desc(d)}, a cargo {art_j} "
            f"{cargo_j} {trato_j} {juez}, Secretaría {art_s} {cargo_s} {trato_s} {sec}, se ha "
            f"dispuesto dirigir a Usted el presente a efectos de que sirva TRANSFERIR, "
            + _bloque_transferencia(d), ESTILO_CUERPO),
        Spacer(1, 6),
        Paragraph("Salúdale a Ud. Atentamente.-", ESTILO_CUERPO),
        Spacer(1, 30),
        Paragraph(
            f"Se hace saber que el Dr. {apellido_abog} abogado, Matrícula L&ordm; {tomo}, "
            f"F&ordm; {folio} se encuentra debidamente habilitado para el diligenciamiento "
            f"del presente Oficio.-", ESTILO_CUERPO),
    ]

def elementos_escrito(d):
    abogado = _esc(d.get("abogado", "SANTIAGO A. SEGOVIA"))
    return [
        Paragraph("MANIFIESTA", ESTILO_TITULO_DER),
        Paragraph("SOLICITA", ESTILO_TITULO_DER),
        Spacer(1, 14),
        Paragraph("<b>Sr. Juez:</b>", ESTILO_CAMPO),
        Spacer(1, 6),
        Paragraph(
            f"{abogado}, abogado por la parte actora, en la representación acreditada dentro "
            f"de los autos caratulados: &ldquo;{_esc(d.get('caratula',''))} "
            f"{_esc(d.get('cuij',''))}&rdquo;, ante V.S. me presento y digo:",
            ESTILO_CUERPO_SANGRIA),
        Paragraph("<b>MANIFIESTA:</b>", ESTILO_CAMPO),
        Spacer(1, 4),
        Paragraph("I.- Que vengo por intermedio de la presente a solicitar se TRANSFIERA, "
            + _bloque_transferencia(d), ESTILO_CUERPO),
        Paragraph("<b>SOLICITA:</b>", ESTILO_CAMPO),
        Spacer(1, 4),
        Paragraph("II.- Conforme lo expuesto en el Punto I, solicito a V.S. se libre oficio de pago "
            "de capital.", ESTILO_CUERPO),
        Spacer(1, 10),
        Paragraph("Proveer de conformidad,", ESTILO_CUERPO),
        Paragraph("<b>Y SERA JUSTICIA.</b>", ESTILO_CAMPO),
    ]

def generar_pdf(d, ruta):
    elementos = elementos_oficio(d) + [PageBreak()] + elementos_escrito(d)
    _doc(ruta).build(elementos)
    return ruta

def _merge(pdfs, ruta):
    from pypdf import PdfWriter
    w = PdfWriter()
    for f in pdfs:
        w.append(f)
    with open(ruta, "wb") as fh:
        w.write(fh)
    return ruta

def _apellido(caratula):
    m = re.match(r'^\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)', caratula or "")
    return m.group(1).upper() if m else "ACTOR"

def _nombre_archivo(prefijo, d):
    apellido = _apellido(d.get("caratula", ""))
    cuij = re.sub(r'[^0-9-]', '', d.get("cuij", "")) or "SINCUIJ"
    return f"{prefijo}_{apellido}_{cuij}.pdf"

def main():
    if len(sys.argv) < 3:
        print("Uso: python3 generar_transferencia.py datos.json CARPETA_SALIDA "
              "[informe.pdf constancia.pdf ...]"); sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    carpeta = sys.argv[2]; os.makedirs(carpeta, exist_ok=True)
    extras = sys.argv[3:]
    ruta = os.path.join(carpeta, _nombre_archivo("TRANSFERENCIA", d))
    generar_pdf(d, ruta)
    print("Generado (escritos):\n ", ruta)
    if extras:
        completo = os.path.join(carpeta, _nombre_archivo("TRANSFERENCIA", d).replace(".pdf", "_COMPLETO.pdf"))
        _merge([ruta] + extras, completo)
        print("Generado (completo):\n ", completo)

if __name__ == "__main__":
    main()
```

