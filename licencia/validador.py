"""
validador.py — Estado de licencia (modo híbrido online + clave HMAC)
Si hay token GitHub: usa GitHub con fallback offline.
Si no hay token: usa clave HMAC local (modo original).
"""

import datetime
from herramientas.db import obtener_config, guardar_config
from herramientas.seguridad import obtener_hardware_id, validar_clave_licencia
from config import DIAS_AVISO_VENCIMIENTO, DIAS_GRACIA, MESES_ES

ESTADO_ACTIVA      = "activa"
ESTADO_POR_VENCER  = "por_vencer"
ESTADO_RESTRINGIDA = "restringida"
ESTADO_BLOQUEADA   = "bloqueada"
ESTADO_NO_ACTIVADA = "no_activada"


def estado_licencia() -> dict:
    from herramientas.licencia_online import token_configurado
    return _estado_online() if token_configurado() else _estado_hmac()


def _estado_online() -> dict:
    from herramientas.licencia_online import verificar_licencia_online, DIAS_GRACIA_OFFLINE
    hardware_id = obtener_hardware_id()
    r = verificar_licencia_online()

    if r["bloqueado_offline"]:
        return {
            "estado": ESTADO_BLOQUEADA, "dias_restantes": -DIAS_GRACIA_OFFLINE,
            "fecha_exp": _normalizar_fecha(r["vence"]) or None, "hardware_id": hardware_id,
            "mensaje": r["mensaje"], "modo": "online",
        }
    if not r["activa"]:
        return {
            "estado": ESTADO_BLOQUEADA, "dias_restantes": 0,
            "fecha_exp": _normalizar_fecha(r["vence"]) or None, "hardware_id": hardware_id,
            "mensaje": r["mensaje"], "modo": "online",
        }

    vence      = _normalizar_fecha(r["vence"])
    dias_rest  = _calcular_dias(vence)
    desde_cache = r["desde_cache"]
    dias_gracia = r["dias_gracia_restantes"]

    if dias_rest is None:
        estado, mensaje = ESTADO_ACTIVA, r["mensaje"]
    elif dias_rest > DIAS_AVISO_VENCIMIENTO:
        estado  = ESTADO_ACTIVA
        sufijo  = f" (sin internet, {dias_gracia} día(s) de gracia)" if desde_cache else ""
        mensaje = f"✅ Licencia activa{sufijo}."
    elif dias_rest > 0:
        estado  = ESTADO_POR_VENCER
        mensaje = f"⚠️ Suscripción vence en {dias_rest} días. Renueve a tiempo."
    elif dias_rest > -DIAS_GRACIA:
        estado  = ESTADO_RESTRINGIDA
        mensaje = (
            f"⚠️ Suscripción vencida. {DIAS_GRACIA + dias_rest} día(s) de gracia. "
            "Funciones de cobro deshabilitadas."
        )
    else:
        estado  = ESTADO_BLOQUEADA
        mensaje = "❌ Suscripción vencida. Contacte al desarrollador para renovar."

    return {
        "estado": estado,
        "dias_restantes": dias_rest if dias_rest is not None else 999,
        "fecha_exp": vence or None, "hardware_id": hardware_id,
        "mensaje": mensaje, "modo": "online",
    }


def _estado_hmac() -> dict:
    hardware_id    = obtener_hardware_id()
    activada       = obtener_config("licencia_activada", "0")
    clave_guardada = obtener_config("licencia_clave", "")

    if activada != "1" or not clave_guardada:
        return {
            "estado": ESTADO_NO_ACTIVADA, "dias_restantes": 0,
            "fecha_exp": None, "hardware_id": hardware_id,
            "mensaje": "El sistema no está activado.", "modo": "hmac",
        }

    resultado = validar_clave_licencia(clave_guardada, hardware_id)
    if not resultado["valida"]:
        return {
            "estado": ESTADO_BLOQUEADA, "dias_restantes": 0,
            "fecha_exp": None, "hardware_id": hardware_id,
            "mensaje": "Licencia inválida o no corresponde a este equipo.", "modo": "hmac",
        }

    fecha_exp = resultado["fecha_expiracion"]
    dias_rest = _calcular_dias(fecha_exp)

    if dias_rest is None:
        return {
            "estado": ESTADO_BLOQUEADA, "dias_restantes": 0,
            "fecha_exp": fecha_exp, "hardware_id": hardware_id,
            "mensaje": "Fecha de expiración inválida.", "modo": "hmac",
        }

    if dias_rest > DIAS_AVISO_VENCIMIENTO:
        estado, mensaje = ESTADO_ACTIVA, f"Licencia activa. Vence en {dias_rest} días."
    elif dias_rest > 0:
        estado  = ESTADO_POR_VENCER
        mensaje = f"⚠️ Suscripción vence en {dias_rest} días. Renueve a tiempo."
    elif dias_rest > -DIAS_GRACIA:
        estado  = ESTADO_RESTRINGIDA
        mensaje = (
            f"⚠️ Suscripción venció. {DIAS_GRACIA + dias_rest} día(s) de gracia. "
            "Funciones de cobro deshabilitadas."
        )
    else:
        estado  = ESTADO_BLOQUEADA
        mensaje = "❌ Suscripción vencida. Contáctenos para renovar."

    return {
        "estado": estado, "dias_restantes": dias_rest,
        "fecha_exp": fecha_exp, "hardware_id": hardware_id,
        "mensaje": mensaje, "modo": "hmac",
    }


def _normalizar_fecha(fecha: str) -> str:
    """
    Convierte cualquier formato de fecha a YYYY-MM-DD.
    Acepta: YYYY-MM-DD (sin cambios), YYYY-MM (último día del mes), YYYY-M (ídem).
    """
    if not fecha:
        return fecha
    import calendar as _cal
    partes = fecha.strip().split("-")
    if len(partes) == 3:
        # Ya está en formato correcto
        return f"{int(partes[0]):04d}-{int(partes[1]):02d}-{int(partes[2]):02d}"
    if len(partes) == 2:
        # YYYY-MM → convertir al último día del mes
        anio, mes = int(partes[0]), int(partes[1])
        dia = _cal.monthrange(anio, mes)[1]
        return f"{anio:04d}-{mes:02d}-{dia:02d}"
    return fecha  # formato desconocido, devolver tal cual


def _calcular_dias(fecha_exp: str) -> int | None:
    if not fecha_exp:
        return None
    try:
        partes = fecha_exp.split("-")
        if len(partes) == 3:
            # Formato nuevo: YYYY-MM-DD — expira al final del día indicado
            fecha_vence = datetime.date(int(partes[0]), int(partes[1]), int(partes[2]))
        elif len(partes) == 2:
            # Formato legado: YYYY-MM — expira al inicio del mes siguiente
            anio, mes = int(partes[0]), int(partes[1])
            fecha_vence = (
                datetime.date(anio + 1, 1, 1) if mes == 12
                else datetime.date(anio, mes + 1, 1)
            )
        else:
            return None
        return (fecha_vence - datetime.date.today()).days
    except (ValueError, TypeError):
        return None


def activar_licencia(clave: str) -> tuple[bool, str]:
    hardware_id = obtener_hardware_id()
    resultado   = validar_clave_licencia(clave, hardware_id)

    if not resultado["valida"]:
        return False, resultado["mensaje"]

    fecha_exp = resultado["fecha_expiracion"]
    guardar_config("licencia_activada",    "1")
    guardar_config("licencia_fecha_exp",   fecha_exp)
    guardar_config("licencia_hardware_id", hardware_id)
    guardar_config("licencia_clave",       clave.strip().upper())

    partes = fecha_exp.split("-")
    if len(partes) == 3:
        anio, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
        mes_nombre = MESES_ES.get(mes, str(mes))
        fecha_display = f"{dia} de {mes_nombre} de {anio}"
    else:
        anio, mes = int(partes[0]), int(partes[1])
        mes_nombre = MESES_ES.get(mes, str(mes))
        fecha_display = f"{mes_nombre} {anio}"

    from herramientas.licencia_online import limpiar_cache_sesion
    limpiar_cache_sesion()

    return True, f"✅ Licencia activada correctamente.\nVálida hasta: {fecha_display}"


def licencia_operativa() -> bool:
    return estado_licencia()["estado"] in (ESTADO_ACTIVA, ESTADO_POR_VENCER)


def licencia_restringida() -> bool:
    return estado_licencia()["estado"] == ESTADO_RESTRINGIDA


def licencia_bloqueada() -> bool:
    return estado_licencia()["estado"] in (ESTADO_BLOQUEADA, ESTADO_NO_ACTIVADA)