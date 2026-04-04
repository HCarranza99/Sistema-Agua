import customtkinter as ctk
import sqlite3
import datetime
from tkinter import messagebox
import herramientas.logger as logger
import herramientas.whatsapp_pdf as wp
from herramientas.email_sender import enviar_correo_async, construir_cuerpo_recibo
from herramientas.db import obtener_conexion, obtener_config
from licencia.bloqueador import verificar_accion
from pantallas.componentes import (
    topbar, stat_card, badge, encabezado_tabla, mensaje_vacio,
    aplicar_validacion_decimal
)
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_NARANJA,
    COLOR_TEXTO, COLOR_TEXTO_MUTED, COLOR_GRIS_CLARO,
    COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
    COLOR_BADGE_ROJO_BG, COLOR_BADGE_ROJO_TEXT,
    COLOR_BADGE_GRIS_BG, COLOR_BADGE_GRIS_TEXT,
    COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_BODY,
    FONT_SMALL, FONT_LABEL, FONT_STAT_VAL, FONT_STAT_LBL,
    MESES_ES
)


def _darken(hex_color):
    try:
        r = max(0, int(hex_color[1:3], 16) - 20)
        g = max(0, int(hex_color[3:5], 16) - 20)
        b = max(0, int(hex_color[5:7], 16) - 20)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _obtener_stats():
    hoy       = datetime.date.today().strftime("%Y-%m-%d")
    mes_actual = datetime.date.today().strftime("%Y-%m")
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(monto_cobrado),0) FROM transacciones "
            "WHERE date(fecha_cobro)=?", (hoy,))
        total_hoy = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM transacciones WHERE date(fecha_cobro)=?", (hoy,))
        pagos_hoy = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM vecinos WHERE activo=1")
        total_vecinos = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(DISTINCT vecino_id) FROM recibos WHERE estado_pago='Pendiente'")
        con_deuda = cur.fetchone()[0]
        cur.execute(
            "SELECT COALESCE(SUM(monto_cobrado),0) FROM transacciones "
            "WHERE strftime('%Y-%m',fecha_cobro)=?", (mes_actual,))
        total_mes = cur.fetchone()[0]
        return total_hoy, pagos_hoy, total_vecinos, con_deuda, total_mes
    except Exception:
        return 0, 0, 0, 0, 0
    finally:
        if 'con' in locals():
            con.close()


def _es_mes_atrasado(mes: str, anio: int) -> bool:
    """Retorna True si el mes del recibo es anterior al mes actual."""
    hoy = datetime.date.today()
    meses_inv = {v: k for k, v in MESES_ES.items()}
    num_mes = meses_inv.get(mes, 0)
    if num_mes == 0:
        return False
    fecha_recibo = datetime.date(anio, num_mes, 1)
    fecha_actual = datetime.date(hoy.year, hoy.month, 1)
    return fecha_recibo < fecha_actual


def crear_pantalla(parent_frame, get_usuario_actual_id, get_usuario_actual_rol):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    hoy_str = datetime.date.today().strftime("%A, %d de %B %Y")

    estado = {
        "vecino_id":    None,
        "checkboxes":   [],
        "cargos_extra": [],   # [{recibo_id, tipo, descripcion, monto}]
    }

    # ── Topbar ────────────────────────────────────────────────────────────────
    topbar(frame, "Registro de Pagos", hoy_str)

    # ── Contenido ─────────────────────────────────────────────────────────────
    contenido = ctk.CTkFrame(frame, fg_color="transparent")
    contenido.pack(fill="both", expand=True, padx=24, pady=20)

    # Stats
    stats_frame = ctk.CTkFrame(contenido, fg_color="transparent")
    stats_frame.pack(fill="x", pady=(0, 16))

    total_hoy, pagos_hoy, total_vecinos, con_deuda, total_mes = _obtener_stats()

    stat_card(stats_frame, "Recaudado hoy", f"${total_hoy:.2f}",
              f"+{pagos_hoy} pagos registrados", True).grid(
        row=0, column=0, sticky="nsew", padx=(0, 8))
    stat_card(stats_frame, "Vecinos activos", str(total_vecinos)).grid(
        row=0, column=1, sticky="nsew", padx=(0, 8))
    stat_card(stats_frame, "Con deuda", str(con_deuda),
              f"{(con_deuda/total_vecinos*100):.1f}% del total" if total_vecinos else "",
              False).grid(row=0, column=2, sticky="nsew", padx=(0, 8))
    stat_card(stats_frame, "Recaudado este mes", f"${total_mes:.2f}").grid(
        row=0, column=3, sticky="nsew")
    for i in range(4):
        stats_frame.grid_columnconfigure(i, weight=1)

    # Buscador
    search_frame = ctk.CTkFrame(contenido, fg_color=COLOR_BLANCO,
                                 corner_radius=10, height=50)
    search_frame.pack(fill="x", pady=(0, 12))
    search_frame.pack_propagate(False)
    ctk.CTkLabel(search_frame, text="⌕", font=("Arial", 18),
                 text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=14)
    entrada_busqueda = ctk.CTkEntry(
        search_frame, placeholder_text="Buscar vecino por nombre o DUI...",
        border_width=0, fg_color="transparent", font=FONT_BODY, height=44)
    entrada_busqueda.pack(side="left", fill="x", expand=True)
    btn_limpiar = ctk.CTkButton(
        search_frame, text="✕", width=36, height=36, corner_radius=8,
        fg_color="transparent", hover_color=COLOR_FONDO,
        text_color=COLOR_TEXTO_MUTED, font=("Arial", 14),
        command=lambda: limpiar_busqueda())
    btn_limpiar.pack(side="right", padx=6)
    btn_limpiar.pack_forget()

    # Sugerencias
    marco_sugerencias = ctk.CTkScrollableFrame(
        contenido, fg_color=COLOR_BLANCO, border_width=1,
        border_color=COLOR_BORDE, corner_radius=8, height=130, width=500)

    # Tarjeta principal con tabla
    tarjeta = ctk.CTkFrame(contenido, fg_color=COLOR_BLANCO, corner_radius=10)
    tarjeta.pack(fill="both", expand=True)

    encabezado_tabla(tarjeta, [
        ("Mes", 150), ("Año", 70), ("Monto", 90), ("Estado", 110), ("Cargos extra", 200)
    ])

    marco_tabla = ctk.CTkScrollableFrame(tarjeta, fg_color=COLOR_FONDO, corner_radius=0)
    marco_tabla.pack(fill="both", expand=True, padx=1, pady=1)
    mensaje_vacio(marco_tabla, "Use la barra de búsqueda para encontrar un vecino...")

    # ── Pie de pantalla ────────────────────────────────────────────────────────
    pie = ctk.CTkFrame(tarjeta, fg_color=COLOR_BLANCO, height=72)
    pie.pack(fill="x")
    pie.pack_propagate(False)
    ctk.CTkFrame(pie, height=1, fg_color=COLOR_BORDE).pack(side="top", fill="x")

    # Columna izquierda: total
    col_total = ctk.CTkFrame(pie, fg_color="transparent")
    col_total.pack(side="left", padx=20, pady=10)
    label_total = ctk.CTkLabel(col_total, text="Total a Pagar: $0.00",
                                font=("Arial", 16, "bold"),
                                text_color=COLOR_AZUL_MARINO)
    label_total.pack(anchor="w")
    label_desglose = ctk.CTkLabel(col_total, text="",
                                   font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
    label_desglose.pack(anchor="w")

    # Columna central: checklist de envío
    ctk.CTkFrame(pie, width=1, fg_color=COLOR_BORDE).pack(side="left", fill="y", pady=8)

    col_envio = ctk.CTkFrame(pie, fg_color="transparent")
    col_envio.pack(side="left", padx=16, pady=8)
    ctk.CTkLabel(col_envio, text="Enviar comprobante por:",
                 font=("Arial", 10, "bold"),
                 text_color=COLOR_TEXTO_MUTED).pack(anchor="w")

    checks_frame = ctk.CTkFrame(col_envio, fg_color="transparent")
    checks_frame.pack(fill="x")

    var_wp    = ctk.IntVar(value=0)
    var_email = ctk.IntVar(value=0)
    var_fisico = ctk.IntVar(value=0)

    chk_wp = ctk.CTkCheckBox(checks_frame, text="WhatsApp",
                               variable=var_wp, font=FONT_SMALL)
    chk_wp.pack(side="left", padx=(0, 12))

    chk_email = ctk.CTkCheckBox(checks_frame, text="Correo",
                                  variable=var_email, font=FONT_SMALL)
    chk_email.pack(side="left", padx=(0, 12))

    chk_fisico = ctk.CTkCheckBox(checks_frame, text="Recibo físico",
                                   variable=var_fisico, font=FONT_SMALL)
    chk_fisico.pack(side="left")

    # Referencias para actualizar estado de checks según datos del vecino
    checks_ref = {
        "wp": chk_wp, "email": chk_email, "fisico": chk_fisico
    }

    ctk.CTkFrame(pie, width=1, fg_color=COLOR_BORDE).pack(side="left", fill="y", pady=8)

    # Botón registrar pago
    btn_pagar = ctk.CTkButton(
        pie, text="REGISTRAR\nPAGO",
        height=56, width=130, corner_radius=8,
        fg_color=COLOR_VERDE_PAGO, hover_color="#276749",
        font=("Arial", 12, "bold"), text_color=COLOR_BLANCO,
        command=lambda: registrar_pago()
    )
    btn_pagar.pack(side="right", padx=16, pady=8)

    # ── Lógica ────────────────────────────────────────────────────────────────

    def recalcular_total():
        total_cuotas = sum(
            item.get("monto_a_pagar", item["monto"]) for item in estado["checkboxes"]
            if item["var"].get() == 1
        )
        total_cargos = sum(
            c["monto"] for c in estado["cargos_extra"]
        )
        total = total_cuotas + total_cargos
        label_total.configure(text=f"Total a Pagar: ${total:.2f}")

        partes = []
        if total_cuotas:
            partes.append(f"${total_cuotas:.2f} cuotas")
        if total_cargos:
            partes.append(f"${total_cargos:.2f} cargos extra")
        label_desglose.configure(text=" + ".join(partes))

    def actualizar_estado_checks(vecino_id):
        """Habilita/deshabilita checks según datos del vecino."""
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("SELECT telefono, email FROM vecinos WHERE id=?", (vecino_id,))
            row = cur.fetchone()
            telefono = row[0] if row else None
            email    = row[1] if row else None
        except Exception:
            telefono = email = None
        finally:
            if 'con' in locals():
                con.close()

        var_wp.set(0)
        var_email.set(0)
        var_fisico.set(0)

        if telefono:
            chk_wp.configure(state="normal")
        else:
            chk_wp.configure(state="disabled")

        if email:
            chk_email.configure(state="normal")
        else:
            chk_email.configure(state="disabled")

        chk_fisico.configure(state="normal")

    def limpiar_busqueda():
        estado["vecino_id"] = None
        estado["checkboxes"].clear()
        estado["cargos_extra"].clear()
        entrada_busqueda.delete(0, "end")
        marco_sugerencias.place_forget()
        btn_limpiar.pack_forget()
        label_total.configure(text="Total a Pagar: $0.00")
        label_desglose.configure(text="")
        for w in marco_tabla.winfo_children():
            w.destroy()
        mensaje_vacio(marco_tabla,
                      "Use la barra de búsqueda para encontrar un vecino...")
        var_wp.set(0)
        var_email.set(0)
        var_fisico.set(0)
        for chk in [chk_wp, chk_email, chk_fisico]:
            chk.configure(state="disabled")

    def actualizar_sugerencias(event):
        texto = entrada_busqueda.get().strip()
        if len(texto) < 1:
            marco_sugerencias.place_forget()
            btn_limpiar.pack_forget()
            return
        btn_limpiar.pack(side="right", padx=6)
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute(
                "SELECT id, dui, nombre FROM vecinos "
                "WHERE activo=1 AND (nombre LIKE ? OR dui LIKE ?) LIMIT 6",
                (f"%{texto}%", f"%{texto}%"))
            resultados = cur.fetchall()
        except sqlite3.Error as e:
            logger.registrar("cobros.py", "actualizar_sugerencias", e)
            return
        finally:
            if 'con' in locals():
                con.close()

        for w in marco_sugerencias.winfo_children():
            w.destroy()

        if resultados:
            marco_sugerencias.lift()
            marco_sugerencias.place(x=0, y=170)
            for v_id, dui, nombre in resultados:
                txt = f"{dui}   |   {nombre}"
                ctk.CTkButton(
                    marco_sugerencias, text=txt, fg_color="transparent",
                    text_color=COLOR_TEXTO, hover_color=COLOR_FONDO, anchor="w",
                    font=FONT_BODY,
                    command=lambda i=v_id, t=txt: seleccionar_vecino(i, t)
                ).pack(fill="x", pady=1, padx=4)
        else:
            marco_sugerencias.place_forget()

    def seleccionar_vecino(v_id, texto):
        estado["vecino_id"] = v_id
        marco_sugerencias.place_forget()
        entrada_busqueda.delete(0, "end")
        entrada_busqueda.insert(0, texto)
        actualizar_estado_checks(v_id)
        cargar_recibos(v_id)

    def cargar_recibos(v_id):
        estado["checkboxes"].clear()
        estado["cargos_extra"].clear()
        for w in marco_tabla.winfo_children():
            w.destroy()

        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute(
                "SELECT id, mes, anio, monto, estado_pago FROM recibos "
                "WHERE vecino_id=? ORDER BY anio, "
                "CASE mes "
                "WHEN 'Enero' THEN 1 WHEN 'Febrero' THEN 2 WHEN 'Marzo' THEN 3 "
                "WHEN 'Abril' THEN 4 WHEN 'Mayo' THEN 5 WHEN 'Junio' THEN 6 "
                "WHEN 'Julio' THEN 7 WHEN 'Agosto' THEN 8 WHEN 'Septiembre' THEN 9 "
                "WHEN 'Octubre' THEN 10 WHEN 'Noviembre' THEN 11 WHEN 'Diciembre' THEN 12 "
                "END",
                (v_id,))
            recibos = cur.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Error",
                                  f"No se pudieron cargar los recibos:\n{e}")
            logger.registrar("cobros.py", "cargar_recibos", e)
            return
        finally:
            if 'con' in locals():
                con.close()

        if not recibos:
            mensaje_vacio(marco_tabla,
                          "Este vecino no tiene recibos registrados.")
            label_total.configure(text="Total a Pagar: $0.00")
            return

        for r_id, mes, anio, monto, epago in recibos:
            _renderizar_fila_recibo(r_id, mes, anio, monto, epago, v_id)

        marco_tabla.update_idletasks()
        recalcular_total()

    def _renderizar_fila_recibo(r_id, mes, anio, monto, epago, v_id):
        """Renderiza una fila de recibo en la tabla."""
        atrasado = _es_mes_atrasado(mes, anio)
        bg_fila  = "#FFF5F5" if (atrasado and epago == "Pendiente") else COLOR_BLANCO

        fila = ctk.CTkFrame(marco_tabla, fg_color=bg_fila, corner_radius=6, height=44)
        fila.pack(fill="x", pady=2, padx=4)
        fila.pack_propagate(False)

        ctk.CTkLabel(fila, text=mes, font=FONT_BODY,
                     width=150, anchor="w").pack(side="left", padx=16)
        ctk.CTkLabel(fila, text=str(anio), font=FONT_BODY,
                     width=70, anchor="w").pack(side="left")
        ctk.CTkLabel(fila, text=f"${monto:.2f}",
                     font=("Arial", 12, "bold"), width=90, anchor="w",
                     text_color=COLOR_AZUL_MARINO).pack(side="left")

        if epago == "Pendiente":
            badge(fila, "Pendiente", COLOR_BADGE_ROJO_BG,
                  COLOR_BADGE_ROJO_TEXT).pack(side="left")

            var = ctk.IntVar(value=1)
            chk = ctk.CTkCheckBox(fila, text="", variable=var, width=24,
                                   command=recalcular_total)
            chk.pack(side="left", padx=8)

            # Campo de monto editable (pago parcial)
            var_monto_str = ctk.StringVar(value=f"{monto:.2f}")
            entry_parcial = ctk.CTkEntry(
                fila, textvariable=var_monto_str,
                width=70, height=28, corner_radius=6,
                fg_color=COLOR_FONDO, border_color=COLOR_BORDE,
                font=FONT_SMALL, justify="right")
            entry_parcial.pack(side="left", padx=(0, 4))

            def _on_monto_change(name, index, mode, _r_id=r_id, _sv=var_monto_str, _orig=monto):
                try:
                    val = float(_sv.get().replace(",", "."))
                    val = max(0.01, min(val, _orig))
                except ValueError:
                    val = _orig
                for cb in estado["checkboxes"]:
                    if cb["id"] == _r_id:
                        cb["monto_a_pagar"] = val
                        break
                recalcular_total()

            var_monto_str.trace_add("write", _on_monto_change)

            estado["checkboxes"].append({
                "id": r_id, "monto": monto, "monto_a_pagar": monto,
                "var": var, "mes_anio": f"{mes} {anio}",
                "entry_monto": var_monto_str
            })

            # Botones de cargos extra
            frame_btns = ctk.CTkFrame(fila, fg_color="transparent")
            frame_btns.pack(side="left", padx=4)

            if atrasado:
                ctk.CTkButton(
                    frame_btns, text="+ Mora", height=26, width=70,
                    corner_radius=6, fg_color=COLOR_BADGE_ROJO_BG,
                    text_color=COLOR_BADGE_ROJO_TEXT,
                    hover_color="#FED7D7", font=FONT_SMALL,
                    command=lambda rid=r_id, m=mes, a=anio:
                        abrir_form_cargo(rid, "mora", m, a)
                ).pack(side="left", padx=2)

            ctk.CTkButton(
                frame_btns, text="+ Consumo", height=26, width=86,
                corner_radius=6, fg_color=COLOR_BADGE_AMBER_BG,
                text_color=COLOR_BADGE_AMBER_TEXT,
                hover_color="#FEEBC8", font=FONT_SMALL,
                command=lambda rid=r_id, m=mes, a=anio:
                    abrir_form_cargo(rid, "consumo", m, a)
            ).pack(side="left", padx=2)

        elif epago == "Parcial":
            badge(fila, "Parcial", COLOR_BADGE_AMBER_BG,
                  COLOR_BADGE_AMBER_TEXT).pack(side="left")
            # Permitir pagar el saldo restante
            var = ctk.IntVar(value=1)
            chk = ctk.CTkCheckBox(fila, text="", variable=var, width=24,
                                   command=recalcular_total)
            chk.pack(side="left", padx=8)
            var_monto_str = ctk.StringVar(value=f"{monto:.2f}")
            entry_parcial = ctk.CTkEntry(
                fila, textvariable=var_monto_str,
                width=70, height=28, corner_radius=6,
                fg_color=COLOR_FONDO, border_color=COLOR_BORDE,
                font=FONT_SMALL, justify="right")
            entry_parcial.pack(side="left", padx=(0, 4))

            def _on_monto_change_p(name, index, mode, _r_id=r_id, _sv=var_monto_str, _orig=monto):
                try:
                    val = float(_sv.get().replace(",", "."))
                    val = max(0.01, min(val, _orig))
                except ValueError:
                    val = _orig
                for cb in estado["checkboxes"]:
                    if cb["id"] == _r_id:
                        cb["monto_a_pagar"] = val
                        break
                recalcular_total()

            var_monto_str.trace_add("write", _on_monto_change_p)
            estado["checkboxes"].append({
                "id": r_id, "monto": monto, "monto_a_pagar": monto,
                "var": var, "mes_anio": f"{mes} {anio} (saldo)",
                "entry_monto": var_monto_str
            })
        else:
            badge(fila, "Pagado", COLOR_BADGE_VERDE_BG,
                  COLOR_BADGE_VERDE_TEXT).pack(side="left")

    def abrir_form_cargo(recibo_id, tipo, mes, anio):
        """Abre un formulario inline para agregar mora o consumo extra."""
        if not verificar_accion("registrar_cobro"):
            return

        titulo = f"Mora — {mes} {anio}" if tipo == "mora" else f"Consumo extra — {mes} {anio}"
        color  = COLOR_BADGE_ROJO_BG if tipo == "mora" else COLOR_BADGE_AMBER_BG
        color_btn = COLOR_ROJO if tipo == "mora" else COLOR_AMARILLO

        modal = ctk.CTkToplevel()
        modal.title(titulo)
        modal.geometry("380x280")
        modal.resizable(False, False)
        modal.grab_set()
        modal.focus_set()

        frame_m = ctk.CTkFrame(modal, fg_color=color, corner_radius=12)
        frame_m.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(frame_m, text=titulo,
                     font=("Arial", 14, "bold"),
                     text_color=COLOR_TEXTO).pack(pady=(14, 4))
        ctk.CTkFrame(frame_m, height=1, fg_color=COLOR_BORDE).pack(
            fill="x", padx=12)

        ctk.CTkLabel(frame_m, text="Descripción:", font=FONT_LABEL,
                     text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(10, 2))
        desc_default = "Mora por atraso" if tipo == "mora" else "Consumo excedente"
        entry_desc = ctk.CTkEntry(
            frame_m, placeholder_text=desc_default,
            height=36, corner_radius=8, fg_color=COLOR_BLANCO)
        entry_desc.pack(fill="x", padx=16)
        entry_desc.insert(0, desc_default)

        if tipo == "consumo":
            fila_consumo = ctk.CTkFrame(frame_m, fg_color="transparent")
            fila_consumo.pack(fill="x", padx=16, pady=(8, 0))
            ctk.CTkLabel(fila_consumo, text="m³ extra:", font=FONT_LABEL,
                         text_color=COLOR_TEXTO).pack(side="left")
            entry_m3 = ctk.CTkEntry(fila_consumo, width=70, height=36,
                                    corner_radius=8, fg_color=COLOR_BLANCO)
            entry_m3.pack(side="left", padx=6)
            aplicar_validacion_decimal(entry_m3)
            ctk.CTkLabel(fila_consumo, text="Tarifa/m³: $", font=FONT_LABEL,
                         text_color=COLOR_TEXTO).pack(side="left", padx=(8, 0))
            entry_tarifa = ctk.CTkEntry(fila_consumo, width=70, height=36,
                                        corner_radius=8, fg_color=COLOR_BLANCO)
            entry_tarifa.pack(side="left", padx=6)
            entry_tarifa.insert(0, "0.50")
            aplicar_validacion_decimal(entry_tarifa)
            lbl_calc = ctk.CTkLabel(frame_m, text="= $0.00", font=FONT_SMALL,
                                    text_color=COLOR_TEXTO_MUTED)
            lbl_calc.pack(anchor="e", padx=20)

            def actualizar_calculo(*_):
                try:
                    m3     = float(entry_m3.get() or 0)
                    tarifa = float(entry_tarifa.get() or 0)
                    lbl_calc.configure(text=f"= ${m3 * tarifa:.2f}")
                except ValueError:
                    lbl_calc.configure(text="= $0.00")

            entry_m3.bind("<KeyRelease>", actualizar_calculo)
            entry_tarifa.bind("<KeyRelease>", actualizar_calculo)
        else:
            entry_m3 = entry_tarifa = lbl_calc = None
            ctk.CTkLabel(frame_m, text="Monto: $", font=FONT_LABEL,
                         text_color=COLOR_TEXTO).pack(anchor="w", padx=16, pady=(10, 2))
            entry_monto = ctk.CTkEntry(frame_m, placeholder_text="1.00",
                                       height=36, corner_radius=8,
                                       fg_color=COLOR_BLANCO)
            entry_monto.pack(fill="x", padx=16)
            aplicar_validacion_decimal(entry_monto)

        def agregar_cargo():
            desc = entry_desc.get().strip() or desc_default
            try:
                if tipo == "consumo":
                    m3     = float(entry_m3.get() or 0)
                    tarifa = float(entry_tarifa.get() or 0)
                    monto  = round(m3 * tarifa, 2)
                else:
                    monto = float(entry_monto.get() or 0)

                if monto <= 0:
                    messagebox.showwarning("Atención", "El monto debe ser mayor a $0.00.",
                                           parent=modal)
                    return
            except ValueError:
                messagebox.showwarning("Atención", "Ingrese valores numéricos válidos.",
                                       parent=modal)
                return

            estado["cargos_extra"].append({
                "recibo_id":  recibo_id,
                "tipo":       tipo,
                "descripcion": desc,
                "monto":      monto,
                "mes_anio":   f"{mes} {anio}",
            })
            modal.destroy()
            recalcular_total()

        ctk.CTkButton(
            frame_m, text="Agregar cargo",
            height=38, corner_radius=8,
            fg_color=color_btn, hover_color=_darken(color_btn),
            font=FONT_BTN_SM, text_color=COLOR_BLANCO,
            command=agregar_cargo
        ).pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkButton(
            frame_m, text="Cancelar", height=32, corner_radius=8,
            fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
            border_width=1, border_color=COLOR_BORDE, font=FONT_SMALL,
            command=modal.destroy
        ).pack(fill="x", padx=16, pady=(0, 8))

    def registrar_pago():
        if not verificar_accion("registrar_cobro"):
            return

        v_id = estado["vecino_id"]
        if not v_id:
            messagebox.showwarning("Atención", "Seleccione un vecino primero.")
            return

        a_pagar = [i for i in estado["checkboxes"] if i["var"].get() == 1]
        if not a_pagar and not estado["cargos_extra"]:
            messagebox.showinfo("Sin selección",
                                "No hay meses seleccionados ni cargos para pagar.")
            return

        # FIX: construir texto de confirmación dinámicamente para no mostrar "Meses: 0"
        lineas_confirmacion = ["¿Confirma el registro del pago?\n"]
        if a_pagar:
            lineas_confirmacion.append(f"Meses: {len(a_pagar)}")
        if estado["cargos_extra"]:
            lineas_confirmacion.append(f"Cargos extra: {len(estado['cargos_extra'])}")
        lineas_confirmacion.append(label_total.cget("text"))

        if not messagebox.askyesno(
            "Confirmar Pago",
            "\n".join(lineas_confirmacion)
        ):
            return

        total_pagado = 0.0
        items_pagados = []
        fecha_local  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        usuario_id   = get_usuario_actual_id()

        try:
            con = obtener_conexion()
            cur = con.cursor()

            # Registrar pagos de cuotas
            for item in a_pagar:
                monto_item    = item.get("monto_a_pagar", item["monto"])
                es_parcial    = monto_item < item["monto"] - 0.001
                nuevo_estado_recibo = "Parcial" if es_parcial else "Pagado"

                # Si es parcial: reducir el monto pendiente del recibo en vez de
                # marcarlo Pagado. Si ya queda en $0 por redondeo, se marca Pagado.
                if es_parcial:
                    saldo_restante = round(item["monto"] - monto_item, 2)
                    if saldo_restante <= 0:
                        nuevo_estado_recibo = "Pagado"
                    cur.execute(
                        "UPDATE recibos SET estado_pago=?, monto=? WHERE id=?",
                        (nuevo_estado_recibo, saldo_restante, item["id"]))
                else:
                    cur.execute(
                        "UPDATE recibos SET estado_pago='Pagado' WHERE id=?",
                        (item["id"],))

                cur.execute(
                    "INSERT INTO transacciones "
                    "(recibo_id, usuario_id, monto_cobrado, fecha_cobro) "
                    "VALUES (?,?,?,?)",
                    (item["id"], usuario_id, monto_item, fecha_local))
                total_pagado += monto_item
                items_pagados.append({
                    "mes_anio":   item["mes_anio"],
                    "monto":      monto_item,
                    "monto_orig": item["monto"],
                    "parcial":    es_parcial and nuevo_estado_recibo == "Parcial"
                })

            # Registrar cargos extra
            cargos_pagados = []
            for cargo in estado["cargos_extra"]:
                cur.execute(
                    "INSERT INTO cargos_extra "
                    "(recibo_id, tipo, descripcion, monto, usuario_id, pagado) "
                    "VALUES (?,?,?,?,?,1)",
                    (cargo["recibo_id"], cargo["tipo"],
                     cargo["descripcion"], cargo["monto"], usuario_id))
                cargo_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO transacciones "
                    "(cargo_id, usuario_id, monto_cobrado, fecha_cobro) "
                    "VALUES (?,?,?,?)",
                    (cargo_id, usuario_id, cargo["monto"], fecha_local))
                total_pagado += cargo["monto"]
                cargos_pagados.append(cargo)

            # Actualizar estado del vecino
            cur.execute(
                "SELECT COUNT(*) FROM recibos "
                "WHERE vecino_id=? AND estado_pago IN ('Pendiente','Parcial')", (v_id,))
            pendientes = cur.fetchone()[0]
            nuevo_estado = "Solvente" if pendientes == 0 else "En Deuda"
            cur.execute("UPDATE vecinos SET estado=? WHERE id=?",
                        (nuevo_estado, v_id))

            # Datos del vecino para el comprobante
            cur.execute(
                "SELECT nombre, telefono, email FROM vecinos WHERE id=?", (v_id,))
            vecino      = cur.fetchone()
            cur.execute("SELECT usuario FROM usuarios WHERE id=?", (usuario_id,))
            cajero_row  = cur.fetchone()
            cajero      = cajero_row[0] if cajero_row else "Sistema"

            con.commit()

        except sqlite3.Error as e:
            messagebox.showerror("Error",
                                  f"No se pudo registrar el pago:\n{e}")
            logger.registrar("cobros.py", "registrar_pago", e)
            return
        finally:
            if 'con' in locals():
                con.close()

        nombre_vecino = vecino[0]
        telefono      = vecino[1]
        email_vecino  = vecino[2]
        numero_recibo = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # Generar PDF
        pdf_path = wp.generar_pdf_recibo(
            nombre_vecino, items_pagados, total_pagado, cajero, cargos_pagados
        )

        # Enviar por canales seleccionados
        mensajes_resultado = []

        if var_wp.get() and telefono:
            mensaje_wa = wp.construir_mensaje_recibo_pago(
                nombre_vecino, items_pagados, total_pagado, cajero, numero_recibo)
            wp.abrir_whatsapp(telefono, mensaje_wa)
            mensajes_resultado.append("WhatsApp abierto.")
            # Abrir la carpeta donde quedó el PDF para adjuntarlo fácilmente
            if pdf_path:
                import os, platform, subprocess
                carpeta_pdf = os.path.dirname(pdf_path)
                try:
                    if platform.system() == "Windows":
                        # /select resalta el archivo específico en el Explorador
                        subprocess.Popen(["explorer", f"/select,{pdf_path}"])
                    elif platform.system() == "Darwin":
                        subprocess.Popen(["open", "-R", pdf_path])
                    else:
                        subprocess.Popen(["xdg-open", carpeta_pdf])
                    mensajes_resultado.append("Carpeta del PDF abierta para adjuntarlo.")
                except Exception:
                    mensajes_resultado.append(f"PDF guardado en: {carpeta_pdf}")

        if var_email.get() and email_vecino:
            comunidad = obtener_config("nombre_comunidad", "ADESCO")
            def _parse_item(item):
                partes = item["mes_anio"].rsplit(" ", 1)
                return {
                    "mes":   partes[0] if len(partes) > 0 else "",
                    "anio":  int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 0,
                    "monto": item["monto"],
                }
            items_parseados = [_parse_item(i) for i in items_pagados]
            primer = items_parseados[0] if items_parseados else {"mes": "", "anio": 0, "monto": 0}
            resto  = items_parseados[1:]
            cuerpo = construir_cuerpo_recibo(
                nombre_vecino,
                primer["mes"], primer["anio"], primer["monto"],
                resto,
                total_pagado, cajero, comunidad, numero_recibo
            )
            # FIX: enviar en background para no congelar la UI durante SMTP
            enviar_correo_async(
                email_vecino,
                f"Comprobante de Pago — {comunidad}",
                cuerpo, pdf_path
            )
            mensajes_resultado.append("Correo enviándose en segundo plano.")

        if var_fisico.get() and pdf_path:
            import os, platform, subprocess
            try:
                if platform.system() == "Windows":
                    os.startfile(pdf_path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", pdf_path])
                else:
                    subprocess.Popen(["xdg-open", pdf_path])
                mensajes_resultado.append("PDF abierto para imprimir.")
            except Exception:
                mensajes_resultado.append("PDF guardado (no se pudo abrir).")

        resultado_txt = "\n".join(mensajes_resultado) if mensajes_resultado else "PDF guardado."
        messagebox.showinfo(
            "Pago Registrado",
            f"Pago de ${total_pagado:.2f} registrado correctamente.\n\n{resultado_txt}"
        )
        cargar_recibos(v_id)

    entrada_busqueda.bind("<KeyRelease>", actualizar_sugerencias)

    # Deshabilitar checks al inicio
    for chk in [chk_wp, chk_email, chk_fisico]:
        chk.configure(state="disabled")

    return frame