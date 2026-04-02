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
    """
    Convierte un string a Latin-1 de forma segura para fpdf v1.
    Reemplaza caracteres sin equivalente Latin-1 por su versión más cercana
    en vez de crashear con UnicodeEncodeError.
    Ejemplo: 'José García' → 'Jos\xe9 Garc\xeda' (Latin-1 válido)
    """
    return texto.encode("latin-1", "replace").decode("latin-1")


# =============================================================================
# GENERACIÓN DE PDF — RECIBO DE PAGO
# =============================================================================

def generar_pdf_recibo(
    nombre_vecino: str,
    meses_pagados: list,
    total_pagado: float,
    cajero: str,
    cargos_extra: list = None
) -> str:
    """
    Genera el PDF del recibo de pago y retorna la ruta del archivo.
    cargos_extra: lista de dicts con {tipo, descripcion, monto}
    """
    try:
        ruta_dir      = _ruta_recibos()
        os.makedirs(ruta_dir, exist_ok=True)

        fecha_actual  = datetime.datetime.now()
        fecha_str     = fecha_actual.strftime("%d/%m/%Y %H:%M")
        numero_recibo = fecha_actual.strftime("%Y%m%d%H%M%S")
        nombre_seguro = _sanitizar_nombre(nombre_vecino)
        nombre_archivo = os.path.join(
            ruta_dir, f"Recibo_{nombre_seguro}_{numero_recibo}.pdf"
        )
        comunidad = _nombre_comunidad()

        pdf = FPDF()
        pdf.add_page()

        # Encabezado
        pdf.set_font("Arial", "B", 18)
        pdf.cell(0, 10, _lat1(comunidad), ln=True, align="C")
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 8, _lat1("Comprobante de Pago — Servicio de Agua"), ln=True, align="C")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        # Datos del recibo
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 7, _lat1(f"Fecha:        {fecha_str}"), ln=True)
        pdf.cell(0, 7, _lat1(f"Recibo N°:    {numero_recibo}"), ln=True)
        pdf.cell(0, 7, _lat1(f"Vecino:       {nombre_vecino}"), ln=True)
        pdf.cell(0, 7, _lat1(f"Atendido por: {cajero}"), ln=True)
        pdf.ln(4)

        # Detalle de meses
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, _lat1("Detalle de pago:"), ln=True)
        pdf.set_font("Arial", "", 12)
        for item in meses_pagados:
            mes_txt   = item.get("mes_anio", str(item)) if isinstance(item, dict) else str(item)
            monto_txt = f"${item.get('monto', 0):.2f}" if isinstance(item, dict) else ""
            es_parcial = isinstance(item, dict) and item.get("parcial", False)
            if es_parcial:
                monto_orig = item.get("monto_orig", 0)
                linea = f"   - Recibo de {mes_txt}  {monto_txt}  (ABONO PARCIAL — saldo pendiente: ${monto_orig - item.get('monto',0):.2f})"
            else:
                linea = f"   - Recibo de {mes_txt}  {monto_txt}"
            pdf.cell(0, 7, _lat1(linea), ln=True)

        # Nota si hay pagos parciales
        hay_parciales = any(isinstance(i, dict) and i.get("parcial") for i in meses_pagados)
        if hay_parciales:
            pdf.ln(2)
            pdf.set_font("Arial", "I", 10)
            pdf.set_text_color(180, 50, 50)
            pdf.cell(0, 7, _lat1("(*) Pago parcial: el saldo restante permanece pendiente."), ln=True)
            pdf.set_text_color(0, 0, 0)

        # Cargos extra
        if cargos_extra:
            pdf.ln(2)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, _lat1("Cargos adicionales:"), ln=True)
            pdf.set_font("Arial", "", 12)
            for cargo in cargos_extra:
                tipo_txt = "Mora" if cargo["tipo"] == "mora" else "Consumo extra"
                pdf.cell(
                    0, 7,
                    _lat1(f"   - {tipo_txt}: {cargo['descripcion']}  ${cargo['monto']:.2f}"),
                    ln=True
                )

        # Total
        pdf.ln(4)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _lat1(f"TOTAL PAGADO: ${total_pagado:.2f}"), ln=True)

        pdf.output(nombre_archivo)
        return nombre_archivo

    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_recibo", e)
        return ""


# =============================================================================
# GENERACIÓN DE PDF — RECIBO DE COBRO PENDIENTE (para envío masivo)
# =============================================================================

def generar_pdf_recibo_pendiente(
    nombre_vecino: str,
    mes: str,
    anio: int,
    monto_cuota: float,
    deudas_pendientes: list,
    total: float,
    numero_recibo: str
) -> str:
    """
    Genera PDF de recibo a cobrar (no pagado aún). Para envío masivo.
    deudas_pendientes: lista de dicts {mes, anio, monto}
    """
    try:
        ruta_dir = _ruta_recibos()
        os.makedirs(ruta_dir, exist_ok=True)

        nombre_seguro  = _sanitizar_nombre(nombre_vecino)
        nombre_archivo = os.path.join(
            ruta_dir, f"Recibo_Pendiente_{nombre_seguro}_{numero_recibo}.pdf"
        )
        comunidad = _nombre_comunidad()

        pdf = FPDF()
        pdf.add_page()

        pdf.set_font("Arial", "B", 18)
        pdf.cell(0, 10, _lat1(comunidad), ln=True, align="C")
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 8, _lat1(f"Recibo de Cobro — {mes} {anio}"), ln=True, align="C")
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 7, _lat1(f"Vecino:    {nombre_vecino}"), ln=True)
        pdf.cell(0, 7, _lat1(f"Período:   {mes} {anio}"), ln=True)
        pdf.cell(0, 7, _lat1(f"Cuota:     ${monto_cuota:.2f}"), ln=True)
        pdf.ln(4)

        if deudas_pendientes:
            pdf.set_font("Arial", "B", 12)
            pdf.set_fill_color(255, 230, 230)
            pdf.cell(0, 8, _lat1("Meses con deuda pendiente:"), ln=True)
            pdf.set_font("Arial", "", 12)
            for d in deudas_pendientes:
                pdf.cell(0, 7, _lat1(f"   - {d['mes']} {d['anio']}:  ${d['monto']:.2f}"), ln=True)
            pdf.ln(2)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _lat1(f"TOTAL A CANCELAR: ${total:.2f}"), ln=True)
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 7,
                 _lat1("Por favor acérquese a realizar su pago o comuníquese con su cobrador."),
                 ln=True)

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

    detalle = "\n".join(
        f"💧 {item.get('mes_anio', str(item))}"
        if isinstance(item, dict) else f"💧 {item}"
        for item in meses_pagados
    )

    return (
        f"*{comunidad}*\n"
        f"✅ *Comprobante de Pago*\n\n"
        f"👤 Vecino: {nombre_vecino}\n"
        f"📅 Fecha: {fecha_str}\n"
        f"📄 Recibo N°: {numero_recibo}\n\n"
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
    comunidad = _nombre_comunidad()

    deuda_txt = ""
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
        f"📄 Recibo N°: {numero_recibo}\n"
        f"💧 Cuota del mes: ${monto_cuota:.2f}"
        f"{deuda_txt}\n\n"
        f"💰 *Total a cancelar: ${total:.2f}*\n\n"
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
# GENERACIÓN DE PDF — REPORTE DE RECAUDACIÓN
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

        # Encabezados de tabla
        pdf.set_font("Arial", "B", 10)
        for h, w in [("Fecha y Hora", 35), ("Vecino", 50),
                     ("Concepto", 55), ("Cajero", 30), ("Monto", 20)]:
            pdf.cell(w, 8, _lat1(h), border=1)
        pdf.ln()

        # Filas
        pdf.set_font("Arial", "", 9)
        for fecha, hora, vecino, mes_p, anio_p, monto, cajero in datos:
            pdf.cell(35, 8, _lat1(f"{fecha} {hora[:5]}"), border=1)
            pdf.cell(50, 8, _lat1(str(vecino)[:24]), border=1)
            pdf.cell(55, 8, _lat1(f"Recibo {mes_p} {anio_p}"), border=1)
            pdf.cell(30, 8, _lat1(str(cajero)), border=1)
            pdf.cell(20, 8, f"${monto:.2f}", border=1, ln=True, align="R")

        # Total
        pdf.set_font("Arial", "B", 12)
        pdf.cell(170, 10, _lat1("TOTAL RECAUDADO:"), border=1, align="R")
        pdf.cell(20, 10, f"${total:.2f}", border=1, ln=True, align="R")

        pdf.output(nombre)
        return nombre

    except Exception as e:
        logger.registrar("whatsapp_pdf.py", "generar_pdf_reporte", e)
        return ""