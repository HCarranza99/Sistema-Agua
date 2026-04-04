import customtkinter as ctk
import os
from tkinter import messagebox, filedialog
import herramientas.logger as logger
from herramientas.db import (
    obtener_config, guardar_config, obtener_conexion
)
from herramientas.seguridad import cifrar_texto, descifrar_texto
from herramientas.email_sender import probar_conexion_smtp
from pantallas.componentes import (
    topbar, separador, aplicar_validacion_decimal, aplicar_validacion_entero
)
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_TEXTO,
    COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM,
    FONT_SMALL, FONT_LABEL, FONT_BODY,
    RUTA_RESPALDOS_DEFAULT, RUTA_SINCRONIZACION_DEFAULT,
    RUTA_RECIBOS_DEFAULT, RUTA_REPORTES_PDF_DEFAULT, RUTA_REPORTES_EXCEL_DEFAULT,
    CATEGORIAS_VECINO_DEFAULT
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
    fila = ctk.CTkFrame(parent, fg_color=COLOR_BLANCO)
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
    scroll = ctk.CTkScrollableFrame(frame, fg_color=COLOR_FONDO)
    scroll.pack(fill="both", expand=True, padx=24, pady=16)

    # Fila superior: dos columnas
    row_top = ctk.CTkFrame(scroll, fg_color=COLOR_FONDO)
    row_top.pack(fill="x", pady=(0, 8))

    col_izq = ctk.CTkFrame(row_top, fg_color=COLOR_BLANCO, corner_radius=10)
    col_izq.pack(side="left", fill="both", expand=True, padx=(0, 8))

    col_der = ctk.CTkFrame(row_top, fg_color=COLOR_BLANCO, corner_radius=10)
    col_der.pack(side="right", fill="both", expand=True)

    pad = ctk.CTkFrame(col_izq, fg_color=COLOR_BLANCO)
    pad.pack(fill="both", expand=True, padx=20, pady=16)

    pad_der = ctk.CTkFrame(col_der, fg_color=COLOR_BLANCO)
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

    # ── Logo de la organización ────────────────────────────────────────────────
    _seccion(pad, "Logo de la organización")
    ctk.CTkLabel(pad, text="Imagen que aparece en el encabezado del PDF de factura.\n"
                            "Formatos: PNG, JPG. Tamaño recomendado: 200×80 px.",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 6))

    fila_logo = ctk.CTkFrame(pad, fg_color=COLOR_BLANCO)
    fila_logo.pack(fill="x", pady=(0, 4))
    e_logo = ctk.CTkEntry(fila_logo, height=40, corner_radius=8, fg_color=COLOR_FONDO,
                           placeholder_text="Ruta al archivo de imagen...")
    e_logo.pack(side="left", fill="x", expand=True, padx=(0, 6))
    ruta_logo_actual = obtener_config("ruta_logo", "")
    if ruta_logo_actual:
        e_logo.insert(0, ruta_logo_actual)

    def seleccionar_logo():
        ruta = filedialog.askopenfilename(
            title="Seleccionar logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp"), ("Todos", "*.*")])
        if ruta:
            e_logo.delete(0, "end")
            e_logo.insert(0, ruta)

    ctk.CTkButton(fila_logo, text="Examinar", width=90, height=40, corner_radius=8,
                   fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                   font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=seleccionar_logo).pack(side="left")

    # ── Categorías de vecino ───────────────────────────────────────────────────
    _seccion(pad, "Categorías de vecino")
    ctk.CTkLabel(pad, text="Lista de categorías disponibles al registrar un vecino.\n"
                            "Separe con comas. Ej: Residencial, Comercial, Institucional",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 6))

    cats_actual = obtener_config("categorias_vecino",
                                  ", ".join(CATEGORIAS_VECINO_DEFAULT))
    e_categorias = ctk.CTkEntry(pad, height=40, corner_radius=8, fg_color=COLOR_FONDO,
                                 placeholder_text="Residencial, Comercial, Honorario")
    e_categorias.pack(fill="x", pady=(0, 4))
    e_categorias.insert(0, cats_actual)

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
    e_smtp_puerto = _campo(pad_der, "Puerto SMTP", "587",
                            obtener_config("smtp_puerto", "587"))
    aplicar_validacion_entero(e_smtp_puerto)
    e_smtp_usuario = _campo(pad_der, "Usuario (correo remitente)",
                             "tucorreo@gmail.com",
                             obtener_config("smtp_usuario", ""))
    e_smtp_pass = _campo(pad_der, "Contraseña de aplicación", "••••••••",
                          descifrar_texto(obtener_config("smtp_password_cifrada", "")),
                          mostrar="*")
    e_smtp_remitente = _campo(pad_der, "Nombre visible del remitente", "ADESCO El Gramal",
                               obtener_config("smtp_remitente", ""))

    lbl_prueba = ctk.CTkLabel(pad_der, text="", font=FONT_SMALL,
                               text_color=COLOR_VERDE_PAGO, wraplength=300)
    lbl_prueba.pack(anchor="w", pady=(4, 0))

    def probar_smtp():
        lbl_prueba.configure(text="Probando conexión...", text_color=COLOR_TEXTO_MUTED)
        frame.update_idletasks()
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

    ctk.CTkButton(pad_der, text="Probar Conexión", height=38, corner_radius=8,
                   fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                   font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=probar_smtp).pack(fill="x", pady=(8, 0))

    # ── Tarifas y cobros ───────────────────────────────────────────────────────
    _seccion(pad_der, "Tarifas y cobros")

    e_tarifa = _campo(pad_der, "Tarifa básica mensual ($)",
                       "5.00", obtener_config("tarifa_basica", "5.00"))
    aplicar_validacion_decimal(e_tarifa)
    e_m3 = _campo(pad_der, "M³ incluidos en tarifa básica",
                   "25", obtener_config("m3_incluidos", "25"))
    aplicar_validacion_decimal(e_m3)
    e_fecha_limite = _campo(pad_der, "Día límite de pago (1–31)",
                             "25", obtener_config("fecha_limite_pago", "25"))
    aplicar_validacion_entero(e_fecha_limite)

    ctk.CTkLabel(pad_der, text="Recargo por mora automático",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).pack(anchor="w", pady=(10, 2))
    mora_row = ctk.CTkFrame(pad_der, fg_color=COLOR_BLANCO)
    mora_row.pack(fill="x", pady=(0, 2))
    mora_tipo_var = ctk.StringVar(
        value=obtener_config("mora_tipo", "fijo"))
    seg_mora = ctk.CTkSegmentedButton(
        mora_row, values=["fijo", "porcentaje"],
        variable=mora_tipo_var,
        selected_color=COLOR_AZUL_MARINO,
        width=160)
    seg_mora.pack(side="left", padx=(0, 8))
    e_mora_valor = ctk.CTkEntry(mora_row, height=40, width=100,
                                 corner_radius=8, fg_color=COLOR_FONDO,
                                 placeholder_text="1.00")
    e_mora_valor.pack(side="left")
    mora_val_actual = obtener_config("mora_valor", "1.00")
    if mora_val_actual:
        e_mora_valor.insert(0, mora_val_actual)
    aplicar_validacion_decimal(e_mora_valor)
    ctk.CTkLabel(mora_row, text="$ / %", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=4)

    # ── Facturación ────────────────────────────────────────────────────────────
    _seccion(pad_der, "Numeración de facturas")
    ctk.CTkLabel(pad_der,
                 text="El correlativo avanza automáticamente con cada factura emitida.",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 6))

    e_num_inicial = _campo(pad_der, "Número de factura inicial",
                            "1", obtener_config("num_factura_inicial", "1"))
    aplicar_validacion_entero(e_num_inicial)
    e_num_actual  = _campo(pad_der, "Número actual (próxima factura)",
                            "1", obtener_config("num_factura_actual",
                                                obtener_config("num_factura_inicial", "1")))
    aplicar_validacion_entero(e_num_actual)
    e_dia_gen = _campo(pad_der, "Día del mes para generar recibos (1–31)",
                        "1", obtener_config("dia_generacion_recibos", "1"))
    aplicar_validacion_entero(e_dia_gen)

    # ── ID del cliente / Hardware ─────────────────────────────────────────────
    _seccion(pad_der, "Información de licencia")
    from herramientas.seguridad import obtener_hardware_id
    hw_id = obtener_hardware_id()
    ctk.CTkLabel(pad_der,
                 text="ID de este equipo — compártalo con soporte para activar o renovar su licencia.",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 wraplength=300, justify="left").pack(anchor="w", pady=(0, 6))

    fila_hw = ctk.CTkFrame(pad_der, fg_color=COLOR_FONDO, corner_radius=8, height=40)
    fila_hw.pack(fill="x", pady=(0, 4))
    fila_hw.pack_propagate(False)
    ctk.CTkLabel(fila_hw, text=hw_id, font=("Courier New", 11),
                 text_color=COLOR_TEXTO, anchor="w").pack(side="left", padx=12, fill="y")

    lbl_copiado = ctk.CTkLabel(pad_der, text="", font=FONT_SMALL,
                                text_color=COLOR_VERDE_PAGO)
    lbl_copiado.pack(anchor="w", pady=(0, 4))

    def copiar_hw_id():
        frame.clipboard_clear()
        frame.clipboard_append(hw_id)
        frame.update()
        lbl_copiado.configure(text="✓ ID copiado al portapapeles")
        frame.after(3000, lambda: lbl_copiado.configure(text=""))

    ctk.CTkButton(pad_der, text="Copiar ID", height=36, corner_radius=8,
                   fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                   font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=copiar_hw_id).pack(fill="x", pady=(0, 8))

    # ── SECCIÓN COMPLETA: Rangos de excedente ─────────────────────────────────
    rangos_card = ctk.CTkFrame(scroll, fg_color=COLOR_BLANCO, corner_radius=10)
    rangos_card.pack(fill="x", pady=(0, 8))
    pad_rangos = ctk.CTkFrame(rangos_card, fg_color=COLOR_BLANCO)
    pad_rangos.pack(fill="both", expand=True, padx=20, pady=16)

    ctk.CTkLabel(pad_rangos, text="Rangos de excedente (tarifas escalonadas)",
                 font=("Arial", 13, "bold"), text_color=COLOR_AZUL_MARINO).pack(anchor="w")
    ctk.CTkFrame(pad_rangos, height=1, fg_color=COLOR_BORDE).pack(fill="x", pady=(4, 8))
    ctk.CTkLabel(pad_rangos,
                 text="Define el precio por m³ para cada tramo de consumo que exceda "
                      "los m³ incluidos en la tarifa básica.\n"
                      "Deja 'Hasta m³' en blanco para el último tramo (sin límite superior).",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 justify="left").pack(anchor="w", pady=(0, 8))

    # Encabezado de la tabla de rangos
    enc_rangos = ctk.CTkFrame(pad_rangos, fg_color=COLOR_FONDO, corner_radius=6, height=32)
    enc_rangos.pack(fill="x")
    enc_rangos.pack_propagate(False)
    for txt, w in [("Desde m³", 90), ("Hasta m³", 90), ("$/m³", 90), ("Descripción", 200)]:
        ctk.CTkLabel(enc_rangos, text=txt, font=("Arial", 10, "bold"),
                     text_color=COLOR_TEXTO_MUTED, width=w, anchor="w"
                     ).pack(side="left", padx=(8 if txt == "Desde m³" else 4, 0))

    # Contenedor dinámico de filas
    filas_rangos = ctk.CTkFrame(pad_rangos, fg_color=COLOR_BLANCO)
    filas_rangos.pack(fill="x", pady=(4, 8))

    _rangos_entries = []  # list of dicts: {desde, hasta, precio, desc, frame}

    def _cargar_rangos_existentes():
        """Carga rangos desde DB al abrir la pantalla."""
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute(
                "SELECT desde_m3, hasta_m3, precio_m3, descripcion "
                "FROM tarifas_excedente ORDER BY orden, desde_m3")
            filas_db = cur.fetchall()
        except Exception:
            filas_db = []
        finally:
            if 'con' in locals():
                con.close()
        for desde, hasta, precio, desc in filas_db:
            _agregar_fila_rango(
                str(desde), str(hasta) if hasta is not None else "",
                str(precio), desc or "")

    def _agregar_fila_rango(desde="", hasta="", precio="", desc=""):
        fila = ctk.CTkFrame(filas_rangos, fg_color=COLOR_FONDO, corner_radius=6, height=40)
        fila.pack(fill="x", pady=2)
        fila.pack_propagate(False)

        e_desde  = ctk.CTkEntry(fila, width=86, height=30, corner_radius=6,
                                 fg_color=COLOR_BLANCO, placeholder_text="0")
        e_hasta  = ctk.CTkEntry(fila, width=86, height=30, corner_radius=6,
                                 fg_color=COLOR_BLANCO, placeholder_text="∞")
        e_precio = ctk.CTkEntry(fila, width=86, height=30, corner_radius=6,
                                 fg_color=COLOR_BLANCO, placeholder_text="0.50")
        e_desc   = ctk.CTkEntry(fila, height=30, corner_radius=6,
                                 fg_color=COLOR_BLANCO, placeholder_text="Descripción opcional")

        e_desde.pack(side="left",  padx=(8, 4))
        e_hasta.pack(side="left",  padx=(0, 4))
        e_precio.pack(side="left", padx=(0, 4))
        e_desc.pack(side="left",   fill="x", expand=True, padx=(0, 4))

        aplicar_validacion_decimal(e_desde)
        aplicar_validacion_decimal(e_hasta)
        aplicar_validacion_decimal(e_precio)

        if desde:  e_desde.insert(0, desde)
        if hasta:  e_hasta.insert(0, hasta)
        if precio: e_precio.insert(0, precio)
        if desc:   e_desc.insert(0, desc)

        entrada = {"desde": e_desde, "hasta": e_hasta,
                   "precio": e_precio, "desc": e_desc, "frame": fila}
        _rangos_entries.append(entrada)

        def _eliminar():
            _rangos_entries.remove(entrada)
            fila.destroy()

        ctk.CTkButton(fila, text="✕", width=28, height=28, corner_radius=6,
                       fg_color=COLOR_ROJO, hover_color="#9B2C2C",
                       text_color=COLOR_BLANCO, font=("Arial", 11, "bold"),
                       command=_eliminar).pack(side="right", padx=6)

    # Botón agregar fila
    btns_rangos = ctk.CTkFrame(pad_rangos, fg_color=COLOR_BLANCO)
    btns_rangos.pack(fill="x", pady=(0, 4))
    ctk.CTkButton(btns_rangos, text="+ Agregar tramo", height=34, width=150,
                   corner_radius=8, fg_color=COLOR_AZUL_MARINO,
                   hover_color="#243F6B", font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=lambda: _agregar_fila_rango()).pack(side="left")

    lbl_rangos_msg = ctk.CTkLabel(btns_rangos, text="", font=FONT_SMALL,
                                   text_color=COLOR_VERDE_PAGO)
    lbl_rangos_msg.pack(side="left", padx=12)

    def _guardar_rangos():
        """Guarda los rangos de excedente en la tabla tarifas_excedente."""
        nuevos = []
        for i, entrada in enumerate(_rangos_entries):
            desde_s  = entrada["desde"].get().strip()
            hasta_s  = entrada["hasta"].get().strip()
            precio_s = entrada["precio"].get().strip()
            desc_s   = entrada["desc"].get().strip()
            if not desde_s or not precio_s:
                messagebox.showwarning("Datos incompletos",
                                       f"El tramo {i + 1} requiere 'Desde m³' y '$/m³'.")
                return
            try:
                desde_f  = float(desde_s)
                hasta_f  = float(hasta_s) if hasta_s else None
                precio_f = float(precio_s)
            except ValueError:
                messagebox.showwarning("Valor inválido",
                                       f"Los valores numéricos del tramo {i + 1} no son válidos.")
                return
            nuevos.append((desde_f, hasta_f, precio_f, desc_s, i))

        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("DELETE FROM tarifas_excedente")
            for desde_f, hasta_f, precio_f, desc_s, orden in nuevos:
                cur.execute(
                    "INSERT INTO tarifas_excedente "
                    "(desde_m3, hasta_m3, precio_m3, descripcion, orden) "
                    "VALUES (?,?,?,?,?)",
                    (desde_f, hasta_f, precio_f, desc_s or None, orden))
            con.commit()
            lbl_rangos_msg.configure(text="✓ Rangos guardados", text_color=COLOR_VERDE_PAGO)
            frame.after(3000, lambda: lbl_rangos_msg.configure(text=""))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar los rangos:\n{e}")
        finally:
            if 'con' in locals():
                con.close()

    ctk.CTkButton(btns_rangos, text="Guardar rangos", height=34, width=140,
                   corner_radius=8, fg_color=COLOR_VERDE_PAGO,
                   hover_color="#276749", font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=_guardar_rangos).pack(side="right")

    # Cargar rangos existentes al inicio
    _cargar_rangos_existentes()

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

        # Validar números
        for label, entry in [
            ("Tarifa básica", e_tarifa),
            ("M³ incluidos",  e_m3),
            ("Fecha límite",  e_fecha_limite),
            ("Mora valor",    e_mora_valor),
            ("Número inicial",e_num_inicial),
            ("Número actual", e_num_actual),
            ("Día generación",e_dia_gen),
        ]:
            val = entry.get().strip()
            if val:
                try:
                    float(val)
                except ValueError:
                    errores.append(f"'{label}' debe ser un número válido.")

        if errores:
            messagebox.showwarning("Datos incompletos",
                                   "\n".join(f"• {e}" for e in errores))
            return

        # Información de la comunidad
        guardar_config("nombre_comunidad",       nombre)
        guardar_config("municipio",              e_municipio.get().strip())
        guardar_config("telefono_organizacion",  e_telefono_org.get().strip())

        # Logo
        ruta_logo = e_logo.get().strip()
        guardar_config("ruta_logo", ruta_logo)

        # Categorías de vecino
        cats = e_categorias.get().strip()
        if cats:
            guardar_config("categorias_vecino", cats)

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

        # Tarifas y cobros
        if e_tarifa.get().strip():
            guardar_config("tarifa_basica",    e_tarifa.get().strip())
        if e_m3.get().strip():
            guardar_config("m3_incluidos",     e_m3.get().strip())
        if e_fecha_limite.get().strip():
            guardar_config("fecha_limite_pago", e_fecha_limite.get().strip())
        guardar_config("mora_tipo",  mora_tipo_var.get())
        if e_mora_valor.get().strip():
            guardar_config("mora_valor", e_mora_valor.get().strip())

        # Numeración de facturas
        if e_num_inicial.get().strip():
            guardar_config("num_factura_inicial", e_num_inicial.get().strip())
        if e_num_actual.get().strip():
            guardar_config("num_factura_actual",  e_num_actual.get().strip())
        if e_dia_gen.get().strip():
            guardar_config("dia_generacion_recibos", e_dia_gen.get().strip())

        messagebox.showinfo("Configuración Guardada",
                            "Todos los ajustes han sido guardados correctamente.")

    return frame
