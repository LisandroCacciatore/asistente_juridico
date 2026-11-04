# tests/

Pruebas que **no** necesitan SISFE, FirmAr, Meta Jurídico ni Playwright —
corren en milisegundos, en cualquier máquina, sin login de nadie.

## Correrlas

```powershell
python -m pip install pytest --break-system-packages
python -m pytest tests/ -v
```

## Qué cubren hoy

- `test_cedula_desde_texto.py` — parseo de carátula/CUIJ/fecha, detección
  y recorte de sentencias, formato del nombre de archivo.
- `test_estado.py` — ciclo de vida de una cédula (generada → firmada →
  presentada), el borrado automático de PDF al presentar (y que NO borra
  los de otra cédula), el log de acciones, y una prueba de concurrencia
  que confirma que el `RLock` de `_mutar()` no pierde actualizaciones
  cuando dos procesos escriben al mismo tiempo.
- `test_portal_db.py`, `test_portal_auth.py`, `test_portal_admin.py` — base
  SQLite del portal (personas, sesiones, estado, log, ficha y documentos),
  hash argon2, login/sesiones/cookie firmada y consola de administración.
- `test_portal_permisos.py`, `test_portal_servidor.py` — persona activa y
  regla de la cadena (D25), login HTTP, estado/log/ficha, subida y descarga
  de PDFs, anti-duplicado (D22), CSRF y panel mínimo. Usan una base y una
  carpeta de subidas temporales: no tocan `portal.db` ni `portal_uploads/`.

## Qué NO cubren (y no pueden cubrir así)

Todo lo que necesita un portal real (SISFE, FirmAr, Meta Jurídico) o
Hermes con sesión real de Gmail. Eso queda en `PENDIENTES.feature.md`
como validación manual — no tiene sentido fingir que se puede automatizar
un login con reCAPTCHA humano.

## Si agregás una prueba nueva

Usá `monkeypatch` para redirigir cualquier archivo que el código toque
(`estado.ARCHIVO`, `estado.ARCHIVO_LOG`, etc.) a una carpeta temporal —
mirá el fixture `_archivos_temporales` en `test_estado.py` como modelo.
Ninguna prueba de esta carpeta debe tocar `estado.json` real.
