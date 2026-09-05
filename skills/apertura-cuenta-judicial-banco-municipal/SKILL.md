---
name: "apertura-cuenta-judicial-banco-municipal"
description: "Prepara la solicitud de APERTURA DE CUENTA JUDICIAL en el Banco Municipal de Rosario (Sucursal 80 - Caja de Abogados) para un expediente radicado en Rosario. En el secretario Hermes, este flujo usa el motor Playwright del repo (scripts/apertura_cuenta_judicial.py) con el MISMO perfil Chrome del monitor (sesión SISFE ya logueada): busca el expediente por CUIJ, toma la captura de la ficha y la de la pantalla 'Ver cuenta judicial en el Banco Municipal de Rosario', y arma un PDF (una captura por página). El PDF + datos (carátula, CUIJ) se entregan para armar el borrador en Gmail dirigido a suc80jud@bmros.com.ar. NUNCA envía el mail: queda en borrador para que Santiago lo revise, adjunte el PDF y lo envíe. Usar cuando Santiago pida 'abrir/aperturar una cuenta judicial', 'apertura de cuenta judicial en el Banco Municipal', 'solicitar cuenta judicial', 'mail a suc80jud'."
---

# Apertura de cuenta judicial — Banco Municipal de Rosario (migrada al repo)

Reemplaza a la skill de Claude del mismo nombre. La diferencia: la lectura
de SISFE ya no usa "Claude in Chrome" sino el **Playwright del repo** con el
perfil persistente del monitor (`chrome_profile_sisfe`) — la sesión ya
logueada, sin re-loguear.

**Regla dura: NUNCA enviar el mail. Se deja SIEMPRE en borrador.** Solo
aplica al Banco Municipal de Rosario (expedientes radicados en Rosario).

Datos fijos: destinatario `suc80jud@bmros.com.ar` (Sucursal N° 80 – Caja de
Abogados, Banco Municipal de Rosario, Montevideo 2076); firma
`Dr. Santiago A. Segovia`.

## Uso

```bash
python scripts/apertura_cuenta_judicial.py --cuij 21-XXXXXXXX-X \
    --out "CARPETA_SALIDA" [--caratula "ACTOR C/ DEMANDADO S/ OBJETO"]
```

Hace:
1. Abre SISFE con el perfil del monitor (si la sesión expiró, pide login
   a Santiago — puerta humana, igual que el monitor).
2. Busca el CUIJ (primero en la lista cargada; si no está, usa el buscador
   con el campo CUIJ + "Efectuar la búsqueda").
3. Abre el detalle del expediente y **verifica que carátula/CUIJ
   coincidan** (si no, aborta — error grave evitado).
4. Captura #1: la ficha del expediente.
5. Clic en "Ver cuenta judicial en el Banco Municipal de Rosario" →
   captura #2 (muestra "NO SE ENCONTRARON CUENTAS BANCARIAS ASOCIADAS AL
   EXPEDIENTE." cuando todavía no hay cuenta — eso fundamenta el pedido).
6. Arma `CAPTURAS_APERTURA_CUENTA_{APELLIDO}_{CUIJ}.pdf` (una captura por
   página) y entrega los datos del borrador por stdout.

## Después (capa secretario / Gmail)

Con el PDF y los datos (carátula, CUIJ), crear el borrador con
google-workspace (gws) — nunca enviar:

- `to`: `suc80jud@bmros.com.ar`
- `subject`: `SOLICITUD DE APERTURA CUENTA JUDICIAL`
- `body`:
  > Estimado/a: Buenos días, vengo por el presente a solicitar apertura de
  > cuenta judicial dentro de los autos caratulados "{CARATULA}" CUIJ {CUIJ}.
  > Se acompañan capturas de pantalla del sistema SISFE. Aguardo
  > comentarios. Muchas gracias. Saludos. Dr. Santiago A. Segovia
- adjunto: el PDF va **a mano** (Santiago lo arrastra al borrador) — el
  PDF de capturas es grande y no se incrusta por base64 de forma confiable.

## ⚠️ Pendiente de validación

- Selectores del buscador SISFE (campo CUIJ) marcados ⬅ VALIDAR en el
  script — verificar contra el portal real en la primera corrida.
- Validar el flujo completo con un caso real de Santiago antes de dar la
  skill por buena.
