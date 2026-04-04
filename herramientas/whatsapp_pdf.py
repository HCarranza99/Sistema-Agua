import os
import datetime
import calendar
import webbrowser
import urllib.parse
import platform
import subprocess
from fpdf import FPDF
from config import RUTA_RECIBOS_DEFAULT, RUTA_REPORTES_PDF_DEFAULT
import herramientas.logger as logger


# ── Utilidades ────────────────────────────────────────────────────────────────

def _ruta_recibos() -> str:
    from herramientas.db import obtener_ruta
    return obtener_ruta("ruta_recibos", RUTA_RECIBOS_DEFAULT)


def _ruta_reportes_pdf() -> str:
    from herramientas.db import obtener_ruta
    return obtener_ruta("ruta_reportes_pdf", RUTA_REPORTES_PDF_DEFAULT)


def _nombre_comunidad() -> str:
    from herramientas.db import obtener_config
    return obtener_config("nombre_comunidad", "ADESCO")


def _sanitizar_nombre(nombre: str) -> str:
    invalidos = r'\/:*?"<>|()'
    return "".join("_" if c in invalidos else c for c in nombre).replace(" ", "_")


def _lat1(texto) -> str:
    if texto is None:
        return ""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _abrir_carpeta(ruta: str) -> None:
    try:
        if platform.system() == "Windows":
            os.startfile(os.path.abspath(ruta))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", os.path.abspath(ruta)])
        else:
            subprocess.Popen(["xdg-open", os.path.abspath(ruta)])
    except Exception:
        pass


def _fecha_limite_str(anio: int, mes_nombre: str) -> tuple:
    """Retorna (dia_int, 'DD DE MES DE YYYY') según config."""
    from herramientas.db import obtener_config
    from config import MESES_ES
    try:
        dia_lim   = int(obtener_config("fecha_limite_pago", "25") or 25)
        meses_inv = {v: k for k, v in MESES_ES.items()}
        num_mes   = meses_inv.get(mes_nombre, 1)
        dias_mes  = calendar.monthrange(anio, num_mes)[1]
        dia_lim   = min(dia_lim, dias_mes)
        nombre_mes_up = mes_nombre.upper()
        return dia_lim, f"{dia_lim} DE {nombre_mes_up} DE {anio}"
    except Exception:
        return 25, "25"


# =============================================================================
# CLASE PDF — diseño fiel al formato físico de la imagen
# =============================================================================

class _FacturaRecibo(FPDF):
    """
    Genera un recibo en A5 (148 x 210 mm) con diseño de factura física:
    encabezado institucional, datos del abonado, tabla de lecturas,
    tabla de conceptos y pie con totales.
    """

    def __init__(self):
        super().__init__(format="A5")
        self.set_margins(6, 6, 6)
        self.set_auto_page_break(False)
        self.add_page()
        self._W = self.w - 12          # 136 mm de ancho útil
        self._X = self.l_margin        # 6 mm margen izquierdo
        self._BORDE = "LRTB"

    # ── helpers ───────────────────────────────────────────────────────────────

    def _at(self, x=None, y=None):
        if x is not None:
            self.set_x(x)
        if y is not None:
            self.set_y(y)

    def _cell(self, w, h, txt="", borde=0, ln=0, align="L",
              fill=False, bold=False, size=9):
        self.set_font("Arial", "B" if bold else "", size)
        self.cell(w, h, _lat1(txt), border=borde, ln=ln,
                  align=align, fill=fill)

    def _multi(self, w, h, txt="", borde=0, align="L",
               bold=False, size=9):
        self.set_font("Arial", "B" if bold else "", size)
        self.multi_cell(w, h, _lat1(txt), border=borde, align=align)

    # ── secciones ─────────────────────────────────────────────────────────────

    def header_institucional(self, comunidad: str, municipio: str,
                              logo_path: str = None):
        """Bloque superior: logo (opcional), nombre organización, subtítulo."""
        W = self._W
        X = self._X
        y0 = self.get_y()

        # Borde exterior del encabezado (dibujado al final cuando sabemos la altura)
        self.set_font("Arial", "B", 10)

        # Logo a la derecha si existe
        if logo_path and os.path.exists(logo_path):
            try:
                self.image(logo_path, x=X + W - 22, y=y0 + 2, h=14)
            except Exception:
                logo_path = None

        logo_w = 22 if logo_path else 0

        # Nombre organización centrado
        self.set_xy(X, y0)
        self.set_font("Arial", "B", 10)
        self.multi_cell(W - logo_w, 5,
                        _lat1(comunidad.upper()),
                        border=0, align="C")

        # Subtítulo
        self.set_x(X)
        self.set_font("Arial", "", 9)
        self.cell(W - logo_w, 5,
                  _lat1("FACTURA POR SERVICIO DE AGUA POTABLE"),
                  ln=True, align="C")

        # Borde del bloque
        h_bloque = self.get_y() - y0 + 2
        self.rect(X, y0, W, h_bloque)
        self.ln(2)

    def fila_numero_factura(self, num_factura: str):
        """Número de factura alineado a la derecha."""
        W = self._W
        X = self._X
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "", 8)
        self.cell(W - 38, 5, "", ln=0)
        self.set_font("Arial", "B", 9)
        self.cell(38, 5, _lat1(f"Factura N.{num_factura}"), ln=True, align="R")

    def seccion_datos_cliente(self, nombre: str, num_abonado: str,
                               categoria: str, direccion: str,
                               num_medidor: str, fecha_emision: str):
        """Bloque con datos del abonado (izq) y medidor/fecha (der)."""
        W  = self._W
        X  = self._X
        y0 = self.get_y()
        W_izq = round(W * 0.64)
        W_der = W - W_izq
        H_fila = 5

        # ── Columna izquierda ─────────────────────────────────────────────────
        self.set_xy(X, y0)
        self.set_font("Arial", "", 7)
        self.cell(W_izq, H_fila, _lat1("Nombre del Usuario:"), border="LT")
        # columna derecha header
        self.set_font("Arial", "B", 7)
        self.cell(W_der, H_fila, _lat1("Medidor"), border="LRT", align="C", ln=True)

        # nombre del vecino (más grande)
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "B", 11)
        # Nombre puede ser largo, lo truncamos a una línea
        nombre_corto = nombre[:30] if len(nombre) > 30 else nombre
        self.cell(W_izq, 7, _lat1(nombre_corto), border="LB")
        # número de medidor
        self.set_font("Arial", "B", 10)
        self.cell(W_der, 7, _lat1(num_medidor or "—"), border="LRB", align="C", ln=True)

        # abonado + categoría
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "", 8)
        self.cell(W_izq, H_fila,
                  _lat1(f"Numero #{num_abonado or '—'}"),
                  border="LT")
        self.set_font("Arial", "B", 7)
        self.cell(W_der, H_fila, _lat1("Fecha de"),
                  border="LT", align="C", ln=True)

        # categoría
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "B", 8)
        self.cell(W_izq, H_fila, _lat1((categoria or "Residencial").upper()),
                  border="L")
        self.set_font("Arial", "", 7)
        self.cell(W_der, H_fila, _lat1("Emision:"),
                  border="L", align="C", ln=True)

        # dirección (dos filas si es larga)
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "", 7)
        dir_txt = f"Direccion: {direccion or '—'}"
        self.cell(W_izq, H_fila, _lat1(dir_txt[:42]), border="L")
        self.set_font("Arial", "B", 9)
        self.cell(W_der, H_fila, _lat1(fecha_emision), border="LR", align="C", ln=True)

        # fila de cierre
        self.set_xy(X, self.get_y())
        self.cell(W_izq, 2, "", border="LB")
        self.cell(W_der, 2, "", border="LRB", ln=True)

    def seccion_lecturas(self, ant: float, act: float,
                          consumo: float, excedente: float):
        """Tabla de lecturas de medidor (4 columnas)."""
        W  = self._W
        X  = self._X
        Hh = 5   # header height
        Hr = 6   # row height
        c  = [38, 34, 30, W - 38 - 34 - 30]  # column widths

        # Encabezados
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "", 8)
        for txt, w in zip(["Lectura Anterior", "Lectura Actual",
                            "Consumo", "Sobre consumo"], c):
            self.cell(w, Hh, _lat1(txt), border=1, align="C")
        self.ln()

        # Valores
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "B", 10)
        for val, w in zip([f"{ant:.0f}", f"{act:.0f}",
                           f"{consumo:.0f}", f"{excedente:.0f}"], c):
            self.cell(w, Hr, _lat1(val), border=1, align="C")
        self.ln()

    def seccion_conceptos(self, tarifa_basica: float,
                           cargo_consumo: float, mora: float,
                           otros: list):
        """
        Tabla de conceptos: header + filas de detalle + filas vacías de relleno.
        otros: lista de (descripcion, monto)
        """
        W    = self._W
        X    = self._X
        Wc   = round(W * 0.72)   # col conceptos
        Wv   = W - Wc             # col valores
        Hh   = 6
        Hr   = 6
        N_FILAS_MIN = 6   # siempre al menos este número de filas en el cuerpo

        # Encabezado
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "B", 9)
        self.cell(Wc, Hh, _lat1("CONCEPTOS"), border=1, align="C")
        self.cell(Wv, Hh, _lat1("VALORES"),   border=1, align="C", ln=True)

        # Armar filas
        filas = []
        filas.append(("Tarifa Basica", tarifa_basica))
        if cargo_consumo > 0:
            filas.append(("Cargo Por Sobre consumo", cargo_consumo))
        if mora > 0:
            filas.append(("Recargo por mora", mora))
        for desc, mto in (otros or []):
            filas.append((desc, mto))

        # Dibujar filas reales
        self.set_font("Arial", "", 9)
        for desc, mto in filas:
            self.set_xy(X, self.get_y())
            self.cell(Wc, Hr, _lat1(f"  {desc}"), border="LRB", align="R")
            self.cell(Wv, Hr, _lat1(f"  ${mto:.2f}"), border="LRB", align="R", ln=True)

        # Filas vacías de relleno
        vacías = max(0, N_FILAS_MIN - len(filas))
        for _ in range(vacías):
            self.set_xy(X, self.get_y())
            self.cell(Wc, Hr, "", border="LRB")
            self.cell(Wv, Hr, "", border="LRB", ln=True)

    def seccion_footer(self, mes: str, anio: int,
                        m3_incluidos: float,
                        monto_mes: float,
                        total_deudas: float,
                        mora_si_vence: float):
        """
        Pie de factura:
          - Fila "Después De Vencido Pagará" | "Tarifa Básica por X m³"
          - Última Fecha De Pago | Total Del Mes    | $X
          -                      | Meses Anteriores | $X
          -  31 DE MES DE YYYY   | Total General    | $X
        """
        W   = self._W
        X   = self._X
        _, fecha_lim_txt = _fecha_limite_str(anio, mes)
        total_general    = monto_mes + total_deudas
        monto_vencido    = total_general + mora_si_vence

        # Anchos de columnas del pie
        W1 = round(W * 0.40)   # "Última Fecha..."
        W2 = round(W * 0.38)   # "Total Del Mes" etc.
        W3 = W - W1 - W2       # monto

        H = 6

        # Fila vencido
        self.set_xy(X, self.get_y())
        self.set_font("Arial", "", 7)
        self.cell(W1, H * 2,
                  _lat1(f"Despues De Vencido Pagara\n${monto_vencido:.2f}"),
                  border="LTR", align="C")
        self.set_font("Arial", "", 7)
        self.cell(W2 + W3, H * 2,
                  _lat1(f"Tarifa Basica por\n{m3_incluidos:.0f} Metros Cubicos."),
                  border="LTR", align="C", ln=True)

        # Totales (3 filas x 3 columnas)
        totales = [
            ("Total Del Mes",    monto_mes),
            ("Meses Anteriores", total_deudas),
            ("Total General",    total_general),
        ]
        fechas_col = [
            "Ultima Fecha",
            "De Pago",
            fecha_lim_txt,
        ]

        for i, ((label, monto), fecha_txt) in enumerate(zip(totales, fechas_col)):
            self.set_xy(X, self.get_y())

            borde_izq  = "LTB" if i < 2 else "LTRB"
            borde_med  = "LTB" if i < 2 else "LTRB"
            borde_der  = "LTRB"

            # Columna izquierda (fecha)
            if i == 2:
                self.set_font("Arial", "B", 8)
            else:
                self.set_font("Arial", "", 7)
            self.cell(W1, H, _lat1(fecha_txt), border=borde_izq, align="C")

            # Columna central (label)
            self.set_font("Arial", "", 8)
            self.cell(W2, H, _lat1(label), border=borde_med, align="C")

            # Columna derecha (monto)
            self.set_font("Arial", "B", 9 if i == 2 else 8)
            self.cell(W3, H, _lat1(f"${monto:.2f}"),
                      border=borde_der, align="R", ln=True)

    def sello_pagado(self):
        """Dibuja el sello 'PAGADO' en diagonal sobre el contenido."""
        self.set_font("Arial", "B", 40)
        self.set_text_color(47, 133, 90)
        # Guardar estado y rotar
        with self.rotation(30, self.w / 2, self.h / 2):
            self.set_xy(self.w / 2 - 45, self.h / 2 - 10)
            self.cell(90, 20, _lat1("PAGADO"), border=0, align="C")
        self.set_text_color(0, 0, 0)


# =============================================================================
# FUNCIÓN PRINCIPAL — construir y guardar el PDF
# =============================================================================

def _generar_factura(
    nombre_vecino: str,
    num_abonado:   str,
    categoria:     str,
    direccion:     str,
    num_medidor:   str,
    mes:           str,
    anio:          int,
    tarifa_basica: float,
    lectura_datos: dict,     # None si cuota fija
    deudas_pendientes: list,
    cargos_extra:  list,
    mora_auto:     float,
    es_pagado:     bool,
    num_factura:   str,
    ruta_salida:   str,
) -> str:
    """
    Construye el PDF en el formato físico de factura y lo guarda en ruta_salida.
    lectura_datos: {anterior, actual, consumo, excedente, monto_excedente, monto}
    """
    from herramientas.db import obtener_config
    comunidad   = _nombre_comunidad()
    municipio   = obtener_config("municipio", "")
    ruta_logo   = obtener_config("ruta_logo", "")
    m3_inc      = float(obtener_config("m3_incluidos", "25") or 25)
    mora_tipo   = obtener_config("mora_tipo", "fijo")
    mora_valor  = float(obtener_config("mora_valor", "1.00") or 1.0)

    fecha_emi = datetime.date.today().strftime("%d/%m/%y")

    # Calcular montos
    if lectura_datos:
        monto_mes     = lectura_datos.get("monto", tarifa_basica)
        cargo_consumo = lectura_datos.get("monto_excedente", 0)
        ant  = lectura_datos.get("anterior", 0)
        act  = lectura_datos.get("actual",   0)
        cons = lectura_datos.get("consumo",  0)
        exc  = lectura_datos.get("excedente", 0)
    else:
        monto_mes     = tarifa_basica
        cargo_consumo = 0
        ant = act = cons = exc = 0

    # Mora automática si el recibo ya está vencido (solo en recibos pendientes)
    if mora_auto > 0:
        mora_display = mora_auto
    else:
        mora_display = 0

    # Mora que aparecería si no paga a tiempo (para "Después de Vencido")
    if mora_tipo == "porcentaje":
        mora_si_vence = round(monto_mes * mora_valor / 100, 2)
    else:
        mora_si_vence = mora_valor

    total_deudas  = sum(d.get("monto", 0) for d in (deudas_pendientes or []))
    otros_cargos  = [(c.get("descripcion", "Cargo"), c.get("monto", 0))
                     for c in (cargos_extra or [])]

    try:
        pdf = _FacturaRecibo()

        # 1 — Encabezado institucional
        pdf.header_institucional(comunidad, municipio,
                                  ruta_logo if ruta_logo else None)

        # 2 — Número de factura
        pdf.fila_numero_factura(num_factura)

        # 3 — Datos del cliente
        pdf.seccion_datos_cliente(
            nombre_vecino, num_abonado, categoria, direccion,
            num_medidor, fecha_emi)

        # 4 — Lecturas (solo si tiene medidor con datos)
        if lectura_datos and act > 0:
            pdf.seccion_lecturas(ant, act, cons, exc)

        # 5 — Conceptos
        pdf.seccion_conceptos(
            tarifa_basica=tarifa_basica,
            cargo_consumo=cargo_consumo,
            mora=mora_display,
            otros=otros_cargos)

        # 6 — Pie de factura
        pdf.seccion_footer(
            mes=mes,
            anio=anio,
            m3_incluidos=m3_inc,
            monto_mes=monto_mes + mora_display,
            total_deudas=total_deudas,
            mora_si_vence=mora_si_vence)

        # 7 — Sello PAGADO si aplica
        if es_pagado:
            pdf.sello_pagado()

        pdf.output(ruta_salida)
        return ruta_salida

    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "_generar_factura", e)
        return ""


# =============================================================================
# API PÚBLICA — generar_pdf_recibo  (comprobante de PAGO)
# =============================================================================

def generar_pdf_recibo(
    nombre_vecino: str,
    meses_pagados: list,
    total_pagado:  float,
    cajero:        str,
    cargos_extra:  list = None,
    lectura_datos: dict = None,
    num_abonado:   str  = "",
    categoria:     str  = "Residencial",
    direccion:     str  = "",
    num_medidor:   str  = "",
    zona:          str  = "",
) -> str:
    """Genera el PDF del comprobante de PAGO realizado."""
    try:
        from herramientas.db import incrementar_num_factura, obtener_config
        ruta_dir = _ruta_recibos()
        os.makedirs(ruta_dir, exist_ok=True)

        num_factura   = incrementar_num_factura()
        ts            = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        nombre_seguro = _sanitizar_nombre(nombre_vecino)
        ruta_salida   = os.path.join(
            ruta_dir, f"Factura_{num_factura}_{nombre_seguro}_{ts}.pdf")

        # Extraer mes/anio del primer item pagado
        primer = meses_pagados[0] if meses_pagados else {}
        partes = primer.get("mes_anio", "").rsplit(" ", 1)
        mes    = partes[0] if partes else ""
        anio   = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() \
                 else datetime.date.today().year
        tarifa = float(obtener_config("tarifa_basica", "5.00") or 5.0)

        # Normalizar lectura_datos
        lec = None
        if lectura_datos:
            lec = {
                "anterior":        lectura_datos.get("lectura_anterior", 0),
                "actual":          lectura_datos.get("lectura_actual",   0),
                "consumo":         lectura_datos.get("consumo_m3",       0),
                "excedente":       lectura_datos.get("excedente_m3",     0),
                "monto_excedente": lectura_datos.get("monto_excedente",  0),
                "monto":           lectura_datos.get("monto_total",      tarifa),
            }

        return _generar_factura(
            nombre_vecino=nombre_vecino,
            num_abonado=num_abonado,
            categoria=categoria,
            direccion=direccion,
            num_medidor=num_medidor,
            mes=mes,
            anio=anio,
            tarifa_basica=tarifa,
            lectura_datos=lec,
            deudas_pendientes=[],
            cargos_extra=cargos_extra or [],
            mora_auto=0.0,
            es_pagado=True,
            num_factura=num_factura,
            ruta_salida=ruta_salida,
        )
    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_recibo", e)
        return ""


# =============================================================================
# API PÚBLICA — generar_pdf_recibo_pendiente  (para envío masivo)
# =============================================================================

def generar_pdf_recibo_pendiente(
    nombre_vecino:     str,
    mes:               str,
    anio:              int,
    monto_cuota:       float,
    deudas_pendientes: list,
    total:             float,
    numero_recibo:     str,
    lectura_datos:     dict = None,
    num_abonado:       str  = "",
    categoria:         str  = "Residencial",
    direccion:         str  = "",
    num_medidor:       str  = "",
    zona:              str  = "",
) -> str:
    """Genera el PDF del recibo pendiente de pago (para envío masivo)."""
    try:
        from herramientas.db import incrementar_num_factura, obtener_config
        ruta_dir = _ruta_recibos()
        os.makedirs(ruta_dir, exist_ok=True)

        num_factura   = incrementar_num_factura()
        nombre_seguro = _sanitizar_nombre(nombre_vecino)
        ruta_salida   = os.path.join(
            ruta_dir, f"Recibo_{num_factura}_{nombre_seguro}_{numero_recibo}.pdf")
        tarifa = float(obtener_config("tarifa_basica", "5.00") or 5.0)

        # Normalizar lectura_datos (viene de envio_recibos con keys distintos)
        lec = None
        if lectura_datos:
            lec = {
                "anterior":        lectura_datos.get("anterior",        0),
                "actual":          lectura_datos.get("actual",          0),
                "consumo":         lectura_datos.get("consumo",         0),
                "excedente":       lectura_datos.get("excedente",       0),
                "monto_excedente": lectura_datos.get("monto_excedente", 0),
                "monto":           lectura_datos.get("monto",           monto_cuota),
            }

        return _generar_factura(
            nombre_vecino=nombre_vecino,
            num_abonado=num_abonado,
            categoria=categoria,
            direccion=direccion,
            num_medidor=num_medidor,
            mes=mes,
            anio=anio,
            tarifa_basica=monto_cuota,
            lectura_datos=lec,
            deudas_pendientes=deudas_pendientes or [],
            cargos_extra=[],
            mora_auto=0.0,
            es_pagado=False,
            num_factura=num_factura,
            ruta_salida=ruta_salida,
        )
    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_recibo_pendiente", e)
        return ""


# =============================================================================
# ENVÍO POR WHATSAPP WEB
# =============================================================================

def abrir_whatsapp(telefono: str, mensaje: str) -> bool:
    if not telefono:
        return False
    try:
        numero = "".join(filter(str.isdigit, str(telefono)))
        if len(numero) == 8:
            numero = "503" + numero
        elif not numero:
            return False
        url = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"
        webbrowser.open(url)
        return True
    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "abrir_whatsapp", e)
        return False


def construir_mensaje_recibo_pago(
    nombre_vecino: str,
    meses_pagados: list,
    total_pagado:  float,
    cajero:        str,
    numero_recibo: str,
) -> str:
    comunidad = _nombre_comunidad()
    fecha_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    detalle   = "\n".join(
        f"💧 {i.get('mes_anio', str(i))}" if isinstance(i, dict) else f"💧 {i}"
        for i in meses_pagados)
    return (
        f"*{comunidad}*\n"
        f"✅ *Comprobante de Pago*\n\n"
        f"👤 Vecino: {nombre_vecino}\n"
        f"📅 Fecha: {fecha_str}\n"
        f"📄 Factura N°: {numero_recibo}\n\n"
        f"*Detalle cancelado:*\n{detalle}\n\n"
        f"💰 *Total: ${total_pagado:.2f}*\n\n"
        f"Adjunto encontrará su comprobante oficial en PDF. Gracias por su pago.\n"
        f"_Atendido por: {cajero}_"
    )


def construir_mensaje_recibo_pendiente(
    nombre_vecino:     str,
    mes:               str,
    anio:              int,
    monto_cuota:       float,
    deudas_pendientes: list,
    total:             float,
    numero_recibo:     str,
) -> str:
    comunidad = _nombre_comunidad()
    _, fecha_lim = _fecha_limite_str(anio, mes)
    deuda_txt   = ""
    if deudas_pendientes:
        lineas    = "\n".join(
            f"   ⚠️ {d['mes']} {d['anio']}: ${d['monto']:.2f}"
            for d in deudas_pendientes)
        deuda_txt = f"\n\n*Meses pendientes:*\n{lineas}"
    return (
        f"*{comunidad}*\n"
        f"📋 *Recibo de Cobro — {mes} {anio}*\n\n"
        f"👤 {nombre_vecino}\n"
        f"📄 Factura N°: {numero_recibo}\n"
        f"💧 Cuota del mes: ${monto_cuota:.2f}"
        f"{deuda_txt}\n\n"
        f"💰 *Total a cancelar: ${total:.2f}*\n"
        f"📅 Fecha limite: {fecha_lim}\n\n"
        f"Por favor acerquese a realizar su pago o comuniquese con su cobrador.\n"
        f"Adjunto su comprobante en PDF."
    )


def construir_mensaje_cierre_caja(
    fecha:    str,
    total:    float,
    cantidad: int,
    cajero:   str,
) -> str:
    comunidad = _nombre_comunidad()
    return (
        f"*{comunidad}*\n"
        f"🔒 *Cierre de Caja — {fecha}*\n\n"
        f"💰 Total recaudado: *${total:.2f}*\n"
        f"📊 Transacciones: {cantidad}\n"
        f"👤 Cajero: {cajero}\n\n"
        f"Adjunto el reporte PDF detallado del dia."
    )


# =============================================================================
# PDF REPORTE DE RECAUDACIÓN (sin cambio de diseño)
# =============================================================================

def generar_pdf_reporte(
    datos:         list,
    total:         float,
    titulo:        str,
    cierre_de_caja: bool = False,
) -> str:
    try:
        ruta_dir = _ruta_reportes_pdf()
        os.makedirs(ruta_dir, exist_ok=True)

        ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        titulo_s  = _sanitizar_nombre(titulo)
        nombre    = os.path.join(ruta_dir, f"Reporte_{titulo_s}_{ts}.pdf")
        comunidad = _nombre_comunidad()
        titulo_pdf = (f"{comunidad} - CIERRE DE CAJA"
                      if cierre_de_caja
                      else f"{comunidad} - Reporte de Recaudacion")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, _lat1(titulo_pdf), ln=True, align="C")
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 8, _lat1(f"Periodo: {titulo}"), ln=True, align="C")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        pdf.set_font("Arial", "B", 10)
        for h, w in [("Fecha y Hora", 35), ("Vecino", 50),
                     ("Concepto", 55), ("Cajero", 30), ("Monto", 20)]:
            pdf.cell(w, 8, _lat1(h), border=1)
        pdf.ln()

        pdf.set_font("Arial", "", 9)
        for fecha, hora, vecino, mes_p, anio_p, monto, cajero in datos:
            pdf.cell(35, 8, _lat1(f"{fecha} {hora[:5]}"), border=1)
            pdf.cell(50, 8, _lat1(str(vecino)[:24]), border=1)
            pdf.cell(55, 8, _lat1(f"Recibo {mes_p} {anio_p}"), border=1)
            pdf.cell(30, 8, _lat1(str(cajero)), border=1)
            pdf.cell(20, 8, f"${monto:.2f}", border=1, ln=True, align="R")

        pdf.set_font("Arial", "B", 12)
        pdf.cell(170, 10, _lat1("TOTAL RECAUDADO:"), border=1, align="R")
        pdf.cell(20,  10, f"${total:.2f}", border=1, ln=True, align="R")

        pdf.output(nombre)
        return nombre
    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_reporte", e)
        return ""


# =============================================================================
# PDF REPORTE DE LECTURAS
# =============================================================================

def generar_pdf_lecturas(datos: list, mes: str, anio: int,
                          anomalias: set = None) -> str:
    try:
        ruta_dir = _ruta_reportes_pdf()
        os.makedirs(ruta_dir, exist_ok=True)

        ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre    = os.path.join(ruta_dir, f"Lecturas_{mes}_{anio}_{ts}.pdf")
        comunidad = _nombre_comunidad()
        anomalias = anomalias or set()

        pdf = FPDF(orientation="L")
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _lat1(f"{comunidad} - Lecturas de Medidor"), ln=True, align="C")
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 7, _lat1(f"Periodo: {mes} {anio}"), ln=True, align="C")
        pdf.line(10, pdf.get_y(), 287, pdf.get_y())
        pdf.ln(4)

        cols = [("Abonado", 20), ("Nombre", 55), ("Medidor", 25),
                ("Zona", 35), ("Lect. Ant.", 25), ("Lect. Act.", 25),
                ("Consumo m3", 28), ("Excedente", 25), ("Monto", 22), ("Estado", 25)]
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(26, 54, 93)
        pdf.set_text_color(255, 255, 255)
        for txt, w in cols:
            pdf.cell(w, 7, _lat1(txt), border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Arial", "", 8)
        for d in datos:
            anom = d["vecino_id"] in anomalias
            if anom:
                pdf.set_fill_color(255, 235, 235)
            else:
                pdf.set_fill_color(255, 255, 255)
            fill = anom
            pdf.cell(20, 6, _lat1(d["num_abonado"] or "—"), border=1, fill=fill)
            pdf.cell(55, 6, _lat1((d["nombre"] or "")[:28]), border=1, fill=fill)
            pdf.cell(25, 6, _lat1(d["num_medidor"] or "—"), border=1, fill=fill)
            pdf.cell(35, 6, _lat1((d["zona"] or "—")[:18]), border=1, fill=fill)
            if d["tiene_lectura"]:
                pdf.cell(25, 6, f"{d['lectura_anterior']:.1f}", border=1, align="R", fill=fill)
                pdf.cell(25, 6, f"{d['lectura_actual']:.1f}",  border=1, align="R", fill=fill)
                pdf.cell(28, 6, f"{d['consumo_m3']:.1f}",      border=1, align="R", fill=fill)
                pdf.cell(25, 6, f"{d['excedente_m3']:.1f}",    border=1, align="R", fill=fill)
                pdf.cell(22, 6, f"${d['monto_total']:.2f}",    border=1, align="R", fill=fill)
                estado = "ANOMALIA" if anom else "OK"
                cr = (196, 48, 48) if anom else (47, 133, 90)
                pdf.set_text_color(*cr)
                pdf.cell(25, 6, _lat1(estado), border=1, align="C", fill=fill)
                pdf.set_text_color(0, 0, 0)
            else:
                for cw in [25, 25, 28, 25, 22]:
                    pdf.cell(cw, 6, "—", border=1, align="C", fill=fill)
                pdf.set_text_color(196, 48, 48)
                pdf.cell(25, 6, _lat1("PENDIENTE"), border=1, align="C", fill=fill)
                pdf.set_text_color(0, 0, 0)
            pdf.ln()

        pdf.ln(4)
        total_reg  = sum(1 for d in datos if d["tiene_lectura"])
        pendientes = len(datos) - total_reg
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 6, _lat1(
            f"Total medidores: {len(datos)}  |  "
            f"Registradas: {total_reg}  |  "
            f"Pendientes: {pendientes}  |  "
            f"Anomalias: {len(anomalias)}"), ln=True)

        pdf.output(nombre)
        return nombre
    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_lecturas", e)
        return ""
