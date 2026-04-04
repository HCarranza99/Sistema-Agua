"""
migrar.py — Script de migración manual de la base de datos.

Ejecutar UNA VEZ cuando se actualiza el sistema a una nueva versión:

    python migrar.py

Es seguro ejecutarlo varias veces: cada paso verifica si ya existe
antes de aplicar el cambio.
"""

import sqlite3
import os
import sys

RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "sistema_agua.db")


def ok(msg):
    print(f"  [OK]   {msg}")


def skip(msg):
    print(f"  [--]   {msg} (ya existe)")


def err(msg, e):
    print(f"  [ERR]  {msg}: {e}")


# ── Columnas nuevas en tablas existentes ───────────────────────────────────────
COLUMNAS_NUEVAS = [
    # vecinos
    ("vecinos", "email",          "TEXT"),
    ("vecinos", "zona_id",        "INTEGER REFERENCES zonas(id) ON DELETE SET NULL"),
    ("vecinos", "num_abonado",    "TEXT"),
    ("vecinos", "num_medidor",    "TEXT"),
    ("vecinos", "direccion",      "TEXT"),
    ("vecinos", "categoria",      "TEXT DEFAULT 'Residencial'"),
    ("vecinos", "tipo_cobro",     "TEXT DEFAULT 'fijo'"),
    ("vecinos", "lectura_inicial","REAL DEFAULT 0"),
    # transacciones
    ("transacciones", "cargo_id",        "INTEGER REFERENCES cargos_extra(id)"),
    ("transacciones", "anulado",          "INTEGER DEFAULT 0"),
    ("transacciones", "motivo_anulacion", "TEXT"),
    ("transacciones", "fecha_anulacion",  "DATETIME"),
    # usuarios
    ("usuarios", "telefono", "TEXT"),
    ("usuarios", "email",    "TEXT"),
]

# ── Tablas nuevas (CREATE IF NOT EXISTS) ───────────────────────────────────────
TABLAS_NUEVAS = [
    ("lecturas_medidor", """
        CREATE TABLE IF NOT EXISTS lecturas_medidor (
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
        )
    """),
    ("tarifas_excedente", """
        CREATE TABLE IF NOT EXISTS tarifas_excedente (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            desde_m3    REAL NOT NULL,
            hasta_m3    REAL,
            precio_m3   REAL NOT NULL,
            descripcion TEXT,
            orden       INTEGER DEFAULT 0
        )
    """),
    ("cargos_extra", """
        CREATE TABLE IF NOT EXISTS cargos_extra (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            recibo_id   INTEGER NOT NULL REFERENCES recibos(id),
            tipo        TEXT NOT NULL CHECK(tipo IN ('mora','consumo')),
            descripcion TEXT NOT NULL,
            monto       REAL NOT NULL,
            usuario_id  INTEGER REFERENCES usuarios(id),
            fecha       DATETIME DEFAULT CURRENT_TIMESTAMP,
            pagado      INTEGER DEFAULT 0
        )
    """),
    ("envios_recibos", """
        CREATE TABLE IF NOT EXISTS envios_recibos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vecino_id   INTEGER NOT NULL REFERENCES vecinos(id),
            mes         TEXT NOT NULL,
            anio        INTEGER NOT NULL,
            canal       TEXT NOT NULL CHECK(canal IN ('whatsapp','email','fisico')),
            fecha_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
            usuario_id  INTEGER REFERENCES usuarios(id)
        )
    """),
    ("cierres_caja", """
        CREATE TABLE IF NOT EXISTS cierres_caja (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha                  DATE NOT NULL UNIQUE,
            usuario_id             INTEGER NOT NULL REFERENCES usuarios(id),
            total_recaudado        REAL NOT NULL,
            cantidad_transacciones INTEGER NOT NULL,
            hora_cierre            DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """),
]


def main():
    if not os.path.exists(RUTA_BD):
        print(f"\n✗  No se encontró la base de datos en:\n   {RUTA_BD}")
        print("   Inicie la aplicación primero para crearla.\n")
        sys.exit(1)

    print(f"\nBase de datos: {RUTA_BD}")
    print("=" * 60)

    con = sqlite3.connect(RUTA_BD)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    # 1. Tablas nuevas
    print("\n[1/3] Verificando tablas nuevas...")
    for nombre, ddl in TABLAS_NUEVAS:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {nombre}")
            skip(nombre)
        except sqlite3.OperationalError:
            try:
                cur.execute(ddl)
                ok(f"Tabla '{nombre}' creada")
            except Exception as e:
                err(f"Tabla '{nombre}'", e)

    # 2. Columnas nuevas
    print("\n[2/3] Verificando columnas nuevas...")
    for tabla, columna, tipo in COLUMNAS_NUEVAS:
        try:
            cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            ok(f"{tabla}.{columna}")
        except sqlite3.OperationalError:
            skip(f"{tabla}.{columna}")
        except Exception as e:
            err(f"{tabla}.{columna}", e)

    # 3. Verificación de integridad
    print("\n[3/3] Verificando integridad...")
    cur.execute("PRAGMA integrity_check")
    resultado = cur.fetchone()[0]
    if resultado == "ok":
        ok("Integridad de la BD: ok")
    else:
        print(f"  ⚠  Integridad: {resultado}")

    con.commit()
    con.close()

    print("\n" + "=" * 60)
    print("Migracion completada. Puede abrir la aplicacion con normalidad.\n")


if __name__ == "__main__":
    main()
