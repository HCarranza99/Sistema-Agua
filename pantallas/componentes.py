"""
Componentes reutilizables de UI.
Elimina la duplicación de _topbar y otros widgets comunes.
"""
import customtkinter as ctk
from config import (
    COLOR_BLANCO, COLOR_BORDE, COLOR_FONDO, COLOR_TEXTO, COLOR_TEXTO_MUTED,
    COLOR_AZUL_MARINO, COLOR_GRIS_CLARO,
    FONT_TOPBAR, FONT_BTN_SM, FONT_SMALL, FONT_STAT_VAL, FONT_STAT_LBL,
    FONT_BODY, FONT_LABEL
)


def topbar(parent, titulo: str, subtitulo: str, acciones: list = None):
    """
    Barra superior estándar con título, subtítulo y botones de acción.

    acciones: lista de (texto, comando, color_hex) — se agregan a la derecha.
    Retorna el frame de la topbar.
    """
    bar = ctk.CTkFrame(parent, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")

    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text=titulo, font=FONT_TOPBAR,
                 text_color=COLOR_TEXTO).pack(anchor="w")
    lbl_sub = ctk.CTkLabel(izq, text=subtitulo, font=FONT_SMALL,
                            text_color=COLOR_TEXTO_MUTED)
    lbl_sub.pack(anchor="w")

    if acciones:
        der = ctk.CTkFrame(bar, fg_color="transparent")
        der.pack(side="right", padx=20)
        for texto, cmd, color in reversed(acciones):
            ctk.CTkButton(
                der, text=texto, command=cmd, height=36, corner_radius=8,
                fg_color=color, hover_color=_darken(color),
                font=FONT_BTN_SM, text_color=COLOR_BLANCO
            ).pack(side="right", padx=4)

    return bar, lbl_sub


def _darken(hex_color: str) -> str:
    try:
        r = max(0, int(hex_color[1:3], 16) - 20)
        g = max(0, int(hex_color[3:5], 16) - 20)
        b = max(0, int(hex_color[5:7], 16) - 20)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def stat_card(parent, label: str, valor: str, delta: str = "",
              delta_up: bool = True, color_fondo: str = COLOR_BLANCO):
    """Tarjeta de estadística con valor grande y delta opcional."""
    from config import COLOR_VERDE_PAGO, COLOR_ROJO
    card = ctk.CTkFrame(parent, fg_color=color_fondo, corner_radius=10)
    ctk.CTkLabel(card, text=label, font=FONT_STAT_LBL,
                 text_color=COLOR_TEXTO_MUTED).pack(anchor="w", padx=14, pady=(12, 2))
    ctk.CTkLabel(card, text=valor, font=FONT_STAT_VAL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=14)
    if delta:
        color = COLOR_VERDE_PAGO if delta_up else COLOR_ROJO
        ctk.CTkLabel(card, text=delta, font=FONT_SMALL,
                     text_color=color).pack(anchor="w", padx=14, pady=(2, 12))
    else:
        ctk.CTkLabel(card, text=" ").pack(pady=(0, 6))
    return card


def badge(parent, texto: str, bg: str, fg: str, width: int = 90):
    """Etiqueta tipo badge con color de fondo y texto."""
    return ctk.CTkLabel(parent, text=texto, fg_color=bg, text_color=fg,
                        corner_radius=20, font=FONT_SMALL,
                        width=width, height=22)


def separador(parent, padx: int = 0, pady: int = 8):
    """Línea separadora horizontal."""
    ctk.CTkFrame(parent, height=1, fg_color=COLOR_BORDE).pack(
        fill="x", padx=padx, pady=pady)


def campo_formulario(parent, label: str, placeholder: str = "",
                     mostrar: str = None, valor_inicial: str = "") -> ctk.CTkEntry:
    """Campo de formulario estándar con label encima."""
    ctk.CTkLabel(parent, text=label, font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(10, 2))
    kwargs = dict(placeholder_text=placeholder, height=40,
                  corner_radius=8, fg_color=COLOR_FONDO)
    if mostrar:
        kwargs["show"] = mostrar
    entry = ctk.CTkEntry(parent, **kwargs)
    entry.pack(fill="x", padx=16, pady=(0, 2))
    if valor_inicial:
        entry.insert(0, valor_inicial)
    return entry


def encabezado_tabla(parent, columnas: list):
    """
    Encabezado de tabla estándar.
    columnas: lista de (texto, ancho_px)
    """
    enc = ctk.CTkFrame(parent, fg_color="#F8F9FB", corner_radius=0, height=36)
    enc.pack(fill="x")
    enc.pack_propagate(False)
    ctk.CTkFrame(enc, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    primera = True
    for texto, w in columnas:
        ctk.CTkLabel(
            enc, text=texto.upper(), font=("Arial", 10, "bold"),
            text_color=COLOR_TEXTO_MUTED, width=w, anchor="w"
        ).pack(side="left", padx=(16 if primera else 4, 0))
        primera = False
    return enc


def mensaje_vacio(parent, texto: str = "No hay datos que mostrar."):
    """Mensaje centrado cuando no hay datos en una tabla."""
    ctk.CTkLabel(parent, text=texto, font=("Arial", 13, "italic"),
                 text_color=COLOR_TEXTO_MUTED).pack(pady=40)


def boton_primario(parent, texto: str, comando, ancho: int = 200,
                   alto: int = 40, color: str = COLOR_AZUL_MARINO) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=texto, command=comando,
        height=alto, width=ancho, corner_radius=8,
        fg_color=color, hover_color=_darken(color),
        font=FONT_BTN_SM, text_color=COLOR_BLANCO
    )


def boton_secundario(parent, texto: str, comando,
                     ancho: int = 200, alto: int = 36) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=texto, command=comando,
        height=alto, width=ancho, corner_radius=8,
        fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
        border_width=1, border_color=COLOR_BORDE,
        font=FONT_BTN_SM
    )
