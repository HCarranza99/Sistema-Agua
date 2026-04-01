import customtkinter as ctk
from licencia.validador import estado_licencia, ESTADO_ACTIVA, ESTADO_POR_VENCER
from config import COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO


def aplicar_bloqueo(frame: ctk.CTkFrame, acciones_bloqueadas: set) -> None:
    """
    Recorre recursivamente los widgets de un frame y deshabilita
    los botones cuyo nombre de acción esté en acciones_bloqueadas.

    Los widgets que se deben bloquear deben tener el atributo
    _accion_licencia configurado, ej:
        btn = ctk.CTkButton(...)
        btn._accion_licencia = "registrar_cobro"
    """
    info = estado_licencia()
    if info["estado"] in (ESTADO_ACTIVA, ESTADO_POR_VENCER):
        return  # No hay nada que bloquear

    _recorrer_y_bloquear(frame, acciones_bloqueadas)


def _recorrer_y_bloquear(widget, acciones_bloqueadas: set) -> None:
    """Recursión sobre el árbol de widgets."""
    accion = getattr(widget, "_accion_licencia", None)
    if accion and accion in acciones_bloqueadas:
        try:
            widget.configure(state="disabled",
                             fg_color=COLOR_GRIS_CLARO,
                             text_color=COLOR_TEXTO_MUTED)
        except Exception:
            try:
                widget.configure(state="disabled")
            except Exception:
                pass

    for hijo in widget.winfo_children():
        _recorrer_y_bloquear(hijo, acciones_bloqueadas)


def btn_accion(parent, accion: str, **kwargs) -> ctk.CTkButton:
    """
    Crea un CTkButton y le asigna automáticamente el tag de acción.
    Usar en lugar de ctk.CTkButton cuando el botón debe responder al bloqueo.

    Ejemplo:
        btn = btn_accion(frame, "registrar_cobro",
                         text="Registrar Pago", command=...)
    """
    btn = ctk.CTkButton(parent, **kwargs)
    btn._accion_licencia = accion
    return btn


def esta_bloqueado() -> bool:
    """Retorna True si el sistema está en modo restringido o bloqueado."""
    from licencia.validador import licencia_operativa
    return not licencia_operativa()


def verificar_accion(accion: str, callback_bloqueado=None) -> bool:
    """
    Verifica si una acción está permitida antes de ejecutarla.
    Si está bloqueada, llama a callback_bloqueado (si se provee) y retorna False.

    Uso:
        if not verificar_accion("registrar_cobro"):
            return
    """
    from herramientas.permisos import ACCIONES_BLOQUEADAS_MODO_RESTRINGIDO
    from licencia.validador import licencia_operativa

    if licencia_operativa():
        return True

    if accion in ACCIONES_BLOQUEADAS_MODO_RESTRINGIDO:
        if callback_bloqueado:
            callback_bloqueado()
        else:
            from tkinter import messagebox
            messagebox.showwarning(
                "Suscripción Vencida",
                "Esta función no está disponible porque su suscripción ha vencido.\n\n"
                "Renueve su licencia para continuar usando el sistema."
            )
        return False

    return True
