import customtkinter as ctk
import sqlite3
import datetime
import threading
from tkinter import messagebox
import herramientas.logger as logger
import herramientas.whatsapp_pdf as wp
from herramientas.email_sender import enviar_correo_async, construir_cuerpo_recibo
from herramientas.db import obtener_conexion, obtener_config
from licencia.bloqueador import verificar_accion
from pantallas.componentes import (
    topbar, badge, encabezado_tabla, mensaje_vacio
)
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_TEXTO,
    COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO,
    COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
    COLOR_BADGE_ROJO_BG, COLOR_BADGE_ROJO_TEXT,
    COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT,
    COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_BODY, FONT_SMALL, FONT_LABEL,
    MESES_ES
)

COLOR_EMAIL = "#6B46C1"


def _mes_anterior() -> tuple[str, int]:
    hoy = datetime.date.today()
    if hoy.month == 1:
        return MESES_ES[12], hoy.year - 1
    return MESES_ES[hoy.month - 1], hoy.year


def _registrar_envio(vecino_id: int, mes: str, anio: int,
                     canal: str, usuario_id: int) -> None:
    try:
        con = obtener_conexion()
        con.execute(
            "INSERT INTO envios_recibos (vecino_id, mes, anio, canal, usuario_id) "
            "VALUES (?,?,?,?,?)",
            (vecino_id, mes, anio, canal, usuario_id))
        con.commit()
    except Exception:
        pass
    finally:
        if 'con' in locals():
            con.close()


def crear_pantalla(parent_frame, get_usuario_id, get_usuario_nombre):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    _periodo = {"mes": _mes_anterior()[0], "anio": _mes_anterior()[1]}

    def mes_cobro():  return _periodo["mes"]
    def anio_cobro(): return _periodo["anio"]

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Envío de Recibos",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    lbl_sub = ctk.CTkLabel(
        izq,
        text=f"Recibos de {mes_cobro()} {anio_cobro()} — cargando...",
        font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
    lbl_sub.pack(anchor="w")

    der = ctk.CTkFrame(bar, fg_color="transparent")
    der.pack(side="right", padx=20)

    hoy = datetime.date.today()
    meses_nombres = list(MESES_ES.values())
    lista_anios   = [str(a) for a in range(2025, hoy.year + 2)]

    combo_anio_env = ctk.CTkComboBox(der, values=lista_anios, width=76, state="readonly")
    combo_anio_env.pack(side="right", padx=(0, 4))
    combo_anio_env.set(str(_periodo["anio"]))

    combo_mes_env = ctk.CTkComboBox(der, values=meses_nombres, width=110, state="readonly")
    combo_mes_env.pack(side="right", padx=(0, 2))
    combo_mes_env.set(_periodo["mes"])

    ctk.CTkLabel(der, text="Período:", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="right", padx=(0, 4))

    def _cambiar_periodo():
        _periodo["mes"]  = combo_mes_env.get()
        _periodo["anio"] = int(combo_anio_env.get())
        cargar_vecinos()

    ctk.CTkButton(der, text="Cargar", height=30, width=60, corner_radius=6,
                  fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                  text_color=COLOR_BLANCO, font=FONT_SMALL,
                  command=_cambiar_periodo).pack(side="right", padx=(0, 12))

    filtro_zona = {"zona_id": None}
    zonas_disponibles = []
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("SELECT id, nombre FROM zonas WHERE activa=1 ORDER BY orden, nombre")
        zonas_disponibles = cur.fetchall()
        con.close()
    except Exception:
        pass

    if zonas_disponibles:
        nombres_zonas = ["Todas las zonas"] + [z[1] for z in zonas_disponibles]
        ids_zonas     = [None] + [z[0] for z in zonas_disponibles]
        combo_zona = ctk.CTkComboBox(
            der, values=nombres_zonas, width=160, state="readonly",
            command=lambda v: _filtrar_zona(v, nombres_zonas, ids_zonas))
        combo_zona.pack(side="right", padx=8)
        combo_zona.set("Todas las zonas")
        ctk.CTkLabel(der, text="Zona:", font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED).pack(side="right")

    def _filtrar_zona(valor, nombres, ids):
        idx = nombres.index(valor) if valor in nombres else 0
        filtro_zona["zona_id"] = ids[idx]
        cargar_vecinos()

    # ── Contenido ──────────────────────────────────────────────────────────────
    contenido = ctk.CTkFrame(frame, fg_color="transparent")
    contenido.pack(fill="both", expand=True, padx=24, pady=16)

    stats_row = ctk.CTkFrame(contenido, fg_color="transparent")
    stats_row.pack(fill="x", pady=(0, 12))

    lbl_enviados = ctk.CTkLabel(stats_row, text="—", font=("Arial", 18, "bold"),
                                text_color=COLOR_VERDE_PAGO)
    lbl_enviados.pack(side="left", padx=(0, 4))
    ctk.CTkLabel(stats_row, text="enviados", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=(0, 24))

    lbl_pendientes = ctk.CTkLabel(stats_row, text="—", font=("Arial", 18, "bold"),
                                  text_color=COLOR_AZUL_MARINO)
    lbl_pendientes.pack(side="left", padx=(0, 4))
    ctk.CTkLabel(stats_row, text="pendientes", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=(0, 24))

    lbl_sin_contacto = ctk.CTkLabel(stats_row, text="—", font=("Arial", 18, "bold"),
                                    text_color=COLOR_AMARILLO)
    lbl_sin_contacto.pack(side="left", padx=(0, 4))
    ctk.CTkLabel(stats_row, text="sin contacto", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left")

    leyenda = ctk.CTkFrame(stats_row, fg_color="transparent")
    leyenda.pack(side="right")
    ctk.CTkLabel(leyenda, text="🟢 WhatsApp", font=FONT_SMALL,
                 text_color=COLOR_VERDE_PAGO).pack(side="left", padx=8)
    ctk.CTkLabel(leyenda, text="🟣 Email", font=FONT_SMALL,
                 text_color=COLOR_EMAIL).pack(side="left", padx=8)

    tabla_card = ctk.CTkFrame(contenido, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(fill="both", expand=True)

    encabezado_tabla(tabla_card, [
        ("Vecino", 190), ("Teléfono / Email", 200), ("Deuda pendiente", 160),
        ("Estado envío", 120), ("Acciones", 180)
    ])

    lista_scroll = ctk.CTkScrollableFrame(tabla_card, fg_color=COLOR_FONDO,
                                          corner_radius=0)
    lista_scroll.pack(fill="both", expand=True, padx=1, pady=1)

    panel_sin_contacto = ctk.CTkFrame(tabla_card, fg_color="#FFFBEB", corner_radius=0)

    # ── Datos ──────────────────────────────────────────────────────────────────
    datos_vecinos = []

    def cargar_vecinos():
        nonlocal datos_vecinos
        for w in lista_scroll.winfo_children():
            w.destroy()
        for w in panel_sin_contacto.winfo_children():
            w.destroy()
        panel_sin_contacto.pack_forget()

        zona_id = filtro_zona["zona_id"]
        try:
            con = obtener_conexion()
            cur = con.cursor()

            q = ("SELECT v.id, v.nombre, v.telefono, v.email, v.cuota "
                 "FROM vecinos v WHERE v.activo=1")
            params = []
            if zona_id:
                q += " AND v.zona_id=?"
                params.append(zona_id)
            q += " ORDER BY v.nombre"
            cur.execute(q, params)
            datos_vecinos = cur.fetchall()

            if not datos_vecinos:
                con.close()
                mensaje_vacio(lista_scroll, "No hay vecinos activos.")
                return

            ids_vecinos  = [v[0] for v in datos_vecinos]
            placeholders = ",".join("?" * len(ids_vecinos))

            cur.execute(
                f"SELECT vecino_id, canal FROM envios_recibos "
                f"WHERE mes=? AND anio=? AND vecino_id IN ({placeholders})",
                [mes_cobro(), anio_cobro()] + ids_vecinos
            )
            enviados_map: dict[int, set] = {}
            for v_id_e, canal_e in cur.fetchall():
                enviados_map.setdefault(v_id_e, set()).add(canal_e)

            cur.execute(
                f"""SELECT vecino_id, mes, anio, monto FROM recibos
                    WHERE estado_pago='Pendiente'
                      AND vecino_id IN ({placeholders})
                      AND NOT (mes=? AND anio=?)
                    ORDER BY anio,
                      CASE mes
                        WHEN 'Enero' THEN 1 WHEN 'Febrero' THEN 2 WHEN 'Marzo' THEN 3
                        WHEN 'Abril' THEN 4 WHEN 'Mayo' THEN 5 WHEN 'Junio' THEN 6
                        WHEN 'Julio' THEN 7 WHEN 'Agosto' THEN 8 WHEN 'Septiembre' THEN 9
                        WHEN 'Octubre' THEN 10 WHEN 'Noviembre' THEN 11 WHEN 'Diciembre' THEN 12
                      END""",
                ids_vecinos + [mes_cobro(), anio_cobro()]
            )
            deudas_map: dict[int, list] = {}
            for v_id_d, mes_d, anio_d, monto_d in cur.fetchall():
                deudas_map.setdefault(v_id_d, []).append(
                    {"mes": mes_d, "anio": anio_d, "monto": monto_d})

        except sqlite3.Error as e:
            logger.registrar("envio_recibos.py", "cargar_vecinos", e)
            datos_vecinos = []
        finally:
            if 'con' in locals():
                con.close()

        if not datos_vecinos:
            mensaje_vacio(lista_scroll, "No hay vecinos activos.")
            return

        enviados_count   = 0
        pendientes_count = 0
        sin_contacto     = []

        for v_id, nombre, telefono, email, cuota in datos_vecinos:
            canales_enviados = enviados_map.get(v_id, set())
            tiene_tel        = bool(telefono)
            tiene_email      = bool(email and "@" in email)
            deudas           = deudas_map.get(v_id, [])
            total_deuda      = sum(d["monto"] for d in deudas)

            if canales_enviados:
                enviados_count += 1
            elif tiene_tel or tiene_email:
                pendientes_count += 1
            else:
                sin_contacto.append(nombre)

            _renderizar_fila(
                v_id, nombre, telefono, email, cuota,
                deudas, total_deuda, canales_enviados,
                tiene_tel, tiene_email)

        lbl_enviados.configure(text=str(enviados_count))
        lbl_pendientes.configure(text=str(pendientes_count))
        lbl_sin_contacto.configure(text=str(len(sin_contacto)))
        lbl_sub.configure(
            text=f"Recibos de {mes_cobro()} {anio_cobro()} — "
                 f"{len(datos_vecinos)} vecinos activos")

        if sin_contacto:
            panel_sin_contacto.pack(fill="x")
            ctk.CTkFrame(panel_sin_contacto, height=1,
                         fg_color=COLOR_BORDE).pack(fill="x")
            txt = "Sin teléfono ni email: " + ", ".join(sin_contacto)
            ctk.CTkLabel(panel_sin_contacto, text=txt, font=FONT_SMALL,
                         text_color="#92400E",
                         wraplength=700, justify="left").pack(
                anchor="w", padx=16, pady=8)

    def _renderizar_fila(v_id, nombre, telefono, email, cuota,
                         deudas, total_deuda, canales_enviados,
                         tiene_tel, tiene_email):
        ya_enviado_wa    = "whatsapp" in canales_enviados
        ya_enviado_email = "email"    in canales_enviados
        alguno_enviado   = bool(canales_enviados)

        bg = "#F0FFF4" if alguno_enviado else (
            COLOR_BLANCO if (tiene_tel or tiene_email) else "#FAFAFA")
        fila = ctk.CTkFrame(lista_scroll, fg_color=bg, corner_radius=6, height=52)
        fila.pack(fill="x", pady=2, padx=4)
        fila.pack_propagate(False)

        # Nombre
        ctk.CTkLabel(fila, text=nombre, font=("Arial", 12, "bold"),
                     text_color=COLOR_TEXTO if (tiene_tel or tiene_email) else COLOR_TEXTO_MUTED,
                     width=190, anchor="w").pack(side="left", padx=16)

        # Contacto
        col_contacto = ctk.CTkFrame(fila, fg_color="transparent", width=200)
        col_contacto.pack(side="left", padx=4)
        col_contacto.pack_propagate(False)
        ctk.CTkLabel(col_contacto,
                     text=f"📱 {telefono}" if telefono else "📱 —",
                     font=FONT_SMALL,
                     text_color=COLOR_TEXTO if tiene_tel else COLOR_TEXTO_MUTED,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(col_contacto,
                     text=f"✉️ {email}" if email else "✉️ —",
                     font=FONT_SMALL,
                     text_color=COLOR_TEXTO if tiene_email else COLOR_TEXTO_MUTED,
                     anchor="w").pack(anchor="w")

        # Deuda
        if deudas:
            deuda_txt = f"${total_deuda:.2f} ({len(deudas)} mes{'es' if len(deudas) > 1 else ''})"
            badge(fila, deuda_txt, COLOR_BADGE_ROJO_BG,
                  COLOR_BADGE_ROJO_TEXT, width=160).pack(side="left", padx=4)
        else:
            ctk.CTkLabel(fila, text="Al día", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED,
                         width=160, anchor="w").pack(side="left", padx=4)

        # Estado de envío
        estado_frame = ctk.CTkFrame(fila, fg_color="transparent", width=120)
        estado_frame.pack(side="left", padx=4)
        estado_frame.pack_propagate(False)
        if ya_enviado_wa:
            badge(estado_frame, "✓ WhatsApp",
                  COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT, width=100).pack(anchor="w")
        if ya_enviado_email:
            badge(estado_frame, "✓ Email",
                  "#F5F3FF", COLOR_EMAIL, width=80).pack(anchor="w", pady=(2, 0))
        if not alguno_enviado and not (tiene_tel or tiene_email):
            badge(estado_frame, "Sin contacto",
                  COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT, width=100).pack(anchor="w")

        # Botones de acción
        btns = ctk.CTkFrame(fila, fg_color="transparent")
        btns.pack(side="right", padx=10)

        if tiene_tel:
            lbl_wa = "Reenviar WA" if ya_enviado_wa else "WhatsApp"
            col_wa = "transparent" if ya_enviado_wa else COLOR_VERDE_PAGO
            txt_wa = COLOR_VERDE_PAGO if ya_enviado_wa else COLOR_BLANCO
            ctk.CTkButton(
                btns, text=lbl_wa, width=96, height=30, corner_radius=6,
                fg_color=col_wa,
                hover_color="#276749" if not ya_enviado_wa else "#E6F4EA",
                border_width=1, border_color=COLOR_VERDE_PAGO,
                text_color=txt_wa, font=FONT_SMALL,
                command=lambda _id=v_id, _n=nombre, _t=telefono, _e=email, _c=cuota, _d=deudas:
                    _enviar_whatsapp(_id, _n, _t, _e, _c, _d)
            ).pack(side="left", padx=(0, 4))

        if tiene_email:
            lbl_em = "Reenviar Email" if ya_enviado_email else "Email"
            col_em = "transparent"    if ya_enviado_email else COLOR_EMAIL
            txt_em = COLOR_EMAIL if ya_enviado_email else COLOR_BLANCO
            ctk.CTkButton(
                btns, text=lbl_em, width=96, height=30, corner_radius=6,
                fg_color=col_em,
                hover_color="#553C9A" if not ya_enviado_email else "#FAF5FF",
                border_width=1, border_color=COLOR_EMAIL,
                text_color=txt_em, font=FONT_SMALL,
                command=lambda _id=v_id, _n=nombre, _t=telefono, _e=email, _c=cuota, _d=deudas:
                    _enviar_email(_id, _n, _t, _e, _c, _d)
            ).pack(side="left")

    # ── Envío WhatsApp ─────────────────────────────────────────────────────────
    def _enviar_whatsapp(v_id, nombre, telefono, email, cuota, deudas):
        if not verificar_accion("enviar_recibo"):
            return

        total         = cuota + sum(d["monto"] for d in deudas)
        numero_recibo = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        wp.generar_pdf_recibo_pendiente(
            nombre, mes_cobro(), anio_cobro(), cuota, deudas, total, numero_recibo)

        mensaje = wp.construir_mensaje_recibo_pendiente(
            nombre, mes_cobro(), anio_cobro(), cuota, deudas, total, numero_recibo)
        wp.abrir_whatsapp(telefono, mensaje)

        uid = get_usuario_id() if callable(get_usuario_id) else 1
        _registrar_envio(v_id, mes_cobro(), anio_cobro(), "whatsapp", uid)
        cargar_vecinos()

    # ── Envío Email ────────────────────────────────────────────────────────────
    def _enviar_email(v_id, nombre, telefono, email, cuota, deudas):
        if not verificar_accion("enviar_recibo"):
            return

        if not obtener_config("smtp_usuario", ""):
            messagebox.showwarning(
                "Correo no configurado",
                "Configure el servidor de correo (SMTP) en\n"
                "Configuración → Correo electrónico\n"
                "antes de enviar recibos por email.")
            return

        total         = cuota + sum(d["monto"] for d in deudas)
        numero_recibo = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        cajero        = get_usuario_nombre() if callable(get_usuario_nombre) else "Sistema"
        comunidad     = obtener_config("nombre_comunidad", "Sistema de Agua")

        pdf_path = wp.generar_pdf_recibo_pendiente(
            nombre, mes_cobro(), anio_cobro(), cuota, deudas, total, numero_recibo)

        cuerpo_html = construir_cuerpo_recibo(
            nombre_vecino=nombre,
            mes=mes_cobro(),
            anio=anio_cobro(),
            monto_cuota=cuota,
            deudas_pendientes=deudas,
            total=total,
            cajero=cajero,
            nombre_comunidad=comunidad,
            numero_recibo=numero_recibo
        )

        asunto = f"Recibo de agua — {mes_cobro()} {anio_cobro()} | {comunidad}"
        uid    = get_usuario_id() if callable(get_usuario_id) else 1

        def _al_terminar(ok, err):
            if ok:
                _registrar_envio(v_id, mes_cobro(), anio_cobro(), "email", uid)
                frame.after(0, cargar_vecinos)
            else:
                frame.after(0, lambda: messagebox.showerror(
                    "Error al enviar email",
                    f"No se pudo enviar el correo a {nombre}:\n\n{err}\n\n"
                    "Verifique la configuración SMTP en Configuración."))

        enviar_correo_async(
            destinatario=email,
            asunto=asunto,
            cuerpo_html=cuerpo_html,
            adjunto_pdf=pdf_path,
            callback=_al_terminar
        )

        messagebox.showinfo(
            "Enviando...",
            f"Enviando correo a {nombre} ({email}).\n"
            "La lista se actualizará al terminar.")

    frame.after(200, cargar_vecinos)
    return frame