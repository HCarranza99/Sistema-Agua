import customtkinter as ctk
import sqlite3
from tkinter import messagebox
import herramientas.logger as logger
from herramientas.db import obtener_conexion
from herramientas.seguridad import hashear_contrasena
from herramientas.permisos import puede_modificar_usuario, ROL_SOPORTE
from pantallas.componentes import (
    topbar, badge, encabezado_tabla, mensaje_vacio
)
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_ROJO, COLOR_AMARILLO, COLOR_TEXTO, COLOR_TEXTO_MUTED,
    COLOR_GRIS_CLARO, COLOR_VERDE_PAGO,
    COLOR_BADGE_AZUL_BG, COLOR_BADGE_AZUL_TEXT,
    COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT,
    COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
    COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT,
    COLOR_BADGE_PURPLE_BG, COLOR_BADGE_PURPLE_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_BODY,
    FONT_SMALL, FONT_LABEL, ROLES_DISPONIBLES, ROL_CAJERO
)

_COLORES_ROL = {
    "Soporte":        (COLOR_BADGE_PURPLE_BG, COLOR_BADGE_PURPLE_TEXT),
    "Administrador":  (COLOR_BADGE_AZUL_BG,   COLOR_BADGE_AZUL_TEXT),
    "Presidente":     (COLOR_BADGE_VERDE_BG,  COLOR_BADGE_VERDE_TEXT),
    "Cajero":         (COLOR_BADGE_GRIS_BG,   COLOR_BADGE_GRIS_TEXT),
}


def crear_pantalla(parent_frame, get_usuario_actual_id, get_usuario_actual_rol):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    estado_ed = {"usuario_id": None}

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Gestión de Accesos", font=FONT_TOPBAR,
                 text_color=COLOR_TEXTO).pack(anchor="w")
    ctk.CTkLabel(izq, text="Administración de usuarios del sistema",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED).pack(anchor="w")
    der = ctk.CTkFrame(bar, fg_color="transparent")
    der.pack(side="right", padx=20)
    ctk.CTkButton(
        der, text="+ Nuevo Usuario", height=36, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=lambda: abrir_formulario(None)
    ).pack(side="right")

    # ── Cuerpo ─────────────────────────────────────────────────────────────────
    cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
    cuerpo.pack(fill="both", expand=True, padx=24, pady=16)

    tabla_card = ctk.CTkFrame(cuerpo, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(side="left", fill="both", expand=True)

    encabezado_tabla(tabla_card, [("Usuario", 200), ("Rol", 160), ("Teléfono", 130), ("Email", 180)])

    lista_scroll = ctk.CTkScrollableFrame(tabla_card, fg_color=COLOR_FONDO,
                                           corner_radius=0)
    lista_scroll.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Modal formulario ───────────────────────────────────────────────────────
    modal_visible = [False]
    modal_frame   = ctk.CTkFrame(cuerpo, fg_color=COLOR_BLANCO,
                                  corner_radius=12, width=380)
    modal_frame.pack_propagate(False)

    def abrir_formulario(datos):
        limpiar_form()
        estado_ed["usuario_id"] = datos["id"] if datos else None
        rol_actual_editor = get_usuario_actual_rol()
        roles_visibles = _roles_asignables(rol_actual_editor)
        seg_rol.configure(values=roles_visibles)
        if datos:
            entry_usuario.insert(0, datos["usuario"])
            entry_tel.insert(0, datos.get("telefono") or "")
            entry_email.insert(0, datos.get("email") or "")
            if datos["rol"] in roles_visibles:
                seg_rol.set(datos["rol"])
            else:
                seg_rol.set(roles_visibles[0])
            lbl_titulo.configure(text="Editando Usuario")
        else:
            seg_rol.set(ROL_CAJERO if ROL_CAJERO in roles_visibles else roles_visibles[0])
            lbl_titulo.configure(text="Nuevo Usuario")

        if not modal_visible[0]:
            modal_frame.pack(side="right", fill="y", padx=(12, 0))
            modal_visible[0] = True

    def cerrar_formulario():
        modal_frame.pack_forget()
        modal_visible[0] = False
        limpiar_form()

    def limpiar_form():
        estado_ed["usuario_id"] = None
        entry_usuario.delete(0, "end")
        entry_password.delete(0, "end")
        entry_tel.delete(0, "end")
        entry_email.delete(0, "end")
        seg_rol.set(ROL_CAJERO)

    def _roles_asignables(rol_editor: str) -> list:
        """Retorna los roles que puede asignar el editor."""
        from config import JERARQUIA_ROLES
        return [r for r in ROLES_DISPONIBLES
                if JERARQUIA_ROLES.get(r, 0) < JERARQUIA_ROLES.get(rol_editor, 0)
                or r == rol_editor]

    modal_inner = ctk.CTkScrollableFrame(modal_frame, fg_color="transparent")
    modal_inner.pack(fill="both", expand=True, padx=4, pady=4)

    modal_header = ctk.CTkFrame(modal_inner, fg_color="transparent")
    modal_header.pack(fill="x", padx=12, pady=(12, 4))
    lbl_titulo = ctk.CTkLabel(modal_header, text="Nuevo Usuario",
                               font=("Arial", 15, "bold"), text_color=COLOR_TEXTO)
    lbl_titulo.pack(side="left")
    ctk.CTkButton(
        modal_header, text="✕", width=28, height=28, corner_radius=6,
        fg_color=COLOR_GRIS_CLARO, text_color=COLOR_TEXTO_MUTED,
        font=("Arial", 13), command=cerrar_formulario
    ).pack(side="right")

    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(
        fill="x", padx=12, pady=6)

    ctk.CTkLabel(modal_inner, text="Nombre de Usuario", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    entry_usuario = ctk.CTkEntry(modal_inner, placeholder_text="Nombre de usuario",
                                  height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_usuario.pack(fill="x", padx=16, pady=(0, 8))

    ctk.CTkLabel(modal_inner, text="Contraseña (mín. 8 caracteres)",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(
        anchor="w", padx=16, pady=(4, 2))
    entry_password = ctk.CTkEntry(
        modal_inner, placeholder_text="Contraseña",
        height=40, corner_radius=8, fg_color=COLOR_FONDO, show="*")
    entry_password.pack(fill="x", padx=16, pady=(0, 2))
    ctk.CTkLabel(modal_inner,
                 text="Al editar, dejar vacía para no cambiarla.",
                 font=("Arial", 10, "italic"),
                 text_color=COLOR_TEXTO_MUTED).pack(anchor="w", padx=16, pady=(0, 8))

    ctk.CTkLabel(modal_inner, text="Teléfono (opcional)",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(
        anchor="w", padx=16, pady=(4, 2))
    entry_tel = ctk.CTkEntry(modal_inner, placeholder_text="0000-0000",
                              height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_tel.pack(fill="x", padx=16, pady=(0, 8))

    ctk.CTkLabel(modal_inner, text="Correo Electrónico (opcional)",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(
        anchor="w", padx=16, pady=(4, 2))
    entry_email = ctk.CTkEntry(modal_inner, placeholder_text="correo@ejemplo.com",
                                height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_email.pack(fill="x", padx=16, pady=(0, 8))

    ctk.CTkLabel(modal_inner, text="Nivel de Privilegios",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(
        anchor="w", padx=16, pady=(4, 6))
    # FIX: usar _roles_asignables() también al crear (no solo al editar)
    # para que el SegmentedButton muestre solo los roles permitidos al editor actual
    _roles_iniciales = _roles_asignables(get_usuario_actual_rol())
    seg_rol = ctk.CTkSegmentedButton(
        modal_inner, values=_roles_iniciales,
        selected_color=COLOR_AZUL_MARINO)
    seg_rol.pack(fill="x", padx=16, pady=(0, 8))
    seg_rol.set(ROL_CAJERO if ROL_CAJERO in _roles_iniciales else _roles_iniciales[0])

    ctk.CTkLabel(
        modal_inner,
        text="• Cajero: registrar cobros y enviar recibos.\n"
             "• Presidente: acceso completo excepto configuración.\n"
             "• Administrador: acceso completo al sistema.",
        font=("Arial", 11), text_color=COLOR_TEXTO_MUTED,
        justify="left"
    ).pack(anchor="w", padx=16, pady=(0, 12))

    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(
        fill="x", padx=12, pady=6)

    ctk.CTkButton(
        modal_inner, text="GUARDAR", height=42, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, font=FONT_BTN,
        command=lambda: guardar_usuario()
    ).pack(fill="x", padx=16, pady=(0, 6))

    ctk.CTkButton(
        modal_inner, text="Cancelar", height=36, corner_radius=8,
        fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
        border_width=1, border_color=COLOR_BORDE, font=FONT_BTN_SM,
        command=cerrar_formulario
    ).pack(fill="x", padx=16, pady=(0, 12))

    # ── Lógica ─────────────────────────────────────────────────────────────────
    def guardar_usuario():
        usuario  = entry_usuario.get().strip()
        password = entry_password.get().strip()
        tel      = entry_tel.get().strip()
        email    = entry_email.get().strip()
        rol      = seg_rol.get()

        if not usuario:
            messagebox.showwarning("Atención", "El nombre de usuario es obligatorio.")
            return
        if len(usuario) < 3:
            messagebox.showwarning("Atención",
                                   "El nombre debe tener al menos 3 caracteres.")
            return

        try:
            con = obtener_conexion()
            cur = con.cursor()

            if estado_ed["usuario_id"]:
                if password:
                    if len(password) < 8:
                        messagebox.showwarning(
                            "Contraseña débil",
                            "La contraseña debe tener al menos 8 caracteres.")
                        return
                    cur.execute(
                        "UPDATE usuarios SET usuario=?, contrasena=?, rol=?, "
                        "telefono=?, email=? WHERE id=?",
                        (usuario, hashear_contrasena(password), rol,
                         tel or None, email or None, estado_ed["usuario_id"]))
                else:
                    cur.execute(
                        "UPDATE usuarios SET usuario=?, rol=?, "
                        "telefono=?, email=? WHERE id=?",
                        (usuario, rol, tel or None, email or None,
                         estado_ed["usuario_id"]))
                msg = "Usuario actualizado correctamente."
            else:
                if not password:
                    messagebox.showwarning("Atención",
                                           "La contraseña es obligatoria.")
                    return
                if len(password) < 8:
                    messagebox.showwarning(
                        "Contraseña débil",
                        "La contraseña debe tener al menos 8 caracteres.")
                    return
                cur.execute("SELECT id FROM usuarios WHERE usuario=?", (usuario,))
                if cur.fetchone():
                    messagebox.showerror("Duplicado",
                                          "Este nombre de usuario ya está en uso.")
                    return
                cur.execute(
                    "INSERT INTO usuarios (usuario, contrasena, rol, telefono, email) "
                    "VALUES (?,?,?,?,?)",
                    (usuario, hashear_contrasena(password), rol,
                     tel or None, email or None))
                msg = "Usuario creado correctamente."

            con.commit()
            messagebox.showinfo("Éxito", msg)
            cerrar_formulario()
            actualizar_tabla()

        except sqlite3.IntegrityError as e:
            messagebox.showerror("Error", "Este nombre de usuario ya está en uso.")
            logger.registrar("usuarios.py", "guardar_usuario", e)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            logger.registrar("usuarios.py", "guardar_usuario", e)
        finally:
            if 'con' in locals():
                con.close()

    def eliminar_usuario(u_id, u_nombre, u_rol):
        mi_id  = get_usuario_actual_id()
        mi_rol = get_usuario_actual_rol()

        if u_id == mi_id:
            messagebox.showerror("Acción Denegada",
                                  "No puedes eliminar tu propio usuario.")
            return
        if not puede_modificar_usuario(mi_rol, u_rol):
            messagebox.showerror("Acceso Denegado",
                                  "No tienes permiso para eliminar este usuario.")
            return
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar al usuario '{u_nombre}'?\n\nEsta acción no se puede deshacer."
        ):
            return
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("DELETE FROM usuarios WHERE id=?", (u_id,))
            con.commit()
            messagebox.showinfo("Éxito", "Usuario eliminado del sistema.")
            actualizar_tabla()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")
            logger.registrar("usuarios.py", "eliminar_usuario", e)
        finally:
            if 'con' in locals():
                con.close()

    def actualizar_tabla():
        for w in lista_scroll.winfo_children():
            w.destroy()
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute(
                "SELECT id, usuario, rol, telefono, email FROM usuarios "
                "ORDER BY rol DESC, usuario")
            filas = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo cargar la lista:\n{e}")
            logger.registrar("usuarios.py", "actualizar_tabla", e)
            return
        finally:
            if 'con' in locals():
                con.close()

        if not filas:
            mensaje_vacio(lista_scroll, "No hay usuarios registrados.")
            return

        mi_rol = get_usuario_actual_rol()
        mi_id  = get_usuario_actual_id()

        for u_id, usuario, rol, tel, email in filas:
            fila = ctk.CTkFrame(lista_scroll, fg_color=COLOR_BLANCO,
                                 corner_radius=6, height=52)
            fila.pack(fill="x", pady=2, padx=4)
            fila.pack_propagate(False)

            # Avatar
            iniciales = usuario[:2].upper()
            bg_avatar, _ = _COLORES_ROL.get(rol, (COLOR_GRIS_CLARO, COLOR_TEXTO_MUTED))
            avatar = ctk.CTkFrame(fila, width=32, height=32, corner_radius=16,
                                   fg_color=bg_avatar)
            avatar.pack(side="left", padx=16)
            avatar.pack_propagate(False)
            ctk.CTkLabel(avatar, text=iniciales, font=("Arial", 11, "bold"),
                          text_color=COLOR_AZUL_MARINO).place(
                relx=0.5, rely=0.5, anchor="center")

            ctk.CTkLabel(fila, text=usuario, font=("Arial", 13, "bold"),
                         width=170, anchor="w").pack(side="left", padx=4)

            bg_r, fg_r = _COLORES_ROL.get(rol, (COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT))
            badge(fila, rol, bg_r, fg_r, width=120).pack(side="left", padx=4)

            ctk.CTkLabel(fila, text=tel or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=130,
                         anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila, text=email or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=180,
                         anchor="w").pack(side="left", padx=4)

            # Botones solo si tengo permiso
            if puede_modificar_usuario(mi_rol, rol) or u_id == mi_id:
                if u_id != mi_id and puede_modificar_usuario(mi_rol, rol):
                    ctk.CTkButton(
                        fila, text="Eliminar", width=80, height=30,
                        corner_radius=6, fg_color=COLOR_ROJO,
                        hover_color="#9B2C2C", text_color=COLOR_BLANCO,
                        font=FONT_SMALL,
                        command=lambda id=u_id, n=usuario, r=rol:
                            eliminar_usuario(id, n, r)
                    ).pack(side="right", padx=12)

                ctk.CTkButton(
                    fila, text="Editar", width=70, height=30,
                    corner_radius=6, fg_color=COLOR_AMARILLO,
                    hover_color="#B7791F", text_color=COLOR_BLANCO,
                    font=FONT_SMALL,
                    command=lambda d={
                        "id": u_id, "usuario": usuario, "rol": rol,
                        "telefono": tel, "email": email
                    }: abrir_formulario(d)
                ).pack(side="right", padx=4)

    actualizar_tabla()
    return frame
