import os
import datetime
import traceback
from config import RUTA_LOG


def registrar(modulo: str, accion: str, error: Exception) -> None:
    """Registra un error en errores.log sin interrumpir la ejecución."""
    try:
        ahora   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        detalle = traceback.format_exc().strip()
        linea = (
            f"[{ahora}] | {modulo} | {accion} | "
            f"{type(error).__name__}: {error}\n"
            f"    {detalle}\n"
            f"{'-' * 80}\n"
        )
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            f.write(linea)
    except Exception:
        pass


def leer_log(max_lineas: int = 200) -> str:
    """Lee las últimas N líneas del log. Usado por el panel de Soporte."""
    try:
        if not os.path.exists(RUTA_LOG):
            return "Sin errores registrados."
        with open(RUTA_LOG, "r", encoding="utf-8") as f:
            lineas = f.readlines()
        return "".join(lineas[-max_lineas:]) or "Sin errores registrados."
    except Exception as e:
        return f"Error al leer log: {e}"


def limpiar_log() -> bool:
    """Borra el contenido del log. Solo para Soporte."""
    try:
        with open(RUTA_LOG, "w", encoding="utf-8") as f:
            f.write("")
        return True
    except Exception:
        return False
