import smtplib
import ssl
import os
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import herramientas.logger as logger

_SMTP_TIMEOUT = 10  # segundos — evita colgar la app si el servidor no responde


def _obtener_config_smtp() -> dict:
    """Lee la configuración SMTP desde la base de datos."""
    from herramientas.db import obtener_config
    from herramientas.seguridad import descifrar_texto
    # FIX: 'or "587"' evita ValueError si el campo quedó vacío en BD
    puerto_str = obtener_config("smtp_puerto", "587") or "587"
    try:
        puerto = int(puerto_str)
    except ValueError:
        puerto = 587
    return {
        "host":      obtener_config("smtp_host", "smtp.gmail.com"),
        "puerto":    puerto,
        "usuario":   obtener_config("smtp_usuario", ""),
        "password":  descifrar_texto(obtener_config("smtp_password_cifrada", "")),
        "remitente": obtener_config("smtp_remitente", ""),
    }


def enviar_correo(
    destinatario: str,
    asunto: str,
    cuerpo_html: str,
    adjunto_pdf: str = None
) -> tuple[bool, str]:
    """
    Envía un correo con adjunto PDF opcional (síncrono, para background threads).
    Para no bloquear la UI usar enviar_correo_async().

    Returns:
        (True, "") si fue exitoso
        (False, "mensaje de error") si falló
    """
    cfg = _obtener_config_smtp()

    if not cfg["usuario"] or not cfg["password"]:
        return False, "El correo no está configurado. Configure el SMTP en Configuración."

    if not destinatario or "@" not in destinatario:
        return False, "Dirección de correo inválida."

    try:
        msg = MIMEMultipart()
        msg["From"]    = cfg["remitente"] or cfg["usuario"]
        msg["To"]      = destinatario
        msg["Subject"] = asunto

        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

        if adjunto_pdf and os.path.exists(adjunto_pdf):
            nombre_pdf = os.path.basename(adjunto_pdf)
            with open(adjunto_pdf, "rb") as f:
                parte = MIMEBase("application", "octet-stream")
                parte.set_payload(f.read())
            encoders.encode_base64(parte)
            parte.add_header(
                "Content-Disposition",
                f'attachment; filename="{nombre_pdf}"'
            )
            msg.attach(parte)

        contexto = ssl.create_default_context()
        # FIX: timeout evita congelar la app con servidores lentos o caídos
        with smtplib.SMTP(cfg["host"], cfg["puerto"], timeout=_SMTP_TIMEOUT) as servidor:
            servidor.ehlo()
            servidor.starttls(context=contexto)
            servidor.login(cfg["usuario"], cfg["password"])
            servidor.sendmail(cfg["usuario"], destinatario, msg.as_string())

        return True, ""

    except smtplib.SMTPAuthenticationError:
        return False, "Credenciales SMTP incorrectas. Revise usuario y contraseña."
    except smtplib.SMTPConnectError:
        return False, "No se pudo conectar al servidor SMTP. Verifique host y puerto."
    except TimeoutError:
        return False, f"Tiempo de espera agotado ({_SMTP_TIMEOUT}s). Verifique el servidor SMTP."
    except Exception as e:
        logger.registrar("email_sender.py", "enviar_correo", e)
        return False, str(e)


def enviar_correo_async(
    destinatario: str,
    asunto: str,
    cuerpo_html: str,
    adjunto_pdf: str = None,
    callback=None
) -> None:
    """
    Envía un correo en un hilo background para NO bloquear la UI de Tkinter.

    callback(ok: bool, error: str) se llama cuando termina.
    Si el callback necesita actualizar widgets Tkinter, usar widget.after(0, fn).
    """
    def _worker():
        ok, err = enviar_correo(destinatario, asunto, cuerpo_html, adjunto_pdf)
        if callback:
            try:
                callback(ok, err)
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


def probar_conexion_smtp() -> tuple[bool, str]:
    """Prueba la conexión SMTP sin enviar correo. Para el panel de configuración."""
    cfg = _obtener_config_smtp()
    if not cfg["usuario"] or not cfg["password"]:
        return False, "Configure usuario y contraseña primero."
    try:
        contexto = ssl.create_default_context()
        # FIX: timeout evita congelar la UI al probar con host incorrecto
        with smtplib.SMTP(cfg["host"], cfg["puerto"], timeout=_SMTP_TIMEOUT) as servidor:
            servidor.ehlo()
            servidor.starttls(context=contexto)
            servidor.login(cfg["usuario"], cfg["password"])
        return True, f"Conexión exitosa con {cfg['host']}:{cfg['puerto']}"
    except smtplib.SMTPAuthenticationError:
        return False, "Credenciales incorrectas."
    except TimeoutError:
        return False, f"Tiempo de espera agotado ({_SMTP_TIMEOUT}s). Verifique el servidor."
    except Exception as e:
        return False, str(e)


def construir_cuerpo_recibo(
    nombre_vecino: str,
    mes: str,
    anio: int,
    monto_cuota: float,
    deudas_pendientes: list,
    total: float,
    cajero: str,
    nombre_comunidad: str,
    numero_recibo: str
) -> str:
    """Genera el HTML del cuerpo del correo para un recibo de cobro."""
    deudas_html = ""
    if deudas_pendientes:
        filas = "".join(
            f"<tr><td style='padding:4px 8px'>{d['mes']} {d['anio']}</td>"
            f"<td style='padding:4px 8px;color:#C53030'>${d['monto']:.2f}</td></tr>"
            for d in deudas_pendientes
        )
        deudas_html = f"""
        <p style='margin:16px 0 4px;font-weight:bold;color:#C53030'>
            Meses pendientes de pago:
        </p>
        <table style='border-collapse:collapse;width:100%'>{filas}</table>
        """

    return f"""
    <div style='font-family:Arial,sans-serif;max-width:520px;margin:auto'>
      <div style='background:#1A365D;color:white;padding:20px;border-radius:8px 8px 0 0'>
        <h2 style='margin:0'>💧 {nombre_comunidad}</h2>
        <p style='margin:4px 0 0;opacity:.8'>Comprobante de pago — Servicio de Agua</p>
      </div>
      <div style='background:#f9f9f9;padding:20px;border:1px solid #ddd'>
        <p>Estimado/a <strong>{nombre_vecino}</strong>,</p>
        <p>Le informamos que se ha registrado su recibo correspondiente a:</p>
        <table style='width:100%;border-collapse:collapse'>
          <tr>
            <td style='padding:6px 8px;background:#e8f0fe'>Recibo N°</td>
            <td style='padding:6px 8px'>{numero_recibo}</td>
          </tr>
          <tr>
            <td style='padding:6px 8px;background:#e8f0fe'>Período</td>
            <td style='padding:6px 8px'>{mes} {anio}</td>
          </tr>
          <tr>
            <td style='padding:6px 8px;background:#e8f0fe'>Cuota del mes</td>
            <td style='padding:6px 8px'>${monto_cuota:.2f}</td>
          </tr>
          <tr>
            <td style='padding:6px 8px;background:#1A365D;color:white;font-weight:bold'>
                Total a cancelar
            </td>
            <td style='padding:6px 8px;background:#1A365D;color:white;font-weight:bold'>
                ${total:.2f}
            </td>
          </tr>
        </table>
        {deudas_html}
        <p style='margin-top:16px;font-size:12px;color:#666'>
          Atendido por: {cajero}<br>
          Adjunto encontrará su comprobante oficial en PDF.
        </p>
      </div>
      <div style='background:#eee;padding:10px;text-align:center;font-size:11px;
                  color:#666;border-radius:0 0 8px 8px'>
        {nombre_comunidad} · Sistema de Pagos de Agua
      </div>
    </div>
    """


def construir_cuerpo_cierre_caja(
    fecha: str,
    total: float,
    cantidad: int,
    cajero: str,
    nombre_comunidad: str
) -> str:
    """Genera el HTML del cuerpo del correo para el cierre de caja."""
    return f"""
    <div style='font-family:Arial,sans-serif;max-width:520px;margin:auto'>
      <div style='background:#1A365D;color:white;padding:20px;border-radius:8px 8px 0 0'>
        <h2 style='margin:0'>🔒 Cierre de Caja</h2>
        <p style='margin:4px 0 0;opacity:.8'>{nombre_comunidad}</p>
      </div>
      <div style='background:#f9f9f9;padding:20px;border:1px solid #ddd'>
        <table style='width:100%;border-collapse:collapse'>
          <tr>
            <td style='padding:8px;background:#e8f0fe'>Fecha</td>
            <td style='padding:8px'>{fecha}</td>
          </tr>
          <tr>
            <td style='padding:8px;background:#e8f0fe'>Total recaudado</td>
            <td style='padding:8px;font-weight:bold;font-size:18px;color:#2F855A'>
                ${total:.2f}
            </td>
          </tr>
          <tr>
            <td style='padding:8px;background:#e8f0fe'>Transacciones</td>
            <td style='padding:8px'>{cantidad}</td>
          </tr>
          <tr>
            <td style='padding:8px;background:#e8f0fe'>Cajero</td>
            <td style='padding:8px'>{cajero}</td>
          </tr>
        </table>
        <p style='margin-top:16px;font-size:12px;color:#666'>
          Adjunto encontrará el reporte PDF detallado del día.
        </p>
      </div>
    </div>
    """
