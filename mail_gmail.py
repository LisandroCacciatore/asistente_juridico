# -*- coding: utf-8 -*-
# ============================================================
#  MAIL_GMAIL.PY — Capa de Gmail del secretario
# ------------------------------------------------------------
#  Usa el token OAuth que ya administra Hermes
#  (~/AppData/Local/hermes/google_token.json) — el mismo que
#  google-workspace. NO guarda credenciales propias.
#
#  Regla del secretario: SIEMPRE borradores, nunca envío directo.
#  El envío lo aprueba el abogado (un clic en el dashboard).
#
#  Uso:
#    python mail_gmail.py search "is:unread" [--max 10]
#    python mail_gmail.py read MESSAGE_ID
#    python mail_gmail.py draft --to a@b.com --subject "Asunto" \
#        --body "Texto" [--adjunto ruta.pdf] [--adjunto otra.pdf]
#    python mail_gmail.py drafts [--max 10]
# ============================================================

import argparse
import base64
import json
import mimetypes
import os
import sys
from email.message import EmailMessage

TOKEN_PATH = os.path.join(
    os.environ.get("HERMES_HOME", os.path.expanduser("~/AppData/Local/hermes")),
    "google_token.json",
)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _servicio():
    """Construye el cliente de Gmail a partir del token de Hermes."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not os.path.isfile(TOKEN_PATH):
        raise FileNotFoundError(
            f"No hay token de Google en {TOKEN_PATH}. "
            "Correr el setup de la skill google-workspace."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _cabecera(msg, nombre):
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == nombre.lower():
            return h.get("value", "")
    return ""


def _cuerpo_texto(msg):
    """Extrae el texto plano del mensaje (recorre multipart)."""
    def walk(part):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
        for sub in part.get("parts", []) or []:
            r = walk(sub)
            if r:
                return r
        return ""
    return walk(msg.get("payload", {}))


def buscar(query, max_resultados=10):
    svc = _servicio()
    res = svc.users().messages().list(
        userId="me", q=query, maxResults=max_resultados).execute()
    salida = []
    for ref in res.get("messages", []):
        m = svc.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["From", "To", "Subject", "Date"]).execute()
        salida.append({
            "id": ref["id"],
            "from": _cabecera(m, "From"),
            "to": _cabecera(m, "To"),
            "subject": _cabecera(m, "Subject"),
            "date": _cabecera(m, "Date"),
            "snippet": m.get("snippet", ""),
            "labels": m.get("labelIds", []),
        })
    return salida


def leer(message_id):
    svc = _servicio()
    m = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    return {
        "id": message_id,
        "from": _cabecera(m, "From"),
        "to": _cabecera(m, "To"),
        "subject": _cabecera(m, "Subject"),
        "date": _cabecera(m, "Date"),
        "body": _cuerpo_texto(m),
    }


def crear_borrador(to, subject, body, adjuntos=None):
    """Crea un BORRADOR (nunca envía). Devuelve {id, message_id}.

    adjuntos: lista de rutas de archivos (PDFs, Word, etc.) que se
    adjuntan con su tipo MIME detectado por extensión.
    """
    svc = _servicio()
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    for ruta in (adjuntos or []):
        if not os.path.isfile(ruta):
            print(f"  ⚠ Adjunto no encontrado, se omite: {ruta}", file=sys.stderr)
            continue
        ctype, _ = mimetypes.guess_type(ruta)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(ruta, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(ruta))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = svc.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}).execute()
    return {"id": draft.get("id"), "message_id": draft.get("message", {}).get("id")}


def cuenta():
    """Dirección de la casilla configurada (el dashboard la muestra)."""
    svc = _servicio()
    return svc.users().getProfile(userId="me").execute().get("emailAddress", "")


def _adjuntos(msg):
    """Nombres de archivo de los adjuntos de un mensaje."""
    nombres = []

    def walk(part):
        fn = part.get("filename") or ""
        if fn:
            nombres.append(fn)
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(msg.get("payload", {}))
    return nombres


def listar_borradores(max_resultados=10):
    svc = _servicio()
    res = svc.users().drafts().list(userId="me", maxResults=max_resultados).execute()
    salida = []
    for d in res.get("drafts", []):
        m = svc.users().drafts().get(userId="me", id=d["id"], format="full").execute()
        msg = m.get("message", {})
        salida.append({
            "draft_id": d["id"],
            "message_id": msg.get("id"),
            "to": _cabecera(msg, "To"),
            "subject": _cabecera(msg, "Subject"),
            "snippet": msg.get("snippet", ""),
            "adjuntos": _adjuntos(msg),
        })
    return salida


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Capa de Gmail del secretario (borradores)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--max", type=int, default=10)

    p = sub.add_parser("read")
    p.add_argument("message_id")

    p = sub.add_parser("draft")
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--adjunto", action="append", default=[])

    p = sub.add_parser("drafts")
    p.add_argument("--max", type=int, default=10)

    sub.add_parser("cuenta")

    args = ap.parse_args()
    if args.cmd == "search":
        print(json.dumps(buscar(args.query, args.max), ensure_ascii=False, indent=2))
    elif args.cmd == "read":
        print(json.dumps(leer(args.message_id), ensure_ascii=False, indent=2))
    elif args.cmd == "draft":
        res = crear_borrador(args.to, args.subject, args.body, args.adjunto)
        print(json.dumps({"ok": True, **res}, ensure_ascii=False))
    elif args.cmd == "drafts":
        print(json.dumps(listar_borradores(args.max), ensure_ascii=False, indent=2))
    elif args.cmd == "cuenta":
        print(json.dumps({"cuenta": cuenta()}, ensure_ascii=False))
