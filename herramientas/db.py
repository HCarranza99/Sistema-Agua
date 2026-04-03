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
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            dui             TEXT UNIQUE NOT NULL,
            nombre          TEXT NOT NULL,
            telefono        TEXT,
            email           TEXT,
            estado          TEXT DEFAULT 'Solvente',
            activo          INTEGER DEFAULT 1,
            cuota           REAL DEFAULT 5.00,
            zona_id         INTEGER REFERENCES zonas(id) ON DELETE SET NULL,
            num_abonado     TEXT,
            num_medidor     TEXT,
            direccion       TEXT,
            categoria       TEXT DEFAULT 'Residencial',
            tipo_cobro      TEXT DEFAULT 'fijo',
            lectura_inicial REAL DEFAULT 0
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

        # ── Tabla: lecturas_medidor ──────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS lecturas_medidor (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            vecino_id        INTEGER NOT NULL REFERENCES vecinos(id),
            mes              TEXT NOT NULL,
            anio             INTEGER NOT NULL,
            lectura_anterior REAL NOT NULL,
            lectura_actual   REAL NOT NULL,
            consumo_m3       REAL NOT NULL,
            excedente_m3     REAL DEFAULT 0,
            monto_excedente  REAL DEFAULT 0,
            monto_total      REAL NOT NULL,
            registrado_por   INTEGER REFERENCES usuarios(id),
            fecha_registro   DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(vecino_id, mes, anio)
        )''')

        # ── Tabla: tarifas_excedente ──────────────────────────────────────────
        cur.execute('''CREATE TABLE IF NOT EXISTS tarifas_excedente (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            desde_m3    REAL NOT NULL,
            hasta_m3    REAL,
            precio_m3   REAL NOT NULL,
            descripcion TEXT,
            orden       INTEGER DEFAULT 0
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
        ("transacciones","cargo_id",       "INTEGER REFERENCES cargos_extra(id)"),
        ("transacciones","anulado",         "INTEGER DEFAULT 0"),
        ("transacciones","motivo_anulacion","TEXT"),
        ("transacciones","fecha_anulacion", "DATETIME"),
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
    activos que todavía no tengan uno, si ya llegó el día de generación configurado.

    - Vecinos con cuota fija  → monto = cuota del vecino
    - Vecinos con medidor     → monto = 0 (provisional hasta ingresar lectura)

    Usa INSERT selectivo (NOT EXISTS) para ser idempotente.

    Returns:
        Cantidad de recibos nuevos creados.
    """
    import datetime
    from config import MESES_ES
    hoy        = datetime.date.today()
    dia_gen    = int(obtener_config("dia_generacion_recibos", "1") or 1)

    # Solo generar si ya llegó el día configurado del mes
    if hoy.day < dia_gen:
        return 0

    mes_nombre = MESES_ES[hoy.month]
    anio       = hoy.year

    try:
        con = obtener_conexion()
        cur = con.cursor()

        # Vecinos de cuota fija → usar su cuota
        cur.execute("""
            INSERT INTO recibos (vecino_id, mes, anio, monto, estado_pago)
            SELECT v.id, ?, ?, v.cuota, 'Pendiente'
            FROM vecinos v
            WHERE v.activo = 1
              AND v.tipo_cobro = 'fijo'
              AND NOT EXISTS (
                  SELECT 1 FROM recibos r
                  WHERE r.vecino_id = v.id
                    AND r.mes = ?
                    AND r.anio = ?
              )
        """, (mes_nombre, anio, mes_nombre, anio))
        creados = cur.rowcount

        # Vecinos con medidor → monto provisional $0 hasta lectura
        cur.execute("""
            INSERT INTO recibos (vecino_id, mes, anio, monto, estado_pago)
            SELECT v.id, ?, ?, 0, 'Pendiente'
            FROM vecinos v
            WHERE v.activo = 1
              AND v.tipo_cobro = 'medidor'
              AND NOT EXISTS (
                  SELECT 1 FROM recibos r
                  WHERE r.vecino_id = v.id
                    AND r.mes = ?
                    AND r.anio = ?
              )
        """, (mes_nombre, anio, mes_nombre, anio))
        creados += cur.rowcount

        con.commit()
        return creados
    except Exception as e:
        logger.registrar("db.py", "generar_recibos_mes_actual", e)
        return 0
    finally:
        if 'con' in locals():
            con.close()


def obtener_tarifas_excedente() -> list:
    """
    Retorna lista de tarifas ordenadas: [(desde, hasta, precio, desc), ...]
    hasta=None significa sin límite superior.
    """
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute(
            "SELECT desde_m3, hasta_m3, precio_m3, descripcion "
            "FROM tarifas_excedente ORDER BY orden, desde_m3")
        return cur.fetchall()
    except Exception:
        return []
    finally:
        if 'con' in locals():
            con.close()


def calcular_monto_medidor(consumo_m3: float, cuota_base: float,
                            m3_incluidos: float) -> tuple:
    """
    Calcula el monto total para un vecino con medidor.

    Returns:
        (excedente_m3, monto_excedente, monto_total)
    """
    excedente_m3    = max(0.0, consumo_m3 - m3_incluidos)
    monto_excedente = 0.0

    if excedente_m3 > 0:
        tarifas = obtener_tarifas_excedente()
        restante = excedente_m3
        for desde, hasta, precio, _ in tarifas:
            if restante <= 0:
                break
            limite = (hasta - desde) if hasta is not None else restante
            tramo  = min(restante, limite)
            monto_excedente += tramo * precio
            restante        -= tramo

    monto_total = round(cuota_base + monto_excedente, 2)
    return round(excedente_m3, 3), round(monto_excedente, 2), monto_total


def registrar_lectura(vecino_id: int, mes: str, anio: int,
                       lectura_anterior: float, lectura_actual: float,
                       usuario_id: int) -> tuple:
    """
    Registra la lectura del medidor, calcula excedente y actualiza el recibo.
    Returns: (ok: bool, mensaje: str, monto_total: float)
    """
    try:
        consumo_m3  = round(max(0.0, lectura_actual - lectura_anterior), 3)
        cuota_base  = float(obtener_config("tarifa_basica", "5.00") or 5.0)
        m3_incluidos = float(obtener_config("m3_incluidos", "25") or 25.0)

        excedente_m3, monto_excedente, monto_total = calcular_monto_medidor(
            consumo_m3, cuota_base, m3_incluidos)

        con = obtener_conexion()
        cur = con.cursor()

        # Insertar o reemplazar lectura
        cur.execute("""
            INSERT INTO lecturas_medidor
              (vecino_id, mes, anio, lectura_anterior, lectura_actual,
               consumo_m3, excedente_m3, monto_excedente, monto_total,
               registrado_por)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(vecino_id, mes, anio) DO UPDATE SET
              lectura_anterior=excluded.lectura_anterior,
              lectura_actual=excluded.lectura_actual,
              consumo_m3=excluded.consumo_m3,
              excedente_m3=excluded.excedente_m3,
              monto_excedente=excluded.monto_excedente,
              monto_total=excluded.monto_total,
              registrado_por=excluded.registrado_por,
              fecha_registro=CURRENT_TIMESTAMP
        """, (vecino_id, mes, anio, lectura_anterior, lectura_actual,
              consumo_m3, excedente_m3, monto_excedente, monto_total, usuario_id))

        # Actualizar monto del recibo correspondiente
        cur.execute(
            "UPDATE recibos SET monto=? "
            "WHERE vecino_id=? AND mes=? AND anio=? AND estado_pago='Pendiente'",
            (monto_total, vecino_id, mes, anio))

        con.commit()
        return True, f"Lectura registrada. Consumo: {consumo_m3} m³. Total: ${monto_total:.2f}", monto_total

    except Exception as e:
        logger.registrar("db.py", "registrar_lectura", e)
        return False, str(e), 0.0
    finally:
        if 'con' in locals():
            con.close()


def obtener_proximo_num_factura() -> str:
    """Retorna el próximo número de factura formateado (ej: '0467')."""
    try:
        inicial = int(obtener_config("num_factura_inicial", "1") or 1)
        actual  = int(obtener_config("num_factura_actual",  str(inicial)) or inicial)
        return str(actual).zfill(4)
    except Exception:
        return "0001"


def incrementar_num_factura() -> str:
    """Incrementa el contador de facturas y retorna el número usado (antes del incremento)."""
    numero = obtener_proximo_num_factura()
    guardar_config("num_factura_actual", str(int(numero) + 1))
    return numero


def obtener_lecturas_periodo(mes: str, anio: int) -> list:
    """
    Retorna datos de lectura del período para todos los vecinos con medidor.
    Cada elemento es un dict con datos del vecino y su lectura (o None si no tiene).
    """
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("""
            SELECT v.id, v.nombre, v.num_abonado, v.num_medidor,
                   z.nombre AS zona,
                   lm.lectura_anterior, lm.lectura_actual,
                   lm.consumo_m3, lm.excedente_m3, lm.monto_total,
                   lm.fecha_registro
            FROM vecinos v
            LEFT JOIN zonas z ON v.zona_id = z.id
            LEFT JOIN lecturas_medidor lm
                   ON lm.vecino_id = v.id AND lm.mes = ? AND lm.anio = ?
            WHERE v.activo = 1 AND v.tipo_cobro = 'medidor'
            ORDER BY v.nombre
        """, (mes, anio))
        filas = cur.fetchall()
        return [
            {
                "vecino_id":       r[0],
                "nombre":          r[1],
                "num_abonado":     r[2],
                "num_medidor":     r[3],
                "zona":            r[4],
                "lectura_anterior": r[5],
                "lectura_actual":   r[6],
                "consumo_m3":      r[7],
                "excedente_m3":    r[8],
                "monto_total":     r[9],
                "fecha_registro":  r[10],
                "tiene_lectura":   r[5] is not None,
            }
            for r in filas
        ]
    except Exception as e:
        logger.registrar("db.py", "obtener_lecturas_periodo", e)
        return []
    finally:
        if 'con' in locals():
            con.close()


def obtener_anomalias_consumo(mes: str, anio: int) -> set:
    """
    Retorna set de vecino_ids cuyo consumo del período supera el doble
    de su promedio histórico (basado en lecturas anteriores al período dado).
    """
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute("""
            SELECT cur.vecino_id
            FROM lecturas_medidor cur
            JOIN (
                SELECT vecino_id, AVG(consumo_m3) AS promedio
                FROM lecturas_medidor
                WHERE NOT (mes = ? AND anio = ?)
                GROUP BY vecino_id
                HAVING COUNT(*) >= 2
            ) hist ON hist.vecino_id = cur.vecino_id
            WHERE cur.mes = ? AND cur.anio = ?
              AND cur.consumo_m3 > hist.promedio * 2
        """, (mes, anio, mes, anio))
        return {r[0] for r in cur.fetchall()}
    except Exception:
        return set()
    finally:
        if 'con' in locals():
            con.close()


def obtener_lectura_anterior(vecino_id: int, mes: str, anio: int) -> float:
    """
    Retorna la lectura_actual del mes anterior, o lectura_inicial del vecino
    si no hay registros previos.
    """
    try:
        from config import MESES_ES
        meses_inv = {v: k for k, v in MESES_ES.items()}
        num_mes   = meses_inv.get(mes, 1)
        if num_mes == 1:
            mes_ant, anio_ant = MESES_ES[12], anio - 1
        else:
            mes_ant, anio_ant = MESES_ES[num_mes - 1], anio

        con = obtener_conexion()
        cur = con.cursor()
        cur.execute(
            "SELECT lectura_actual FROM lecturas_medidor "
            "WHERE vecino_id=? AND mes=? AND anio=?",
            (vecino_id, mes_ant, anio_ant))
        row = cur.fetchone()
        if row:
            return row[0]
        # Sin historial: usar lectura_inicial del vecino
        cur.execute("SELECT lectura_inicial FROM vecinos WHERE id=?", (vecino_id,))
        row2 = cur.fetchone()
        return row2[0] if row2 and row2[0] else 0.0
    except Exception:
        return 0.0
    finally:
        if 'con' in locals():
            con.close()


def vecino_tiene_datos_completos(vecino_id: int) -> tuple:
    """
    Verifica si un vecino tiene todos los campos obligatorios según su tipo.
    Returns: (completo: bool, campos_faltantes: list)
    """
    try:
        con = obtener_conexion()
        cur = con.cursor()
        cur.execute(
            "SELECT nombre, num_abonado, num_medidor, direccion, tipo_cobro "
            "FROM vecinos WHERE id=?", (vecino_id,))
        row = cur.fetchone()
        if not row:
            return False, ["vecino no encontrado"]
        nombre, num_abonado, num_medidor, direccion, tipo_cobro = row
        faltantes = []
        if not nombre:
            faltantes.append("nombre")
        if not num_abonado:
            faltantes.append("número de abonado")
        if not direccion:
            faltantes.append("dirección")
        if tipo_cobro == "medidor" and not num_medidor:
            faltantes.append("número de medidor")
        return len(faltantes) == 0, faltantes
    except Exception:
        return False, ["error al verificar"]
    finally:
        if 'con' in locals():
            con.close()