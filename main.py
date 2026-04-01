import os
import sys
import threading
import customtkinter as ctk
from tkinter import messagebox

from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_AZUL_MARINO, COLOR_BORDE,
    COLOR_SIDEBAR, COLOR_SIDEBAR_HOVER, COLOR_SIDEBAR_ACTIVE,
    COLOR_SIDEBAR_TEXT, COLOR_TEXTO, COLOR_TEXTO_MUTED, COLOR_ROJO,
    COLOR_VERDE_PAGO,
    FONT_NAV, FONT_BTN, FONT_SMALL, FONT_LABEL, FONT_BTN_SM,
    ROL_SOPORTE, ROL_ADMINISTRADOR, ROL_PRESIDENTE, ROL_CAJERO,
    MESES_ES, VERSION
)
from herramientas.db import inicializar_base_datos, obtener_config, guardar_config, generar_recibos_mes_actual
from herramientas.seguridad import hashear_contrasena
from herramientas.permisos import (
    puede_gestionar_vecinos, puede_gestionar_usuarios,
    puede_gestionar_zonas, puede_configurar_sistema,
    puede_ver_panel_soporte, puede_exportar
)
from licencia.validador import (
    estado_licencia, licencia_bloqueada,
    ESTADO_NO_ACTIVADA, ESTADO_BLOQUEADA
)
from licencia.activacion import mostrar_pantalla_activacion, mostrar_pantalla_renovacion
from licencia.banner import crear_banner, actualizar_banner
import herramientas.respaldos as p_respaldos

import pantallas.cobros as p_cobros
import pantallas.vecinos as p_vecinos
import pantallas.reportes as p_reportes
import pantallas.usuarios as p_usuarios
import pantallas.zonas as p_zonas
import pantallas.configuracion as p_config
import pantallas.envio_recibos as p_envio
import pantallas.soporte as p_soporte

ctk.set_appearance_mode("Light")

# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================
ventana = ctk.CTk()
ventana.title(f"Sistema de Pagos de Agua — v{VERSION}")
ventana.geometry("1200x720")

# =============================================================================
# SESIÓN GLOBAL
# =============================================================================
sesion = {
    "usuario_id":     None,
    "usuario_rol":    None,
    "usuario_nombre": None,
}
frames_pantallas = {}
nav_botones      = {}
nav_activo       = [None]
banner_ref       = [None]

# =============================================================================
# FRAMES PRINCIPALES
# =============================================================================
frame_login     = ctk.CTkFrame(ventana, fg_color=COLOR_FONDO)
frame_dashboard = ctk.CTkFrame(ventana, fg_color=COLOR_FONDO)

# ── Sidebar ───────────────────────────────────────────────────────────────────
sidebar = ctk.CTkFrame(frame_dashboard, width=230, corner_radius=0,
                        fg_color=COLOR_SIDEBAR)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

# Logo
logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
logo_frame.pack(fill="x", padx=16, pady=(24, 16))
logo_icon = ctk.CTkFrame(logo_frame, width=38, height=38, corner_radius=10,
                           fg_color="#2A4A7A")
logo_icon.pack(anchor="w")
logo_icon.pack_propagate(False)
ctk.CTkLabel(logo_icon, text="💧", font=("Arial", 18)).place(
    relx=0.5, rely=0.5, anchor="center")
lbl_nombre_org = ctk.CTkLabel(logo_frame, text="Sistema de Agua",
                                font=("Arial", 13, "bold"),
                                text_color=COLOR_BLANCO)
lbl_nombre_org.pack(anchor="w", pady=(8, 0))
ctk.CTkLabel(logo_frame, text="Pagos de Agua",
             font=FONT_SMALL, text_color=COLOR_SIDEBAR_TEXT).pack(anchor="w")

ctk.CTkFrame(sidebar, height=1, fg_color="#243F6B").pack(fill="x", padx=16, pady=4)

nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
nav_frame.pack(fill="x", padx=10, pady=8)

nav_botones_frame = ctk.CTkFrame(nav_frame, fg_color="transparent")
nav_botones_frame.pack(fill="x")

# Footer sidebar
sidebar_footer = ctk.CTkFrame(sidebar, fg_color="transparent")
sidebar_footer.pack(side="bottom", fill="x", padx=10, pady=12)
ctk.CTkFrame(sidebar, height=1, fg_color="#243F6B").pack(
    side="bottom", fill="x", padx=16)

# Área de contenido
area_contenido = ctk.CTkFrame(frame_dashboard, corner_radius=0,
                               fg_color=COLOR_FONDO)
area_contenido.pack(side="right", fill="both", expand=True)

# Banner de suscripción — empacado primero (side="top") para que quede
# encima del contenido. Se oculta con pack_forget() cuando no hay aviso.
banner_container = ctk.CTkFrame(area_contenido, fg_color="transparent")
# (no se llama .pack() aquí; lo gestiona actualizar_banner en banner.py)

contenido_pantallas = ctk.CTkFrame(area_contenido, fg_color="transparent")
contenido_pantallas.pack(side="top", fill="both", expand=True)

# =============================================================================
# NAVEGACIÓN
# =============================================================================
def _desactivar_todos():
    for btn in nav_botones.values():
        try:
            btn.configure(fg_color="transparent",
                           text_color=COLOR_SIDEBAR_TEXT)
        except Exception:
            pass


def activar_nav(nombre):
    _desactivar_todos()
    nav_activo[0] = nombre
    if nombre in nav_botones:
        nav_botones[nombre].configure(
            fg_color=COLOR_SIDEBAR_ACTIVE, text_color=COLOR_BLANCO)


def mostrar_pantalla(nombre):
    for f in frames_pantallas.values():
        f.pack_forget()
    if nombre in frames_pantallas:
        frames_pantallas[nombre].pack(fill="both", expand=True)
    activar_nav(nombre)


def cargar_pantallas():
    for widget in contenido_pantallas.winfo_children():
        widget.destroy()
    frames_pantallas.clear()

    rol = sesion["usuario_rol"]

    frames_pantallas["cobros"] = p_cobros.crear_pantalla(
        contenido_pantallas,
        lambda: sesion["usuario_id"],
        lambda: sesion["usuario_rol"])

    if puede_gestionar_vecinos(rol):
        frames_pantallas["vecinos"] = p_vecinos.crear_pantalla(
            contenido_pantallas,
            lambda: sesion["usuario_rol"])

    frames_pantallas["reportes"] = p_reportes.crear_pantalla(
        contenido_pantallas,
        lambda: sesion["usuario_rol"],
        lambda: sesion["usuario_id"])

    frames_pantallas["envio_recibos"] = p_envio.crear_pantalla(
        contenido_pantallas,
        lambda: sesion["usuario_id"],
        lambda: sesion["usuario_nombre"])

    if puede_gestionar_zonas(rol):
        frames_pantallas["zonas"] = p_zonas.crear_pantalla(contenido_pantallas)

    if puede_gestionar_usuarios(rol):
        frames_pantallas["usuarios"] = p_usuarios.crear_pantalla(
            contenido_pantallas,
            lambda: sesion["usuario_id"],
            lambda: sesion["usuario_rol"])

    if puede_configurar_sistema(rol):
        frames_pantallas["configuracion"] = p_config.crear_pantalla(
            contenido_pantallas)

    if puede_ver_panel_soporte(rol):
        frames_pantallas["soporte"] = p_soporte.crear_pantalla(
            contenido_pantallas, ventana)


def construir_nav():
    for widget in nav_botones_frame.winfo_children():
        widget.destroy()
    nav_botones.clear()

    rol = sesion["usuario_rol"]

    def _nav_btn(nombre, icono, texto, seccion=None):
        if seccion:
            ctk.CTkFrame(nav_botones_frame, height=1,
                          fg_color="#243F6B").pack(fill="x", padx=4, pady=6)
            ctk.CTkLabel(nav_botones_frame, text=seccion,
                         font=("Arial", 10, "bold"),
                         text_color=COLOR_SIDEBAR_TEXT).pack(
                anchor="w", padx=10, pady=(0, 4))

        btn = ctk.CTkButton(
            nav_botones_frame,
            text=f"{icono}  {texto}",
            fg_color="transparent",
            hover_color=COLOR_SIDEBAR_HOVER,
            text_color=COLOR_SIDEBAR_TEXT,
            anchor="w", font=FONT_NAV, height=40, corner_radius=8,
            command=lambda n=nombre: mostrar_pantalla(n))
        btn.pack(fill="x", padx=0, pady=2)
        nav_botones[nombre] = btn

    # Principal — todos los roles
    _nav_btn("cobros",         "🏠", "Registro de Pagos")
    _nav_btn("envio_recibos",  "📨", "Envío de Recibos")
    _nav_btn("reportes",       "📊", "Reportes")

    # Gestión — Presidente y superiores
    if puede_gestionar_vecinos(rol):
        _nav_btn("vecinos", "👥", "Gestionar Vecinos",
                 seccion="GESTIÓN")

    # Administración
    if puede_gestionar_zonas(rol):
        seccion_admin = "ADMINISTRACIÓN" if puede_gestionar_vecinos(rol) else None
        _nav_btn("zonas", "🗺️", "Zonas Geográficas",
                 seccion=seccion_admin)

    if puede_gestionar_usuarios(rol):
        _nav_btn("usuarios",       "🔑", "Gestionar Usuarios")
        _nav_btn("configuracion",  "⚙️", "Configuración")

    # Panel soporte
    if puede_ver_panel_soporte(rol):
        _nav_btn("soporte", "🛠️", "Panel de Soporte",
                 seccion="SOPORTE TÉCNICO")


def construir_footer_sidebar():
    for widget in sidebar_footer.winfo_children():
        widget.destroy()

    iniciales = (sesion["usuario_nombre"][:2].upper()
                 if sesion["usuario_nombre"] else "??")

    avatar_frame = ctk.CTkFrame(sidebar_footer, fg_color="transparent")
    avatar_frame.pack(fill="x", padx=4, pady=(0, 8))

    avatar = ctk.CTkFrame(avatar_frame, width=32, height=32, corner_radius=16,
                           fg_color="#2D5289")
    avatar.pack(side="left")
    avatar.pack_propagate(False)
    ctk.CTkLabel(avatar, text=iniciales, font=("Arial", 11, "bold"),
                  text_color=COLOR_BLANCO).place(relx=0.5, rely=0.5,
                                                  anchor="center")

    info = ctk.CTkFrame(avatar_frame, fg_color="transparent")
    info.pack(side="left", padx=10)
    ctk.CTkLabel(info, text=sesion["usuario_nombre"] or "",
                 font=("Arial", 12, "bold"),
                 text_color=COLOR_BLANCO).pack(anchor="w")
    ctk.CTkLabel(info, text=sesion["usuario_rol"] or "",
                 font=FONT_SMALL,
                 text_color=COLOR_SIDEBAR_TEXT).pack(anchor="w")

    ctk.CTkButton(
        sidebar_footer, text="🚪  Cerrar sesión",
        fg_color="transparent", hover_color="#7B0000",
        text_color="#FCA5A5", anchor="w",
        font=FONT_NAV, height=36, corner_radius=8,
        command=cerrar_sesion
    ).pack(fill="x", padx=0)


def _actualizar_banner():
    actualizar_banner(
        banner_ref, banner_container, ventana,
        callback_renovar=lambda: mostrar_pantalla_renovacion(
            ventana, callback_renovado=_actualizar_banner))


# =============================================================================
# LOGIN
# =============================================================================
def verificar_login(event=None):
    usuario  = entrada_usuario.get().strip()
    password = entrada_password.get().strip()

    if not usuario or not password:
        lbl_error.configure(text="Complete usuario y contraseña.")
        return

    try:
        import sqlite3
        from herramientas.db import obtener_conexion
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute(
            "SELECT id, rol, usuario FROM usuarios "
            "WHERE usuario=? AND contrasena=?",
            (usuario, hashear_contrasena(password)))
        resultado = cur.fetchone()
    except Exception as e:
        messagebox.showerror("Error de Base de Datos",
                              f"No se pudo verificar el acceso:\n{e}")
        return
    finally:
        if 'con' in locals():
            con.close()

    if resultado:
        sesion["usuario_id"]     = resultado[0]
        sesion["usuario_rol"]    = resultado[1]
        sesion["usuario_nombre"] = resultado[2]

        lbl_error.configure(text="")
        cargar_pantallas()
        construir_nav()
        construir_footer_sidebar()

        # Actualizar nombre de organización en sidebar
        nombre_org = obtener_config("nombre_comunidad", "Sistema de Agua")
        lbl_nombre_org.configure(text=nombre_org)

        frame_login.pack_forget()
        frame_dashboard.pack(fill="both", expand=True)

        # Generar recibos del mes actual para todos los vecinos activos
        # (idempotente: no crea duplicados si ya existen)
        generar_recibos_mes_actual()

        # Banner de suscripción
        _actualizar_banner()

        mostrar_pantalla("cobros")
    else:
        lbl_error.configure(text="Usuario o contraseña incorrectos.")
        entrada_password.delete(0, "end")


def cerrar_sesion():
    # FIX: backup en thread background para no congelar la ventana 1-3 segundos
    threading.Thread(
        target=lambda: p_respaldos.crear_respaldo(silencioso=True),
        daemon=True
    ).start()

    sesion["usuario_id"]     = None
    sesion["usuario_rol"]    = None
    sesion["usuario_nombre"] = None

    entrada_usuario.delete(0, "end")
    entrada_password.delete(0, "end")
    lbl_error.configure(text="")
    frame_dashboard.pack_forget()
    frame_login.pack(fill="both", expand=True)

    # Limpiar banner
    if banner_ref[0]:
        try:
            banner_ref[0].destroy()
        except Exception:
            pass
        banner_ref[0] = None


# =============================================================================
# PANTALLA DE LOGIN
# =============================================================================
ctk.CTkLabel(frame_login, text="", fg_color=COLOR_FONDO).place(
    relx=0, rely=0, relwidth=1, relheight=1)

tarjeta = ctk.CTkFrame(frame_login, fg_color=COLOR_BLANCO, corner_radius=16,
                         width=420, height=500)
tarjeta.place(relx=0.5, rely=0.5, anchor="center")
tarjeta.pack_propagate(False)

logo_login = ctk.CTkFrame(tarjeta, width=56, height=56, corner_radius=14,
                            fg_color=COLOR_AZUL_MARINO)
logo_login.place(relx=0.5, y=44, anchor="center")
logo_login.pack_propagate(False)
ctk.CTkLabel(logo_login, text="💧", font=("Arial", 24)).place(
    relx=0.5, rely=0.5, anchor="center")

ctk.CTkLabel(tarjeta, text="Bienvenido",
             font=("Arial", 24, "bold"),
             text_color=COLOR_TEXTO).place(relx=0.5, y=120, anchor="center")

lbl_login_subtitulo = ctk.CTkLabel(
    tarjeta, text="Sistema de Pagos de Agua",
    font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
lbl_login_subtitulo.place(relx=0.5, y=148, anchor="center")

ctk.CTkFrame(tarjeta, height=1, fg_color=COLOR_BORDE,
             width=360).place(relx=0.5, y=170, anchor="center")

ctk.CTkLabel(tarjeta, text="Usuario", font=("Arial", 12, "bold"),
             text_color=COLOR_TEXTO).place(x=30, y=188)
entrada_usuario = ctk.CTkEntry(
    tarjeta, placeholder_text="Nombre de usuario",
    width=360, height=44, corner_radius=8,
    border_color=COLOR_BORDE, fg_color=COLOR_FONDO)
entrada_usuario.place(relx=0.5, y=228, anchor="center")

ctk.CTkLabel(tarjeta, text="Contraseña", font=("Arial", 12, "bold"),
             text_color=COLOR_TEXTO).place(x=30, y=260)
entrada_password = ctk.CTkEntry(
    tarjeta, placeholder_text="Contraseña",
    width=360, height=44, corner_radius=8,
    border_color=COLOR_BORDE, fg_color=COLOR_FONDO, show="*")
entrada_password.place(relx=0.5, y=300, anchor="center")
entrada_password.bind("<Return>", verificar_login)

lbl_error = ctk.CTkLabel(tarjeta, text="", font=FONT_SMALL,
                          text_color=COLOR_ROJO)
lbl_error.place(relx=0.5, y=332, anchor="center")

ctk.CTkButton(
    tarjeta, text="INGRESAR AL SISTEMA",
    height=48, width=360, corner_radius=10,
    fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
    font=FONT_BTN, text_color=COLOR_BLANCO,
    command=verificar_login
).place(relx=0.5, y=390, anchor="center")

ctk.CTkLabel(
    tarjeta, text=f"Sistema v{VERSION} · Uso exclusivo ADESCO",
    font=("Arial", 10), text_color=COLOR_TEXTO_MUTED
).place(relx=0.5, y=456, anchor="center")


# =============================================================================
# WIZARD DE PRIMERA VEZ
# =============================================================================
def mostrar_wizard():
    """Wizard paso a paso para la configuración inicial."""
    wizard = ctk.CTkToplevel(ventana)
    wizard.title("Configuración inicial del sistema")
    wizard.geometry("560x580")
    wizard.resizable(False, False)
    wizard.grab_set()
    wizard.focus_set()

    wizard.update_idletasks()
    x = (wizard.winfo_screenwidth() // 2) - 280
    y = (wizard.winfo_screenheight() // 2) - 290
    wizard.geometry(f"560x580+{x}+{y}")

    paso_actual = [1]
    zonas_ingresadas = []

    # Frame principal del wizard
    fondo = ctk.CTkFrame(wizard, fg_color=COLOR_FONDO)
    fondo.pack(fill="both", expand=True)

    # Indicador de pasos
    indicador = ctk.CTkFrame(fondo, fg_color=COLOR_BLANCO, height=56,
                              corner_radius=0)
    indicador.pack(fill="x")
    indicador.pack_propagate(False)

    pasos_lbl = []
    for i, txt in enumerate(["1. Comunidad", "2. Zonas", "3. Confirmar"], 1):
        lbl = ctk.CTkLabel(indicador, text=txt, font=("Arial", 12, "bold"),
                           text_color=COLOR_AZUL_MARINO if i == 1 else COLOR_TEXTO_MUTED)
        lbl.pack(side="left", padx=30, pady=16)
        pasos_lbl.append(lbl)

    def _actualizar_indicador(paso):
        for i, lbl in enumerate(pasos_lbl, 1):
            lbl.configure(
                text_color=COLOR_AZUL_MARINO if i == paso else COLOR_TEXTO_MUTED)

    # Contenedor de pasos
    contenedor = ctk.CTkFrame(fondo, fg_color="transparent")
    contenedor.pack(fill="both", expand=True, padx=32, pady=20)

    # ── PASO 1: nombre de la comunidad ────────────────────────────────────────
    frame_p1 = ctk.CTkFrame(contenedor, fg_color="transparent")

    ctk.CTkLabel(frame_p1, text="¿Cómo se llama su comunidad?",
                 font=("Arial", 18, "bold"), text_color=COLOR_TEXTO).pack(pady=(0, 8))
    ctk.CTkLabel(
        frame_p1,
        text="Este nombre aparecerá en todos los recibos y reportes.\n"
             "Puede cambiarlo después en Configuración.",
        font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
        justify="center").pack(pady=(0, 20))

    ctk.CTkLabel(frame_p1, text="Nombre de la comunidad", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w")
    e_nombre_comunidad = ctk.CTkEntry(
        frame_p1, placeholder_text="Ej: ADESCO El Gramal",
        height=44, corner_radius=8, fg_color=COLOR_BLANCO,
        font=("Arial", 14))
    e_nombre_comunidad.pack(fill="x", pady=(4, 16))

    ctk.CTkLabel(frame_p1, text="Municipio / Departamento (opcional)",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(anchor="w")
    e_municipio = ctk.CTkEntry(
        frame_p1, placeholder_text="Ej: Tonacatepeque, San Salvador",
        height=44, corner_radius=8, fg_color=COLOR_BLANCO)
    e_municipio.pack(fill="x", pady=(4, 0))

    # ── PASO 2: zonas geográficas ──────────────────────────────────────────────
    frame_p2 = ctk.CTkFrame(contenedor, fg_color="transparent")

    ctk.CTkLabel(frame_p2, text="¿Tiene zonas geográficas?",
                 font=("Arial", 18, "bold"), text_color=COLOR_TEXTO).pack(pady=(0, 8))
    ctk.CTkLabel(
        frame_p2,
        text="Agregue las zonas o caseríos de su comunidad.\n"
             "Puede omitir este paso y agregarlas después.",
        font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
        justify="center").pack(pady=(0, 12))

    # Lista de zonas ingresadas
    lista_zonas_frame = ctk.CTkScrollableFrame(
        frame_p2, fg_color=COLOR_BLANCO, corner_radius=8, height=140)
    lista_zonas_frame.pack(fill="x", pady=(0, 10))

    lbl_sin_zonas = ctk.CTkLabel(
        lista_zonas_frame,
        text="Aún no ha agregado zonas.",
        font=("Arial", 12, "italic"), text_color=COLOR_TEXTO_MUTED)
    lbl_sin_zonas.pack(pady=20)

    def _actualizar_lista_zonas():
        for w in lista_zonas_frame.winfo_children():
            w.destroy()
        if not zonas_ingresadas:
            ctk.CTkLabel(lista_zonas_frame,
                         text="Aún no ha agregado zonas.",
                         font=("Arial", 12, "italic"),
                         text_color=COLOR_TEXTO_MUTED).pack(pady=20)
        else:
            for i, z in enumerate(zonas_ingresadas):
                fz = ctk.CTkFrame(lista_zonas_frame, fg_color=COLOR_FONDO,
                                   corner_radius=6, height=36)
                fz.pack(fill="x", pady=2, padx=4)
                fz.pack_propagate(False)
                ctk.CTkLabel(fz, text=f"{i+1}. {z}", font=FONT_LABEL,
                             anchor="w").pack(side="left", padx=12, fill="y")
                ctk.CTkButton(
                    fz, text="✕", width=28, height=24, corner_radius=4,
                    fg_color="transparent", text_color=COLOR_ROJO,
                    font=("Arial", 12),
                    command=lambda idx=i: _eliminar_zona(idx)
                ).pack(side="right", padx=4)

    def _eliminar_zona(idx):
        zonas_ingresadas.pop(idx)
        _actualizar_lista_zonas()

    fila_agregar = ctk.CTkFrame(frame_p2, fg_color="transparent")
    fila_agregar.pack(fill="x")
    e_nueva_zona = ctk.CTkEntry(
        fila_agregar, placeholder_text="Ej: Caserío Vista Hermosa",
        height=40, corner_radius=8, fg_color=COLOR_BLANCO)
    e_nueva_zona.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _agregar_zona(event=None):
        nombre_zona = e_nueva_zona.get().strip()
        if nombre_zona and nombre_zona not in zonas_ingresadas:
            zonas_ingresadas.append(nombre_zona)
            e_nueva_zona.delete(0, "end")
            _actualizar_lista_zonas()

    e_nueva_zona.bind("<Return>", _agregar_zona)
    ctk.CTkButton(
        fila_agregar, text="Agregar", height=40, width=90,
        corner_radius=8, fg_color=COLOR_AZUL_MARINO,
        hover_color="#243F6B", font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=_agregar_zona
    ).pack(side="left")

    # ── PASO 3: confirmación ───────────────────────────────────────────────────
    frame_p3 = ctk.CTkFrame(contenedor, fg_color="transparent")

    ctk.CTkLabel(frame_p3, text="¡Todo listo!",
                 font=("Arial", 22, "bold"), text_color=COLOR_AZUL_MARINO).pack(pady=(0, 8))
    ctk.CTkLabel(
        frame_p3,
        text="Revise el resumen antes de comenzar.",
        font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED).pack(pady=(0, 16))

    resumen_card = ctk.CTkFrame(frame_p3, fg_color=COLOR_BLANCO, corner_radius=10)
    resumen_card.pack(fill="x")

    lbl_resumen_nombre = ctk.CTkLabel(resumen_card, text="",
                                       font=("Arial", 14, "bold"),
                                       text_color=COLOR_TEXTO)
    lbl_resumen_nombre.pack(anchor="w", padx=16, pady=(14, 2))

    lbl_resumen_municipio = ctk.CTkLabel(resumen_card, text="",
                                          font=FONT_SMALL,
                                          text_color=COLOR_TEXTO_MUTED)
    lbl_resumen_municipio.pack(anchor="w", padx=16, pady=(0, 8))

    ctk.CTkFrame(resumen_card, height=1, fg_color=COLOR_BORDE).pack(
        fill="x", padx=16)

    lbl_resumen_zonas = ctk.CTkLabel(resumen_card, text="",
                                      font=FONT_SMALL, text_color=COLOR_TEXTO,
                                      justify="left", wraplength=430)
    lbl_resumen_zonas.pack(anchor="w", padx=16, pady=10)

    def _actualizar_resumen():
        nombre = e_nombre_comunidad.get().strip() or "Sin nombre"
        municipio = e_municipio.get().strip()
        lbl_resumen_nombre.configure(text=f"💧  {nombre}")
        lbl_resumen_municipio.configure(
            text=municipio or "Sin municipio especificado")
        if zonas_ingresadas:
            txt = "Zonas: " + ", ".join(zonas_ingresadas)
        else:
            txt = "Sin zonas geográficas definidas aún."
        lbl_resumen_zonas.configure(text=txt)

    # ── Navegación entre pasos ─────────────────────────────────────────────────
    nav_btns = ctk.CTkFrame(fondo, fg_color=COLOR_BLANCO, height=64,
                             corner_radius=0)
    nav_btns.pack(fill="x", side="bottom")
    nav_btns.pack_propagate(False)
    ctk.CTkFrame(nav_btns, height=1, fg_color=COLOR_BORDE).pack(
        side="top", fill="x")

    btn_atras = ctk.CTkButton(
        nav_btns, text="← Atrás", height=40, width=120, corner_radius=8,
        fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
        border_width=1, border_color=COLOR_BORDE, font=FONT_BTN_SM)
    btn_atras.pack(side="left", padx=20, pady=12)

    btn_siguiente = ctk.CTkButton(
        nav_btns, text="Siguiente →", height=40, width=160,
        corner_radius=8, fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
        font=FONT_BTN_SM, text_color=COLOR_BLANCO)
    btn_siguiente.pack(side="right", padx=20, pady=12)

    frames_wizard = {1: frame_p1, 2: frame_p2, 3: frame_p3}

    def mostrar_paso(n):
        paso_actual[0] = n
        for f in frames_wizard.values():
            f.pack_forget()
        frames_wizard[n].pack(fill="both", expand=True)
        _actualizar_indicador(n)

        btn_atras.configure(state="normal" if n > 1 else "disabled")
        btn_siguiente.configure(
            text="Finalizar ✓" if n == 3 else "Siguiente →",
            fg_color=COLOR_VERDE_PAGO if n == 3 else COLOR_AZUL_MARINO)

        if n == 3:
            _actualizar_resumen()

    def siguiente():
        p = paso_actual[0]
        if p == 1:
            nombre = e_nombre_comunidad.get().strip()
            if not nombre:
                messagebox.showwarning("Atención",
                                       "El nombre de la comunidad es obligatorio.",
                                       parent=wizard)
                return
        if p < 3:
            mostrar_paso(p + 1)
        else:
            finalizar_wizard()

    def anterior():
        if paso_actual[0] > 1:
            mostrar_paso(paso_actual[0] - 1)

    btn_siguiente.configure(command=siguiente)
    btn_atras.configure(command=anterior)

    def finalizar_wizard():
        nombre    = e_nombre_comunidad.get().strip()
        municipio = e_municipio.get().strip()

        guardar_config("nombre_comunidad", nombre)
        if municipio:
            guardar_config("municipio", municipio)
        guardar_config("wizard_completado", "1")

        # Guardar zonas en BD
        zonas_error = False
        if zonas_ingresadas:
            try:
                from herramientas.db import obtener_conexion
                import herramientas.logger as _logger
                con = obtener_conexion()
                cur = con.cursor()
                for i, zona_nombre in enumerate(zonas_ingresadas):
                    cur.execute(
                        "INSERT OR IGNORE INTO zonas (nombre, orden, activa) "
                        "VALUES (?,?,1)",
                        (zona_nombre, i))
                con.commit()
                con.close()
            except Exception as e:
                zonas_error = True
                _logger.registrar("main.py", "finalizar_wizard", e)

        wizard.destroy()
        lbl_login_subtitulo.configure(text=nombre)
        lbl_nombre_org.configure(text=nombre)

        if zonas_error:
            messagebox.showwarning(
                "Aviso",
                f"¡Bienvenido a {nombre}!\\n\\n"
                "El sistema está listo, pero las zonas geográficas no pudieron "
                "guardarse.\\nPuede agregarlas después desde Gestión de Zonas.")
        else:
            messagebox.showinfo(
                "Configuración completada",
                f"¡Bienvenido a {nombre}!\\n\\n"
                "El sistema está listo para usar.\\n"
                "Ingrese con su usuario y contraseña.")

    mostrar_paso(1)


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
def iniciar():
    # Inicializar BD
    if not inicializar_base_datos():
        sys.exit(1)

    # Verificar licencia antes de cualquier otra cosa
    info_lic = estado_licencia()
    if info_lic["estado"] in (ESTADO_NO_ACTIVADA,):
        # Primera vez — mostrar activación antes del wizard
        mostrar_pantalla_activacion(
            ventana,
            callback_exito=lambda: _post_activacion()
        )
    else:
        _post_activacion()


def _post_activacion():
    """Continúa el flujo después de verificar/activar la licencia."""
    # Verificar si es primera vez (wizard)
    wizard_completado = obtener_config("wizard_completado", "0")
    if wizard_completado != "1":
        ventana.after(300, mostrar_wizard)

    # Actualizar subtítulo del login
    nombre_org = obtener_config("nombre_comunidad", "Sistema de Pagos de Agua")
    lbl_login_subtitulo.configure(text=nombre_org)

    frame_login.pack(fill="both", expand=True)


# Configuración de ventana
frame_login.pack(fill="both", expand=True)
ventana.after(100, lambda: ventana.state('zoomed'))
ventana.after(150, lambda: (
    ventana.iconbitmap(os.path.join(
        os.path.dirname(os.path.abspath(sys.argv[0])), "icono.ico"))
    if os.path.exists(os.path.join(
        os.path.dirname(os.path.abspath(sys.argv[0])), "icono.ico"))
    else None
))
ventana.after(200, iniciar)
try:
    ventana.mainloop()
except KeyboardInterrupt:
    pass