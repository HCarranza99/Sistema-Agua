import sqlite3
from tkinter import messagebox
from config import RUTA_BD
from herramientas.seguridad import hashear_contrasena, cifrar_texto
import herramientas.logger as logger


def obtener_conexion() -> sqlite3.Connection:
    """Retorna una conexión con foreign keys activadas."""
    con = sqlite3.connect(RUTA_BD)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar_base_datos() -> bool:
    """
    Crea todas las tablas si no existen y aplica migraciones necesarias.
    Retorna True si todo fue exitoso.
    """
    try:
        con = obtener_conexion()
        cur = con.cursor()

        # ── Tabla: usuarios ──────────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario   TEXT UNIQUE NOT NULL,
            contrasena TEXT NOT NULL,
            rol       TEXT NOT NULL,
            telefono  TEXT,
            email     TEXT
        )''')

        # ── Tabla: config_sistema ─────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS config_sistema (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )''')

        # ── Tabla: zonas ──────────────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS zonas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            orden       INTEGER DEFAULT 0,
            activa      INTEGER DEFAULT 1
        )''')

        # ── Tabla: vecinos ────────────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS vecinos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            dui      TEXT UNIQUE NOT NULL,
            nombre   TEXT NOT NULL,
            telefono TEXT,
            email    TEXT,
            estado   TEXT DEFAULT 'Solvente',
            activo   INTEGER DEFAULT 1,
            cuota    REAL DEFAULT 5.00,
            zona_id  INTEGER REFERENCES zonas(id) ON DELETE SET NULL
        )''')

        # ── Tabla: recibos ────────────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS recibos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vecino_id   INTEGER NOT NULL REFERENCES vecinos(id),
            mes         TEXT NOT NULL,
            anio        INTEGER NOT NULL,
            monto       REAL NOT NULL,
            estado_pago TEXT DEFAULT 'Pendiente'
        )''')

        # ── Tabla: cargos_extra ───────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS cargos_extra (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            recibo_id   INTEGER NOT NULL REFERENCES recibos(id),
            tipo        TEXT NOT NULL CHECK(tipo IN ('mora','consumo')),
            descripcion TEXT NOT NULL,
            monto       REAL NOT NULL,
            usuario_id  INTEGER REFERENCES usuarios(id),
            fecha       DATETIME DEFAULT CURRENT_TIMESTAMP,
            pagado      INTEGER DEFAULT 0
        )''')

        # ── Tabla: transacciones ──────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS transacciones (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            recibo_id    INTEGER REFERENCES recibos(id),
            cargo_id     INTEGER REFERENCES cargos_extra(id),
            usuario_id   INTEGER REFERENCES usuarios(id),
            monto_cobrado REAL NOT NULL,
            fecha_cobro  DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        # ── Tabla: cierres_caja ───────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS cierres_caja (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha                 DATE NOT NULL UNIQUE,
            usuario_id            INTEGER NOT NULL REFERENCES usuarios(id),
            total_recaudado       REAL NOT NULL,
            cantidad_transacciones INTEGER NOT NULL,
            hora_cierre           DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        # ── Tabla: envios_recibos ─────────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS envios_recibos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vecino_id   INTEGER NOT NULL REFERENCES vecinos(id),
            mes         TEXT NOT NULL,
            anio        INTEGER NOT NULL,
            canal       TEXT NOT NULL CHECK(canal IN ('whatsapp','email','fisico')),
            fecha_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
            usuario_id  INTEGER REFERENCES usuarios(id)
        )''')

        # ── Migraciones: agregar columnas faltantes en tablas existentes ──────
        _migrar_columnas(cur)

        # ── Usuario admin por defecto si no existe ninguno ────────────────────
        cur.execute("SELECT COUNT(*) FROM usuarios")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO usuarios (usuario, contrasena, rol) VALUES (?,?,?)",
                ("admin", hashear_contrasena("admin123"), "Administrador")
            )
            messagebox.showinfo(
                "Bienvenido al Sistema",
                "Instalación nueva detectada.\n\n"
                "Usuario por defecto creado:\n"
                "  Usuario: admin\n"
                "  Contraseña: admin123\n\n"
                "Por favor cambie esta contraseña en Gestión de Usuarios."
            )

        # ── Cuenta Soporte embebida (se sincroniza en cada inicio) ────────────
        # La contraseña se deriva del hardware ID: única por PC, gestionada
        # automáticamente. El cliente nunca puede cambiarla permanentemente.
        from herramientas.seguridad import generar_password_soporte, obtener_hardware_id
        from config import ROL_SOPORTE
        hw_id        = obtener_hardware_id()
        soporte_hash = hashear_contrasena(generar_password_soporte(hw_id))
        cur.execute("SELECT id FROM usuarios WHERE rol=?", (ROL_SOPORTE,))
        soporte_row = cur.fetchone()
        if soporte_row:
            cur.execute("UPDATE usuarios SET contrasena=? WHERE rol=?",
                        (soporte_hash, ROL_SOPORTE))
        else:
            cur.execute(
                "INSERT INTO usuarios (usuario, contrasena, rol) VALUES (?,?,?)",
                ("soporte", soporte_hash, ROL_SOPORTE)
            )

        con.commit()

        return True

    except sqlite3.Error as e:
        messagebox.showerror("Error Crítico",
                             f"No se pudo inicializar la base de datos:\n{e}")
        logger.registrar("db.py", "inicializar_base_datos", e)
        return False
    finally:
        if 'con' in locals():
            con.close()


def _migrar_columnas(cur: sqlite3.Cursor) -> None:
    """Agrega columnas nuevas a tablas existentes sin perder datos."""
    migraciones = [
        ("vecinos",      "email",   "TEXT"),
        ("vecinos",      "zona_id", "INTEGER REFERENCES zonas(id) ON DELETE SET NULL"),
        ("transacciones","cargo_id","INTEGER REFERENCES cargos_extra(id)"),
        ("usuarios",     "telefono","TEXT"),
        ("usuarios",     "email",   "TEXT"),
    ]
    for tabla, columna, tipo in migraciones:
        try:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        except sqlite3.OperationalError:
            pass  # La columna ya existe, se ignora


def obtener_config(clave: str, defecto: str = "") -> str:
    """Lee un valor de config_sistema. Retorna defecto si no existe."""
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("SELECT valor FROM config_sistema WHERE clave=?", (clave,))
        row = cur.fetchone()
        return row[0] if row else defecto
    except Exception:
        return defecto
    finally:
        if 'con' in locals():
            con.close()


def guardar_config(clave: str, valor: str) -> bool:
    """Guarda o actualiza un valor en config_sistema."""
    try:
        con = obtener_conexion()
        con.execute(
            "INSERT OR REPLACE INTO config_sistema (clave, valor) VALUES (?,?)",
            (clave, valor)
        )
        con.commit()
        return True
    except Exception as e:
        logger.registrar("db.py", "guardar_config", e)
        return False
    finally:
        if 'con' in locals():
            con.close()


def obtener_ruta(clave_config: str, ruta_default: str) -> str:
    """
    Retorna la ruta configurada por el usuario o la ruta por defecto.
    Garantiza que el directorio exista.
    """
    import os
    ruta = obtener_config(clave_config, ruta_default)
    os.makedirs(ruta, exist_ok=True)
    return ruta


def generar_recibos_mes_actual() -> int:
    """
    Genera recibos 'Pendiente' para el mes/año actual para todos los vecinos
    activos que todavía no tengan uno. Debe llamarse en cada inicio de sesión.

    Usa un INSERT selectivo (NOT EXISTS) para que sea idempotente:
    ejecutarlo varias veces en el mismo mes no crea duplicados.

    Returns:
        Cantidad de recibos nuevos creados (0 si todos ya existían).
    """
    import datetime
    from config import MESES_ES
    hoy       = datetime.date.today()
    mes_nombre = MESES_ES[hoy.month]
    anio      = hoy.year

    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO recibos (vecino_id, mes, anio, monto, estado_pago)
            SELECT v.id, ?, ?, v.cuota, 'Pendiente'
            FROM vecinos v
            WHERE v.activo = 1
              AND NOT EXISTS (
                  SELECT 1 FROM recibos r
                  WHERE r.vecino_id = v.id
                    AND r.mes = ?
                    AND r.anio = ?
              )
        """, (mes_nombre, anio, mes_nombre, anio))
        creados = cur.rowcount
        con.commit()
        return creados
    except Exception as e:
        logger.registrar("db.py", "generar_recibos_mes_actual", e)
        return 0
    finally:
        if 'con' in locals():
            con.close()
