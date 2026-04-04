import re
import customtkinter as ctk
import sqlite3
import datetime
from tkinter import messagebox
import herramientas.logger as logger
from herramientas.db import (
    obtener_conexion, obtener_config, vecino_tiene_datos_completos
)
from herramientas.permisos import puede_gestionar_vecinos
from licencia.bloqueador import verificar_accion
from pantallas.componentes import (
    topbar, badge, encabezado_tabla, mensaje_vacio,
    separador, boton_primario, boton_secundario,
    aplicar_validacion_decimal
)
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_TEXTO,
    COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO,
    COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
    COLOR_BADGE_ROJO_BG, COLOR_BADGE_ROJO_TEXT,
    COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT,
    COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_BODY,
    FONT_SMALL, FONT_LABEL, MESES_ES,
    TIPO_COBRO_FIJO, TIPO_COBRO_MEDIDOR, CATEGORIAS_VECINO_DEFAULT
)

COLOR_MEDIDOR = "#553C9A"   # morado para vecinos con medidor


def _validar_dui(dui):
    return bool(re.fullmatch(r'\d{8}-\d', dui))

def _validar_tel(tel):
    return not tel or bool(re.fullmatch(r'\d{4}-\d{4}', tel))

def _validar_email(email):
    return not email or bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email))

def _fmt_dui(event, entry):
    if event.keysym in ("Left","Right","Home","End","BackSpace",
                         "Delete","Shift_L","Shift_R","Control_L","Control_R","Tab"):
        return
    digitos = "".join(c for c in entry.get() if c.isdigit())[:9]
    nuevo = digitos if len(digitos) <= 8 else digitos[:8] + "-" + digitos[8:9]
    entry.delete(0, "end"); entry.insert(0, nuevo); entry.icursor(len(nuevo))

def _fmt_tel(event, entry):
    if event.keysym in ("Left","Right","Home","End","BackSpace",
                         "Delete","Shift_L","Shift_R","Control_L","Control_R","Tab"):
        return
    digitos = "".join(c for c in entry.get() if c.isdigit())[:8]
    nuevo = digitos if len(digitos) <= 4 else digitos[:4] + "-" + digitos[4:8]
    entry.delete(0, "end"); entry.insert(0, nuevo); entry.icursor(len(nuevo))

def _obtener_zonas():
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("SELECT id, nombre FROM zonas WHERE activa=1 ORDER BY orden, nombre")
        return cur.fetchall()
    except Exception:
        return []
    finally:
        if 'con' in locals(): con.close()

def _obtener_categorias():
    """Lee categorías desde config o usa las por defecto."""
    cats_str = obtener_config("categorias_vecino", "")
    if cats_str:
        return [c.strip() for c in cats_str.split(",") if c.strip()]
    return CATEGORIAS_VECINO_DEFAULT


def crear_pantalla(parent_frame, get_rol_actual):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")

    checkboxes_meses = []
    estado_ed = {"vecino_id": None, "activo": 1, "zona_id": None}

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Administración de Vecinos",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    lbl_sub = ctk.CTkLabel(izq, text="Cargando...",
                            font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
    lbl_sub.pack(anchor="w")

    der = ctk.CTkFrame(bar, fg_color="transparent")
    der.pack(side="right", padx=20)
    btn_nuevo = ctk.CTkButton(
        der, text="+ Nuevo Vecino", height=36, corner_radius=8,
        fg_color=COLOR_AZUL_MARINO, font=FONT_BTN_SM, text_color=COLOR_BLANCO,
        command=lambda: abrir_formulario(None))
    btn_nuevo.pack(side="right")

    def _refrescar_topbar():
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM vecinos WHERE activo=1")
            total = cur.fetchone()[0]
        except Exception:
            total = 0
        finally:
            if 'con' in locals(): con.close()
        lbl_sub.configure(text=f"{total} vecinos activos registrados")

    def _actualizar_btn_nuevo():
        rol = get_rol_actual() if callable(get_rol_actual) else get_rol_actual
        btn_nuevo.configure(state="normal" if puede_gestionar_vecinos(rol) else "disabled")

    # ── Cuerpo ─────────────────────────────────────────────────────────────────
    cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
    cuerpo.pack(fill="both", expand=True, padx=24, pady=16)

    filtros_frame = ctk.CTkFrame(cuerpo, fg_color="transparent")
    filtros_frame.pack(fill="x", pady=(0, 10))

    fila_inferior = ctk.CTkFrame(cuerpo, fg_color="transparent")
    fila_inferior.pack(fill="both", expand=True)

    tabla_container = ctk.CTkFrame(fila_inferior, fg_color="transparent")
    tabla_container.pack(side="left", fill="both", expand=True)

    filtro_actual = {"valor": "todos"}
    filtro_zona   = {"zona_id": None}

    def aplicar_filtro(valor):
        filtro_actual["valor"] = valor
        for n, b in btns_filtro.items():
            activo = (n == valor)
            b.configure(
                fg_color=COLOR_AZUL_MARINO if activo else COLOR_BLANCO,
                text_color=COLOR_BLANCO if activo else COLOR_TEXTO_MUTED,
                border_width=0 if activo else 1, border_color=COLOR_BORDE)
        actualizar_tabla()

    btns_filtro = {}
    for key, lbl in [("todos","Todos"),("Solvente","Solventes"),
                      ("En Deuda","En Deuda"),("activos","Activos"),("inactivos","Inactivos")]:
        b = ctk.CTkButton(
            filtros_frame, text=lbl, height=32, corner_radius=8,
            fg_color=COLOR_AZUL_MARINO if key=="todos" else COLOR_BLANCO,
            text_color=COLOR_BLANCO if key=="todos" else COLOR_TEXTO_MUTED,
            border_width=0 if key=="todos" else 1,
            border_color=COLOR_BORDE, font=FONT_BTN_SM,
            command=lambda k=key: aplicar_filtro(k))
        b.pack(side="left", padx=(0, 8))
        btns_filtro[key] = b

    zonas_disponibles = _obtener_zonas()
    if zonas_disponibles:
        ctk.CTkLabel(filtros_frame, text="|", font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=4)
        nombres_zonas = ["Todas las zonas"] + [z[1] for z in zonas_disponibles]
        ids_zonas     = [None] + [z[0] for z in zonas_disponibles]
        combo_zona = ctk.CTkComboBox(
            filtros_frame, values=nombres_zonas, width=160, state="readonly",
            command=lambda v: _set_filtro_zona(v, nombres_zonas, ids_zonas))
        combo_zona.pack(side="left", padx=4)
        combo_zona.set("Todas las zonas")

    def _set_filtro_zona(valor, nombres, ids):
        idx = nombres.index(valor) if valor in nombres else 0
        filtro_zona["zona_id"] = ids[idx]
        actualizar_tabla()

    # Tabla
    tabla_card = ctk.CTkFrame(tabla_container, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(fill="both", expand=True)

    encabezado_tabla(tabla_card, [
        ("Nombre", 170), ("Abonado", 70), ("Teléfono", 100),
        ("Dirección", 150), ("Tipo", 70), ("Zona", 90), ("Estado", 90)
    ])

    lista_scroll = ctk.CTkScrollableFrame(tabla_card, fg_color=COLOR_FONDO, corner_radius=0)
    lista_scroll.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Modal formulario ───────────────────────────────────────────────────────
    modal_visible = [False]
    modal_frame   = ctk.CTkFrame(fila_inferior, fg_color=COLOR_BLANCO,
                                  corner_radius=12, width=420)
    modal_frame.pack_propagate(False)

    def abrir_formulario(vecino_data):
        if not verificar_accion("agregar_vecino"):
            return
        rol = get_rol_actual() if callable(get_rol_actual) else get_rol_actual
        if not puede_gestionar_vecinos(rol):
            messagebox.showwarning("Acceso denegado", "Su rol no permite gestionar vecinos.")
            return

        es_edicion = vecino_data is not None
        limpiar_form(es_edicion=es_edicion)
        estado_ed["vecino_id"] = vecino_data["id"] if vecino_data else None

        if vecino_data:
            lbl_dui_edicion.configure(text=f"DUI: {vecino_data['dui']}")
            lbl_dui_edicion.pack(anchor="w", padx=16, pady=(8, 4))
            entry_nombre.insert(0, vecino_data.get("nombre") or "")
            entry_tel.insert(0, vecino_data.get("telefono") or "")
            entry_email.insert(0, vecino_data.get("email") or "")
            entry_cuota.delete(0, "end")
            entry_cuota.insert(0, str(vecino_data.get("cuota", "5.00")))
            entry_abonado.insert(0, vecino_data.get("num_abonado") or "")
            entry_medidor.insert(0, vecino_data.get("num_medidor") or "")
            entry_direccion.insert(0, vecino_data.get("direccion") or "")
            entry_lect_inicial.delete(0, "end")
            entry_lect_inicial.insert(0, str(vecino_data.get("lectura_inicial") or "0"))

            cat = vecino_data.get("categoria") or "Residencial"
            combo_categoria.set(cat if cat in _obtener_categorias() else "Residencial")

            tipo = vecino_data.get("tipo_cobro") or TIPO_COBRO_FIJO
            seg_tipo.set("Con Medidor" if tipo == TIPO_COBRO_MEDIDOR else "Cuota Fija")
            _toggle_tipo_cobro(seg_tipo.get())

            zona_id = vecino_data.get("zona_id")
            estado_ed["zona_id"] = zona_id
            if zona_id:
                for zid, znombre in zonas_disponibles:
                    if zid == zona_id:
                        combo_zona_form.set(znombre); break
            else:
                combo_zona_form.set("Sin zona")

            seg_estado.set("Solvente")
            seg_estado.configure(state="disabled")
            frame_meses_outer.pack_forget()
            frame_meses.pack_forget()
            lbl_form_titulo.configure(text="Editando Vecino")
            activo_val = vecino_data.get("activo", 1)
            estado_ed["activo"] = activo_val
            toggle_activo.select() if activo_val == 1 else toggle_activo.deselect()
            frame_toggle_activo.pack(fill="x", padx=16, pady=(8, 4))
        else:
            lbl_form_titulo.configure(text="Nuevo Vecino")
            frame_toggle_activo.pack_forget()

        if not modal_visible[0]:
            modal_frame.pack(side="right", fill="y", padx=(12, 0))
            modal_visible[0] = True

    def cerrar_formulario():
        modal_frame.pack_forget()
        modal_visible[0] = False
        estado_ed["vecino_id"] = None
        limpiar_form(es_edicion=False)

    def limpiar_form(es_edicion=False):
        for e in [entry_nombre, entry_tel, entry_email,
                  entry_abonado, entry_medidor, entry_direccion]:
            e.configure(state="normal"); e.delete(0, "end")
        entry_cuota.delete(0, "end"); entry_cuota.insert(0, "5.00")
        entry_lect_inicial.delete(0, "end"); entry_lect_inicial.insert(0, "0")
        seg_estado.set("Solvente"); seg_estado.configure(state="normal")
        seg_tipo.set("Cuota Fija")
        _toggle_tipo_cobro("Cuota Fija")
        frame_meses.pack_forget(); frame_meses_outer.pack_forget()
        frame_toggle_activo.pack_forget()
        lbl_dui_edicion.pack_forget()
        combo_zona_form.set("Sin zona"); estado_ed["zona_id"] = None
        combo_categoria.set("Residencial")
        if not es_edicion:
            frame_dui.pack(fill="x", after=separador_form)
        else:
            frame_dui.pack_forget()
        for c in checkboxes_meses:
            c["var"].set(0)

    def _toggle_tipo_cobro(val):
        if val == "Con Medidor":
            frame_medidor_extra.pack(fill="x", padx=16, pady=(4, 0))
            lbl_cuota_hint.configure(text="Tarifa base mensual ($)")
        else:
            frame_medidor_extra.pack_forget()
            lbl_cuota_hint.configure(text="Cuota Mensual ($)")

    def _alternar_meses(val):
        if val == "Con Deuda":
            frame_meses_outer.pack(fill="x", padx=16, pady=(6, 0))
            frame_meses.pack(fill="x", padx=16, pady=(0, 8))
        else:
            frame_meses.pack_forget(); frame_meses_outer.pack_forget()

    # ── Contenido del modal ────────────────────────────────────────────────────
    modal_inner = ctk.CTkScrollableFrame(modal_frame, fg_color="transparent")
    modal_inner.pack(fill="both", expand=True, padx=4, pady=4)

    modal_header = ctk.CTkFrame(modal_inner, fg_color="transparent")
    modal_header.pack(fill="x", padx=12, pady=(12, 4))
    lbl_form_titulo = ctk.CTkLabel(modal_header, text="Nuevo Vecino",
                                    font=("Arial", 15, "bold"), text_color=COLOR_TEXTO)
    lbl_form_titulo.pack(side="left")
    ctk.CTkButton(modal_header, text="✕", width=28, height=28, corner_radius=6,
                   fg_color=COLOR_GRIS_CLARO, text_color=COLOR_TEXTO_MUTED,
                   font=("Arial", 13), command=cerrar_formulario).pack(side="right")

    separador_form = ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE)
    separador_form.pack(fill="x", padx=12, pady=6)

    lbl_dui_edicion = ctk.CTkLabel(modal_inner, text="",
                                    font=("Arial", 12, "bold"), text_color=COLOR_TEXTO_MUTED)

    # DUI (solo nuevo)
    frame_dui = ctk.CTkFrame(modal_inner, fg_color="transparent")
    frame_dui.pack(fill="x")
    ctk.CTkLabel(frame_dui, text="Número de DUI *", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(10, 2))
    entry_dui = ctk.CTkEntry(frame_dui, placeholder_text="00000000-0",
                              height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_dui.pack(fill="x", padx=16, pady=(0, 2))
    entry_dui.bind("<KeyRelease>", lambda e: _fmt_dui(e, entry_dui))

    # ── Sección: Datos personales ──────────────────────────────────────────────
    ctk.CTkLabel(modal_inner, text="DATOS PERSONALES", font=("Arial", 10, "bold"),
                 text_color=COLOR_AZUL_MARINO).pack(anchor="w", padx=16, pady=(14, 2))
    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(fill="x", padx=16, pady=(0,6))

    ctk.CTkLabel(modal_inner, text="Nombre Completo *", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(6, 2))
    entry_nombre = ctk.CTkEntry(modal_inner, placeholder_text="Nombre completo del vecino",
                                 height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_nombre.pack(fill="x", padx=16, pady=(0, 2))

    ctk.CTkLabel(modal_inner, text="Teléfono", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    entry_tel = ctk.CTkEntry(modal_inner, placeholder_text="0000-0000",
                              height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_tel.pack(fill="x", padx=16, pady=(0, 2))
    entry_tel.bind("<KeyRelease>", lambda e: _fmt_tel(e, entry_tel))

    ctk.CTkLabel(modal_inner, text="Correo Electrónico", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    entry_email = ctk.CTkEntry(modal_inner, placeholder_text="correo@ejemplo.com",
                                height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_email.pack(fill="x", padx=16, pady=(0, 2))

    ctk.CTkLabel(modal_inner, text="Dirección *", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    entry_direccion = ctk.CTkEntry(modal_inner, placeholder_text="Cantón, Caserío, etc.",
                                    height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_direccion.pack(fill="x", padx=16, pady=(0, 2))

    # ── Sección: Datos del servicio ────────────────────────────────────────────
    ctk.CTkLabel(modal_inner, text="DATOS DEL SERVICIO", font=("Arial", 10, "bold"),
                 text_color=COLOR_AZUL_MARINO).pack(anchor="w", padx=16, pady=(14, 2))
    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(fill="x", padx=16, pady=(0,6))

    # Número de abonado
    ctk.CTkLabel(modal_inner, text="Número de Abonado *", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(6, 2))
    entry_abonado = ctk.CTkEntry(modal_inner, placeholder_text="Ej: 0232",
                                  height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_abonado.pack(fill="x", padx=16, pady=(0, 2))

    # Categoría
    ctk.CTkLabel(modal_inner, text="Categoría", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    combo_categoria = ctk.CTkComboBox(modal_inner, values=_obtener_categorias(),
                                       state="readonly", height=40, corner_radius=8)
    combo_categoria.pack(fill="x", padx=16, pady=(0, 2))
    combo_categoria.set("Residencial")

    # Zona geográfica
    ctk.CTkLabel(modal_inner, text="Zona Geográfica", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(8, 2))
    nombres_zonas_form = ["Sin zona"] + [z[1] for z in zonas_disponibles]
    ids_zonas_form     = [None]       + [z[0] for z in zonas_disponibles]
    combo_zona_form = ctk.CTkComboBox(
        modal_inner, values=nombres_zonas_form, state="readonly",
        height=40, corner_radius=8,
        command=lambda v: estado_ed.update(
            {"zona_id": ids_zonas_form[nombres_zonas_form.index(v)]
             if v in nombres_zonas_form else None}))
    combo_zona_form.pack(fill="x", padx=16, pady=(0, 2))
    combo_zona_form.set("Sin zona")

    # ── Tipo de cobro ──────────────────────────────────────────────────────────
    ctk.CTkLabel(modal_inner, text="Tipo de Cobro", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(12, 4))
    seg_tipo = ctk.CTkSegmentedButton(
        modal_inner, values=["Cuota Fija", "Con Medidor"],
        selected_color=COLOR_AZUL_MARINO,
        command=_toggle_tipo_cobro)
    seg_tipo.pack(fill="x", padx=16)
    seg_tipo.set("Cuota Fija")

    lbl_cuota_hint = ctk.CTkLabel(modal_inner, text="Cuota Mensual ($)",
                                   font=FONT_LABEL, text_color=COLOR_TEXTO)
    lbl_cuota_hint.pack(anchor="w", padx=16, pady=(10, 2))
    entry_cuota = ctk.CTkEntry(modal_inner, placeholder_text="5.00",
                                height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_cuota.pack(fill="x", padx=16, pady=(0, 2))
    entry_cuota.insert(0, "5.00")
    aplicar_validacion_decimal(entry_cuota)

    # Campos exclusivos para vecinos con medidor
    frame_medidor_extra = ctk.CTkFrame(modal_inner, fg_color="#F5F3FF", corner_radius=8)
    # (se muestra/oculta con _toggle_tipo_cobro)

    ctk.CTkLabel(frame_medidor_extra, text="Número de Medidor *",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(anchor="w", padx=12, pady=(10, 2))
    entry_medidor = ctk.CTkEntry(frame_medidor_extra, placeholder_text="Ej: 072119",
                                  height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_medidor.pack(fill="x", padx=12, pady=(0, 6))

    ctk.CTkLabel(frame_medidor_extra, text="Lectura Inicial del Medidor (m³)",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(anchor="w", padx=12, pady=(4, 2))
    entry_lect_inicial = ctk.CTkEntry(frame_medidor_extra, placeholder_text="Ej: 4410",
                                       height=40, corner_radius=8, fg_color=COLOR_FONDO)
    entry_lect_inicial.pack(fill="x", padx=12, pady=(0, 4))
    aplicar_validacion_decimal(entry_lect_inicial)
    ctk.CTkLabel(frame_medidor_extra,
                 text="Esta será la lectura de referencia para el primer cobro.",
                 font=("Arial", 10, "italic"), text_color=COLOR_TEXTO_MUTED).pack(
        anchor="w", padx=12, pady=(0, 10))

    # ── Estado inicial ─────────────────────────────────────────────────────────
    ctk.CTkLabel(modal_inner, text="Estado Inicial", font=FONT_LABEL,
                 text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(12, 4))
    seg_estado = ctk.CTkSegmentedButton(
        modal_inner, values=["Solvente", "Con Deuda"],
        selected_color=COLOR_AZUL_MARINO,
        command=_alternar_meses)
    seg_estado.pack(fill="x", padx=16)
    seg_estado.set("Solvente")

    # Meses adeudados
    frame_meses_outer = ctk.CTkFrame(modal_inner, fg_color="transparent")
    ctk.CTkLabel(frame_meses_outer, text="Meses adeudados",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(anchor="w", pady=(4, 2))
    frame_meses = ctk.CTkScrollableFrame(frame_meses_outer, fg_color=COLOR_FONDO,
                                          corner_radius=8, height=120)
    hoy = datetime.date.today()
    for anio in range(2025, hoy.year + 1):
        fin = hoy.month if anio == hoy.year else 12
        for m in range(1, fin + 1):
            var = ctk.IntVar(value=0)
            ctk.CTkCheckBox(frame_meses, text=f"{MESES_ES[m]} {anio}",
                             variable=var, font=FONT_SMALL).pack(anchor="w", pady=3, padx=6)
            checkboxes_meses.append({"mes": MESES_ES[m], "anio": anio, "var": var})

    # Toggle activo/inactivo
    frame_toggle_activo = ctk.CTkFrame(modal_inner, fg_color="#FFF5F5", corner_radius=8)
    ctk.CTkLabel(frame_toggle_activo, text="Estado del vecino",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(anchor="w", padx=12, pady=(10, 2))
    toggle_row = ctk.CTkFrame(frame_toggle_activo, fg_color="transparent")
    toggle_row.pack(fill="x", padx=12, pady=(0, 4))
    toggle_activo = ctk.CTkSwitch(
        toggle_row, text="Vecino activo en el sistema",
        font=FONT_BODY, text_color=COLOR_TEXTO,
        progress_color=COLOR_VERDE_PAGO,
        command=lambda: estado_ed.update({"activo": 1 if toggle_activo.get() else 0}))
    toggle_activo.pack(side="left")
    toggle_activo.select()
    ctk.CTkLabel(frame_toggle_activo,
                 text="Si se desactiva, no aparecerá\nen cobros ni reportes activos.",
                 font=("Arial", 10, "italic"), text_color=COLOR_ROJO,
                 justify="left").pack(anchor="w", padx=12, pady=(0, 8))

    ctk.CTkFrame(modal_inner, height=1, fg_color=COLOR_BORDE).pack(fill="x", padx=12, pady=10)

    ctk.CTkButton(modal_inner, text="GUARDAR", height=42, corner_radius=8,
                   fg_color=COLOR_AZUL_MARINO, font=FONT_BTN,
                   command=lambda: guardar_vecino()).pack(fill="x", padx=16, pady=(0, 6))
    ctk.CTkButton(modal_inner, text="Cancelar", height=36, corner_radius=8,
                   fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
                   border_width=1, border_color=COLOR_BORDE, font=FONT_BTN_SM,
                   command=cerrar_formulario).pack(fill="x", padx=16, pady=(0, 12))

    # ── Guardar vecino ─────────────────────────────────────────────────────────
    def guardar_vecino():
        dui       = entry_dui.get().strip()
        nombre    = entry_nombre.get().strip()
        tel       = entry_tel.get().strip()
        email     = entry_email.get().strip()
        cuota     = entry_cuota.get().strip()
        abonado   = entry_abonado.get().strip()
        medidor   = entry_medidor.get().strip()
        direccion = entry_direccion.get().strip()
        categoria = combo_categoria.get()
        tipo_cobro = TIPO_COBRO_MEDIDOR if seg_tipo.get() == "Con Medidor" else TIPO_COBRO_FIJO
        lect_ini_str = entry_lect_inicial.get().strip() or "0"
        zona_id   = estado_ed.get("zona_id")
        estado_seg = seg_estado.get()
        es_edicion = bool(estado_ed["vecino_id"])

        errores = []
        if not nombre or len(nombre) < 3:
            errores.append("El nombre es obligatorio (mínimo 3 caracteres).")
        if not es_edicion and not dui:
            errores.append("El DUI es obligatorio.")
        elif not es_edicion and not _validar_dui(dui):
            errores.append("Formato de DUI inválido (00000000-0).")
        if not _validar_tel(tel):
            errores.append("Formato de teléfono inválido (0000-0000).")
        if not _validar_email(email):
            errores.append("Formato de correo inválido.")
        if not abonado:
            errores.append("El número de abonado es obligatorio.")
        if not direccion:
            errores.append("La dirección es obligatoria.")
        if tipo_cobro == TIPO_COBRO_MEDIDOR and not medidor:
            errores.append("El número de medidor es obligatorio para vecinos con medidor.")
        if not cuota:
            errores.append("La cuota / tarifa base es obligatoria.")
        else:
            try:
                if float(cuota) <= 0:
                    errores.append("La cuota debe ser mayor a $0.00.")
            except ValueError:
                errores.append("La cuota debe ser un número válido.")
        try:
            lect_ini = float(lect_ini_str)
        except ValueError:
            errores.append("La lectura inicial debe ser un número.")
            lect_ini = 0.0

        if errores:
            messagebox.showwarning("Datos incompletos",
                                   "\n".join(f"• {e}" for e in errores))
            return

        cuota_f = float(cuota)

        try:
            con = obtener_conexion()
            cur = con.cursor()

            if es_edicion:
                activo_nuevo = estado_ed.get("activo", 1)
                cur.execute(
                    "UPDATE vecinos SET nombre=?, telefono=?, email=?, cuota=?, "
                    "activo=?, zona_id=?, num_abonado=?, num_medidor=?, "
                    "direccion=?, categoria=?, tipo_cobro=?, lectura_inicial=? "
                    "WHERE id=?",
                    (nombre, tel or None, email or None, cuota_f,
                     activo_nuevo, zona_id, abonado, medidor or None,
                     direccion, categoria, tipo_cobro, lect_ini,
                     estado_ed["vecino_id"]))
                msg = "Vecino actualizado correctamente."
            else:
                meses_deuda = [i for i in checkboxes_meses if i["var"].get() == 1]
                if estado_seg == "Con Deuda" and not meses_deuda:
                    messagebox.showwarning("Sin meses",
                                           "Seleccionó 'Con Deuda' pero no marcó ningún mes.")
                    return
                estado_db = "Solvente" if estado_seg == "Solvente" else "En Deuda"
                cur.execute(
                    "INSERT INTO vecinos "
                    "(dui, nombre, telefono, email, estado, cuota, zona_id, "
                    "num_abonado, num_medidor, direccion, categoria, tipo_cobro, lectura_inicial) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (dui, nombre, tel or None, email or None, estado_db, cuota_f, zona_id,
                     abonado, medidor or None, direccion, categoria, tipo_cobro, lect_ini))
                nv_id = cur.lastrowid

                for item in meses_deuda:
                    cur.execute(
                        "INSERT INTO recibos (vecino_id, mes, anio, monto, estado_pago) "
                        "VALUES (?,?,?,?,?)",
                        (nv_id, item["mes"], item["anio"], cuota_f, "Pendiente"))

                if estado_seg == "Solvente":
                    mes_actual  = MESES_ES[datetime.date.today().month]
                    anio_actual = datetime.date.today().year
                    cur.execute(
                        "INSERT INTO recibos (vecino_id, mes, anio, monto, estado_pago) "
                        "VALUES (?,?,?,?,?)",
                        (nv_id, mes_actual, anio_actual, cuota_f, "Pendiente"))

                msg = f"Vecino {nombre} registrado correctamente."

            con.commit()
            messagebox.showinfo("Éxito", msg)
            cerrar_formulario()
            actualizar_tabla()
            _refrescar_topbar()

        except sqlite3.IntegrityError as e:
            messagebox.showerror("DUI Duplicado", "Este número de DUI ya está registrado.")
            logger.registrar("vecinos.py", "guardar_vecino", e)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
            logger.registrar("vecinos.py", "guardar_vecino", e)
        finally:
            if 'con' in locals(): con.close()

    # ── Actualizar tabla ───────────────────────────────────────────────────────
    def actualizar_tabla():
        for w in lista_scroll.winfo_children():
            w.destroy()

        filtro  = filtro_actual["valor"]
        zona_id = filtro_zona["zona_id"]

        try:
            con = obtener_conexion()
            cur = con.cursor()
            base_q = """
                SELECT v.id, v.dui, v.nombre, v.telefono, v.email,
                       v.cuota, v.estado, v.activo, z.nombre as zona_nombre,
                       v.zona_id, v.num_abonado, v.num_medidor, v.direccion,
                       v.categoria, v.tipo_cobro, v.lectura_inicial
                FROM vecinos v
                LEFT JOIN zonas z ON v.zona_id = z.id
            """
            conditions, params = [], []
            if filtro == "activos":       conditions.append("v.activo=1")
            elif filtro == "inactivos":   conditions.append("v.activo=0")
            elif filtro in ("Solvente","En Deuda"):
                conditions.append("v.activo=1 AND v.estado=?"); params.append(filtro)
            else:                         conditions.append("1=1")

            if zona_id:
                conditions.append("v.zona_id=?"); params.append(zona_id)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            cur.execute(f"{base_q} {where} ORDER BY v.activo DESC, v.nombre", params)
            filas = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo cargar la lista:\n{e}")
            logger.registrar("vecinos.py", "actualizar_tabla", e)
            return
        finally:
            if 'con' in locals(): con.close()

        if not filas:
            mensaje_vacio(lista_scroll, "No hay vecinos que mostrar.")
            return

        rol = get_rol_actual() if callable(get_rol_actual) else get_rol_actual

        for row in filas:
            (v_id, dui, nombre, tel, email, cuota, estado_v, activo,
             zona_nombre, zona_id_actual, num_abonado, num_medidor,
             direccion, categoria, tipo_cobro, lect_ini) = row

            es_activo   = activo == 1
            es_medidor  = tipo_cobro == TIPO_COBRO_MEDIDOR
            bg_fila     = COLOR_BLANCO if es_activo else "#FAFAFA"

            fila = ctk.CTkFrame(lista_scroll, fg_color=bg_fila,
                                 corner_radius=6, height=48)
            fila.pack(fill="x", pady=2, padx=4)
            fila.pack_propagate(False)

            color_n = COLOR_TEXTO if es_activo else COLOR_TEXTO_MUTED
            ctk.CTkLabel(fila, text=nombre, font=("Arial", 12, "bold"),
                         text_color=color_n, width=170, anchor="w").pack(side="left", padx=16)
            ctk.CTkLabel(fila, text=num_abonado or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=70, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila, text=tel or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=100, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila, text=direccion or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=150, anchor="w").pack(side="left", padx=4)

            # Badge tipo de cobro
            if es_medidor:
                badge(fila, "Medidor", "#F5F3FF", COLOR_MEDIDOR, width=70).pack(side="left", padx=4)
            else:
                badge(fila, "Fijo", COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT, width=70).pack(side="left", padx=4)

            ctk.CTkLabel(fila, text=zona_nombre or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=90, anchor="w").pack(side="left", padx=4)

            if not es_activo:
                badge(fila, "Inactivo", COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT, width=90).pack(side="left", padx=4)
            else:
                bg  = COLOR_BADGE_VERDE_BG if estado_v == "Solvente" else COLOR_BADGE_ROJO_BG
                fg  = COLOR_BADGE_VERDE_TEXT if estado_v == "Solvente" else COLOR_BADGE_ROJO_TEXT
                badge(fila, estado_v, bg, fg, width=90).pack(side="left", padx=4)

            if puede_gestionar_vecinos(rol):
                ctk.CTkButton(
                    fila, text="Editar", width=70, height=30, corner_radius=6,
                    fg_color=COLOR_AMARILLO, hover_color="#B7791F",
                    text_color=COLOR_BLANCO, font=FONT_SMALL,
                    command=lambda d={
                        "id": v_id, "dui": dui, "nombre": nombre,
                        "telefono": tel, "email": email, "cuota": cuota,
                        "activo": activo, "zona_id": zona_id_actual,
                        "num_abonado": num_abonado, "num_medidor": num_medidor,
                        "direccion": direccion, "categoria": categoria,
                        "tipo_cobro": tipo_cobro, "lectura_inicial": lect_ini
                    }: abrir_formulario(d)
                ).pack(side="right", padx=12)
        lista_scroll.update_idletasks()

    frame.after(0, actualizar_tabla)
    _refrescar_topbar()
    frame.after(100, _actualizar_btn_nuevo)
    return frame