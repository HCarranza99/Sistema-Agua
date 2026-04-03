import sqlite3, os, sys

RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "sistema_agua.db")

columnas_nuevas = [
    ("vecinos", "num_abonado",     "TEXT"),
    ("vecinos", "num_medidor",     "TEXT"),
    ("vecinos", "direccion",       "TEXT"),
    ("vecinos", "categoria",       "TEXT DEFAULT 'Residencial'"),
    ("vecinos", "tipo_cobro",      "TEXT DEFAULT 'fijo'"),
    ("vecinos", "lectura_inicial", "REAL DEFAULT 0"),
    ("transacciones", "anulado",          "INTEGER DEFAULT 0"),
    ("transacciones", "motivo_anulacion", "TEXT"),
    ("transacciones", "fecha_anulacion",  "DATETIME"),
]

con = sqlite3.connect(RUTA_BD)
cur = con.cursor()

for tabla, columna, tipo in columnas_nuevas:
    try:
        cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        print(f"✓ {tabla}.{columna}")
    except sqlite3.OperationalError:
        print(f"— {tabla}.{columna} (ya existe)")

# Crear tablas nuevas
cur.executescript("""
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
);

CREATE TABLE IF NOT EXISTS tarifas_excedente (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    desde_m3    REAL NOT NULL,
    hasta_m3    REAL,
    precio_m3   REAL NOT NULL,
    descripcion TEXT,
    orden       INTEGER DEFAULT 0
);
""")

con.commit()
con.close()
print("\nMigración completada.")
```

Luego ejecuta en la terminal dentro de la carpeta del proyecto:
```
python migrar.py