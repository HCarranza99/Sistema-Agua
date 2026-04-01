import customtkinter as ctk
from tkinter import messagebox
from config import (
    COLOR_FONDO, COLOR_BLANCO, COLOR_AZUL_MARINO, COLOR_BORDE,
    COLOR_TEXTO, COLOR_TEXTO_MUTED, COLOR_ROJO, COLOR_VERDE_PAGO,
    FONT_BTN, FONT_SMALL, FONT_BODY, FONT_LABEL
)
from licencia.validador import activar_licencia, estado_licencia
from herramientas.seguridad import obtener_hardware_id


def mostrar_pantalla_activacion(ventana_padre, callback_exito) -> None:
    """
    Muestra la pantalla de activación inicial como ventana modal.
    callback_exito se llama cuando la activación es exitosa.
    """
    modal = ctk.CTkToplevel(ventana_padre)
    modal.title("Activación del Sistema")
    modal.geometry("480x520")
    modal.resizable(False, False)
    modal.grab_set()
    modal.focus_set()

    # Centrar en pantalla
    modal.update_idletasks()
    x = (modal.winfo_screenwidth() // 2) - 240
    y = (modal.winfo_screenheight() // 2) - 260
    modal.geometry(f"480x520+{x}+{y}")

    # Fondo
    frame = ctk.CTkFrame(modal, fg_color=COLOR_FONDO)
    frame.pack(fill="both", expand=True)

    # Tarjeta
    tarjeta = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=16,
                            width=420, height=460)
    tarjeta.place(relx=0.5, rely=0.5, anchor="center")
    tarjeta.pack_propagate(False)

    # Ícono
    icono = ctk.CTkFrame(tarjeta, width=56, height=56, corner_radius=14,
                          fg_color=COLOR_AZUL_MARINO)
    icono.place(relx=0.5, y=44, anchor="center")
    icono.pack_propagate(False)
    ctk.CTkLabel(icono, text="💧", font=("Arial", 24)).place(
        relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(tarjeta, text="Activación del Sistema",
                 font=("Arial", 20, "bold"),
                 text_color=COLOR_TEXTO).place(relx=0.5, y=118, anchor="center")

    ctk.CTkLabel(tarjeta,
                 text="Ingrese su clave de licencia para continuar.",
                 font=FONT_SMALL,
                 text_color=COLOR_TEXTO_MUTED).place(relx=0.5, y=144, anchor="center")

    ctk.CTkFrame(tarjeta, height=1, fg_color=COLOR_BORDE,
                 width=370).place(relx=0.5, y=164, anchor="center")

    # Hardware ID (para mostrar al cliente si necesita soporte)
    hw_id = obtener_hardware_id()

    #Función que copia el ID al portapapeles
    def copiar_hw_id():
        modal.clipboard_clear()
        modal.clipboard_append(hw_id)
        messagebox.showinfo("ID Copiado", "El ID de hardware ha sido copiado al portapapeles.", parent=modal)
    ctk.CTkLabel(tarjeta, text=f"ID de Hardware: {hw_id}",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 wraplength=370).place(relx=0.5, y=188, anchor="center")
    ctk.CTkButton(tarjeta, text="Copiar ID",
                   height=28, width=100, corner_radius=8,
                   fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
                   font=FONT_SMALL, text_color=COLOR_BLANCO,
                   command=copiar_hw_id).place(relx=0.5, y=220, anchor="center")
    ctk.CTkLabel(tarjeta, text="Ingrese su clave de licencia a continuación:",
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 wraplength=370).place(relx=0.5, y=244, anchor="center")

    entrada_clave = ctk.CTkEntry(
        tarjeta, placeholder_text="ADESCO-XXXX-XXXX-XXXX-XXXX",
        width=370, height=44, corner_radius=8,
        border_color=COLOR_BORDE, fg_color=COLOR_FONDO,
        font=("Courier New", 12)
    )
    entrada_clave.place(relx=0.5, y=264, anchor="center")

    lbl_error = ctk.CTkLabel(tarjeta, text="", font=FONT_SMALL,
                              text_color=COLOR_ROJO, wraplength=370)
    lbl_error.place(relx=0.5, y=298, anchor="center")

    def intentar_activar(event=None):
        clave = entrada_clave.get().strip()
        if not clave:
            lbl_error.configure(text="Por favor ingrese la clave de licencia.")
            return

        exito, mensaje = activar_licencia(clave)
        if exito:
            messagebox.showinfo("Activación Exitosa", mensaje, parent=modal)
            modal.destroy()
            callback_exito()
        else:
            lbl_error.configure(text=mensaje)

    entrada_clave.bind("<Return>", intentar_activar)

    ctk.CTkButton(
        tarjeta, text="ACTIVAR SISTEMA",
        height=48, width=370, corner_radius=10,
        fg_color=COLOR_AZUL_MARINO, hover_color="#243F6B",
        font=FONT_BTN, text_color=COLOR_BLANCO,
        command=intentar_activar
    ).place(relx=0.5, y=350, anchor="center")

    ctk.CTkLabel(
        tarjeta,
        text="¿No tiene su clave? Contáctenos para obtenerla.",
        font=("Arial", 10), text_color=COLOR_TEXTO_MUTED
    ).place(relx=0.5, y=410, anchor="center")

    ctk.CTkLabel(
        tarjeta,
        text=f"Sistema de Pagos de Agua · v2.0",
        font=("Arial", 9), text_color=COLOR_TEXTO_MUTED
    ).place(relx=0.5, y=434, anchor="center")


def mostrar_pantalla_renovacion(ventana_padre, callback_renovado=None) -> None:
    """
    Muestra la pantalla de renovación de suscripción como modal.
    Puede abrirse desde el banner o desde el panel de Soporte.
    """
    modal = ctk.CTkToplevel(ventana_padre)
    modal.title("Renovar Suscripción")
    modal.geometry("440x360")
    modal.resizable(False, False)
    modal.grab_set()
    modal.focus_set()

    modal.update_idletasks()
    x = (modal.winfo_screenwidth() // 2) - 220
    y = (modal.winfo_screenheight() // 2) - 180
    modal.geometry(f"440x360+{x}+{y}")

    frame = ctk.CTkFrame(modal, fg_color=COLOR_FONDO)
    frame.pack(fill="both", expand=True)

    tarjeta = ctk.CTkFrame(frame, fg_color=COLOR_BLANCO, corner_radius=16,
                            width=400, height=320)
    tarjeta.place(relx=0.5, rely=0.5, anchor="center")
    tarjeta.pack_propagate(False)

    info = estado_licencia()

    ctk.CTkLabel(tarjeta, text="Renovar Suscripción",
                 font=("Arial", 18, "bold"),
                 text_color=COLOR_TEXTO).place(relx=0.5, y=36, anchor="center")

    ctk.CTkLabel(tarjeta, text=info["mensaje"],
                 font=FONT_SMALL, text_color=COLOR_TEXTO_MUTED,
                 wraplength=360).place(relx=0.5, y=70, anchor="center")

    ctk.CTkFrame(tarjeta, height=1, fg_color=COLOR_BORDE,
                 width=360).place(relx=0.5, y=96, anchor="center")

    ctk.CTkLabel(tarjeta, text="Clave de Renovación",
                 font=FONT_LABEL, text_color=COLOR_TEXTO).place(x=24, y=110)

    entrada = ctk.CTkEntry(
        tarjeta, placeholder_text="ADESCO-XXXX-XXXX-XXXX-XXXX",
        width=360, height=44, corner_radius=8,
        border_color=COLOR_BORDE, fg_color=COLOR_FONDO,
        font=("Courier New", 12)
    )
    entrada.place(relx=0.5, y=156, anchor="center")

    lbl_err = ctk.CTkLabel(tarjeta, text="", font=FONT_SMALL,
                            text_color=COLOR_ROJO, wraplength=360)
    lbl_err.place(relx=0.5, y=190, anchor="center")

    def renovar(event=None):
        clave = entrada.get().strip()
        if not clave:
            lbl_err.configure(text="Ingrese la clave de renovación.")
            return
        exito, mensaje = activar_licencia(clave)
        if exito:
            messagebox.showinfo("Renovación Exitosa", mensaje, parent=modal)
            modal.destroy()
            if callback_renovado:
                callback_renovado()
        else:
            lbl_err.configure(text=mensaje)

    entrada.bind("<Return>", renovar)

    ctk.CTkButton(
        tarjeta, text="RENOVAR",
        height=44, width=360, corner_radius=10,
        fg_color=COLOR_VERDE_PAGO, hover_color="#276749",
        font=FONT_BTN, text_color=COLOR_BLANCO,
        command=renovar
    ).place(relx=0.5, y=248, anchor="center")

    ctk.CTkButton(
        tarjeta, text="Cancelar",
        height=34, width=360, corner_radius=8,
        fg_color="transparent", text_color=COLOR_TEXTO_MUTED,
        border_width=1, border_color=COLOR_BORDE,
        font=FONT_SMALL,
        command=modal.destroy
    ).place(relx=0.5, y=298, anchor="center")
