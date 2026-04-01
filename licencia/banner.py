import customtkinter as ctk
from config import COLOR_BLANCO, COLOR_BANNER_WARN, COLOR_BANNER_ERROR, FONT_SMALL, FONT_BTN_SM
from licencia.validador import (
    estado_licencia, ESTADO_POR_VENCER, ESTADO_RESTRINGIDA, ESTADO_BLOQUEADA
)


def crear_banner(parent_frame, ventana_principal, callback_renovar=None) -> ctk.CTkFrame | None:
    """
    Crea y retorna un banner de advertencia si la licencia lo requiere.
    Retorna None si la licencia está activa y no necesita aviso.

    Args:
        parent_frame: frame donde se insertará el banner (al tope del dashboard)
        ventana_principal: referencia a la ventana principal
        callback_renovar: función a llamar al presionar "Renovar"
    """
    info = estado_licencia()
    estado = info["estado"]

    if estado not in (ESTADO_POR_VENCER, ESTADO_RESTRINGIDA, ESTADO_BLOQUEADA):
        return None

    # Color según urgencia
    if estado == ESTADO_POR_VENCER:
        color_fondo = COLOR_BANNER_WARN
        icono       = "⚠️"
    else:
        color_fondo = COLOR_BANNER_ERROR
        icono       = "🔒"

    banner = ctk.CTkFrame(parent_frame, fg_color=color_fondo,
                           corner_radius=0, height=36)
    banner.pack(fill="x", side="top")
    banner.pack_propagate(False)

    contenido = ctk.CTkFrame(banner, fg_color="transparent")
    contenido.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        contenido,
        text=f"{icono}  {info['mensaje']}",
        font=FONT_SMALL,
        text_color=COLOR_BLANCO
    ).pack(side="left", padx=(0, 16))

    if callback_renovar:
        ctk.CTkButton(
            contenido,
            text="Renovar ahora",
            height=24, corner_radius=6,
            fg_color=COLOR_BLANCO,
            text_color=color_fondo,
            hover_color="#F0F0F0",
            font=FONT_BTN_SM,
            command=callback_renovar
        ).pack(side="left")

    return banner


def actualizar_banner(banner_ref: list, parent_frame, ventana_principal,
                       callback_renovar=None) -> None:
    """
    Destruye el banner existente y lo recrea si es necesario.
    Muestra u oculta el parent_frame según haya banner activo o no,
    de modo que no ocupe espacio cuando la licencia está al día.
    banner_ref: lista de un elemento [banner_widget_o_None] (mutable)
    """
    if banner_ref[0]:
        try:
            banner_ref[0].destroy()
        except Exception:
            pass
        banner_ref[0] = None

    nuevo = crear_banner(parent_frame, ventana_principal, callback_renovar)
    banner_ref[0] = nuevo

    if nuevo:
        # Empacar antes del primer hijo existente del contenedor (el área de pantallas)
        # para garantizar que el banner quede siempre en la parte superior.
        hijos = [w for w in parent_frame.master.pack_slaves()
                 if w is not parent_frame]
        if hijos:
            parent_frame.pack(fill="x", side="top", before=hijos[0])
        else:
            parent_frame.pack(fill="x", side="top")
    else:
        # Sin banner: ocultar el contenedor para no robar espacio vertical
        parent_frame.pack_forget()