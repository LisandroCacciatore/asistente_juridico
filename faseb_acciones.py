# -*- coding: utf-8 -*-
"""Épica 2 de la Fase B: lista cerrada de acciones que el portal puede pedir.

El portal no puede ordenar cualquier cosa que el dashboard sepa hacer. Sólo dos
acciones, y con nombre explícito. Si la acción no está en esta lista, no se
ejecuta nada.

Nota de nombres: la especificación habla de `firmar_lote` y `presentar`. En el
código, "presentar en SISFE" es la acción `notificar_sisfe`; `presentar` es el
nombre de cara al usuario y acá se traduce.
"""

ACCIONES_PORTAL = frozenset({"firmar_lote", "presentar"})

# nombre pedido por el portal -> acción interna
_INTERNA = {
    "firmar_lote": "firmar_lote",
    "presentar": "notificar_sisfe",
}


class AccionNoPermitida(Exception):
    """La acción pedida no está en la lista cerrada."""


def resolver(accion):
    """Devuelve la acción interna, o lanza AccionNoPermitida.

    Se normaliza a minúsculas y sin espacios: una acción vacía o con relleno
    tampoco pasa.
    """
    nombre = (accion or "").strip().lower()
    if nombre not in ACCIONES_PORTAL:
        raise AccionNoPermitida(
            f"Acción no permitida desde el portal: {nombre or '(vacía)'}"
        )
    return _INTERNA[nombre]
