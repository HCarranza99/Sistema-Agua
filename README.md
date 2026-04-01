# Sistema de Pagos de Agua — v2.0.0

Sistema de gestión de pagos de agua para comunidades ADESCO.

---

## Requisitos

- Python 3.11 o superior (recomendado: 3.12)
- Windows 10/11

## Instalación

1. Instalar Python desde https://python.org (marcar "Add to PATH" durante la instalación)

2. Abrir una terminal en la carpeta del sistema y ejecutar:

```
pip install -r requirements.txt
```

3. Ejecutar el sistema:

```
python main.py
```

## Primer uso

Al iniciar por primera vez el sistema mostrará:
1. La pantalla de **activación de licencia** — ingrese la clave proporcionada.
2. El **asistente de configuración** — ingrese el nombre de su comunidad y las zonas geográficas.

**Usuario por defecto creado automáticamente:**
- Usuario: `admin`
- Contraseña: `admin123`

⚠️ Cambie esta contraseña inmediatamente desde *Gestión de Usuarios*.

## Roles disponibles

| Rol           | Acceso |
|---------------|--------|
| Cajero        | Registro de cobros y envío de recibos |
| Presidente    | Todo lo anterior + gestión de vecinos y reportes completos |
| Administrador | Todo lo anterior + usuarios, zonas y configuración |
| Soporte       | Panel técnico (uso exclusivo del desarrollador) |

## Archivos generados

El sistema crea automáticamente las siguientes carpetas junto al ejecutable:

- `respaldos_seguridad/` — Respaldos automáticos de la base de datos
- `recibos_guardados/` — Recibos en PDF generados
- `reportes_pdf/` — Reportes exportados en PDF
- `reportes_excel/` — Reportes exportados en Excel
- `errores.log` — Registro de errores (para soporte técnico)

---

*Para soporte técnico contacte al desarrollador.*