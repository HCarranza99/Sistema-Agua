import customtkinter as ctk
import sqlite3
import datetime
import os
import openpyxl
from tkinter import messagebox
import herramientas.logger as logger
from herramientas.permisos import puede_anular_cobro
import herramientas.respaldos as p_respaldos
import herramientas.whatsapp_pdf as wp
from herramientas.email_sender import enviar_correo, construir_cuerpo_cierre_caja
from herramientas.db import obtener_conexion, obtener_config, obtener_ruta
from herramientas.permisos import puede_exportar, puede_ver_historial
from licencia.bloqueador import verificar_accion
from pantallas.componentes import topbar, stat_card, encabezado_tabla, mensaje_vacio
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_BORDE, COLOR_AZUL_MARINO,
    COLOR_VERDE_PAGO, COLOR_ROJO, COLOR_AMARILLO, COLOR_AZUL_BOTON,
    COLOR_TEXTO, COLOR_TEXTO_MUTED,
    COLOR_BADGE_AZUL_BG, COLOR_BADGE_AZUL_TEXT,
    FONT_TOPBAR, FONT_BTN, FONT_BTN_SM, FONT_BODY, FONT_SMALL,
    FONT_STAT_VAL, FONT_STAT_LBL, RUTA_REPORTES_EXCEL_DEFAULT,
    MESES_ES
)


def crear_pantalla(parent_frame, get_usuario_rol, get_usuario_id=None):
    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")

    estado = {
        "datos":          [],
        "total":          0.0,
        "titulo":         "HOY",
        "filtro_activo":  "hoy",
    }

    meses_nombres = list(MESES_ES.values())
    meses_dict    = {m: f"{i:02d}" for i, m in MESES_ES.items()}
    hoy           = datetime.date.today()
    lista_anios   = [str(a) for a in range(2025, hoy.year + 2)]

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")

    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Reportes de Recaudación",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    lbl_sub_topbar = ctk.CTkLabel(izq, text=hoy.strftime("%B %Y"),
                                   font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
    lbl_sub_topbar.pack(anchor="w")

    der = ctk.CTkFrame(bar, fg_color="transparent")
    der.pack(side="right", padx=20)

    # Botones de acción (se muestran según rol)
    btns_topbar = {}

    def _construir_botones_topbar():
        for b in btns_topbar.values():
            try:
                b.destroy()
            except Exception:
                pass
        btns_topbar.clear()

        rol = get_usuario_rol() if callable(get_usuario_rol) else get_usuario_rol

        if puede_exportar(rol):
            btns_topbar["excel"] = ctk.CTkButton(
                der, text="📊 Excel", height=36, corner_radius=8,
                fg_color=COLOR_VERDE_PAGO, font=FONT_BTN_SM,
                text_color=COLOR_BLANCO,
                command=lambda: exportar_excel())
            btns_topbar["excel"].pack(side="right", padx=4)

            btns_topbar["pdf"] = ctk.CTkButton(
                der, text="📄 PDF", height=36, corner_radius=8,
                fg_color=COLOR_ROJO, font=FONT_BTN_SM,
                text_color=COLOR_BLANCO,
                command=lambda: exportar_pdf())
            btns_topbar["pdf"].pack(side="right", padx=4)

            btns_topbar["sync"] = ctk.CTkButton(
                der, text="☁️ Sincronizar", height=36, corner_radius=8,
                fg_color=COLOR_AZUL_BOTON, font=FONT_BTN_SM,
                text_color=COLOR_BLANCO,
                command=lambda: p_respaldos.crear_respaldo(silencioso=False))
            btns_topbar["sync"].pack(side="right", padx=4)

            btns_topbar["restaurar"] = ctk.CTkButton(
                der, text="🔄 Restaurar BD", height=36, corner_radius=8,
                fg_color=COLOR_BLANCO, border_width=1,
                border_color=COLOR_ROJO, text_color=COLOR_ROJO,
                font=FONT_BTN_SM,
                command=lambda: _restaurar_bd())
            btns_topbar["restaurar"].pack(side="right", padx=4)

    def _restaurar_bd():
        ok = p_respaldos.restaurar_desde_respaldo()
        if ok:
            actualizar_reporte("hoy")

    # Botón cierre de caja
    btn_cierre_ref = {}

    def _caja_ya_cerrada_hoy():
        try:
            con = obtener_conexion()
            cur = con.cursor()
            cur.execute("SELECT id, hora_cierre FROM cierres_caja WHERE fecha=?",
                        (hoy.strftime("%Y-%m-%d"),))
            return cur.fetchone()
        except Exception:
            return None
        finally:
            if 'con' in locals():
                con.close()

    def _actualizar_btn_cierre():
        if estado["filtro_activo"] != "hoy":
            if "btn" in btn_cierre_ref:
                try:
                    btn_cierre_ref["btn"].destroy()
                except Exception:
                    pass
                del btn_cierre_ref["btn"]
            return

        cierre = _caja_ya_cerrada_hoy()
        if "btn" in btn_cierre_ref:
            try:
                btn_cierre_ref["btn"].destroy()
            except Exception:
                pass
            del btn_cierre_ref["btn"]

        if cierre:
            hora = cierre[1][:5] if cierre[1] else "—"
            lbl = ctk.CTkLabel(
                der, text=f"✓ Caja cerrada {hora}",
                font=FONT_BTN_SM, text_color=COLOR_VERDE_PAGO,
                fg_color=COLOR_BLANCO, corner_radius=8, height=36, width=160)
            lbl.pack(side="right", padx=4)
            btn_cierre_ref["btn"] = lbl
        else:
            btn = ctk.CTkButton(
                der, text="🔒 Cerrar Caja", height=36, corner_radius=8,
                fg_color="#744210", hover_color="#5C3317",
                text_color=COLOR_BLANCO, font=FONT_BTN_SM,
                command=lambda: ejecutar_cierre_caja())
            btn.pack(side="right", padx=4)
            btn_cierre_ref["btn"] = btn

    def ejecutar_cierre_caja():
        if not verificar_accion("cerrar_caja"):
            return

        if not estado["datos"]:
            messagebox.showwarning(
                "Sin Movimientos",
                "No hay transacciones registradas hoy.\n"
                "No se puede cerrar la caja sin movimientos.")
            return

        total    = estado["total"]
        cantidad = len(estado["datos"])

        if not messagebox.askyesno(
            "Cerrar Caja del Día",
            f"¿Confirma el cierre de caja para HOY "
            f"{hoy.strftime('%d/%m/%Y')}?\n\n"
            f"Total recaudado:  ${total:.2f}\n"
            f"Transacciones:    {cantidad}\n\n"
            "Se generará el reporte PDF y un respaldo automático."
        ):
            return

        try:
            con = obtener_conexion()
            cur = con.cursor()
            uid = get_usuario_id() if callable(get_usuario_id) else 1
            cur.execute(
                "INSERT INTO cierres_caja "
                "(fecha, usuario_id, total_recaudado, cantidad_transacciones) "
                "VALUES (?,?,?,?)",
                (hoy.strftime("%Y-%m-%d"), uid, total, cantidad))
            con.commit()

            # Datos del cajero
            cur.execute("SELECT usuario FROM usuarios WHERE id=?", (uid,))
            cajero_row = cur.fetchone()
            cajero = cajero_row[0] if cajero_row else "Sistema"

        except sqlite3.IntegrityError:
            messagebox.showerror("Caja ya cerrada",
                                  "La caja de hoy ya fue cerrada anteriormente.")
            _actualizar_btn_cierre()
            return
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo registrar el cierre:\n{e}")
            logger.registrar("reportes.py", "ejecutar_cierre_caja", e)
            return
        finally:
            if 'con' in locals():
                con.close()

        # Generar PDF
        pdf_path = exportar_pdf(cierre_de_caja=True, retornar_ruta=True)

        # Respaldo automático
        p_respaldos.crear_respaldo(silencioso=True)

        # Notificar al presidente/administrador
        _notificar_cierre_caja(hoy.strftime("%d/%m/%Y"), total,
                                cantidad, cajero, pdf_path)

        _actualizar_btn_cierre()
        messagebox.showinfo(
            "Caja Cerrada",
            f"Cierre de caja registrado correctamente.\n\n"
            f"Total: ${total:.2f} | {cantidad} transacciones\n"
            "Se generó el reporte PDF y se creó un respaldo automático.")

    def _notificar_cierre_caja(fecha, total, cantidad, cajero, pdf_path):
        """Envía notificación de cierre al presidente o administrador."""
        try:
            con = obtener_conexion()
            cur = con.cursor()
            # Buscar presidente primero, luego administrador
            cur.execute(
                "SELECT telefono, email FROM usuarios "
                "WHERE rol IN ('Presidente','Administrador') "
                "AND (telefono IS NOT NULL OR email IS NOT NULL) "
                "ORDER BY CASE rol WHEN 'Presidente' THEN 1 ELSE 2 END LIMIT 1")
            row = cur.fetchone()
        except Exception:
            row = None
        finally:
            if 'con' in locals():
                con.close()

        if not row:
            return

        telefono, email = row
        comunidad = obtener_config("nombre_comunidad", "ADESCO")
        mensaje   = wp.construir_mensaje_cierre_caja(
            fecha, total, cantidad, cajero)

        if telefono:
            wp.abrir_whatsapp(telefono, mensaje)

        if email and pdf_path:
            cuerpo = construir_cuerpo_cierre_caja(
                fecha, total, cantidad, cajero, comunidad)
            enviar_correo(
                email,
                f"Cierre de Caja {fecha} — {comunidad}",
                cuerpo, pdf_path)

    # ── Contenido ──────────────────────────────────────────────────────────────
    contenido = ctk.CTkFrame(frame, fg_color="transparent")
    contenido.pack(fill="both", expand=True, padx=24, pady=16)

    # Stats
    stats_frame = ctk.CTkFrame(contenido, fg_color="transparent")
    stats_frame.pack(fill="x", pady=(0, 16))

    def _mk_stat(parent, label, col_fondo):
        c = ctk.CTkFrame(parent, fg_color=COLOR_AZUL_MARINO if col_fondo else COLOR_BLANCO,
                          corner_radius=10)
        l = ctk.CTkLabel(c, text=label, font=FONT_STAT_LBL,
                          text_color="#B0C4DE" if col_fondo else COLOR_TEXTO_MUTED)
        l.pack(anchor="w", padx=14, pady=(12, 2))
        v = ctk.CTkLabel(c, text="$0.00", font=FONT_STAT_VAL,
                          text_color=COLOR_BLANCO if col_fondo else COLOR_TEXTO)
        v.pack(anchor="w", padx=14)
        ctk.CTkLabel(c, text=" ").pack(pady=(0, 6))
        return c, v

    card_total, lbl_total_val   = _mk_stat(stats_frame, "Total Recaudado", True)
    card_txn,   lbl_txn_val     = _mk_stat(stats_frame, "Transacciones", False)
    card_prom,  lbl_prom_val    = _mk_stat(stats_frame, "Promedio por pago", False)

    card_total.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    card_txn.grid(row=0, column=1,   sticky="nsew", padx=(0, 8))
    card_prom.grid(row=0, column=2,  sticky="nsew")
    for i in range(3):
        stats_frame.grid_columnconfigure(i, weight=1)

    # Filtros de período
    filtros_frame = ctk.CTkFrame(contenido, fg_color="transparent")
    filtros_frame.pack(fill="x", pady=(0, 12))

    filtro_btns = {}

    def _set_filtro(nombre, callback):
        for n, b in filtro_btns.items():
            activo = (n == nombre)
            b.configure(
                fg_color=COLOR_AZUL_MARINO if activo else COLOR_BLANCO,
                text_color=COLOR_BLANCO if activo else COLOR_TEXTO_MUTED,
                border_width=0 if activo else 1)
        callback()

    for key, lbl, cb in [
        ("hoy", "Hoy", lambda: actualizar_reporte("hoy")),
        ("mes", "Este Mes", lambda: actualizar_reporte("mes_actual")),
        ("todo", "Todo el Historial", lambda: actualizar_reporte("todo")),
    ]:
        b = ctk.CTkButton(
            filtros_frame, text=lbl, height=32, corner_radius=8,
            fg_color=COLOR_AZUL_MARINO if key == "hoy" else COLOR_BLANCO,
            text_color=COLOR_BLANCO if key == "hoy" else COLOR_TEXTO_MUTED,
            border_width=0 if key == "hoy" else 1,
            border_color=COLOR_BORDE, font=FONT_BTN_SM,
            command=lambda k=key, c=cb: _set_filtro(k, c))
        b.pack(side="left", padx=(0, 8))
        filtro_btns[key] = b

    # Selector mes específico
    ctk.CTkLabel(filtros_frame, text="|", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=4)
    combo_mes = ctk.CTkComboBox(filtros_frame, values=meses_nombres,
                                 width=130, state="readonly")
    combo_mes.pack(side="left", padx=4)
    combo_mes.set(meses_nombres[hoy.month - 1])
    combo_anio = ctk.CTkComboBox(filtros_frame, values=lista_anios,
                                  width=80, state="readonly")
    combo_anio.pack(side="left", padx=4)
    combo_anio.set(str(hoy.year))
    ctk.CTkButton(
        filtros_frame, text="Buscar", height=32, corner_radius=8,
        fg_color=COLOR_AMARILLO, hover_color="#B7791F",
        text_color=COLOR_BLANCO, font=FONT_BTN_SM,
        # FIX: resaltar "mes" como activo cuando se busca un mes específico
        command=lambda: [_set_filtro("mes", lambda: None),
                         actualizar_reporte("mes_especifico")]
    ).pack(side="left", padx=4)

    # Filtro por zona
    zonas_disponibles = []
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("SELECT id, nombre FROM zonas WHERE activa=1 ORDER BY orden, nombre")
        zonas_disponibles = cur.fetchall()
    except Exception:
        pass
    finally:
        if 'con' in locals():
            con.close()

    filtro_zona = {"zona_id": None}
    if zonas_disponibles:
        ctk.CTkLabel(filtros_frame, text="|", font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=4)
        nombres_zonas = ["Todas las zonas"] + [z[1] for z in zonas_disponibles]
        ids_zonas     = [None] + [z[0] for z in zonas_disponibles]
        combo_zona = ctk.CTkComboBox(
            filtros_frame, values=nombres_zonas, width=160, state="readonly",
            command=lambda v: _cambiar_zona(v, nombres_zonas, ids_zonas))
        combo_zona.pack(side="left", padx=4)
        combo_zona.set("Todas las zonas")

    def _cambiar_zona(valor, nombres, ids):
        idx = nombres.index(valor) if valor in nombres else 0
        filtro_zona["zona_id"] = ids[idx]
        actualizar_reporte(estado["filtro_activo"])

    # Tabla de transacciones
    tabla_card = ctk.CTkFrame(contenido, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(fill="both", expand=True)

    # Encabezado con todas las columnas alineadas al layout de las filas
    enc = ctk.CTkFrame(tabla_card, fg_color="#F8F9FB", corner_radius=0, height=36)
    enc.pack(fill="x")
    enc.pack_propagate(False)
    ctk.CTkFrame(enc, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    for txt, w, anc in [
        ("FECHA Y HORA", 140, "w"), ("VECINO", 160, "w"), ("ZONA", 100, "w"),
        ("CONCEPTO", 150, "w"), ("USUARIO", 80, "w")
    ]:
        ctk.CTkLabel(enc, text=txt, font=("Arial", 10, "bold"),
                     text_color=COLOR_TEXTO_MUTED, width=w, anchor=anc
                     ).pack(side="left", padx=(16 if txt == "FECHA Y HORA" else 4, 0))
    ctk.CTkLabel(enc, text="MONTO", font=("Arial", 10, "bold"),
                 text_color=COLOR_TEXTO_MUTED, width=75, anchor="e"
                 ).pack(side="right", padx=(0, 12))
    ctk.CTkLabel(enc, text="ACCIONES", font=("Arial", 10, "bold"),
                 text_color=COLOR_TEXTO_MUTED, width=116, anchor="e"
                 ).pack(side="right", padx=0)

    marco_tabla = ctk.CTkScrollableFrame(tabla_card, fg_color=COLOR_FONDO,
                                          corner_radius=0)
    marco_tabla.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Lógica ─────────────────────────────────────────────────────────────────
    def obtener_datos(filtro, mes_esp=None, anio_esp=None):
        try:
            con = obtener_conexion()
            cur = con.cursor()

            q = """
                SELECT date(t.fecha_cobro), time(t.fecha_cobro),
                       COALESCE(v.nombre, v2.nombre), COALESCE(z.nombre, z2.nombre),
                       COALESCE(r.mes,  r2.mes),
                       COALESCE(r.anio, r2.anio),
                       t.monto_cobrado, u.usuario,
                       ce.tipo, ce.descripcion,
                       t.id, t.anulado,
                       t.recibo_id, t.cargo_id,
                       COALESCE(v.id, v2.id),
                       COALESCE(v.nombre, v2.nombre),
                       COALESCE(v.telefono, v2.telefono),
                       COALESCE(v.email, v2.email)
                FROM transacciones t
                LEFT JOIN recibos      r   ON t.recibo_id  = r.id
                LEFT JOIN vecinos      v   ON r.vecino_id  = v.id
                LEFT JOIN zonas        z   ON v.zona_id    = z.id
                LEFT JOIN cargos_extra ce  ON t.cargo_id   = ce.id
                LEFT JOIN recibos      r2  ON ce.recibo_id = r2.id
                LEFT JOIN vecinos      v2  ON r2.vecino_id = v2.id
                LEFT JOIN zonas        z2  ON v2.zona_id   = z2.id
                JOIN  usuarios u           ON t.usuario_id = u.id
            """
            conditions = []
            params     = []

            if filtro == "hoy":
                conditions.append("date(t.fecha_cobro)=?")
                params.append(hoy.strftime("%Y-%m-%d"))
                estado["titulo"] = f"HOY ({hoy.strftime('%d/%m/%Y')})"
            elif filtro == "mes_actual":
                conditions.append("strftime('%Y-%m',t.fecha_cobro)=?")
                params.append(hoy.strftime("%Y-%m"))
                estado["titulo"] = hoy.strftime("%B %Y").upper()
            elif filtro == "mes_especifico":
                mes_n = meses_dict[mes_esp]
                conditions.append("strftime('%Y-%m',t.fecha_cobro)=?")
                params.append(f"{anio_esp}-{mes_n}")
                estado["titulo"] = f"{mes_esp.upper()} {anio_esp}"
            elif filtro == "todo":
                estado["titulo"] = "TODO EL HISTORIAL"

            if filtro_zona["zona_id"]:
                conditions.append("v.zona_id=?")
                params.append(filtro_zona["zona_id"])

            if conditions:
                q += " WHERE " + " AND ".join(conditions)
            q += " ORDER BY t.fecha_cobro DESC"

            cur.execute(q, params)
            return cur.fetchall()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudieron obtener los datos:\n{e}")
            logger.registrar("reportes.py", "obtener_datos", e)
            return []
        finally:
            if 'con' in locals():
                con.close()

    def actualizar_reporte(filtro):
        for w in marco_tabla.winfo_children():
            w.destroy()
        estado["filtro_activo"] = filtro
        _actualizar_btn_cierre()

        rol = get_usuario_rol() if callable(get_usuario_rol) else get_usuario_rol
        if filtro not in ("hoy",) and not puede_ver_historial(rol):
            mensaje_vacio(marco_tabla,
                          "Su rol solo permite ver el reporte del día.")
            return

        mes  = combo_mes.get() if filtro == "mes_especifico" else None
        anio = combo_anio.get() if filtro == "mes_especifico" else None
        datos = obtener_datos(filtro, mes, anio)
        estado["datos"] = datos

        total = sum(f[6] for f in datos if not f[11])  # excluir anuladas del total
        estado["total"] = total
        lbl_total_val.configure(text=f"${total:.2f}")
        activas = sum(1 for f in datos if not f[11])
        lbl_txn_val.configure(text=str(activas))
        prom = total / len(datos) if datos else 0
        lbl_prom_val.configure(text=f"${prom:.2f}")
        lbl_sub_topbar.configure(text=estado["titulo"])

        if not datos:
            mensaje_vacio(marco_tabla, "No hay transacciones en este período.")
            return

        for fecha, hora, vecino, zona, mes_p, anio_p, monto, cajero, ce_tipo, ce_desc, t_id, t_anulado, t_recibo_id, t_cargo_id, v_id, v_nombre, v_tel, v_email in datos:
            es_anulado = bool(t_anulado)
            bg_fila    = "#FFF5F5" if es_anulado else COLOR_BLANCO
            alpha_txt  = COLOR_TEXTO_MUTED if es_anulado else COLOR_TEXTO

            fila_w = ctk.CTkFrame(marco_tabla, fg_color=bg_fila,
                                   corner_radius=6, height=46)
            fila_w.pack(fill="x", pady=2, padx=4)
            fila_w.pack_propagate(False)

            ctk.CTkLabel(fila_w, text=f"{fecha} {hora[:5]}", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=140,
                         anchor="w").pack(side="left", padx=16)
            ctk.CTkLabel(fila_w, text=vecino or "—",
                         font=("Arial", 12, "bold" if not es_anulado else "normal"),
                         text_color=alpha_txt, width=160,
                         anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=zona or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=100,
                         anchor="w").pack(side="left", padx=4)
            if ce_tipo:
                tipo_label = "Mora" if ce_tipo == "mora" else "Consumo extra"
                concepto = f"{tipo_label} — {mes_p} {anio_p}" if mes_p else tipo_label
            elif mes_p:
                concepto = f"Recibo {mes_p} {anio_p}"
            else:
                concepto = "Cargo extra"
            ctk.CTkLabel(
                fila_w,
                text=("✗ ANULADO" if es_anulado else concepto),
                font=FONT_SMALL,
                text_color=COLOR_ROJO if es_anulado else COLOR_TEXTO_MUTED,
                width=150, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=cajero, fg_color=COLOR_BADGE_AZUL_BG,
                          text_color=COLOR_BADGE_AZUL_TEXT, corner_radius=20,
                          font=FONT_SMALL, width=80,
                          height=22).pack(side="left", padx=4)

            # ── Lado derecho: monto + botones (orden importa en pack) ──────────
            # El monto se empaca primero para que quede más a la derecha
            ctk.CTkLabel(fila_w, text=f"${monto:.2f}",
                         font=("Arial", 13, "bold"),
                         text_color=COLOR_TEXTO_MUTED if es_anulado else COLOR_VERDE_PAGO,
                         width=75, anchor="e").pack(side="right", padx=(0, 12))

            # Botones Anular / Reimprimir
            rol_actual = get_usuario_rol() if callable(get_usuario_rol) else get_usuario_rol
            if not es_anulado and puede_anular_cobro(rol_actual):
                ctk.CTkButton(
                    fila_w, text="Anular", width=68, height=28,
                    corner_radius=6, fg_color="transparent",
                    border_width=1, border_color=COLOR_ROJO,
                    text_color=COLOR_ROJO, font=FONT_SMALL,
                    command=lambda _tid=t_id, _rid=t_recibo_id,
                                   _cid=t_cargo_id, _vid=v_id,
                                   _vn=v_nombre, _vt=v_tel, _ve=v_email,
                                   _mp=mes_p, _ap=anio_p, _mo=monto,
                                   _con=concepto:
                        _confirmar_anulacion(
                            _tid, _rid, _cid, _vid, _vn, _vt, _ve,
                            _mp, _ap, _mo, _con)
                ).pack(side="right", padx=(0, 4))

            if mes_p and v_nombre:
                ctk.CTkButton(
                    fila_w, text="🖨", width=32, height=28,
                    corner_radius=6, fg_color="transparent",
                    border_width=1, border_color=COLOR_BORDE,
                    text_color=COLOR_TEXTO_MUTED, font=("Arial", 14),
                    command=lambda _tid=t_id, _vn=v_nombre, _mp=mes_p,
                                   _ap=anio_p, _mo=monto, _cet=ce_tipo,
                                   _ced=ce_desc:
                        _reimprimir(_tid, _vn, _mp, _ap, _mo, _cet, _ced)
                ).pack(side="right", padx=(0, 4))

    # ── Anulación de cobro ────────────────────────────────────────────────────
    def _confirmar_anulacion(t_id, recibo_id, cargo_id, v_id,
                              v_nombre, v_tel, v_email,
                              mes_p, anio_p, monto, concepto):
        """Abre modal para confirmar anulación con motivo obligatorio."""
        from herramientas.email_sender import enviar_correo_async
        from herramientas.db import obtener_config as _cfg
        import herramientas.whatsapp_pdf as _wp

        modal = ctk.CTkToplevel()
        modal.title("Anular Cobro")
        modal.geometry("460x380")
        modal.resizable(False, False)
        modal.grab_set()
        modal.focus_set()
        modal.update_idletasks()
        x = (modal.winfo_screenwidth() // 2) - 230
        y = (modal.winfo_screenheight() // 2) - 190
        modal.geometry(f"460x380+{x}+{y}")

        pad = ctk.CTkFrame(modal, fg_color=COLOR_FONDO)
        pad.pack(fill="both", expand=True, padx=0, pady=0)

        ctk.CTkLabel(pad, text="Anular Cobro", font=("Arial", 15, "bold"),
                     text_color=COLOR_ROJO).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(pad,
                     text=f"Vecino: {v_nombre}\nConcepto: {concepto}\nMonto: ${monto:.2f}",
                     font=FONT_SMALL, text_color=COLOR_TEXTO,
                     justify="left").pack(anchor="w", padx=24, pady=(0, 12))

        ctk.CTkFrame(pad, height=1, fg_color=COLOR_BORDE).pack(fill="x", padx=24)

        ctk.CTkLabel(pad, text="Motivo de anulación *", font=FONT_LABEL,
                     text_color=COLOR_TEXTO).pack(anchor="w", padx=24, pady=(12, 4))
        txt_motivo = ctk.CTkTextbox(pad, height=80, corner_radius=8,
                                     fg_color=COLOR_BLANCO, border_width=1,
                                     border_color=COLOR_BORDE, font=FONT_BODY)
        txt_motivo.pack(fill="x", padx=24)

        # Opciones de notificación
        var_notif_wa    = ctk.BooleanVar(value=bool(v_tel))
        var_notif_email = ctk.BooleanVar(value=bool(v_email and "@" in (v_email or "")))
        notif_row = ctk.CTkFrame(pad, fg_color="transparent")
        notif_row.pack(fill="x", padx=24, pady=(10, 0))
        ctk.CTkLabel(notif_row, text="Notificar por:", font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=(0, 12))
        if v_tel:
            ctk.CTkCheckBox(notif_row, text="WhatsApp", variable=var_notif_wa,
                             font=FONT_SMALL).pack(side="left", padx=4)
        if v_email and "@" in (v_email or ""):
            ctk.CTkCheckBox(notif_row, text="Correo", variable=var_notif_email,
                             font=FONT_SMALL).pack(side="left", padx=4)

        lbl_err = ctk.CTkLabel(pad, text="", font=FONT_SMALL,
                                text_color=COLOR_ROJO)
        lbl_err.pack(anchor="w", padx=24, pady=(4, 0))

        def ejecutar_anulacion():
            motivo = txt_motivo.get("1.0", "end").strip()
            if not motivo:
                lbl_err.configure(text="El motivo es obligatorio.")
                return

            try:
                import datetime
                con = obtener_conexion()
                cur = con.cursor()
                ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 1. Marcar transacción como anulada
                cur.execute(
                    "UPDATE transacciones SET anulado=1, motivo_anulacion=?, "
                    "fecha_anulacion=? WHERE id=?",
                    (motivo, ahora, t_id))

                # 2. Restaurar el recibo a Pendiente si era un pago de cuota
                if recibo_id:
                    # Recuperar monto original del recibo para restaurarlo
                    cur.execute("SELECT monto, estado_pago FROM recibos WHERE id=?",
                                (recibo_id,))
                    rec = cur.fetchone()
                    if rec:
                        cur.execute(
                            "UPDATE recibos SET estado_pago='Pendiente', monto=monto+? "
                            "WHERE id=?", (monto, recibo_id))

                # 3. Si era cargo extra, marcarlo como no pagado y eliminarlo
                if cargo_id:
                    cur.execute("UPDATE cargos_extra SET pagado=0 WHERE id=?",
                                (cargo_id,))

                # 4. Actualizar estado del vecino
                if v_id:
                    cur.execute(
                        "SELECT COUNT(*) FROM recibos "
                        "WHERE vecino_id=? AND estado_pago IN ('Pendiente','Parcial')",
                        (v_id,))
                    pendientes = cur.fetchone()[0]
                    cur.execute("UPDATE vecinos SET estado=? WHERE id=?",
                                ("En Deuda" if pendientes > 0 else "Solvente", v_id))

                con.commit()
                con.close()

            except Exception as e:
                logger.registrar("reportes.py", "_confirmar_anulacion", e)
                messagebox.showerror("Error", f"No se pudo anular el cobro:\n{e}")
                return

            # 5. Notificaciones
            comunidad = obtener_config("nombre_comunidad", "Sistema de Agua")
            msg_wa = (
                f"Estimado/a {v_nombre},\n\n"
                f"Le informamos que el cobro registrado por *{concepto}* "
                f"por un monto de *${monto:.2f}* ha sido *ANULADO*.\n\n"
                f"Motivo: {motivo}\n\n"
                f"Si tiene dudas, comuníquese con {comunidad}."
            )
            if var_notif_wa.get() and v_tel:
                import herramientas.whatsapp_pdf as _wp2
                _wp2.abrir_whatsapp(v_tel, msg_wa)

            if var_notif_email.get() and v_email:
                cuerpo_html = f"""
                <div style='font-family:Arial,sans-serif;max-width:520px;margin:auto'>
                  <div style='background:#C53030;color:white;padding:20px;border-radius:8px 8px 0 0'>
                    <h2 style='margin:0'>⚠️ Cobro Anulado</h2>
                    <p style='margin:4px 0 0;opacity:.8'>{comunidad}</p>
                  </div>
                  <div style='background:#f9f9f9;padding:20px;border:1px solid #ddd'>
                    <p>Estimado/a <strong>{v_nombre}</strong>,</p>
                    <p>Le informamos que el siguiente cobro ha sido <strong>anulado</strong>:</p>
                    <table style='width:100%;border-collapse:collapse'>
                      <tr><td style='padding:6px 8px;background:#fef2f2'>Concepto</td>
                          <td style='padding:6px 8px'>{concepto}</td></tr>
                      <tr><td style='padding:6px 8px;background:#fef2f2'>Monto</td>
                          <td style='padding:6px 8px'>${monto:.2f}</td></tr>
                      <tr><td style='padding:6px 8px;background:#fef2f2'>Motivo</td>
                          <td style='padding:6px 8px'>{motivo}</td></tr>
                    </table>
                    <p style='margin-top:16px;font-size:12px;color:#666'>
                      Si tiene dudas comuníquese con {comunidad}.
                    </p>
                  </div>
                </div>"""
                enviar_correo_async(
                    v_email,
                    f"Cobro anulado — {comunidad}",
                    cuerpo_html)

            modal.destroy()
            # Recargar reporte para reflejar la anulación
            actualizar_reporte(estado["filtro_activo"])

        ctk.CTkButton(
            pad, text="Confirmar Anulación", height=42, corner_radius=8,
            fg_color=COLOR_ROJO, hover_color="#9B2C2C",
            font=FONT_BTN_SM, text_color=COLOR_BLANCO,
            command=ejecutar_anulacion
        ).pack(fill="x", padx=24, pady=(12, 4))
        ctk.CTkButton(
            pad, text="Cancelar", height=36, corner_radius=8,
            fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
            border_width=1, border_color=COLOR_BORDE, font=FONT_SMALL,
            command=modal.destroy
        ).pack(fill="x", padx=24)

    # ── Reimpresión de recibo ──────────────────────────────────────────────────
    def _reimprimir(t_id, v_nombre, mes_p, anio_p, monto, ce_tipo, ce_desc):
        """Regenera y abre el PDF de un cobro ya registrado."""
        import herramientas.whatsapp_pdf as _wp
        try:
            if ce_tipo:
                # Cargo extra: generar PDF simple de cargo
                tipo_label = "Mora" if ce_tipo == "mora" else "Consumo extra"
                items = [{"mes_anio": f"{mes_p} {anio_p}", "monto": monto,
                          "monto_orig": monto, "parcial": False}]
                cargos = [{"tipo": ce_tipo,
                           "descripcion": ce_desc or tipo_label,
                           "monto": monto}]
                pdf_path = _wp.generar_pdf_recibo(v_nombre, [], monto, "—", cargos)
            else:
                items = [{"mes_anio": f"{mes_p} {anio_p}", "monto": monto,
                          "monto_orig": monto, "parcial": False}]
                pdf_path = _wp.generar_pdf_recibo(v_nombre, items, monto, "—", [])

            if not pdf_path:
                messagebox.showerror("Error", "No se pudo generar el PDF.")
                return

            import os, platform, subprocess
            if platform.system() == "Windows":
                os.startfile(pdf_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", pdf_path])
            else:
                subprocess.Popen(["xdg-open", pdf_path])

        except Exception as e:
            logger.registrar("reportes.py", "_reimprimir", e)
            messagebox.showerror("Error", f"No se pudo reimprimir:\n{e}")

    def exportar_pdf(cierre_de_caja=False, retornar_ruta=False):
        if not verificar_accion("exportar_pdf"):
            return None
        if not estado["datos"]:
            if not retornar_ruta:
                messagebox.showwarning("Sin Datos", "No hay datos para exportar.")
            return None

        datos_reporte = [
            (f[0], f[1], f[2] or "—",
             f[4] or "—", f[5] or 0, f[6], f[7])
            for f in estado["datos"]
        ]
        ruta = wp.generar_pdf_reporte(
            datos_reporte, estado["total"], estado["titulo"], cierre_de_caja)

        if ruta and not retornar_ruta:
            if not cierre_de_caja:
                messagebox.showinfo("PDF Generado", f"Guardado correctamente.")
            _abrir_carpeta(os.path.dirname(ruta))

        return ruta if retornar_ruta else None

    def exportar_excel():
        if not verificar_accion("exportar_excel"):
            return
        if not estado["datos"]:
            messagebox.showwarning("Sin Datos", "No hay datos para exportar.")
            return
        try:
            ruta_dir = obtener_ruta("ruta_reportes_excel", RUTA_REPORTES_EXCEL_DEFAULT)
            os.makedirs(ruta_dir, exist_ok=True)
            ts     = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            titulo_s = "".join(
                c if c.isalnum() or c in "-_" else "_"
                for c in estado["titulo"])
            nombre = os.path.join(ruta_dir, f"Reporte_{titulo_s}_{ts}.xlsx")

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Recaudación"
            comunidad = obtener_config("nombre_comunidad", "ADESCO")
            ws.append([f"{comunidad} — Reporte de Recaudación"])
            ws.append([f"Período: {estado['titulo']}"])
            ws.append([])
            ws.append(["Fecha", "Hora", "Vecino", "Zona", "Mes Pagado",
                        "Año Pagado", "Monto", "Cajero"])
            for f in estado["datos"]:
                ws.append([f[0], f[1][:5], f[2] or "—", f[3] or "—",
                            f[4] or "—", f[5] or 0, f[6], f[7]])
            ws.append([])
            ws.append(["", "", "", "", "", "TOTAL:", estado["total"]])
            wb.save(nombre)
            messagebox.showinfo("Excel Generado", "Guardado correctamente.")
            _abrir_carpeta(ruta_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel:\n{e}")
            logger.registrar("reportes.py", "exportar_excel", e)

    def _abrir_carpeta(ruta):
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

    frame.after(200, _construir_botones_topbar)
    frame.after(300, lambda: actualizar_reporte("hoy"))
    return frame


# =============================================================================
# PANTALLA DE LECTURAS DEL PERÍODO
# =============================================================================

def crear_pantalla_lecturas(parent_frame, get_usuario_rol):
    """
    Subpantalla 'Lecturas del período':
    Tabla de todos los vecinos con medidor, su lectura del mes, anomalías y exportación.
    """
    from herramientas.db import obtener_lecturas_periodo, obtener_anomalias_consumo
    import herramientas.whatsapp_pdf as _wp

    frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    hoy = datetime.date.today()
    lista_anios   = [str(a) for a in range(2025, hoy.year + 2)]
    meses_nombres = list(MESES_ES.values())

    _periodo = {"mes": MESES_ES[hoy.month], "anio": hoy.year}
    _datos   = {"filas": [], "anomalias": set()}

    # ── Topbar ─────────────────────────────────────────────────────────────────
    bar = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ctk.CTkFrame(bar, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")

    izq = ctk.CTkFrame(bar, fg_color="transparent")
    izq.pack(side="left", padx=24, pady=10)
    ctk.CTkLabel(izq, text="Lecturas del Período",
                 font=FONT_TOPBAR, text_color=COLOR_TEXTO).pack(anchor="w")
    lbl_sub = ctk.CTkLabel(izq, text="Cargando...",
                            font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED)
    lbl_sub.pack(anchor="w")

    der = ctk.CTkFrame(bar, fg_color="transparent")
    der.pack(side="right", padx=20)

    combo_anio_l = ctk.CTkComboBox(der, values=lista_anios, width=76, state="readonly")
    combo_anio_l.pack(side="right", padx=(0, 4))
    combo_anio_l.set(str(_periodo["anio"]))
    combo_mes_l = ctk.CTkComboBox(der, values=meses_nombres, width=110, state="readonly")
    combo_mes_l.pack(side="right", padx=(0, 2))
    combo_mes_l.set(_periodo["mes"])
    ctk.CTkLabel(der, text="Período:", font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).pack(side="right", padx=(0, 4))

    def _cargar():
        _periodo["mes"]  = combo_mes_l.get()
        _periodo["anio"] = int(combo_anio_l.get())
        cargar_lecturas()

    ctk.CTkButton(der, text="Cargar", height=30, width=60, corner_radius=6,
                  fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                  text_color=COLOR_BLANCO, font=FONT_SMALL,
                  command=_cargar).pack(side="right", padx=(0, 12))

    # Filtro zona
    zonas_d = []
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("SELECT id, nombre FROM zonas WHERE activa=1 ORDER BY orden, nombre")
        zonas_d = cur.fetchall()
        con.close()
    except Exception:
        pass

    filtro_zona = {"zona_id": None}
    if zonas_d:
        nombres_z = ["Todas las zonas"] + [z[1] for z in zonas_d]
        ids_z     = [None] + [z[0] for z in zonas_d]
        combo_z   = ctk.CTkComboBox(der, values=nombres_z, width=150, state="readonly",
                                     command=lambda v: _set_zona(v, nombres_z, ids_z))
        combo_z.pack(side="right", padx=8)
        combo_z.set("Todas las zonas")

    def _set_zona(v, nombres, ids):
        idx = nombres.index(v) if v in nombres else 0
        filtro_zona["zona_id"] = ids[idx]
        cargar_lecturas()

    # Botones export
    btns_exp = ctk.CTkFrame(der, fg_color="transparent")
    btns_exp.pack(side="right", padx=(0, 12))

    def _exportar_excel_lecturas():
        if not _datos["filas"]:
            messagebox.showwarning("Sin datos", "No hay lecturas para exportar.")
            return
        try:
            ruta_dir = obtener_ruta("ruta_reportes_excel", RUTA_REPORTES_EXCEL_DEFAULT)
            os.makedirs(ruta_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = os.path.join(
                ruta_dir, f"Lecturas_{_periodo['mes']}_{_periodo['anio']}_{ts}.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Lecturas"
            comunidad = obtener_config("nombre_comunidad", "ADESCO")
            ws.append([f"{comunidad} — Lecturas {_periodo['mes']} {_periodo['anio']}"])
            ws.append([])
            ws.append(["Abonado", "Nombre", "Medidor", "Zona",
                        "Lect. Anterior", "Lect. Actual", "Consumo m³",
                        "Excedente m³", "Monto", "Anomalía"])
            for d in _datos["filas"]:
                anom = "SÍ" if d["vecino_id"] in _datos["anomalias"] else "No"
                if d["tiene_lectura"]:
                    ws.append([
                        d["num_abonado"] or "—", d["nombre"],
                        d["num_medidor"] or "—", d["zona"] or "—",
                        d["lectura_anterior"], d["lectura_actual"],
                        d["consumo_m3"], d["excedente_m3"], d["monto_total"], anom
                    ])
                else:
                    ws.append([
                        d["num_abonado"] or "—", d["nombre"],
                        d["num_medidor"] or "—", d["zona"] or "—",
                        "—", "—", "—", "—", "—", "PENDIENTE"
                    ])
            wb.save(nombre)
            messagebox.showinfo("Excel generado", "Guardado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel:\n{e}")

    def _exportar_pdf_lecturas():
        if not _datos["filas"]:
            messagebox.showwarning("Sin datos", "No hay lecturas para exportar.")
            return
        ruta = _wp.generar_pdf_lecturas(
            _datos["filas"], _periodo["mes"], _periodo["anio"], _datos["anomalias"])
        if ruta:
            messagebox.showinfo("PDF generado", "Guardado correctamente.")
        else:
            messagebox.showerror("Error", "No se pudo generar el PDF.")

    ctk.CTkButton(btns_exp, text="📊 Excel", height=34, corner_radius=8,
                   fg_color=COLOR_VERDE_PAGO, font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=_exportar_excel_lecturas).pack(side="right", padx=4)
    ctk.CTkButton(btns_exp, text="📄 PDF", height=34, corner_radius=8,
                   fg_color=COLOR_ROJO, font=FONT_BTN_SM, text_color=COLOR_BLANCO,
                   command=_exportar_pdf_lecturas).pack(side="right", padx=4)

    # ── Contenido ──────────────────────────────────────────────────────────────
    contenido = ctk.CTkFrame(frame, fg_color="transparent")
    contenido.pack(fill="both", expand=True, padx=24, pady=16)

    # Banner de alerta lecturas faltantes
    banner_faltantes = ctk.CTkFrame(contenido, fg_color="#FFFBEB", corner_radius=8)
    lbl_banner = ctk.CTkLabel(banner_faltantes, text="",
                               font=FONT_SMALL, text_color="#92400E")
    lbl_banner.pack(anchor="w", padx=12, pady=8)

    # Stats row
    stats_row = ctk.CTkFrame(contenido, fg_color="transparent")
    stats_row.pack(fill="x", pady=(0, 10))
    stats_labels = {}
    for key, texto, color in [
        ("total",     "total medidores", "#1A365D"),
        ("con_lect",  "con lectura",     "#2F855A"),
        ("sin_lect",  "sin lectura",     "#D69E2E"),
        ("anomalias", "anomalías",       "#C53030"),
    ]:
        lbl_n = ctk.CTkLabel(stats_row, text="—",
                              font=("Arial", 18, "bold"), text_color=color)
        lbl_n.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(stats_row, text=texto, font=FONT_SMALL,
                     text_color=COLOR_TEXTO_MUTED).pack(side="left", padx=(0, 20))
        stats_labels[key] = lbl_n

    ctk.CTkLabel(stats_row,
                 text="🔴 = consumo > 2× promedio histórico",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED).pack(side="right")

    # Tabla
    tabla_card = ctk.CTkFrame(contenido, fg_color=COLOR_BLANCO, corner_radius=10)
    tabla_card.pack(fill="both", expand=True)

    enc = ctk.CTkFrame(tabla_card, fg_color="#F8F9FB", corner_radius=0, height=36)
    enc.pack(fill="x")
    enc.pack_propagate(False)
    ctk.CTkFrame(enc, height=1, fg_color=COLOR_BORDE).pack(side="bottom", fill="x")
    for txt, w in [("Abonado", 70), ("Nombre", 170), ("Zona", 100),
                   ("Lect. Ant.", 90), ("Lect. Act.", 90),
                   ("Consumo m³", 95), ("Excedente", 85), ("Monto", 80), ("Estado", 100)]:
        ctk.CTkLabel(enc, text=txt, font=("Arial", 10, "bold"),
                     text_color=COLOR_TEXTO_MUTED, width=w, anchor="w"
                     ).pack(side="left", padx=(12 if txt == "Abonado" else 4, 0))

    marco = ctk.CTkScrollableFrame(tabla_card, fg_color=COLOR_FONDO, corner_radius=0)
    marco.pack(fill="both", expand=True, padx=1, pady=1)

    def cargar_lecturas():
        for w in marco.winfo_children():
            w.destroy()
        banner_faltantes.pack_forget()

        mes_p  = _periodo["mes"]
        anio_p = _periodo["anio"]
        zona_id = filtro_zona["zona_id"]

        filas = obtener_lecturas_periodo(mes_p, anio_p)

        # Filtrar por zona si aplica
        if zona_id and zonas_d:
            nombres_z_map = {z[0]: z[1] for z in zonas_d}
            zona_nombre   = nombres_z_map.get(zona_id, "")
            filas = [f for f in filas if f["zona"] == zona_nombre]

        anomalias = obtener_anomalias_consumo(mes_p, anio_p)

        _datos["filas"]     = filas
        _datos["anomalias"] = anomalias

        total     = len(filas)
        con_lect  = sum(1 for f in filas if f["tiene_lectura"])
        sin_lect  = total - con_lect
        anom_c    = len(anomalias)

        stats_labels["total"].configure(text=str(total))
        stats_labels["con_lect"].configure(text=str(con_lect))
        stats_labels["sin_lect"].configure(text=str(sin_lect))
        stats_labels["anomalias"].configure(text=str(anom_c))

        lbl_sub.configure(
            text=f"{mes_p} {anio_p} — {total} vecinos con medidor")

        if sin_lect > 0:
            lbl_banner.configure(
                text=f"⚠️  {sin_lect} vecino{'s' if sin_lect > 1 else ''} "
                     f"sin lectura registrada este período.")
            banner_faltantes.pack(fill="x", pady=(0, 8))

        if not filas:
            mensaje_vacio(marco, "No hay vecinos con medidor registrados.")
            return

        for d in filas:
            es_anomalia = d["vecino_id"] in anomalias
            bg = "#FFF5F5" if es_anomalia else (
                "#F0FFF4" if d["tiene_lectura"] else COLOR_BLANCO)

            fila = ctk.CTkFrame(marco, fg_color=bg, corner_radius=6, height=42)
            fila.pack(fill="x", pady=2, padx=4)
            fila.pack_propagate(False)

            ctk.CTkLabel(fila, text=d["num_abonado"] or "—",
                         font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                         width=70, anchor="w").pack(side="left", padx=12)
            ctk.CTkLabel(fila, text=d["nombre"],
                         font=("Arial", 12, "bold"), text_color=COLOR_TEXTO,
                         width=170, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila, text=d["zona"] or "—",
                         font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                         width=100, anchor="w").pack(side="left", padx=4)

            if d["tiene_lectura"]:
                for val, w in [
                    (f"{d['lectura_anterior']:.1f}", 90),
                    (f"{d['lectura_actual']:.1f}",   90),
                    (f"{d['consumo_m3']:.1f} m³",    95),
                    (f"{d['excedente_m3']:.1f} m³",  85),
                    (f"${d['monto_total']:.2f}",      80),
                ]:
                    ctk.CTkLabel(fila, text=val, font=FONT_SMALL,
                                 text_color=COLOR_TEXTO, width=w,
                                 anchor="w").pack(side="left", padx=4)

                if es_anomalia:
                    from config import COLOR_BADGE_ROJO_BG, COLOR_BADGE_ROJO_TEXT
                    from pantallas.componentes import badge
                    badge(fila, "⚠ Anomalía",
                          COLOR_BADGE_ROJO_BG, COLOR_BADGE_ROJO_TEXT,
                          width=98).pack(side="left", padx=4)
                else:
                    from config import COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT
                    from pantallas.componentes import badge
                    badge(fila, "✓ OK",
                          COLOR_BADGE_VERDE_BG, COLOR_BADGE_VERDE_TEXT,
                          width=98).pack(side="left", padx=4)
            else:
                for _ in range(5):
                    ctk.CTkLabel(fila, text="—", font=FONT_SMALL,
                                 text_color=COLOR_TEXTO_MUTED,
                                 width=[90, 90, 95, 85, 80][_],
                                 anchor="w").pack(side="left", padx=4)
                from config import COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT
                from pantallas.componentes import badge
                badge(fila, "Pendiente",
                      COLOR_BADGE_AMBER_BG, COLOR_BADGE_AMBER_TEXT,
                      width=98).pack(side="left", padx=4)

    frame.after(200, cargar_lecturas)
    return frame