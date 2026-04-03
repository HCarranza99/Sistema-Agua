import os
import datetime
import webbrowser
import urllib.parse
import platform
import subprocess
from fpdf import FPDF
from config import RUTA_RECIBOS_DEFAULT, RUTA_REPORTES_PDF_DEFAULT
import herramientas.logger as logger


def _ruta_recibos() -> str:
    from herramientas.db import obtener_ruta
    return obtener_ruta("ruta_recibos", RUTA_RECIBOS_DEFAULT)


def _ruta_reportes_pdf() -> str:
    from herramientas.db import obtener_ruta
    return obtener_ruta("ruta_reportes_pdf", RUTA_REPORTES_PDF_DEFAULT)


def _nombre_comunidad() -> str:
    from herramientas.db import obtener_config
    return obtener_config("nombre_comunidad", "ADESCO")


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


def _sanitizar_nombre(nombre: str) -> str:
    """Elimina caracteres inválidos para nombres de archivo en Windows."""
    invalidos = r'\/:*?"<>|()'
    resultado = "".join("_" if c in invalidos else c for c in nombre)
    return resultado.replace(" ", "_")


def _lat1(texto: str) -> str:
    """Convierte string a Latin-1 seguro para fpdf."""
    if texto is None:
        return ""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _fecha_limite_str(anio: int, mes_nombre: str) -> str:
    """Retorna la fecha límite de pago como string 'DD/MM/YYYY'."""
    from herramientas.db import obtener_config
    from config import MESES_ES
    try:
        dia_lim = int(obtener_config("fecha_limite_pago", "25") or 25)
        meses_inv = {v: k for k, v in MESES_ES.items()}
        num_mes   = meses_inv.get(mes_nombre, 1)
        # La fecha límite es en el mismo mes
        import calendar
        dias_mes = calendar.monthrange(anio, num_mes)[1]
        dia_lim  = min(dia_lim, dias_mes)
        return f"{dia_lim:02d}/{num_mes:02d}/{anio}"
    except Exception:
        return "—"


# =============================================================================
# PDF FACTURA — diseño completo (pendiente o pagado)
# =============================================================================

class _FacturaPDF(FPDF):
    """PDF con encabezado institucional y layout de factura."""

    def __init__(self, comunidad, logo_path=None):
        super().__init__()
        self.comunidad  = comunidad
        self.logo_path  = logo_path
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(True, margin=15)

    # ── helpers de estilo ─────────────────────────────────────────────────────
    def _linea(self):
        self.set_draw_color(26, 54, 93)   # azul marino
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(3)

    def _linea_gris(self):
        self.set_draw_color(226, 232, 240)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(2)

    def _seccion(self, titulo):
        self.set_font("Arial", "B", 9)
        self.set_text_color(26, 54, 93)
        self.cell(0, 6, _lat1(titulo.upper()), ln=True)
        self._linea_gris()
        self.set_text_color(0, 0, 0)

    def _fila_kv(self, key, val, ancho_key=50):
        self.set_font("Arial", "B", 10)
        self.set_text_color(113, 128, 150)
        self.cell(ancho_key, 6, _lat1(key + ":"))
        self.set_font("Arial", "", 10)
        self.set_text_color(26, 32, 44)
        self.cell(0, 6, _lat1(str(val)), ln=True)
        self.set_text_color(0, 0, 0)

    def encabezado_factura(self, num_factura, fecha_emision, fecha_limite,
                           mes_periodo, anio_periodo):
        """Encabezado con logo, nombre y número de factura."""
        # Logo (si existe)
        y_inicio = self.get_y()
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.image(self.logo_path, x=15, y=y_inicio, h=18)
            except Exception:
                pass
            self.set_y(y_inicio)
            self.set_x(45)

        # Nombre de la comunidad
        self.set_font("Arial", "B", 16)
        self.set_text_color(26, 54, 93)
        self.cell(0, 9, _lat1(self.comunidad), ln=True, align="C")
        self.set_font("Arial", "I", 11)
        self.set_text_color(113, 128, 150)
        self.cell(0, 6, _lat1("Factura por Servicio de Agua Potable"), ln=True, align="C")
        self.set_text_color(0, 0, 0)
        self._linea()

        # Número de factura y fechas — dos columnas
        y_ref = self.get_y()
        self.set_font("Arial", "B", 12)
        self.set_text_color(26, 54, 93)
        self.cell(90, 8, _lat1(f"Factura N.{num_factura}"))
        self.set_font("Arial", "", 10)
        self.set_text_color(26, 32, 44)
        self.cell(0, 8, _lat1(f"Fecha de emisión: {fecha_emision}"), ln=True, align="R")

        self.set_font("Arial", "", 10)
        self.set_text_color(113, 128, 150)
        self.cell(90, 6, _lat1(f"Período: {mes_periodo} {anio_periodo}"))
        self.set_text_color(196, 48, 48)
        self.set_font("Arial", "B", 10)
        self.cell(0, 6, _lat1(f"Fecha límite de pago: {fecha_limite}"),
                  ln=True, align="R")
        self.set_text_color(0, 0, 0)
        self.ln(2)
        self._linea_gris()


def _construir_pdf_factura(
    nombre_vecino: str,
    num_abonado: str,
    categoria: str,
    direccion: str,
    num_medidor: str,
    zona: str,
    mes: str,
    anio: int,
    tarifa_basica: float,
    lectura_datos: dict,    # None si cuota fija
    deudas_pendientes: list,
    cargos_extra: list,
    mora: float,
    es_pagado: bool,
    num_factura: str,
    cajero: str,
) -> FPDF:
    """
    Construye el objeto FPDF con el diseño completo de factura.
    lectura_datos: {anterior, actual, consumo, excedente, monto_excedente, monto} o None
    """
    from herramientas.db import obtener_config
    comunidad  = _nombre_comunidad()
    ruta_logo  = obtener_config("ruta_logo", "")
    fecha_emi  = datetime.date.today().strftime("%d/%m/%Y")
    fecha_lim  = _fecha_limite_str(anio, mes)
    total_deudas = sum(d["monto"] for d in deudas_pendientes)

    pdf = _FacturaPDF(comunidad, ruta_logo if ruta_logo else None)
    pdf.add_page()

    pdf.encabezado_factura(num_factura, fecha_emi, fecha_lim, mes, anio)

    # ── Datos del abonado ─────────────────────────────────────────────────────
    pdf._seccion("Datos del abonado")
    pdf._fila_kv("Nombre",          nombre_vecino)
    pdf._fila_kv("N° Abonado",      num_abonado or "—")
    pdf._fila_kv("Categoría",       categoria or "Residencial")
    pdf._fila_kv("Dirección",       direccion or "—")
    if num_medidor:
        pdf._fila_kv("N° Medidor",  num_medidor)
    if zona:
        pdf._fila_kv("Zona",        zona)
    pdf.ln(3)

    # ── Tabla de lecturas (solo medidor) ──────────────────────────────────────
    if lectura_datos:
        pdf._seccion("Lecturas del período")
        # Encabezados de tabla
        pdf.set_fill_color(244, 246, 249)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(113, 128, 150)
        for txt, w in [("Lectura anterior", 45), ("Lectura actual", 40),
                       ("Consumo m³", 35), ("Excedente m³", 40), ("Monto excedente", 40)]:
            pdf.cell(w, 7, _lat1(txt), border=1, fill=True, align="C")
        pdf.ln()
        # Valores
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(26, 32, 44)
        ant  = lectura_datos.get("anterior", 0)
        act  = lectura_datos.get("actual",   0)
        cons = lectura_datos.get("consumo",  0)
        exc  = lectura_datos.get("excedente", 0)
        m_exc = lectura_datos.get("monto_excedente", 0)
        for val, w in [(f"{ant:.1f}", 45), (f"{act:.1f}", 40),
                       (f"{cons:.1f}", 35), (f"{exc:.1f}", 40), (f"${m_exc:.2f}", 40)]:
            pdf.cell(w, 7, _lat1(val), border=1, align="C")
        pdf.ln(5)

    # ── Tabla de conceptos ────────────────────────────────────────────────────
    pdf._seccion("Conceptos del mes")
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(244, 246, 249)
    pdf.set_text_color(113, 128, 150)
    pdf.cell(130, 7, _lat1("Descripción"), border=1, fill=True)
    pdf.cell(50,  7, _lat1("Monto"),       border=1, fill=True, align="R")
    pdf.ln()

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(26, 32, 44)

    def _fila_concepto(desc, monto, negrita=False):
        if negrita:
            pdf.set_font("Arial", "B", 10)
        else:
            pdf.set_font("Arial", "", 10)
        pdf.cell(130, 7, _lat1(desc), border=1)
        pdf.cell(50,  7, _lat1(f"${monto:.2f}"), border=1, align="R")
        pdf.ln()

    m3_inc  = float(obtener_config("m3_incluidos", "25") or 25)
    _fila_concepto(f"Tarifa básica (hasta {m3_inc:.0f} m³)", tarifa_basica)

    if lectura_datos and lectura_datos.get("excedente", 0) > 0:
        exc  = lectura_datos["excedente"]
        mxc  = lectura_datos.get("monto_excedente", 0)
        _fila_concepto(f"Cargo por sobre consumo ({exc:.1f} m³)", mxc)

    for cargo in (cargos_extra or []):
        tipo_txt = "Mora" if cargo.get("tipo") == "mora" else "Cargo adicional"
        _fila_concepto(f"{tipo_txt}: {cargo.get('descripcion','')}", cargo.get("monto", 0))

    if mora > 0:
        _fila_concepto("Recargo por mora", mora)

    # Subtotal mes
    monto_mes = (lectura_datos["monto"] if lectura_datos else tarifa_basica) + mora
    monto_mes += sum(c.get("monto", 0) for c in (cargos_extra or []))
    pdf.ln(1)
    pdf.set_fill_color(235, 248, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(130, 7, _lat1("Subtotal mes actual"), border=1, fill=True)
    pdf.cell(50,  7, _lat1(f"${monto_mes:.2f}"), border=1, align="R", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    # Meses anteriores adeudados
    if deudas_pendientes:
        for d in deudas_pendientes:
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(155, 44, 44)
            pdf.cell(130, 7, _lat1(f"Deuda pendiente: {d['mes']} {d['anio']}"), border=1)
            pdf.cell(50,  7, _lat1(f"${d['monto']:.2f}"), border=1, align="R")
            pdf.ln()
        pdf.set_text_color(0, 0, 0)

    # Total general
    total_general = monto_mes + total_deudas
    pdf.ln(2)
    pdf.set_fill_color(26, 54, 93)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(130, 9, _lat1("TOTAL GENERAL"), border=0, fill=True)
    pdf.cell(50,  9, _lat1(f"${total_general:.2f}"), border=0, align="R", fill=True)
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)

    # Nota fecha límite / sello PAGADO
    pdf.ln(4)
    if es_pagado:
        pdf.set_font("Arial", "B", 22)
        pdf.set_text_color(47, 133, 90)
        pdf.cell(0, 12, _lat1("✓  PAGADO"), ln=True, align="C")
    else:
        pdf.set_font("Arial", "I", 9)
        pdf.set_text_color(113, 128, 150)
        pdf.cell(0, 6,
                 _lat1(f"Si paga antes del {fecha_lim}, su servicio se mantiene activo. "
                       f"Atendido por: {cajero}."),
                 ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    return pdf


# =============================================================================
# API PÚBLICA — generar_pdf_recibo (comprobante de pago)
# =============================================================================

def generar_pdf_recibo(
    nombre_vecino: str,
    meses_pagados: list,
    total_pagado: float,
    cajero: str,
    cargos_extra: list = None,
    lectura_datos: dict = None,
    num_abonado: str = "",
    categoria: str = "Residencial",
    direccion: str = "",
    num_medidor: str = "",
    zona: str = "",
) -> str:
    """
    Genera el PDF del comprobante de PAGO realizado.
    meses_pagados: lista de dicts {mes_anio, monto, monto_orig, parcial}
    lectura_datos: {anterior, actual, consumo, excedente, monto_excedente, monto}
    """
    try:
        from herramientas.db import incrementar_num_factura, obtener_config
        ruta_dir = _ruta_recibos()
        os.makedirs(ruta_dir, exist_ok=True)

        fecha_actual   = datetime.datetime.now()
        num_factura    = incrementar_num_factura()
        nombre_seguro  = _sanitizar_nombre(nombre_vecino)
        nombre_archivo = os.path.join(
            ruta_dir, f"Factura_{num_factura}_{nombre_seguro}_{fecha_actual.strftime('%Y%m%d%H%M%S')}.pdf"
        )

        # Extraer mes/anio del primer item pagado
        primer = meses_pagados[0] if meses_pagados else {}
        partes = primer.get("mes_anio", "").rsplit(" ", 1)
        mes    = partes[0] if partes else ""
        anio   = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else fecha_actual.year
        tarifa = float(obtener_config("tarifa_basica", "5.00") or 5.0)

        # Convertir lectura_datos de cobros.py al formato de la factura
        lec_fmt = None
        if lectura_datos:
            lec_fmt = {
                "anterior":        lectura_datos.get("lectura_anterior", 0),
                "actual":          lectura_datos.get("lectura_actual",   0),
                "consumo":         lectura_datos.get("consumo_m3",       0),
                "excedente":       lectura_datos.get("excedente_m3",     0),
                "monto_excedente": lectura_datos.get("monto_excedente",  0),
                "monto":           lectura_datos.get("monto_total", tarifa),
            }

        pdf = _construir_pdf_factura(
            nombre_vecino=nombre_vecino,
            num_abonado=num_abonado,
            categoria=categoria,
            direccion=direccion,
            num_medidor=num_medidor,
            zona=zona,
            mes=mes,
            anio=anio,
            tarifa_basica=tarifa,
            lectura_datos=lec_fmt,
            deudas_pendientes=[],
            cargos_extra=cargos_extra or [],
            mora=0.0,
            es_pagado=True,
            num_factura=num_factura,
            cajero=cajero,
        )

        pdf.output(nombre_archivo)
        return nombre_archivo

    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_recibo", e)
        return ""


# =============================================================================
# API PÚBLICA — generar_pdf_recibo_pendiente (para envío masivo)
# =============================================================================

def generar_pdf_recibo_pendiente(
    nombre_vecino: str,
    mes: str,
    anio: int,
    monto_cuota: float,
    deudas_pendientes: list,
    total: float,
    numero_recibo: str,
    lectura_datos: dict = None,
    num_abonado: str = "",
    categoria: str = "Residencial",
    direccion: str = "",
    num_medidor: str = "",
    zona: str = "",
) -> str:
    """
    Genera PDF de recibo a cobrar (pendiente de pago). Para envío masivo.
    lectura_datos: {anterior, actual, consumo, excedente, monto_excedente, monto}
    """
    try:
        from herramientas.db import incrementar_num_factura, obtener_config
        ruta_dir = _ruta_recibos()
        os.makedirs(ruta_dir, exist_ok=True)

        num_factura    = incrementar_num_factura()
        nombre_seguro  = _sanitizar_nombre(nombre_vecino)
        nombre_archivo = os.path.join(
            ruta_dir, f"Recibo_{num_factura}_{nombre_seguro}_{numero_recibo}.pdf"
        )
        tarifa = float(obtener_config("tarifa_basica", "5.00") or 5.0)

        # Formatear lectura_datos si viene del envío
        lec_fmt = None
        if lectura_datos:
            lec_fmt = {
                "anterior":        lectura_datos.get("anterior",        0),
                "actual":          lectura_datos.get("actual",          0),
                "consumo":         lectura_datos.get("consumo",         0),
                "excedente":       lectura_datos.get("excedente",       lectura_datos.get("excedente_m3", 0)),
                "monto_excedente": lectura_datos.get("monto_excedente", 0),
                "monto":           lectura_datos.get("monto",           monto_cuota),
            }

        pdf = _construir_pdf_factura(
            nombre_vecino=nombre_vecino,
            num_abonado=num_abonado,
            categoria=categoria,
            direccion=direccion,
            num_medidor=num_medidor,
            zona=zona,
            mes=mes,
            anio=anio,
            tarifa_basica=monto_cuota,
            lectura_datos=lec_fmt,
            deudas_pendientes=deudas_pendientes,
            cargos_extra=[],
            mora=0.0,
            es_pagado=False,
            num_factura=num_factura,
            cajero="Sistema",
        )

        pdf.output(nombre_archivo)
        return nombre_archivo

    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_recibo_pendiente", e)
        return ""


# =============================================================================
# ENVÍO POR WHATSAPP WEB
# =============================================================================

def abrir_whatsapp(telefono: str, mensaje: str) -> bool:
    """Abre WhatsApp Web con el número y mensaje prellenado."""
    if not telefono:
        return False
    try:
        numero_limpio = "".join(filter(str.isdigit, str(telefono)))
        if len(numero_limpio) == 8:
            numero_limpio = "503" + numero_limpio
        elif len(numero_limpio) == 0:
            return False
        url = f"https://wa.me/{numero_limpio}?text={urllib.parse.quote(mensaje)}"
        webbrowser.open(url)
        return True
    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "abrir_whatsapp", e)
        return False


def construir_mensaje_recibo_pago(
    nombre_vecino: str,
    meses_pagados: list,
    total_pagado: float,
    cajero: str,
    numero_recibo: str
) -> str:
    """Construye el mensaje de WhatsApp para comprobante de pago."""
    comunidad = _nombre_comunidad()
    fecha_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    detalle   = "\n".join(
        f"💧 {item.get('mes_anio', str(item))}"
        if isinstance(item, dict) else f"💧 {item}"
        for item in meses_pagados
    )
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
    nombre_vecino: str,
    mes: str,
    anio: int,
    monto_cuota: float,
    deudas_pendientes: list,
    total: float,
    numero_recibo: str
) -> str:
    """Construye el mensaje de WhatsApp para recibo de cobro pendiente."""
    comunidad  = _nombre_comunidad()
    fecha_lim  = _fecha_limite_str(anio, mes)
    deuda_txt  = ""
    if deudas_pendientes:
        lineas = "\n".join(
            f"   ⚠️ {d['mes']} {d['anio']}: ${d['monto']:.2f}"
            for d in deudas_pendientes
        )
        deuda_txt = f"\n\n*Meses pendientes:*\n{lineas}"
    return (
        f"*{comunidad}*\n"
        f"📋 *Recibo de Cobro — {mes} {anio}*\n\n"
        f"👤 {nombre_vecino}\n"
        f"📄 Factura N°: {numero_recibo}\n"
        f"💧 Cuota del mes: ${monto_cuota:.2f}"
        f"{deuda_txt}\n\n"
        f"💰 *Total a cancelar: ${total:.2f}*\n"
        f"📅 Fecha límite: {fecha_lim}\n\n"
        f"Por favor acérquese a realizar su pago o comuníquese con su cobrador.\n"
        f"Adjunto su comprobante en PDF."
    )


def construir_mensaje_cierre_caja(
    fecha: str,
    total: float,
    cantidad: int,
    cajero: str
) -> str:
    """Mensaje de WhatsApp para notificación de cierre de caja al presidente."""
    comunidad = _nombre_comunidad()
    return (
        f"*{comunidad}*\n"
        f"🔒 *Cierre de Caja — {fecha}*\n\n"
        f"💰 Total recaudado: *${total:.2f}*\n"
        f"📊 Transacciones: {cantidad}\n"
        f"👤 Cajero: {cajero}\n\n"
        f"Adjunto el reporte PDF detallado del día."
    )


# =============================================================================
# PDF REPORTE DE RECAUDACIÓN (sin cambios de diseño)
# =============================================================================

def generar_pdf_reporte(
    datos: list,
    total: float,
    titulo: str,
    cierre_de_caja: bool = False
) -> str:
    """
    Genera el PDF del reporte de recaudación.
    datos: lista de tuplas (fecha, hora, vecino, mes_p, anio_p, monto, cajero)
    """
    try:
        ruta_dir = _ruta_reportes_pdf()
        os.makedirs(ruta_dir, exist_ok=True)

        ts        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        titulo_s  = _sanitizar_nombre(titulo)
        nombre    = os.path.join(ruta_dir, f"Reporte_{titulo_s}_{ts}.pdf")
        comunidad = _nombre_comunidad()
        titulo_pdf = (
            f"{comunidad} - CIERRE DE CAJA"
            if cierre_de_caja else
            f"{comunidad} - Reporte de Recaudación"
        )

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, _lat1(titulo_pdf), ln=True, align="C")
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 8, _lat1(f"Período: {titulo}"), ln=True, align="C")
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
    """
    Genera PDF del reporte de lecturas del período.
    datos: lista de dicts de obtener_lecturas_periodo()
    anomalias: set de vecino_ids con consumo anómalo
    """
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
        pdf.cell(0, 10, _lat1(f"{comunidad} — Lecturas de Medidor"), ln=True, align="C")
        pdf.set_font("Arial", "I", 11)
        pdf.cell(0, 7, _lat1(f"Período: {mes} {anio}"), ln=True, align="C")
        pdf.line(10, pdf.get_y(), 287, pdf.get_y())
        pdf.ln(4)

        # Encabezados
        cols = [("Abonado", 20), ("Nombre", 55), ("Medidor", 25),
                ("Zona", 35), ("Lect. Ant.", 25), ("Lect. Act.", 25),
                ("Consumo m³", 28), ("Excedente", 25), ("Monto", 22), ("Estado", 25)]
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(26, 54, 93)
        pdf.set_text_color(255, 255, 255)
        for txt, w in cols:
            pdf.cell(w, 7, _lat1(txt), border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Arial", "", 8)
        for d in datos:
            es_anomalia = d["vecino_id"] in anomalias
            if es_anomalia:
                pdf.set_fill_color(255, 235, 235)
            else:
                pdf.set_fill_color(255, 255, 255)

            fill = es_anomalia
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
                estado = "⚠ ANOMALÍA" if es_anomalia else "OK"
                color_e = (196, 48, 48) if es_anomalia else (47, 133, 90)
                pdf.set_text_color(*color_e)
                pdf.cell(25, 6, _lat1(estado), border=1, align="C", fill=fill)
                pdf.set_text_color(0, 0, 0)
            else:
                for _ in range(5):
                    pdf.cell(25 if _ < 4 else 22, 6, "—", border=1, align="C", fill=fill)
                pdf.set_text_color(196, 48, 48)
                pdf.cell(25, 6, _lat1("PENDIENTE"), border=1, align="C", fill=fill)
                pdf.set_text_color(0, 0, 0)
            pdf.ln()

        # Resumen al pie
        pdf.ln(4)
        total_registradas = sum(1 for d in datos if d["tiene_lectura"])
        pendientes_c      = len(datos) - total_registradas
        anomalias_c       = len(anomalias)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 6, _lat1(
            f"Total vecinos con medidor: {len(datos)}  |  "
            f"Lecturas registradas: {total_registradas}  |  "
            f"Pendientes: {pendientes_c}  |  Anomalías: {anomalias_c}"
        ), ln=True)

        pdf.output(nombre)
        return nombre

    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_lecturas", e)
        return ""
