import customtkinter as ctk
import sqlite3
import datetime
import platform
from tkinter import messagebox
import herramientas.logger as logger
import herramientas.respaldos as respaldos
from herramientas.db import obtener_conexion, obtener_config
from herramientas.seguridad import obtener_hardware_id
from licencia.validador import estado_licencia
from licencia.activacion import mostrar_pantalla_renovacion
from pantallas.componentes import topbar
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_NARANJA,
    COLOR_TEXTO, COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO,
    COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
    COLOR_BADGE_ROJO_BG, COLOR_BADGE_ROJO_TEXT,
    COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_SMALL,
    FONT_LABEL, FONT_MONO, VERSION
)


def crear_pantalla(parent_frame, ventana_principal):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")

    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Panel de Soporte Técnico",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    ctk.CTkLabel(izq, text="Acceso exclusivo — Rol Soporte",
                 font=FONT_SMALL, text_color=COLOR_ROJO).pack(anchor="w")

    scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=24, pady=16)

    col1 = ctk.CTkFrame(scroll, fg_color=COLOR_BLANCO, corner_radius=10)
    col1.pack(side="left", fill="both", expand=True, padx=(0, 8), anchor="n")
    col2 = ctk.CTkFrame(scroll, fg_color=COLOR_BLANCO, corner_radius=10)
    col2.pack(side="left", fill="both", expand=True, padx=(0, 8), anchor="n")
    col3 = ctk.CTkFrame(scroll, fg_color=COLOR_BLANCO, corner_radius=10)
    col3.pack(side="left", fill="both", expand=True, anchor="n")

    def _seccion(parent, titulo, color=COLOR_AZUL_MARINO):
        ctk.CTkLabel(parent, text=titulo, font=("Arial", 12, "bold"),
                     text_color=color).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkFrame(parent, height=1, fg_color=COLOR_BORDE).pack(fill="x", padx=16)

    def _fila_info(parent, label, valor, color_val=None):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(f, text=label + ":", font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED, width=140, anchor="w").pack(side="left")
        ctk.CTkLabel(f, text=str(valor), font=FONT_SMALL,
                     text_color=color_val or COLOR_TEXTO, anchor="w").pack(side="left")

    # ── COL 1: Sistema + Licencia ─────────────────────────────────────────────
    _seccion(col1, "Información del sistema")
    _fila_info(col1, "Versión", VERSION)
    _fila_info(col1, "Python", platform.python_version())
    _fila_info(col1, "Sistema operativo", platform.system() + " " + platform.release())
    _fila_info(col1, "Máquina", platform.node())
    hw_id = obtener_hardware_id()
    _fila_info(col1, "Hardware ID", hw_id[:20] + "...")

    ctk.CTkButton(
        col1, text="Copiar Hardware ID completo", height=32, corner_radius=6,
        fg_color="transparent", text_color=COLOR_AZUL_MARINO,
        border_width=1, border_color=COLOR_BORDE, font=FONT_SMALL,
        command=lambda: _copiar_al_portapapeles(hw_id)
    ).pack(fill="x", padx=16, pady=(8, 0))

    _seccion(col1, "Estado de licencia")

    info_lic = estado_licencia()
    _colores_estado = {
        "activa": COLOR_VERDE_PAGO, "por_vencer": COLOR_AMARILLO,
        "restringida": COLOR_NARANJA, "bloqueada": COLOR_ROJO,
        "no_activada": COLOR_ROJO,
    }
    _lic_labels = {}

    def _fila_info_ref(parent, label, valor, color_val=None, ref_key=None):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(f, text=label + ":", font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED, width=140, anchor="w").pack(side="left")
        lbl = ctk.CTkLabel(f, text=str(valor), font=FONT_SMALL,
                           text_color=color_val or COLOR_TEXTO, anchor="w")
        lbl.pack(side="left")
        if ref_key:
            _lic_labels[ref_key] = lbl

    _fila_info_ref(col1, "Estado",
                   info_lic["estado"].replace("_", " ").title(),
                   color_val=_colores_estado.get(info_lic["estado"], COLOR_TEXTO),
                   ref_key="estado")
    _fila_info_ref(col1, "Expira", info_lic["fecha_exp"] or "—", ref_key="expira")
    _fila_info_ref(col1, "Días restantes", str(info_lic["dias_restantes"]), ref_key="dias")
    _fila_info_ref(col1, "Modo", info_lic.get("modo", "—"), ref_key="modo")

    ctk.CTkButton(
        col1, text="Renovar / Activar licencia", height=36, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
        font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=lambda: mostrar_pantalla_renovacion(
            ventana_principal, callback_renovado=_refrescar)
    ).pack(fill="x", padx=16, pady=(12, 4))

    _seccion(col1, "Diagnóstico de base de datos")
    lbl_diag = ctk.CTkLabel(col1, text="Presione para ejecutar diagnóstico.",
                             font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                             wraplength=250, justify="left")
    lbl_diag.pack(anchor="w", padx=16, pady=(8, 4))

    def ejecutar_diagnostico():
        resultados = []
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("PRAGMA integrity_check")
            resultados.append(f"Integridad: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM vecinos WHERE activo=1")
            resultados.append(f"Vecinos activos: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM recibos WHERE estado_pago='Pendiente'")
            resultados.append(f"Recibos pendientes: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM transacciones")
            resultados.append(f"Transacciones totales: {cur.fetchone()[0]}")
            cur.execute("SELECT COALESCE(SUM(monto_cobrado),0) FROM transacciones")
            resultados.append(f"Total recaudado: ${cur.fetchone()[0]:.2f}")
            cur.execute("SELECT COUNT(*) FROM usuarios")
            resultados.append(f"Usuarios: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM zonas WHERE activa=1")
            resultados.append(f"Zonas activas: {cur.fetchone()[0]}")
            lbl_diag.configure(text="\n".join(resultados), text_color=COLOR_TEXTO)
        except Exception as e:
            lbl_diag.configure(text=f"Error: {e}", text_color=COLOR_ROJO)
        finally:
            if 'con' in locals():
                con.close()

    ctk.CTkButton(
        col1, text="Ejecutar diagnóstico", height=36, corner_radius=8,
        fg_color=COLOR_VERDE_PAGO, hover_color="#276749",
        font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=ejecutar_diagnostico
    ).pack(fill="x", padx=16, pady=(0, 16))

    # ── COL 2: Log de errores ─────────────────────────────────────────────────
    _seccion(col2, "Log de errores del sistema", color=COLOR_ROJO)
    txt_log = ctk.CTkTextbox(col2, height=400, font=FONT_MONO,
                              fg_color=COLOR_FONDO, corner_radius=6, wrap="word")
    txt_log.pack(fill="x", padx=16, pady=(8, 4))

    def cargar_log():
        contenido = logger.leer_log(150)
        txt_log.configure(state="normal")
        txt_log.delete("1.0", "end")
        txt_log.insert("1.0", contenido)
        txt_log.configure(state="disabled")
        txt_log.see("end")

    fila_log = ctk.CTkFrame(col2, fg_color="transparent")
    fila_log.pack(fill="x", padx=16, pady=(0, 16))
    ctk.CTkButton(fila_log, text="Actualizar", height=32, corner_radius=6,
                  fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                  font=FONT_SMALL, text_color=COLOR_BLANCO,
                  command=cargar_log).pack(side="left", padx=(0, 8))
    ctk.CTkButton(fila_log, text="Limpiar log", height=32, corner_radius=6,
                  fg_color="transparent", text_color=COLOR_ROJO,
                  border_width=1, border_color=COLOR_ROJO, font=FONT_SMALL,
                  command=lambda: (logger.limpiar_log(), cargar_log())
                  if messagebox.askyesno("Confirmar", "¿Limpiar el log?") else None
                  ).pack(side="left")
    cargar_log()

    # ── COL 3: Mantenimiento + Token + Soporte ────────────────────────────────
    _seccion(col3, "Mantenimiento")

    def _darken(hex_color):
        try:
            r = max(0, int(hex_color[1:3], 16) - 20)
            g = max(0, int(hex_color[3:5], 16) - 20)
            b = max(0, int(hex_color[5:7], 16) - 20)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _btn_accion(parent, texto, cmd, color=COLOR_AZUL_MARINO, desc=""):
        if desc:
            ctk.CTkLabel(parent, text=desc, font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, wraplength=220,
                         justify="left").pack(anchor="w", padx=16, pady=(10, 2))
        ctk.CTkButton(parent, text=texto, height=38, corner_radius=8,
                      fg_color=color, hover_color=_darken(color),
                      font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                      command=cmd).pack(fill="x", padx=16, pady=(0, 4))

    _btn_accion(col3, "Forzar respaldo ahora",
                lambda: respaldos.crear_respaldo(silencioso=False),
                COLOR_VERDE_PAGO, "Crea un respaldo manual de la base de datos.")
    _btn_accion(col3, "Restaurar desde respaldo",
                lambda: respaldos.restaurar_desde_respaldo(),
                COLOR_AMARILLO, "Restaura la BD desde un archivo .db.")
    _btn_accion(col3, "Abrir carpeta de respaldos",
                lambda: respaldos.abrir_carpeta_respaldos(),
                COLOR_AZUL_MARINO, "Abre el explorador en la carpeta de respaldos.")

    # ── Cuenta Soporte ────────────────────────────────────────────────────────
    _seccion(col3, "Cuenta Soporte")
    info_frame = ctk.CTkFrame(col3, fg_color="#EBF8FF", corner_radius=8)
    info_frame.pack(fill="x", padx=16, pady=(10, 4))
    ctk.CTkLabel(info_frame, text="Contraseña gestionada automáticamente",
                 font=("Arial", 11, "bold"), text_color="#2C5282"
                 ).pack(anchor="w", padx=12, pady=(10, 2))
    ctk.CTkLabel(info_frame,
                 text="Derivada del hardware de esta PC.\nComparta el Hardware ID con\nel desarrollador para obtenerla.",
                 font=FONT_SMALL, text_color="#2C5282", justify="left"
                 ).pack(anchor="w", padx=12, pady=(0, 10))

    # ── Token GitHub ──────────────────────────────────────────────────────────
    _seccion(col3, "Verificación de licencia online")

    from herramientas.licencia_online import (
        token_configurado, guardar_token_github, limpiar_cache_sesion
    )

    _tok = {"ok": token_configurado()}
    lbl_tok_estado = ctk.CTkLabel(
        col3,
        text="✓ Token configurado" if _tok["ok"] else "✗ Sin token — solo verificación local",
        font=FONT_SMALL,
        text_color=COLOR_VERDE_PAGO if _tok["ok"] else COLOR_AMARILLO,
        wraplength=240, justify="left"
    )
    lbl_tok_estado.pack(anchor="w", padx=16, pady=(8, 4))

    ctk.CTkLabel(col3, text="Token GitHub (ghp_...):",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(
        anchor="w", padx=16, pady=(4, 2))
    entry_token = ctk.CTkEntry(col3, placeholder_text="ghp_xxxxxxxxxxxxxxxxxxxx",
                                height=36, corner_radius=8,
                                fg_color=COLOR_FONDO, show="*")
    entry_token.pack(fill="x", padx=16, pady=(0, 4))

    lbl_tok_msg = ctk.CTkLabel(col3, text="", font=FONT_SMALL,
                                text_color=COLOR_VERDE_PAGO, wraplength=240)
    lbl_tok_msg.pack(anchor="w", padx=16)

    def guardar_token_accion():
        token = entry_token.get().strip()
        if not token:
            lbl_tok_msg.configure(text="Ingrese el token.", text_color=COLOR_ROJO)
            return
        lbl_tok_msg.configure(text="Guardando...", text_color=COLOR_TEXTO_MUTED)
        ok = guardar_token_github(token)
        if ok:
            entry_token.delete(0, "end")
            limpiar_cache_sesion()
            _tok["ok"] = True
            lbl_tok_estado.configure(text="✓ Token configurado",
                                      text_color=COLOR_VERDE_PAGO)
            lbl_tok_msg.configure(text="✓ Token guardado.", text_color=COLOR_VERDE_PAGO)
        else:
            lbl_tok_msg.configure(text="Error al guardar.", text_color=COLOR_ROJO)

    ctk.CTkButton(col3, text="Guardar token", height=34, corner_radius=8,
                  fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                  font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                  command=guardar_token_accion).pack(fill="x", padx=16, pady=(4, 4))

    ctk.CTkLabel(col3,
                 text="Token se guarda cifrado en la BD.\nGeneralo en GitHub → Settings →\nDeveloper settings → scope: repo",
                 font=("Arial", 10, "italic"), text_color=COLOR_TEXTO_MUTED,
                 justify="left").pack(anchor="w", padx=16, pady=(0, 16))

    # ── Funciones internas ────────────────────────────────────────────────────
    def _copiar_al_portapapeles(texto):
        ventana_principal.clipboard_clear()
        ventana_principal.clipboard_append(texto)
        messagebox.showinfo("Copiado", "Hardware ID copiado al portapapeles.")

    def _refrescar():
        nueva = estado_licencia()
        nuevo_color = _colores_estado.get(nueva["estado"], COLOR_TEXTO)
        if "estado" in _lic_labels:
            _lic_labels["estado"].configure(
                text=nueva["estado"].replace("_", " ").title(),
                text_color=nuevo_color)
        if "expira" in _lic_labels:
            _lic_labels["expira"].configure(text=nueva["fecha_exp"] or "—")
        if "dias" in _lic_labels:
            _lic_labels["dias"].configure(text=str(nueva["dias_restantes"]))
        if "modo" in _lic_labels:
            _lic_labels["modo"].configure(text=nueva.get("modo", "—"))

    return frame