"""
GENERA_CLAVE.PY — Herramienta exclusiva del desarrollador.
NO incluir en el instalador del cliente.
"""

import hashlib
import hmac
import datetime
import json
import urllib.request
import urllib.error

_LICENCIA_SECRET = b"ADESCO_SISTEMA_AGUA_SECRET_2025_XK9"
_SOPORTE_SECRET  = b"ADESCO_SOPORTE_MASTER_2025_ZQ7XK"

GITHUB_USUARIO = "HCarranza99"
GITHUB_REPO    = "sistema-agua-licencias"
GITHUB_ARCHIVO = "licencias.json"

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}


def generar_clave_hmac(hardware_id: str, fecha_exp: str) -> str:
    payload = f"{hardware_id}|{fecha_exp}"
    firma   = hmac.new(_LICENCIA_SECRET, payload.encode("utf-8"),
                       hashlib.sha256).hexdigest()[:15].upper()
    bloques = [firma[i:i+5] for i in range(0, 15, 5)]
    return "ADESCO-" + fecha_exp.replace("-", "") + "-" + "-".join(bloques)


def calcular_password_soporte(hardware_id: str) -> str:
    raw = hmac.new(_SOPORTE_SECRET, hardware_id.encode("utf-8"),
                   hashlib.sha256).hexdigest()[:12].upper()
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}"


def _pedir_fecha() -> tuple[int, int, str]:
    hoy = datetime.date.today()
    print(f"\nFecha de expiración (actual: {MESES_ES[hoy.month]} {hoy.year})")
    anio = int(input(f"Año [{hoy.year}]: ").strip() or hoy.year)
    mes  = int(input(f"Mes (1-12) [{hoy.month}]: ").strip() or hoy.month)
    if not (1 <= mes <= 12):
        raise ValueError("Mes inválido")
    return anio, mes, f"{anio}-{mes:02d}"


def _api_github(token: str, method: str, endpoint: str, body=None):
    url  = f"https://api.github.com{endpoint}"
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def _leer_licencias(token: str):
    status, resp = _api_github(
        token, "GET",
        f"/repos/{GITHUB_USUARIO}/{GITHUB_REPO}/contents/{GITHUB_ARCHIVO}"
    )
    if status != 200:
        print(f"  Error ({status}): {resp.get('message','')}")
        return None
    import base64
    try:
        contenido = base64.b64decode(resp["content"]).decode("utf-8")
        return json.loads(contenido), resp["sha"]
    except Exception as e:
        print(f"  Error al parsear JSON: {e}")
        return None


def _escribir_licencias(token: str, datos: dict, sha: str, mensaje: str) -> bool:
    import base64
    contenido_b64 = base64.b64encode(
        json.dumps(datos, indent=2, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    status, resp = _api_github(
        token, "PUT",
        f"/repos/{GITHUB_USUARIO}/{GITHUB_REPO}/contents/{GITHUB_ARCHIVO}",
        body={"message": mensaje, "content": contenido_b64, "sha": sha}
    )
    if status not in (200, 201):
        print(f"  Error al escribir ({status}): {resp.get('message','')}")
    return status in (200, 201)


def accion_generar_clave(token: str) -> None:
    print("\n── Clave de activación inicial ──────────────────────────")
    hw_id = input("Hardware ID del cliente: ").strip()
    if len(hw_id) < 10:
        print("Hardware ID inválido.")
        return

    cliente = input("Nombre del cliente (ej: ADESCO El Gramal): ").strip()
    notas   = input("Notas opcionales: ").strip()

    try:
        anio, mes, fecha_exp = _pedir_fecha()
    except ValueError:
        print("Fecha inválida.")
        return

    clave = generar_clave_hmac(hw_id, fecha_exp)

    print()
    print("=" * 60)
    print(f"  Cliente      : {cliente}")
    print(f"  Válida hasta : {MESES_ES[mes]} {anio}")
    print(f"\n  ✦  {clave}  ✦")
    print("=" * 60)

    if token:
        print("\n  Registrando en GitHub...", end=" ", flush=True)
        resultado = _leer_licencias(token)
        if resultado:
            datos, sha = resultado
            datos[hw_id] = {
                "activa": True, "vence": fecha_exp,
                "cliente": cliente, "notas": notas or "Activación inicial",
            }
            ok = _escribir_licencias(token, datos, sha,
                                     f"Nuevo cliente: {cliente}")
            print("✓ Registrado" if ok else "✗ Error")
        else:
            print("✗ No se pudo leer el archivo")

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open("registro_licencias.txt", "a", encoding="utf-8") as f:
        f.write(f"{ts} | {cliente} | {hw_id[:16]}... | {fecha_exp} | {clave}\n")
    print("  (Guardado en registro_licencias.txt)")
    input("\nPresione Enter para continuar...")


def accion_ver_clientes(token: str) -> None:
    if not token:
        print("  Configurá el token primero (opción 4).")
        input("\nEnter para continuar...")
        return
    print("\n  Leyendo desde GitHub...", end=" ", flush=True)
    resultado = _leer_licencias(token)
    if not resultado:
        input("\nEnter para continuar...")
        return
    datos, _ = resultado
    print("✓\n")
    if not datos:
        print("  Sin clientes registrados.")
        input("\nEnter para continuar...")
        return
    print(f"  {'CLIENTE':<30} {'ESTADO':<12} {'VENCE':<10} HW_ID")
    print("  " + "─" * 70)
    for hw_id, info in datos.items():
        estado  = "✓ activa" if info.get("activa") else "✗ pausada"
        cliente = info.get("cliente", "—")[:28]
        vence   = info.get("vence", "—")
        print(f"  {cliente:<30} {estado:<12} {vence:<10} {hw_id[:16]}...")
    input("\nEnter para continuar...")


def accion_pausar_cliente(token: str) -> None:
    if not token:
        print("  Configurá el token primero (opción 4).")
        input("\nEnter para continuar...")
        return
    resultado = _leer_licencias(token)
    if not resultado:
        input("\nEnter para continuar...")
        return
    datos, sha = resultado
    clientes = list(datos.items())
    if not clientes:
        print("  Sin clientes registrados.")
        input("\nEnter para continuar...")
        return

    print()
    for i, (hw_id, info) in enumerate(clientes, 1):
        estado = "activa" if info.get("activa") else "PAUSADA"
        print(f"  {i}. {info.get('cliente','—')} — {estado} — vence {info.get('vence','?')}")

    sel = input("\nNúmero a modificar (0 cancelar): ").strip()
    if not sel.isdigit() or sel == "0":
        return
    idx = int(sel) - 1
    if not (0 <= idx < len(clientes)):
        print("Inválido.")
        return

    hw_id, info    = clientes[idx]
    nuevo_estado   = not info.get("activa", True)
    accion_txt     = "activar" if nuevo_estado else "pausar"
    confirma       = input(f"  ¿{accion_txt.capitalize()} '{info.get('cliente')}'? (s/n): ").strip().lower()
    if confirma != "s":
        return

    datos[hw_id]["activa"] = nuevo_estado
    print("  Guardando...", end=" ", flush=True)
    ok = _escribir_licencias(token, datos, sha,
                              f"{'Activar' if nuevo_estado else 'Pausar'}: {info.get('cliente')}")
    print("✓ Listo" if ok else "✗ Error")
    input("\nEnter para continuar...")


def accion_configurar_token() -> str:
    print("\n── Configurar token de GitHub ───────────────────────────")
    token = input("  Pegá tu token (ghp_...): ").strip()
    print("  Verificando...", end=" ", flush=True)
    resultado = _leer_licencias(token)
    if resultado is None:
        print("✗ No se pudo acceder al repo.")
        input("\nEnter para continuar...")
        return ""
    print("✓ Token válido")
    try:
        with open("dev_config.json", "w", encoding="utf-8") as f:
            json.dump({"github_token": token}, f)
        print("  Guardado en dev_config.json")
    except Exception as e:
        print(f"  Error al guardar: {e}")
    input("\nEnter para continuar...")
    return token


def accion_soporte() -> None:
    hw_id = input("\nHardware ID del cliente: ").strip()
    if len(hw_id) < 10:
        print("Hardware ID inválido.")
        input("\nEnter para continuar...")
        return
    pwd = calcular_password_soporte(hw_id)
    print()
    print("=" * 50)
    print(f"  Hardware ID : {hw_id[:20]}...")
    print(f"  Contraseña  : {pwd}")
    print("=" * 50)
    input("\nEnter para continuar...")


def _cargar_token() -> str:
    try:
        with open("dev_config.json", "r", encoding="utf-8") as f:
            return json.load(f).get("github_token", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def main():
    token = _cargar_token()
    while True:
        print()
        print("=" * 60)
        print("  SISTEMA DE AGUA — Herramienta del Desarrollador")
        print("=" * 60)
        print(f"  Token GitHub: {'✓ configurado' if token else '✗ no configurado'}")
        print()
        print("  1. Generar clave de activación + registrar cliente")
        print("  2. Ver clientes registrados")
        print("  3. Activar / pausar cliente")
        print("  4. Configurar token de GitHub")
        print("  5. Calcular contraseña Soporte")
        print("  0. Salir")
        print()
        opcion = input("Opción: ").strip()
        if opcion == "0":
            break
        elif opcion == "1":
            accion_generar_clave(token)
        elif opcion == "2":
            accion_ver_clientes(token)
        elif opcion == "3":
            accion_pausar_cliente(token)
        elif opcion == "4":
            nuevo = accion_configurar_token()
            if nuevo:
                token = nuevo
        elif opcion == "5":
            accion_soporte()
        else:
            print("  Opción inválida.")


if __name__ == "__main__":
    main()