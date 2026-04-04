import customtkinter as ctk
import sqlite3
from tkinter import messagebox
import herramientas.logger as logger
from herramientas.db import obtener_conexion
from pantallas.componentes import (
    topbar, badge, encabezado_tabla, mensaje_vacio,
    aplicar_validacion_entero
)
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_TEXTO,
    COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO,
    COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
    COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_SMALL, FONT_LABEL
)


def crear_pantalla(parent_frame):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    estado_ed = {"zona_id": None}

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Gestión de Zonas Geográficas",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    lbl_sub = ctk.CTkLabel(izq, text="Cargando...",
                            font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
    lbl_sub.pack(anchor="w")
    der = ctk.CTkFrame(bar, fg_color="transparent")
    der.pack(side="right", padx=20)
    ctk.CTkButton(
        der, text="+ Nueva Zona", height=36, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=lambda: abrir_formulario(None)
    ).pack(side="right")

    # ── Cuerpo ─────────────────────────────────────────────────────────────────
    cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
    cuerpo.pack(fill="both", expand=True, padx=24, pady=16)

    fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
    fila.pack(fill="both", expand=True)

    tabla_card = ctk.CTkFrame(fila, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(side="left", fill="both", expand=True)

    encabezado_tabla(tabla_card, [
        ("Orden", 60), ("Nombre de la zona", 220),
        ("Descripción", 240), ("Vecinos", 80), ("Estado", 90)
    ])

    lista_scroll = ctk.CTkScrollableFrame(tabla_card, fg_color=COLOR_FONDO,
                                           corner_radius=0)
    lista_scroll.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Modal ──────────────────────────────────────────────────────────────────
    modal_visible = [False]
    modal_frame   = ctk.CTkFrame(fila, fg_color=COLOR_BLANCO,
                                  corner_radius=12, width=340)
    modal_frame.pack_propagate(False)

    def abrir_formulario(zona_data):
        estado_ed["zona_id"] = zona_data["id"] if zona_data else None
        limpiar_form()
        if zona_data:
            entry_nombre.insert(0, zona_data["nombre"])
            entry_desc.insert(0, zona_data.get("descripcion") or "")
            entry_orden.delete(0, "end")
            entry_orden.insert(0, str(zona_data.get("orden", 0)))
            activa = zona_data.get("activa", 1)
            toggle_activa.select() if activa else toggle_activa.deselect()
            lbl_titulo.configure(text="Editando Zona")
        else:
            lbl_titulo.configure(text="Nueva Zona")

        if not modal_visible[0]:
            modal_frame.pack(side="right", fill="y", padx=(12, 0))
            modal_visible[0] = True

    def cerrar_formulario():
        modal_frame.pack_forget()
        modal_visible[0] = False
        estado_ed["zona_id"] = None
        limpiar_form()

    def limpiar_form():
        entry_nombre.delete(0, "end")
        entry_desc.delete(0, "end")
        entry_orden.delete(0, "end")
        entry_orden.insert(0, "0")
        toggle_activa.select()

    modal_inner = ctk.CTkScrollableFrame(modal_frame, fg_color="transparent")
    modal_inner.pack(fill="both", expand=True, padx=4, pady=4)

    hdr = ctk.CTkFrame(modal_inner, fg_color="transparent")
    hdr.pack(fill="x", padx=12, pady=(12, 4))
    lbl_titulo = ctk.CTkLabel(hdr, text="Nueva Zona",
                               font=("Arial", 15, "bold"), text_color=COLOR_TEXTO)
    lbl_titulo.pack(side="left")
    ctk.CTkButton(
        hdr, text="✕", width=28, height=28, corner_radius=6,
        fg_color=COLOR_GRIS_CLARO, text_color=COLOR_TEXTO_MUTED,
        font=("Arial", 13), command=cerrar_formulario
    ).pack(side="right")

    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(
        fill="x", padx=12, pady=6)

    ctk.CTkLabel(modal_inner, text="Nombre de la Zona", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    entry_nombre = ctk.CTkEntry(
        modal_inner, placeholder_text="Ej: Caserío Vista Hermosa",
        height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_nombre.pack(fill="x", padx=16, pady=(0, 8))

    ctk.CTkLabel(modal_inner, text="Descripción (opcional)", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(4, 2))
    entry_desc = ctk.CTkEntry(
        modal_inner, placeholder_text="Descripción breve de la zona",
        height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_desc.pack(fill="x", padx=16, pady=(0, 8))

    ctk.CTkLabel(modal_inner, text="Orden de aparición", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(4, 2))
    entry_orden = ctk.CTkEntry(
        modal_inner, placeholder_text="0",
        height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_orden.pack(fill="x", padx=16, pady=(0, 2))
    aplicar_validacion_entero(entry_orden)
    ctk.CTkLabel(modal_inner,
                 text="Número menor aparece primero en las listas.",
                 font=("Arial", 10, "italic"),
                 text_color=COLOR_TEXTO_MUTED).pack(anchor="w", padx=16, pady=(0, 8))
    entry_orden.insert(0, "0")

    toggle_row = ctk.CTkFrame(modal_inner, fg_color="transparent")
    toggle_row.pack(fill="x", padx=16, pady=(8, 12))
    toggle_activa = ctk.CTkSwitch(
        toggle_row, text="Zona activa",
        font=FONT_LABEL, text_color=COLOR_TEXTO,
        progress_color=COLOR_VERDE_PAGO)
    toggle_activa.pack(side="left")
    toggle_activa.select()

    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(
        fill="x", padx=12, pady=6)

    ctk.CTkButton(
        modal_inner, text="GUARDAR", height=42, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, font=FONT_BTN,
        command=lambda: guardar_zona()
    ).pack(fill="x", padx=16, pady=(0, 6))

    ctk.CTkButton(
        modal_inner, text="Cancelar", height=36, corner_radius=8,
        fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
        border_width=1, border_color=COLOR_BORDE, font=FONT_BTN_SM,
        command=cerrar_formulario
    ).pack(fill="x", padx=16, pady=(0, 12))

    # ── Lógica ─────────────────────────────────────────────────────────────────
    def guardar_zona():
        nombre = entry_nombre.get().strip()
        desc   = entry_desc.get().strip()
        activa = 1 if toggle_activa.get() else 0
        try:
            orden = int(entry_orden.get().strip() or 0)
        except ValueError:
            orden = 0

        if not nombre:
            messagebox.showwarning("Atención", "El nombre es obligatorio.")
            return
        if len(nombre) < 2:
            messagebox.showwarning("Atención",
                                   "El nombre debe tener al menos 2 caracteres.")
            return

        try:
            con = obtener_conexion()
            cur = con.cursor()
            if estado_ed["zona_id"]:
                cur.execute(
                    "UPDATE zonas SET nombre=?, descripcion=?, orden=?, activa=? "
                    "WHERE id=?",
                    (nombre, desc or None, orden, activa, estado_ed["zona_id"]))
                msg = "Zona actualizada correctamente."
            else:
                cur.execute(
                    "INSERT INTO zonas (nombre, descripcion, orden, activa) "
                    "VALUES (?,?,?,?)",
                    (nombre, desc or None, orden, activa))
                msg = f"Zona '{nombre}' creada correctamente."
            con.commit()
            messagebox.showinfo("Éxito", msg)
            cerrar_formulario()
            actualizar_tabla()
            _refrescar_topbar()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicado",
                                  "Ya existe una zona con ese nombre.")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            logger.registrar("zonas.py", "guardar_zona", e)
        finally:
            if 'con' in locals():
                con.close()

    def _refrescar_topbar():
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM zonas WHERE activa=1")
            total = cur.fetchone()[0]
        except Exception:
            total = 0
        finally:
            if 'con' in locals():
                con.close()
        lbl_sub.configure(text=f"{total} zonas activas registradas")

    def actualizar_tabla():
        for w in lista_scroll.winfo_children():
            w.destroy()
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("""
                SELECT z.id, z.nombre, z.descripcion, z.orden, z.activa,
                       COUNT(v.id) as total_vecinos
                FROM zonas z
                LEFT JOIN vecinos v ON v.zona_id = z.id AND v.activo=1
                GROUP BY z.id
                ORDER BY z.orden, z.nombre
            """)
            filas = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo cargar:\n{e}")
            logger.registrar("zonas.py", "actualizar_tabla", e)
            return
        finally:
            if 'con' in locals():
                con.close()

        if not filas:
            mensaje_vacio(lista_scroll,
                          "No hay zonas registradas. Cree la primera zona.")
            return

        for z_id, nombre, desc, orden, activa, total_v in filas:
            fila_w = ctk.CTkFrame(lista_scroll, fg_color=COLOR_BLANCO,
                                   corner_radius=6, height=48)
            fila_w.pack(fill="x", pady=2, padx=4)
            fila_w.pack_propagate(False)

            ctk.CTkLabel(fila_w, text=str(orden), font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=60,
                         anchor="w").pack(side="left", padx=16)
            ctk.CTkLabel(fila_w, text=nombre, font=("Arial", 12, "bold"),
                         width=220, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=desc or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=240,
                         anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=str(total_v), font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=80,
                         anchor="center").pack(side="left", padx=4)

            bg = COLOR_BADGE_VERDE_BG if activa else COLOR_BADGE_GRIS_BG
            fg = COLOR_BADGE_VERDE_TEXT if activa else COLOR_BADGE_GRIS_TEXT
            txt = "Activa" if activa else "Inactiva"
            badge(fila_w, txt, bg, fg).pack(side="left", padx=4)

            ctk.CTkButton(
                fila_w, text="Editar", width=70, height=30, corner_radius=6,
                fg_color=COLOR_AMARILLO, hover_color="#B7791F",
                text_color=COLOR_BLANCO, font=FONT_SMALL,
                command=lambda d={
                    "id": z_id, "nombre": nombre, "descripcion": desc,
                    "orden": orden, "activa": activa
                }: abrir_formulario(d)
            ).pack(side="right", padx=12)
        lista_scroll.update_idletasks()

    frame.after(0, actualizar_tabla)
    _refrescar_topbar()
    return frame
