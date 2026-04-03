from config import (
    ROL_SOPORTE, ROL_ADMINISTRADOR, ROL_PRESIDENTE, ROL_CAJERO,
    JERARQUIA_ROLES
)


def _nivel(rol: str) -> int:
    return JERARQUIA_ROLES.get(rol, 0)


def puede_registrar_cobros(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_CAJERO)


def puede_cerrar_caja(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_CAJERO)


def puede_enviar_recibos(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_CAJERO)


def puede_ver_reporte_dia(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_CAJERO)


def puede_ver_historial(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_PRESIDENTE)


def puede_exportar(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_PRESIDENTE)


def puede_gestionar_vecinos(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_PRESIDENTE)


def puede_gestionar_usuarios(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_ADMINISTRADOR)


def puede_gestionar_zonas(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_ADMINISTRADOR)


def puede_configurar_sistema(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_ADMINISTRADOR)


def puede_restaurar_bd(rol: str) -> bool:
    return _nivel(rol) >= _nivel(ROL_ADMINISTRADOR)


def puede_ver_panel_soporte(rol: str) -> bool:
    return rol == ROL_SOPORTE


def es_superior_o_igual(rol_actual: str, rol_objetivo: str) -> bool:
    """Verifica si rol_actual tiene igual o mayor jerarquía que rol_objetivo."""
    return _nivel(rol_actual) >= _nivel(rol_objetivo)


def puede_anular_cobro(rol: str) -> bool:
    """Todos los roles pueden anular cobros."""
    return _nivel(rol) >= _nivel(ROL_CAJERO)


def puede_modificar_usuario(rol_editor: str, rol_objetivo: str) -> bool:
    """
    Un usuario solo puede editar/eliminar usuarios de menor jerarquía.
    Nadie puede modificar al Soporte excepto el propio Soporte.
    """
    if rol_objetivo == ROL_SOPORTE and rol_editor != ROL_SOPORTE:
        return False
    return _nivel(rol_editor) > _nivel(rol_objetivo)


# Mapa de permisos para el bloqueador de suscripción
# Define qué acciones quedan bloqueadas en modo restringido
ACCIONES_BLOQUEADAS_MODO_RESTRINGIDO = {
    "registrar_cobro",
    "agregar_vecino",
    "editar_vecino",
    "exportar_pdf",
    "exportar_excel",
    "crear_respaldo",
    "cerrar_caja",
    "enviar_recibo",
}