# -*- coding: utf-8 -*-
# ============================================================
#  ESTADO.PY — Registro de cédulas (estado.json) + log de acciones
# ------------------------------------------------------------
#  Es el puente entre la skill (que genera las cédulas) y el
#  dashboard (que las muestra y dispara firma/subida).
#
#  Los PDF son TRANSITORIOS: viven mientras dura el trámite (generar →
#  firmar → subir) y se borran solos al quedar presentados. Lo que
#  queda para siempre es el LOG DE ACCIONES (log_acciones.jsonl):
#  un registro con fecha y hora de cada paso, que sobrevive aunque
#  el archivo ya no exista.
#
#  Concurrencia (Fase 0): toda secuencia cargar → modificar → guardar
#  corre bajo un RLock (hilos) y un FileLock (procesos), para que dos
#  trabajos en paralelo (ej: consola local + portal) no se pisen.
# ============================================================

import os
import json
import getpass
import platform
import tempfile
import threading
import time
import datetime
from contextlib import contextmanager

from filelock import FileLock, Timeout

ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estado.json")
ARCHIVO_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_acciones.jsonl")
# RLock: las operaciones compuestas (cargar → modificar → guardar) vuelven a
# entrar al lock desde cargar()/guardar() sin deadlock.
_lock = threading.RLock()

# FileLock (no SoftFileLock): el sistema operativo libera el lock si el
# proceso muere. SoftFileLock deja un .lock huérfano y traba todo.
BLOQUEO_TIMEOUT = 10
_REINTENTOS_REPLACE = 8
_ESPERA_REPLACE = 0.075


class EstadoBloqueado(RuntimeError):
    """No se pudo obtener el lock de archivo dentro del timeout."""


class ErrorEscrituraEstado(RuntimeError):
    """No se pudo reemplazar estado.json después de varios reintentos."""


@contextmanager
def _bloqueo_archivo(archivo, timeout=None):
    """Lock interproceso para un archivo de estado o de log.

    El RLock de arriba protege hilos dentro del mismo proceso. Desde que la
    consola local y el portal son dos procesos distintos, hace falta además
    un lock de archivo para que no lean y escriban el mismo JSON a la vez.

    Orden fijo en todo el módulo: primero RLock, después FileLock. No
    invertirlo en ninguna función para evitar deadlocks.
    """
    timeout = BLOQUEO_TIMEOUT if timeout is None else timeout
    try:
        with FileLock(f"{archivo}.lock", timeout=timeout):
            yield
    except Timeout as e:
        raise EstadoBloqueado(
            f"No pude obtener el lock de {os.path.basename(archivo)} en "
            f"{timeout} s. Otro proceso puede estar usando el estado; "
            "probá de nuevo en unos segundos."
        ) from e


def _leer_disco():
    """Lee el JSON sin lock (solo para uso interno de cargar()/_mutar())."""
    if not os.path.isfile(ARCHIVO):
        return {"cedulas": [], "pendientes": []}
    with open(ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("cedulas", [])
    data.setdefault("pendientes", [])
    return data


def cargar():
    """Devuelve el estado completo bajo lock de hilo y de archivo.

    El lock de archivo también evita que un lector tenga abierto el JSON
    justo cuando otro proceso lo reemplaza con os.replace (en Windows eso
    puede hacer fallar el reemplazo).
    """
    with _lock:
        with _bloqueo_archivo(ARCHIVO):
            return _leer_disco()


def _reemplazar_con_reintentos(origen, destino):
    """os.replace con reintentos ante PermissionError de Windows.

    El lock protege contra nuestros procesos, no contra antivirus,
    indexadores, backups o un lector externo que tenga el archivo abierto.
    En Windows eso aparece como PermissionError; se reintenta un rato y,
    si sigue bloqueado, se falla con un mensaje accionable.
    """
    ultimo = None
    for intento in range(1, _REINTENTOS_REPLACE + 1):
        try:
            os.replace(origen, destino)
            return
        except PermissionError as e:
            ultimo = e
            if intento == _REINTENTOS_REPLACE:
                break
            time.sleep(_ESPERA_REPLACE)
    raise ErrorEscrituraEstado(
        f"No pude reemplazar {os.path.basename(destino)} después de "
        f"{_REINTENTOS_REPLACE} intentos. Otro programa puede tener el archivo "
        "abierto (antivirus, indexador, backup). Cerrá ese programa o probá "
        "de nuevo."
    ) from ultimo


def _guardar_sin_lock(data):
    """Escribe el JSON de forma atómica: temporal + fsync + os.replace.

    Si el proceso muere a mitad de la escritura, el archivo original queda
    intacto. El temporal vive en la misma carpeta para que os.replace sea
    atómico también en Windows.
    """
    carpeta = os.path.dirname(ARCHIVO) or "."
    os.makedirs(carpeta, exist_ok=True)
    fd, temporal = tempfile.mkstemp(
        prefix=os.path.basename(ARCHIVO) + ".", suffix=".tmp", dir=carpeta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        _reemplazar_con_reintentos(temporal, ARCHIVO)
    except Exception:
        try:
            os.remove(temporal)
        except OSError:
            pass
        raise


def guardar(data):
    with _lock:
        with _bloqueo_archivo(ARCHIVO):
            _guardar_sin_lock(data)


def _mutar(modificador):
    """Aplica modificador(data) en una operación atómica y persiste.

    Es la ÚNICA vía para cambiar el estado: el lock cubre la secuencia
    completa cargar → modificar → guardar, así dos hilos o dos procesos no
    pierden actualizaciones (cada uno lee el resultado del anterior).
    """
    with _lock:
        with _bloqueo_archivo(ARCHIVO):
            data = _leer_disco()
            modificador(data)
            _guardar_sin_lock(data)
            return data


def _ahora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _quien():
    """Quién hizo la acción y desde qué máquina.

    Decisión D11 del SPEC: el log tiene que decir *quién* hizo cada cosa, no
    solo qué se hizo. Hoy la identidad disponible es la de Windows (la sesión
    con la que corre el servidor). Cuando cada persona del estudio tenga su
    cuenta y su perfil de Chrome (Fase 10, multiagente) va a seguir siendo
    este mismo campo: el usuario de la sesión que disparó la acción.

    No usa `whoami` ni depende de que el proceso tenga consola: getpass y
    platform funcionan igual corriendo como servicio.
    """
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = os.environ.get("USERNAME") or os.environ.get("USER") or "?"
    try:
        maquina = platform.node()
    except Exception:
        maquina = ""
    return usuario, maquina


# --- Log de acciones (append-only, sobrevive a los archivos) ------
def registrar_log(accion, id_cedula, caratula="", cuij="", detalle="", identidad=None,
                  operador=None, usuario=None, maquina=None):
    """
    Agrega una línea al log de acciones. No se pisa nunca — cada llamada
    suma una entrada nueva. `accion` típicas: "generada", "firmada",
    "presentada", "eliminado_pdf", "error_eliminar_pdf".

    Cada entrada queda sellada con el usuario de Windows y la máquina
    (D11). Si el estudio tiene una sola persona, alcanza con la máquina
    para saber de dónde salió; con varias, el usuario distingue quién.

    `operador`, `identidad`, `usuario` y `maquina` se pueden pasar
    explícitos cuando el que registra no es la consola local (por ejemplo,
    el portal, que tiene su propio login y no comparte `sesion.json`).
    """
    usuario_win, maquina_win = _quien()
    usuario = usuario or usuario_win
    maquina = maquina or maquina_win
    # Quién operó y con qué identidad se ejecutó (SPEC D18). Si no hay
    # jornada declarada, el operador cae al usuario de Windows: es el único
    # dato que hay, y así el log nunca queda con el campo vacío.
    try:
        import sesion
        jornada = sesion.actual() or {}
    except Exception:
        jornada = {}
    operador = operador or jornada.get("operador") or usuario
    entrada = {
        "fecha_hora": _ahora(),
        "accion": accion,
        "id": id_cedula,
        "caratula": caratula,
        "cuij": cuij,
        "detalle": detalle,
        "usuario": usuario,
        "maquina": maquina,
        "operador": operador,
        "identidad": identidad or jornada.get("identidad") or operador,
    }
    with _lock:
        with _bloqueo_archivo(ARCHIVO_LOG):
            with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
    return entrada


def leer_log(limite=None):
    """Devuelve las entradas del log, más recientes primero.

    Las entradas viejas (escritas antes de D11) no tienen `usuario` ni
    `maquina`. Se completan vacías acá y no en el que lee: así ningún
    consumidor — el dashboard, un informe, una auditoría — tiene que
    acordarse de que el campo puede faltar.
    """
    with _lock:
        with _bloqueo_archivo(ARCHIVO_LOG):
            if not os.path.isfile(ARCHIVO_LOG):
                return []
            with open(ARCHIVO_LOG, encoding="utf-8") as f:
                lineas = [json.loads(l) for l in f if l.strip()]
    for e in lineas:
        e.setdefault("usuario", "")
        e.setdefault("maquina", "")
        e.setdefault("operador", e.get("usuario", ""))
        e.setdefault("identidad", "")
    lineas.reverse()
    return lineas[:limite] if limite else lineas


def _actualizar(id_cedula, **campos):
    def mod(data):
        for c in data["cedulas"]:
            if c.get("id") == id_cedula:
                c.update(campos)
    return _mutar(mod)


# --- Pendientes de clasificar (el decreto ya se detectó, falta que ---
# --- el abogado elija el tipo de cédula antes de generar el PDF) -----
def agregar_pendiente(pendiente):
    """
    pendiente: dict con los mismos campos que espera generar_cedula.generar()
    (caratula, cuij, radicado, ciudad, fecha_decreto, texto_decreto,
    novedad, destinatarios, y los extras de audiencia si los hay) MÁS
    "tipo_sugerido" (lo que las reglas hubieran elegido solas, para
    preseleccionar en el dashboard). Todavía NO tiene "tipo" definitivo
    ni se generó ningún PDF.
    """
    def mod(data):
        data["pendientes"] = [p for p in data["pendientes"] if p.get("id") != pendiente["id"]]
        data["pendientes"].append(pendiente)
    _mutar(mod)
    registrar_log("pendiente_detectado", pendiente["id"], pendiente.get("caratula", ""), pendiente.get("cuij", ""))


def obtener_pendiente(id_pendiente):
    data = cargar()
    for p in data.get("pendientes", []):
        if p.get("id") == id_pendiente:
            return p
    return None


def eliminar_pendiente(id_pendiente):
    def mod(data):
        data["pendientes"] = [p for p in data.get("pendientes", []) if p.get("id") != id_pendiente]
    _mutar(mod)


def marcar_atencion(id_cedula, motivo, etiqueta="Solicita Revisión"):
    """
    Marca la cédula como 'atencion' — el mismo estado que ya usa el
    dashboard para Bus Federal y decretos ambiguos (se muestra en la
    sección "Requieren atención" con el motivo, sin necesitar ningún
    cambio de pantalla nuevo).
    """
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, estado="atencion", reason=f"{etiqueta}: {motivo}")
    registrar_log("atencion", id_cedula, cedula.get("caratula", ""), cedula.get("cuij", ""), motivo)


def marcar_firmada(id_cedula, ruta_firmada, identidad=None):
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, estado="firmada", ruta_firmada=ruta_firmada, fecha_firmada=_ahora())
    registrar_log("firmada", id_cedula, cedula.get("caratula", ""), cedula.get("cuij", ""),
                  ruta_firmada or "", identidad=identidad)


def fijar_cadena(id_cedula, identidad):
    """Fija de quién es esta cédula, y no se cambia más (SPEC D25).

    "Del SISFE que bajé, es el mismo que tiene que firmar": la identidad
    queda grabada en la cédula en el primer acto del portal, y los actos
    siguientes la tienen que respetar. Fijarla no es un detalle de
    auditoría: es el candado.
    """
    if not identidad:
        return ""
    cedula = obtener_cedula(id_cedula) or {}
    if (cedula.get("identidad_cadena") or "") == identidad:
        return identidad
    ya_es_de_alguien = cedula.get("identidad_cadena") or ""
    if ya_es_de_alguien:
        # La cadena es un candado, no un dato que se corrige por atrás: si ya
        # es de alguien, no se cambia. El que llama tendría que haber frenado
        # antes (acciones.verificar_cadena).
        return ya_es_de_alguien
    _actualizar(id_cedula, identidad_cadena=identidad)
    registrar_log("cadena_fijada", id_cedula, cedula.get("caratula", ""),
                  cedula.get("cuij", ""), f"la cédula queda de {identidad}",
                  identidad=identidad)
    return identidad


def cadena_de(id_cedula):
    """De quién es esta cédula, o "" si todavía no se fijó."""
    return (obtener_cedula(id_cedula) or {}).get("identidad_cadena") or ""


def marcar_cargada_sisfe(id_cedula, detalle="", descripcion="", identidad=None):
    """La cédula quedó cargada en el SISFE, esperando el clic en NOTIFICAR.

    OJO: no se cambia `estado`. El dashboard dibuja tres estados (generada
    → firmada → presentada) y meter uno nuevo haría que la cédula
    desaparezca de la pantalla. El paso intermedio queda en el LOG, que es
    justamente para lo que existe: la cédula sigue en «a presentar», con
    el dato de que ya está cargada en el portal.
    """
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, sisfe_cargada=True, sisfe_fecha=_ahora(),
                sisfe_descripcion=descripcion)
    registrar_log("cargada_en_sisfe", id_cedula, cedula.get("caratula", ""),
                  cedula.get("cuij", ""), detalle or descripcion, identidad=identidad)


def marcar_presentada(id_cedula, identidad=None):
    """
    Marca la cédula como presentada Y borra los PDF locales (original y
    firmado) — ya cumplieron su función. El registro de que existieron
    y qué pasó con ellos queda en el log de acciones, no en el disco.
    """
    cedula = obtener_cedula(id_cedula) or {}
    _actualizar(id_cedula, estado="presentada", fecha_presentada=_ahora())
    registrar_log("presentada", id_cedula, cedula.get("caratula", ""), cedula.get("cuij", ""),
                  identidad=identidad)

    for campo in ("ruta_pdf", "ruta_firmada"):
        ruta = cedula.get(campo)
        if ruta and os.path.isfile(ruta):
            try:
                os.remove(ruta)
                registrar_log("eliminado_pdf", id_cedula, cedula.get("caratula", ""),
                              cedula.get("cuij", ""), f"{campo}: {ruta}")
            except Exception as e:
                registrar_log("error_eliminar_pdf", id_cedula, cedula.get("caratula", ""),
                              cedula.get("cuij", ""), f"{campo}: {ruta} -> {e}")


def reiniciar_estado(id_cedula):
    _actualizar(id_cedula, estado="generada", ruta_firmada=None)


def obtener_cedula(id_cedula):
    data = cargar()
    for c in data.get("cedulas", []):
        if c.get("id") == id_cedula:
            return c
    return None


def eliminar_cedula(id_cedula):
    def mod(data):
        data["cedulas"] = [c for c in data.get("cedulas", []) if c.get("id") != id_cedula]
    return _mutar(mod)


def editar_cedula(id_cedula, nuevos_datos):
    return _actualizar(id_cedula, **nuevos_datos)


# --- Función que llamaría la skill al generar una cédula ----------
def registrar_cedula(cedula):
    """
    cedula: dict con al menos id, caratula, cuij, ruta_pdf, estado='generada'.
    Si ya existe (mismo id) la reemplaza; si no, la agrega.
    """
    cedula.setdefault("fecha_generada", _ahora())
    def mod(data):
        data["cedulas"] = [c for c in data["cedulas"] if c.get("id") != cedula["id"]]
        data["cedulas"].append(cedula)
    _mutar(mod)
    registrar_log("generada", cedula["id"], cedula.get("caratula", ""), cedula.get("cuij", ""))
