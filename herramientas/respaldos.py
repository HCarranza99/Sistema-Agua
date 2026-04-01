import os
import shutil
import sqlite3
import datetime
from tkinter import messagebox, filedialog
from config import RUTA_BD, RUTA_RESPALDOS_DEFAULT, RUTA_SINCRONIZACION_DEFAULT
import herramientas.logger as logger

TABLAS_REQUERIDAS = {
    "usuarios", "vecinos", "recibos", "transacciones",
    "zonas", "cargos_extra", "cierres_caja", "config_sistema",
}


def _ruta_respaldos() -> str:
    """Retorna la ruta de respaldos configurada por el usuario o la default."""
    from herramientas.db import obtener_ruta
    return obtener_ruta("ruta_respaldos", RUTA_RESPALDOS_DEFAULT)


def _ruta_sincronizacion() -> str:
    from herramientas.db import obtener_ruta
    return obtener_ruta("ruta_sincronizacion", RUTA_SINCRONIZACION_DEFAULT)


def _verificar_integridad(ruta_db: str) -> bool:
    """Verifica que un .db se puede abrir y tiene las tablas esperadas."""
    try:
        conn = sqlite3.connect(ruta_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = {row[0] for row in cursor.fetchall()}
        conn.close()
        return TABLAS_REQUERIDAS.issubset(tablas)
    except Exception:
        return False


def crear_respaldo(silencioso: bool = False) -> bool:
    """
    Crea respaldo local y en carpeta de sincronización.
    Verifica integridad del archivo resultante.
    """
    try:
        if not os.path.exists(RUTA_BD):
            if not silencioso:
                messagebox.showerror("Error",
                                     "No se encontró la base de datos principal.")
            return False

        ruta_local = _ruta_respaldos()
        os.makedirs(ruta_local, exist_ok=True)

        timestamp     = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_backup = f"Backup_BD_{timestamp}.db"
        ruta_archivo  = os.path.join(ruta_local, nombre_backup)

        shutil.copy2(RUTA_BD, ruta_archivo)

        if not _verificar_integridad(ruta_archivo):
            if not silencioso:
                messagebox.showerror(
                    "Error de Verificación",
                    "El respaldo se creó pero no pasó la verificación de integridad."
                )
            os.remove(ruta_archivo)
            return False

        # Copia a sincronización en nube
        mensaje_nube = ""
        try:
            ruta_nube = _ruta_sincronizacion()
            os.makedirs(ruta_nube, exist_ok=True)
            shutil.copy2(RUTA_BD, os.path.join(ruta_nube, nombre_backup))
            mensaje_nube = (
                "\n\n☁️ Copia guardada en carpeta de sincronización.\n"
                "Asegúrese de vincularla con su servicio de nube."
            )
        except Exception as e:
            mensaje_nube = f"\n\n⚠️ Respaldo local creado, pero falló la copia a la nube:\n{e}"

        if not silencioso:
            messagebox.showinfo(
                "Respaldo Completado",
                f"Respaldo verificado y guardado:\n{nombre_backup}{mensaje_nube}"
            )
        return True

    except Exception as e:
        if not silencioso:
            messagebox.showerror("Error Crítico",
                                 f"No se pudo crear el respaldo:\n{e}")
        logger.registrar("respaldos.py", "crear_respaldo", e)
        return False


def restaurar_desde_respaldo() -> bool:
    """
    Permite al administrador seleccionar un .db de respaldo y restaurarlo.
    Verifica integridad antes de restaurar.
    """
    ruta_seleccionada = filedialog.askopenfilename(
        title="Seleccionar respaldo para restaurar",
        filetypes=[("Base de datos SQLite", "*.db"), ("Todos los archivos", "*.*")],
        initialdir=_ruta_respaldos()
    )

    if not ruta_seleccionada:
        return False

    if not _verificar_integridad(ruta_seleccionada):
        messagebox.showerror(
            "Archivo Inválido",
            "El archivo seleccionado no es una base de datos válida del sistema.\n\n"
            "Asegúrese de seleccionar un respaldo generado por esta aplicación."
        )
        return False

    nombre_archivo = os.path.basename(ruta_seleccionada)
    confirmacion = messagebox.askyesno(
        "Confirmar Restauración",
        f"¿Está seguro de restaurar desde:\n\n{nombre_archivo}?\n\n"
        "ADVERTENCIA: Esto reemplazará todos los datos actuales del sistema.\n"
        "Se creará un respaldo automático antes de continuar."
    )

    if not confirmacion:
        return False

    try:
        crear_respaldo(silencioso=True)
        shutil.copy2(ruta_seleccionada, RUTA_BD)
        messagebox.showinfo(
            "Restauración Exitosa",
            f"La base de datos fue restaurada correctamente desde:\n{nombre_archivo}\n\n"
            "La aplicación utilizará los datos restaurados a partir de ahora."
        )
        logger.registrar("respaldos.py", "restaurar_desde_respaldo",
                         Exception(f"Restauración exitosa desde: {nombre_archivo}"))
        return True

    except Exception as e:
        messagebox.showerror("Error al Restaurar",
                             f"No se pudo completar la restauración:\n{e}")
        logger.registrar("respaldos.py", "restaurar_desde_respaldo", e)
        return False


def abrir_carpeta_respaldos() -> None:
    """Abre la carpeta de respaldos en el explorador de archivos."""
    import platform
    import subprocess
    ruta = _ruta_respaldos()
    os.makedirs(ruta, exist_ok=True)
    try:
        if platform.system() == "Windows":
            os.startfile(ruta)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", ruta])
        else:
            subprocess.Popen(["xdg-open", ruta])
    except Exception:
        pass
