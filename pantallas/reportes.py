import customtkinter as ctk
import sqlite3
import datetime
import os
import openpyxl
from tkinter import messagebox
import herramientas.logger as logger
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

    encabezado_tabla(tabla_card, [
        ("Fecha y Hora", 140), ("Vecino", 190), ("Zona", 110),
        ("Concepto", 150), ("Usuario", 90)
    ])
    ctk.CTkLabel(
        tabla_card, text="MONTO", font=("Arial", 10, "bold"),
        text_color=COLOR_TEXTO_MUTED, width=80, anchor="e"
    ).place(relx=1.0, x=-80, y=18)

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
                       t.monto_cobrado, u.usuario
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

        total = sum(f[6] for f in datos)
        estado["total"] = total
        lbl_total_val.configure(text=f"${total:.2f}")
        lbl_txn_val.configure(text=str(len(datos)))
        prom = total / len(datos) if datos else 0
        lbl_prom_val.configure(text=f"${prom:.2f}")
        lbl_sub_topbar.configure(text=estado["titulo"])

        if not datos:
            mensaje_vacio(marco_tabla, "No hay transacciones en este período.")
            return

        for fecha, hora, vecino, zona, mes_p, anio_p, monto, cajero in datos:
            fila_w = ctk.CTkFrame(marco_tabla, fg_color=COLOR_BLANCO,
                                   corner_radius=6, height=46)
            fila_w.pack(fill="x", pady=2, padx=4)
            fila_w.pack_propagate(False)

            ctk.CTkLabel(fila_w, text=f"{fecha} {hora[:5]}", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=140,
                         anchor="w").pack(side="left", padx=16)
            ctk.CTkLabel(fila_w, text=vecino or "—",
                         font=("Arial", 12, "bold"), width=190,
                         anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=zona or "—", font=FONT_SMALL,
                         text_color=COLOR_TEXTO_MUTED, width=110,
                         anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(
                fila_w,
                text=f"Recibo {mes_p} {anio_p}" if mes_p else "Cargo extra",
                font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                width=150, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=cajero, fg_color=COLOR_BADGE_AZUL_BG,
                          text_color=COLOR_BADGE_AZUL_TEXT, corner_radius=20,
                          font=FONT_SMALL, width=80,
                          height=22).pack(side="left", padx=4)
            ctk.CTkLabel(fila_w, text=f"${monto:.2f}",
                         font=("Arial", 13, "bold"),
                         text_color=COLOR_VERDE_PAGO, width=80,
                         anchor="e").pack(side="right", padx=16)

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