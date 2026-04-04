import customtkinter as ctk
import sqlite3
import datetime
import threading
from tkinter import messagebox
import herramientas.logger as logger
import herramientas.whatsapp_pdf as wp
from herramientas.email_sender import enviar_correo_async, construir_cuerpo_recibo
from herramientas.db import (
    obtener_conexion, obtener_config,
    registrar_lectura, obtener_lectura_anterior,
    vecino_tiene_datos_completos
)
from licencia.bloqueador import verificar_accion
from pantallas.componentes import (
    topbar, badge, encabezado_tabla, mensaje_vacio,
    aplicar_validacion_decimal
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
    MESES_ES, TIPO_COBRO_MEDIDOR
)

COLOR_EMAIL   = "#6B46C1"
COLOR_MEDIDOR = "#553C9A"


def _mes_actual() -> tuple:
    hoy = datetime.date.today()
    return MESES_ES[hoy.month], hoy.year


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
    _periodo = {"mes": _mes_actual()[0], "anio": _mes_actual()[1]}

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

    # ── Panel de alerta de lecturas faltantes ─────────────────────────────────
    panel_lecturas = ctk.CTkFrame(contenido, fg_color="#FFFBEB", corner_radius=8, height=40)
    # Se muestra solo cuando hay medidores sin lectura

    # ── Stats row ─────────────────────────────────────────────────────────────
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

    lbl_sin_lectura = ctk.CTkLabel(stats_row, text="—", font=("Arial", 18, "bold"),
                                   text_color=COLOR_AMARILLO)
    lbl_sin_lectura.pack(side="left", padx=(0, 4))
    ctk.CTkLabel(stats_row, text="sin lectura (medidor)", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=(0, 24))

    lbl_sin_contacto_stat = ctk.CTkLabel(stats_row, text="—", font=("Arial", 18, "bold"),
                                         text_color=COLOR_TEXTO_MUTED)
    lbl_sin_contacto_stat.pack(side="left", padx=(0, 4))
    ctk.CTkLabel(stats_row, text="sin contacto", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left")

    leyenda = ctk.CTkFrame(stats_row, fg_color="transparent")
    leyenda.pack(side="right")
    ctk.CTkLabel(leyenda, text="🟢 WhatsApp", font=FONT_SMALL,
                 text_color=COLOR_VERDE_PAGO).pack(side="left", padx=8)
    ctk.CTkLabel(leyenda, text="🟣 Email", font=FONT_SMALL,
                 text_color=COLOR_EMAIL).pack(side="left", padx=8)
    ctk.CTkLabel(leyenda, text="🔵 Medidor", font=FONT_SMALL,
                 text_color=COLOR_MEDIDOR).pack(side="left", padx=8)

    tabla_card = ctk.CTkFrame(contenido, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(fill="both", expand=True)

    encabezado_tabla(tabla_card, [
        ("Vecino", 170), ("Teléfono / Email", 180), ("Lectura", 160),
        ("Deuda pendiente", 130), ("Estado envío", 110), ("Acciones", 170)
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
        panel_lecturas.pack_forget()
        for w in panel_lecturas.winfo_children():
            w.destroy()

        zona_id = filtro_zona["zona_id"]
        try:
            con = obtener_conexion()
            cur = con.cursor()

            q = ("SELECT v.id, v.nombre, v.telefono, v.email, v.cuota, v.tipo_cobro "
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

            # Envíos ya realizados este período
            cur.execute(
                f"SELECT vecino_id, canal FROM envios_recibos "
                f"WHERE mes=? AND anio=? AND vecino_id IN ({placeholders})",
                [mes_cobro(), anio_cobro()] + ids_vecinos
            )
            enviados_map: dict = {}
            for v_id_e, canal_e in cur.fetchall():
                enviados_map.setdefault(v_id_e, set()).add(canal_e)

            # Deudas pendientes (excluyendo el mes actual)
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
            deudas_map: dict = {}
            for v_id_d, mes_d, anio_d, monto_d in cur.fetchall():
                deudas_map.setdefault(v_id_d, []).append(
                    {"mes": mes_d, "anio": anio_d, "monto": monto_d})

            # Lecturas ya registradas este período (solo medidor)
            cur.execute(
                f"SELECT vecino_id, lectura_anterior, lectura_actual, consumo_m3, monto_total "
                f"FROM lecturas_medidor "
                f"WHERE mes=? AND anio=? AND vecino_id IN ({placeholders})",
                [mes_cobro(), anio_cobro()] + ids_vecinos
            )
            lecturas_map: dict = {}
            for row in cur.fetchall():
                lecturas_map[row[0]] = {
                    "anterior": row[1], "actual": row[2],
                    "consumo": row[3], "monto": row[4]
                }

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
        sin_lectura_count = 0
        sin_contacto     = []

        for v_id, nombre, telefono, email, cuota, tipo_cobro in datos_vecinos:
            canales_enviados = enviados_map.get(v_id, set())
            tiene_tel        = bool(telefono)
            tiene_email      = bool(email and "@" in email)
            deudas           = deudas_map.get(v_id, [])
            lectura          = lecturas_map.get(v_id)
            es_medidor       = tipo_cobro == TIPO_COBRO_MEDIDOR

            if es_medidor and not lectura:
                sin_lectura_count += 1

            if canales_enviados:
                enviados_count += 1
            elif tiene_tel or tiene_email:
                pendientes_count += 1
            else:
                sin_contacto.append(nombre)

            _renderizar_fila(
                v_id, nombre, telefono, email, cuota, tipo_cobro,
                deudas, canales_enviados,
                tiene_tel, tiene_email, lectura)

        lbl_enviados.configure(text=str(enviados_count))
        lbl_pendientes.configure(text=str(pendientes_count))
        lbl_sin_lectura.configure(text=str(sin_lectura_count))
        lbl_sin_contacto_stat.configure(text=str(len(sin_contacto)))
        lbl_sub.configure(
            text=f"Recibos de {mes_cobro()} {anio_cobro()} — "
                 f"{len(datos_vecinos)} vecinos activos")

        # Banner de lecturas faltantes
        if sin_lectura_count > 0:
            panel_lecturas.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(
                panel_lecturas,
                text=f"⚠️  {sin_lectura_count} vecino{'s' if sin_lectura_count > 1 else ''} "
                     f"con medidor sin lectura registrada este período. "
                     f"Ingrese la lectura antes de enviar su recibo.",
                font=FONT_SMALL, text_color="#92400E", justify="left"
            ).pack(anchor="w", padx=12, pady=8)

        if sin_contacto:
            panel_sin_contacto.pack(fill="x")
            ctk.CTkFrame(panel_sin_contacto, height=1,
                         fg_color=COLOR_BORDE).pack(fill="x")
            txt = "Sin teléfono ni email: " + ", ".join(sin_contacto)
            ctk.CTkLabel(panel_sin_contacto, text=txt, font=FONT_SMALL,
                         text_color="#92400E",
                         wraplength=700, justify="left").pack(
                anchor="w", padx=16, pady=8)

    def _renderizar_fila(v_id, nombre, telefono, email, cuota, tipo_cobro,
                         deudas, canales_enviados,
                         tiene_tel, tiene_email, lectura_reg):
        ya_enviado_wa    = "whatsapp" in canales_enviados
        ya_enviado_email = "email"    in canales_enviados
        alguno_enviado   = bool(canales_enviados)
        es_medidor       = tipo_cobro == TIPO_COBRO_MEDIDOR

        bg = "#F0FFF4" if alguno_enviado else (
            COLOR_BLANCO if (tiene_tel or tiene_email) else "#FAFAFA")

        fila_altura = 76 if es_medidor else 52
        fila = ctk.CTkFrame(lista_scroll, fg_color=bg, corner_radius=6,
                             height=fila_altura)
        fila.pack(fill="x", pady=2, padx=4)
        fila.pack_propagate(False)

        # Nombre + badge tipo
        col_nombre = ctk.CTkFrame(fila, fg_color="transparent", width=170)
        col_nombre.pack(side="left", padx=16)
        col_nombre.pack_propagate(False)
        ctk.CTkLabel(col_nombre, text=nombre, font=("Arial", 12, "bold"),
                     text_color=COLOR_TEXTO if (tiene_tel or tiene_email) else COLOR_TEXTO_MUTED,
                     anchor="w").pack(anchor="w")
        if es_medidor:
            ctk.CTkLabel(col_nombre, text="Con medidor", font=("Arial", 10),
                         text_color=COLOR_MEDIDOR, anchor="w").pack(anchor="w")

        # Contacto
        col_contacto = ctk.CTkFrame(fila, fg_color="transparent", width=180)
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

        # Columna lectura (solo medidor)
        col_lectura = ctk.CTkFrame(fila, fg_color="transparent", width=160)
        col_lectura.pack(side="left", padx=4)
        col_lectura.pack_propagate(False)

        lectura_ref = {"datos": lectura_reg}  # mutable para callbacks

        if es_medidor:
            if lectura_reg:
                # Ya tiene lectura registrada
                ctk.CTkLabel(col_lectura,
                             text=f"Ant: {lectura_reg['anterior']:.1f}  →  Act: {lectura_reg['actual']:.1f}",
                             font=("Arial", 10), text_color=COLOR_MEDIDOR,
                             anchor="w").pack(anchor="w")
                ctk.CTkLabel(col_lectura,
                             text=f"Consumo: {lectura_reg['consumo']:.1f} m³  |  ${lectura_reg['monto']:.2f}",
                             font=("Arial", 10, "bold"), text_color=COLOR_VERDE_PAGO,
                             anchor="w").pack(anchor="w")
            else:
                # Sin lectura: mostrar campo de entrada
                lectura_ant = obtener_lectura_anterior(v_id, mes_cobro(), anio_cobro())
                ctk.CTkLabel(col_lectura,
                             text=f"Anterior: {lectura_ant:.1f} m³",
                             font=("Arial", 10), text_color=COLOR_TEXTO_MUTED,
                             anchor="w").pack(anchor="w")
                fila_entry = ctk.CTkFrame(col_lectura, fg_color="transparent")
                fila_entry.pack(anchor="w", fill="x")
                ctk.CTkLabel(fila_entry, text="Actual:", font=("Arial", 10),
                             text_color=COLOR_TEXTO_MUTED).pack(side="left")
                e_actual = ctk.CTkEntry(fila_entry, width=70, height=26,
                                        corner_radius=6, fg_color=COLOR_BLANCO,
                                        placeholder_text="m³")
                e_actual.pack(side="left", padx=4)
                aplicar_validacion_decimal(e_actual)

                lbl_calc_lectura = ctk.CTkLabel(col_lectura, text="",
                                                font=("Arial", 10), text_color=COLOR_AMARILLO,
                                                anchor="w")
                lbl_calc_lectura.pack(anchor="w")

                def _registrar(vid=v_id, ant=lectura_ant, entry=e_actual,
                               lbl=lbl_calc_lectura, lref=lectura_ref):
                    val_s = entry.get().strip()
                    if not val_s:
                        return
                    try:
                        val_f = float(val_s.replace(",", "."))
                    except ValueError:
                        lbl.configure(text="Valor inválido", text_color=COLOR_ROJO)
                        return
                    if val_f < ant:
                        lbl.configure(text=f"< anterior ({ant:.1f})", text_color=COLOR_ROJO)
                        return
                    uid = get_usuario_id() if callable(get_usuario_id) else 1
                    ok, msg, monto = registrar_lectura(
                        vid, mes_cobro(), anio_cobro(), ant, val_f, uid)
                    if ok:
                        lref["datos"] = {
                            "anterior": ant, "actual": val_f,
                            "consumo": round(val_f - ant, 3), "monto": monto
                        }
                        lbl.configure(text=f"✓ ${monto:.2f}", text_color=COLOR_VERDE_PAGO)
                    else:
                        lbl.configure(text=f"Error: {msg}", text_color=COLOR_ROJO)

                ctk.CTkButton(fila_entry, text="✓", width=26, height=26,
                               corner_radius=6, fg_color=COLOR_VERDE_PAGO,
                               hover_color="#276749", text_color=COLOR_BLANCO,
                               font=("Arial", 11, "bold"),
                               command=_registrar).pack(side="left")
        else:
            ctk.CTkLabel(col_lectura, text="Cuota fija",
                         font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(col_lectura, text=f"${cuota:.2f}/mes",
                         font=("Arial", 11, "bold"), text_color=COLOR_AZUL_MARINO,
                         anchor="w").pack(anchor="w")

        # Deuda
        col_deuda = ctk.CTkFrame(fila, fg_color="transparent", width=130)
        col_deuda.pack(side="left", padx=4)
        col_deuda.pack_propagate(False)
        if deudas:
            total_deuda = sum(d["monto"] for d in deudas)
            deuda_txt = f"${total_deuda:.2f} ({len(deudas)} mes{'es' if len(deudas) > 1 else ''})"
            badge(col_deuda, deuda_txt, COLOR_BADGE_ROJO_BG,
                  COLOR_BADGE_ROJO_TEXT, width=128).pack(anchor="w")
        else:
            ctk.CTkLabel(col_deuda, text="Al día", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED,
                         anchor="w").pack(anchor="w")

        # Estado de envío
        estado_frame = ctk.CTkFrame(fila, fg_color="transparent", width=110)
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

        # Datos del vecino para completitud
        completo, faltantes = vecino_tiene_datos_completos(v_id)

        # Botones de acción
        btns = ctk.CTkFrame(fila, fg_color="transparent")
        btns.pack(side="right", padx=10)

        def _tooltip_incompleto():
            messagebox.showwarning(
                "Datos incompletos",
                f"El vecino no puede recibir su recibo porque le faltan:\n"
                + "\n".join(f"  • {f}" for f in faltantes)
                + "\n\nEdite el vecino para completar su perfil.")

        if not completo:
            ctk.CTkButton(
                btns, text="⚠ Incompleto", width=108, height=30, corner_radius=6,
                fg_color=COLOR_BADGE_AMBER_BG, text_color=COLOR_BADGE_AMBER_TEXT,
                hover_color="#FEF3C7", border_width=1,
                border_color=COLOR_AMARILLO, font=FONT_SMALL,
                command=_tooltip_incompleto
            ).pack(side="left", padx=(0, 4))
        else:
            if tiene_tel:
                # Para medidor: bloquear si no tiene lectura
                def _check_y_enviar_wa(lref=lectura_ref, vid=v_id, nom=nombre,
                                       tel=telefono, em=email, c=cuota, d=deudas):
                    if es_medidor and not lref["datos"]:
                        messagebox.showwarning(
                            "Pendiente de lectura",
                            "Ingrese la lectura actual del medidor antes de enviar el recibo.")
                        return
                    _enviar_whatsapp(vid, nom, tel, em, c, d, lref["datos"])

                lbl_wa = "Reenviar WA" if ya_enviado_wa else "WhatsApp"
                col_wa = "transparent" if ya_enviado_wa else COLOR_VERDE_PAGO
                txt_wa = COLOR_VERDE_PAGO if ya_enviado_wa else COLOR_BLANCO
                ctk.CTkButton(
                    btns, text=lbl_wa, width=96, height=30, corner_radius=6,
                    fg_color=col_wa,
                    hover_color="#276749" if not ya_enviado_wa else "#E6F4EA",
                    border_width=1, border_color=COLOR_VERDE_PAGO,
                    text_color=txt_wa, font=FONT_SMALL,
                    command=_check_y_enviar_wa
                ).pack(side="left", padx=(0, 4))

            if tiene_email:
                def _check_y_enviar_email(lref=lectura_ref, vid=v_id, nom=nombre,
                                          tel=telefono, em=email, c=cuota, d=deudas):
                    if es_medidor and not lref["datos"]:
                        messagebox.showwarning(
                            "Pendiente de lectura",
                            "Ingrese la lectura actual del medidor antes de enviar el recibo.")
                        return
                    _enviar_email(vid, nom, tel, em, c, d, lref["datos"])

                lbl_em = "Reenviar Email" if ya_enviado_email else "Email"
                col_em = "transparent"    if ya_enviado_email else COLOR_EMAIL
                txt_em = COLOR_EMAIL if ya_enviado_email else COLOR_BLANCO
                ctk.CTkButton(
                    btns, text=lbl_em, width=96, height=30, corner_radius=6,
                    fg_color=col_em,
                    hover_color="#553C9A" if not ya_enviado_email else "#FAF5FF",
                    border_width=1, border_color=COLOR_EMAIL,
                    text_color=txt_em, font=FONT_SMALL,
                    command=_check_y_enviar_email
                ).pack(side="left")
        lista_scroll.update_idletasks()

    # ── Envío WhatsApp ─────────────────────────────────────────────────────────
    def _enviar_whatsapp(v_id, nombre, telefono, email, cuota, deudas, lectura_datos):
        if not verificar_accion("enviar_recibo"):
            return

        monto_mes = lectura_datos["monto"] if lectura_datos else cuota
        total         = monto_mes + sum(d["monto"] for d in deudas)
        numero_recibo = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        wp.generar_pdf_recibo_pendiente(
            nombre, mes_cobro(), anio_cobro(), monto_mes, deudas, total,
            numero_recibo, lectura_datos=lectura_datos)

        mensaje = wp.construir_mensaje_recibo_pendiente(
            nombre, mes_cobro(), anio_cobro(), monto_mes, deudas, total, numero_recibo)
        wp.abrir_whatsapp(telefono, mensaje)

        uid = get_usuario_id() if callable(get_usuario_id) else 1
        _registrar_envio(v_id, mes_cobro(), anio_cobro(), "whatsapp", uid)
        cargar_vecinos()

    # ── Envío Email ────────────────────────────────────────────────────────────
    def _enviar_email(v_id, nombre, telefono, email, cuota, deudas, lectura_datos):
        if not verificar_accion("enviar_recibo"):
            return

        if not obtener_config("smtp_usuario", ""):
            messagebox.showwarning(
                "Correo no configurado",
                "Configure el servidor de correo (SMTP) en\n"
                "Configuración → Correo electrónico\n"
                "antes de enviar recibos por email.")
            return

        monto_mes     = lectura_datos["monto"] if lectura_datos else cuota
        total         = monto_mes + sum(d["monto"] for d in deudas)
        numero_recibo = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        cajero        = get_usuario_nombre() if callable(get_usuario_nombre) else "Sistema"
        comunidad     = obtener_config("nombre_comunidad", "Sistema de Agua")

        pdf_path = wp.generar_pdf_recibo_pendiente(
            nombre, mes_cobro(), anio_cobro(), monto_mes, deudas, total,
            numero_recibo, lectura_datos=lectura_datos)

        cuerpo_html = construir_cuerpo_recibo(
            nombre_vecino=nombre,
            mes=mes_cobro(),
            anio=anio_cobro(),
            monto_cuota=monto_mes,
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
