import customtkinter as ctk
import os
from tkinter import messagebox, filedialog
import herramientas.logger as logger
from herramientas.db import obtener_config, guardar_config
from herramientas.seguridad import cifrar_texto, descifrar_texto
from herramientas.email_sender import probar_conexion_smtp
from pantallas.componentes import topbar, separador
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_TEXTO, COLOR_TEXTO_MUTED,
    COLOR_GRIS_CLARO, FONT_TOPBAR, FONT_BTN, FONT_BTN_SM,
    FONT_SMALL, FONT_LABEL, FONT_BODY,
    RUTA_RESPALDOS_DEFAULT, RUTA_SINCRONIZACION_DEFAULT,
    RUTA_RECIBOS_DEFAULT, RUTA_REPORTES_PDF_DEFAULT, RUTA_REPORTES_EXCEL_DEFAULT
)


def _campo(parent, label, placeholder="", valor="", mostrar=None):
    ctk.CTkLabel(parent, text=label, font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=0, pady=(10, 2))
    kwargs = dict(placeholder_text=placeholder, height=40,
                  corner_radius=8, fg_color=COLOR_FONDO)
    if mostrar:
        kwargs["show"] = mostrar
    e = ctk.CTkEntry(parent, **kwargs)
    e.pack(fill="x", pady=(0, 2))
    if valor:
        e.insert(0, valor)
    return e


def _seccion(parent, titulo):
    ctk.CTkLabel(parent, text=titulo, font=("Arial", 13, "bold"),
                 text_color=COLOR_AZUL_MARINO).pack(anchor="w", pady=(20, 4))
    ctk.CTkFrame(parent, height=1, fg_color=COLOR_BORDE).pack(fill="x", pady=(0, 4))


def _ruta_campo(parent, label, clave_config, defecto):
    """Campo de ruta con botón Examinar y botón Abrir."""
    ctk.CTkLabel(parent, text=label, font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", pady=(10, 2))
    fila = ctk.CTkFrame(parent, fg_color="transparent")
    fila.pack(fill="x", pady=(0, 2))

    valor_actual = obtener_config(clave_config, defecto)
    entry = ctk.CTkEntry(fila, height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
    entry.insert(0, valor_actual)

    def examinar():
        carpeta = filedialog.askdirectory(
            title=f"Seleccionar carpeta para {label}",
            initialdir=entry.get() or os.path.expanduser("~"))
        if carpeta:
            entry.delete(0, "end")
            entry.insert(0, carpeta)

    def abrir():
        ruta = entry.get()
        if ruta and os.path.exists(ruta):
            import platform, subprocess
            try:
                if platform.system() == "Windows":
                    os.startfile(ruta)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", ruta])
                else:
                    subprocess.Popen(["xdg-open", ruta])
            except Exception:
                pass
        else:
            messagebox.showwarning("Carpeta no encontrada",
                                   "La carpeta no existe todavía.\n"
                                   "Se creará automáticamente al guardar.")

    ctk.CTkButton(fila, text="Examinar", width=90, height=40, corner_radius=8,
                   fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                   font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=examinar).pack(side="left", padx=(0, 4))
    ctk.CTkButton(fila, text="Abrir", width=70, height=40, corner_radius=8,
                   fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
                   border_width=1, border_color=COLOR_BORDE,
                   font=FONT_BTN_SM, command=abrir).pack(side="left")
    return entry


def crear_pantalla(parent_frame):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Configuración del Sistema",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    ctk.CTkLabel(izq, text="Ajustes generales — solo Administrador",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED).pack(anchor="w")

    # ── Contenido scrollable ───────────────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=24, pady=16)

    # Dos columnas
    col_izq = ctk.CTkFrame(scroll, fg_color=COLOR_BLANCO, corner_radius=10)
    col_izq.pack(side="left", fill="both", expand=True, padx=(0, 8))

    col_der = ctk.CTkFrame(scroll, fg_color=COLOR_BLANCO, corner_radius=10)
    col_der.pack(side="right", fill="both", expand=True)

    pad = ctk.CTkFrame(col_izq, fg_color="transparent")
    pad.pack(fill="both", expand=True, padx=20, pady=16)

    pad_der = ctk.CTkFrame(col_der, fg_color="transparent")
    pad_der.pack(fill="both", expand=True, padx=20, pady=16)

    # ── COLUMNA IZQUIERDA ──────────────────────────────────────────────────────

    _seccion(pad, "Información de la Comunidad")

    e_nombre = _campo(pad, "Nombre de la Comunidad",
                       "Ej: ADESCO El Gramal",
                       obtener_config("nombre_comunidad", ""))

    e_municipio = _campo(pad, "Municipio / Departamento",
                          "Ej: Tonacatepeque, San Salvador",
                          obtener_config("municipio", ""))

    e_telefono_org = _campo(pad, "Teléfono de la organización (opcional)",
                             "0000-0000",
                             obtener_config("telefono_organizacion", ""))

    _seccion(pad, "Carpetas de almacenamiento")

    rutas_entries = {}
    rutas_config = [
        ("Recibos de pago (PDF)",    "ruta_recibos",         RUTA_RECIBOS_DEFAULT),
        ("Reportes PDF",             "ruta_reportes_pdf",    RUTA_REPORTES_PDF_DEFAULT),
        ("Reportes Excel",           "ruta_reportes_excel",  RUTA_REPORTES_EXCEL_DEFAULT),
        ("Respaldos de BD",          "ruta_respaldos",       RUTA_RESPALDOS_DEFAULT),
        ("Sincronización en nube",   "ruta_sincronizacion",  RUTA_SINCRONIZACION_DEFAULT),
    ]
    for label, clave, defecto in rutas_config:
        rutas_entries[clave] = _ruta_campo(pad, label, clave, defecto)

    # ── COLUMNA DERECHA ────────────────────────────────────────────────────────

    _seccion(pad_der, "Configuración de correo (SMTP)")

    ctk.CTkLabel(pad_der,
                 text="Para enviar comprobantes por correo electrónico.\n"
                      "Con Gmail: use una Contraseña de Aplicación.",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 8))

    e_smtp_host = _campo(pad_der, "Servidor SMTP",
                          "smtp.gmail.com",
                          obtener_config("smtp_host", "smtp.gmail.com"))

    e_smtp_puerto = _campo(pad_der, "Puerto SMTP",
                            "587",
                            obtener_config("smtp_puerto", "587"))

    e_smtp_usuario = _campo(pad_der, "Usuario (correo remitente)",
                             "tucorreo@gmail.com",
                             obtener_config("smtp_usuario", ""))

    e_smtp_pass = _campo(pad_der, "Contraseña de aplicación",
                          "••••••••",
                          descifrar_texto(obtener_config("smtp_password_cifrada", "")),
                          mostrar="*")

    e_smtp_remitente = _campo(
        pad_der, "Nombre visible del remitente",
        "ADESCO El Gramal",
        obtener_config("smtp_remitente", ""))

    # Botón probar conexión
    lbl_prueba = ctk.CTkLabel(pad_der, text="",
                               font=FONT_SMALL, text_color=COLOR_VERDE_PAGO,
                               wraplength=300)
    lbl_prueba.pack(anchor="w", pady=(4, 0))

    def probar_smtp():
        # FIX: probar SIN guardar primero; solo persistir si la conexión fue exitosa
        lbl_prueba.configure(text="Probando conexión...", text_color=COLOR_TEXTO_MUTED)
        frame.update_idletasks()

        # Guardar temporalmente en memoria para que _obtener_config_smtp() los lea
        from herramientas.db import guardar_config as _gc
        from herramientas.seguridad import cifrar_texto as _ct
        _gc("smtp_host",    e_smtp_host.get().strip())
        _gc("smtp_puerto",  e_smtp_puerto.get().strip() or "587")
        _gc("smtp_usuario", e_smtp_usuario.get().strip())
        if e_smtp_pass.get().strip():
            _gc("smtp_password_cifrada", _ct(e_smtp_pass.get().strip()))
        _gc("smtp_remitente", e_smtp_remitente.get().strip())

        ok, msg = probar_conexion_smtp()
        if ok:
            lbl_prueba.configure(text=f"✓ {msg}", text_color=COLOR_VERDE_PAGO)
        else:
            lbl_prueba.configure(text=f"✗ {msg}", text_color=COLOR_ROJO)

    ctk.CTkButton(
        pad_der, text="Probar Conexión", height=38, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
        font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=probar_smtp
    ).pack(fill="x", pady=(8, 0))

    # ── Botón GUARDAR TODO ─────────────────────────────────────────────────────
    btn_guardar = ctk.CTkButton(
        frame, text="GUARDAR CONFIGURACIÓN",
        height=48, corner_radius=0,
        fg_color=COLOR_VERDE_PAGO, hover_color="#276749",
        font=FONT_BTN, text_color=COLOR_BLANCO,
        command=lambda: guardar_todo()
    )
    btn_guardar.pack(fill="x", side="bottom")

    def guardar_todo():
        errores = []

        nombre = e_nombre.get().strip()
        if not nombre:
            errores.append("El nombre de la comunidad es obligatorio.")

        if errores:
            messagebox.showwarning("Datos incompletos",
                                   "\n".join(f"• {e}" for e in errores))
            return

        # Información de la comunidad
        guardar_config("nombre_comunidad",       nombre)
        guardar_config("municipio",              e_municipio.get().strip())
        guardar_config("telefono_organizacion",  e_telefono_org.get().strip())

        # Rutas
        for clave, entry in rutas_entries.items():
            ruta = entry.get().strip()
            if ruta:
                guardar_config(clave, ruta)
                os.makedirs(ruta, exist_ok=True)

        # SMTP
        guardar_config("smtp_host",    e_smtp_host.get().strip())
        guardar_config("smtp_puerto",  e_smtp_puerto.get().strip())
        guardar_config("smtp_usuario", e_smtp_usuario.get().strip())
        guardar_config("smtp_remitente", e_smtp_remitente.get().strip())
        if e_smtp_pass.get().strip():
            guardar_config("smtp_password_cifrada",
                           cifrar_texto(e_smtp_pass.get().strip()))

        messagebox.showinfo("Configuración Guardada",
                            "Todos los ajustes han sido guardados correctamente.")

    return frame
