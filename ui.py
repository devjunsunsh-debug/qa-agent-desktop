import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
from agent import get_pbi, generate_test_cases, create_test_case_in_azure, agregar_tag_pbi, tiene_test_cases, validar_asignacion, buscar_tc_manual
from auth import get_token
from config import config_existe, cargar_config, guardar_config, aplicar_config, eliminar_config
import os
import requests
import base64

class QAAgentApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QA Agent - Generador de Test Cases")
        self.root.geometry("520x380")
        self.root.resizable(False, False)
        self._pbi = None
        self._test_cases = None
        self._user = None
        self._token = None
        self._config = None
        self.show_login()

    # ── PANTALLA LOGIN ─────────────────────────────────────────────────────────

    def show_login(self):
        self._clear_window()
        self.root.geometry("400x300")

        frame = tk.Frame(self.root, padx=40, pady=40)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="QA Agent",
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(frame, text="Generador automatico de test cases",
                 font=("Segoe UI", 10), fg="gray").pack(anchor="w", pady=(0, 30))

        self.btn_login = tk.Button(
            frame,
            text="Conectar con Azure DevOps",
            font=("Segoe UI", 11, "bold"),
            bg="#0078D4", fg="white",
            relief="flat", cursor="hand2",
            padx=12, pady=10,
            command=self.ejecutar_login
        )
        self.btn_login.pack(fill="x")

        self.login_status = tk.Label(
            frame, text="", font=("Segoe UI", 10), fg="gray")
        self.login_status.pack(pady=(12, 0))

    def ejecutar_login(self):
        self.btn_login.config(state="disabled", text="Conectando...")
        self.login_status.config(text="Conectando con Azure DevOps...")
        threading.Thread(target=self._login_thread, daemon=True).start()

    def _login_thread(self):
        token, info = get_token()

        if not token:
            self.root.after(0, lambda: self._login_error(str(info)))
            return

        self._token = token
        self._user = info
        self.root.after(0, self._post_login)

    def _post_login(self):
        # Verificar si ya tiene configuracion guardada
        if config_existe():
            self._config = cargar_config()
            aplicar_config(self._config)
            self.show_main()
        else:
            self.show_wizard()

        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(500, lambda: self.root.attributes("-topmost", False))
        # Cerrar pestaña del navegador
        import time
        import pyautogui
        time.sleep(1)
        pyautogui.hotkey('ctrl', 'w')

    def _login_error(self, msg):
        self.btn_login.config(
            state="normal", text="Iniciar sesion con Microsoft")
        self.login_status.config(text=f"Error: {msg[:60]}", fg="red")

    # ── WIZARD DE CONFIGURACIÓN (primera vez) ─────────────────────────────────

    def show_wizard(self):
        self._clear_window()
        self.root.geometry("480x660")

        frame = tk.Frame(self.root, padx=30, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Configuracion inicial",
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(frame,
                 text="Completa estos datos una sola vez. Podras editarlos despues.",
                 font=("Segoe UI", 10), fg="gray",
                 wraplength=400).pack(anchor="w", pady=(4, 20))

        # Sección Azure
        tk.Label(frame, text="Azure DevOps",
                 font=("Segoe UI", 11, "bold"), fg="#185FA5").pack(anchor="w")
        tk.Frame(frame, height=1, bg="#e0e0e0").pack(fill="x", pady=(2, 10))

        self.w_org = self._campo_wizard(frame, "Organizacion")
        self.w_project = self._campo_wizard(frame, "Proyecto")
        self.w_pat = self._campo_wizard(frame, "Personal Access Token (PAT)", oculto=True)

        # Sección IA
        tk.Label(frame, text="Inteligencia Artificial",
                 font=("Segoe UI", 11, "bold"), fg="#185FA5").pack(anchor="w", pady=(16, 0))
        tk.Frame(frame, height=1, bg="#e0e0e0").pack(fill="x", pady=(2, 10))

        # Selector de proveedor de IA
        tk.Label(frame, text="Proveedor de IA",
                 font=("Segoe UI", 10), fg="#444").pack(anchor="w", pady=(0, 2))
        self.w_ia_provider = tk.StringVar(value="Anthropic (Claude)")
        provider_menu = ttk.Combobox(
            frame,
            textvariable=self.w_ia_provider,
            values=["Anthropic (Claude)", "OpenAI (GPT)", "Google (Gemini)", "DeepSeek"],
            state="readonly",
            font=("Segoe UI", 11)
        )
        provider_menu.pack(fill="x", ipady=4)

        self.w_api_key = self._campo_wizard(frame, "API Key del proveedor", oculto=True)

        # Botón guardar
        tk.Button(
            frame,
            text="Guardar y continuar",
            font=("Segoe UI", 11, "bold"),
            bg="#185FA5", fg="white",
            relief="flat", cursor="hand2",
            padx=12, pady=14,
            command=self.guardar_wizard
        ).pack(fill="x", pady=(20, 12))
    def _campo_wizard(self, parent, label, oculto=False):
        tk.Label(parent, text=label,
                 font=("Segoe UI", 10), fg="#444").pack(anchor="w", pady=(6, 2))
        var = tk.StringVar()
        tk.Entry(parent, textvariable=var,
                 font=("Segoe UI", 11),
                 relief="solid", bd=1,
                 show="*" if oculto else "").pack(fill="x", ipady=5)
        return var

    def guardar_wizard(self):
        if not all([self.w_org.get(), self.w_project.get(),
                    self.w_pat.get(), self.w_api_key.get()]):
            messagebox.showwarning(
                "Campos incompletos", "Por favor completa todos los campos.")
            return

        config = {
            "azure_org": self.w_org.get().strip(),
            "azure_project": self.w_project.get().strip(),
            "azure_pat": self.w_pat.get().strip(),
            "ia_provider": self.w_ia_provider.get(),
            "anthropic_key": self.w_api_key.get().strip()
        }

        if guardar_config(config):
            self._config = config
            aplicar_config(config)
            self.show_main()
        else:
            messagebox.showerror(
                "Error", "No se pudo guardar la configuracion.")

    # ── PANTALLA CONFIGURACIÓN (editar) ───────────────────────────────────────

    def show_config(self):
        self._clear_window()
        self.root.geometry("480x660")

        frame = tk.Frame(self.root, padx=30, pady=24)
        frame.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(frame)
        header.pack(fill="x", pady=(0, 4))
        tk.Label(header, text="Configuracion",
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Button(header, text="Volver",
                  font=("Segoe UI", 10), fg="gray",
                  bg=self.root.cget("bg"), relief="flat",
                  cursor="hand2",
                  command=self.show_main).pack(side="right")

        tk.Label(frame,
                 text="Edita los datos de conexion cuando lo necesites.",
                 font=("Segoe UI", 10), fg="gray").pack(anchor="w", pady=(0, 16))

        # Azure
        tk.Label(frame, text="Azure DevOps",
                 font=("Segoe UI", 11, "bold"), fg="#185FA5").pack(anchor="w")
        tk.Frame(frame, height=1, bg="#e0e0e0").pack(fill="x", pady=(2, 10))

        self.c_org = self._campo_config(
            frame, "Organizacion",
            self._config.get("azure_org", ""))
        self.c_project = self._campo_config(
            frame, "Proyecto",
            self._config.get("azure_project", ""))
        self.c_pat = self._campo_config(
            frame, "Personal Access Token (PAT)",
            self._config.get("azure_pat", ""), oculto=True)

        # IA
        tk.Label(frame, text="Inteligencia Artificial",
                 font=("Segoe UI", 11, "bold"),
                 fg="#185FA5").pack(anchor="w", pady=(16, 0))
        tk.Frame(frame, height=1, bg="#e0e0e0").pack(fill="x", pady=(2, 10))

        tk.Label(frame, text="Proveedor de IA",
                 font=("Segoe UI", 10), fg="#444").pack(anchor="w", pady=(0, 2))
        self.c_provider = tk.StringVar(
            value=self._config.get("ia_provider", "Anthropic (Claude)"))
        ttk.Combobox(
            frame,
            textvariable=self.c_provider,
            values=["Anthropic (Claude)", "OpenAI (GPT)", "Google (Gemini)"],
            state="readonly",
            font=("Segoe UI", 11)
        ).pack(fill="x", ipady=4)

        self.c_api_key = self._campo_config(
            frame, "API Key",
            self._config.get("anthropic_key", ""), oculto=True)

        # Botones
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        tk.Button(
            btn_frame,
            text="Guardar cambios",
            font=("Segoe UI", 11, "bold"),
            bg="#185FA5", fg="white",
            relief="flat", cursor="hand2",
            padx=12, pady=10,
            command=self.guardar_config_edit
        ).pack(fill="x", pady=(0, 8))

        tk.Button(
            btn_frame,
            text="Restablecer configuracion",
            font=("Segoe UI", 10),
            fg="red", bg=self.root.cget("bg"),
            relief="flat", cursor="hand2",
            command=self.resetear_config
        ).pack(anchor="center")

    def _campo_config(self, parent, label, valor="", oculto=False):
        tk.Label(parent, text=label,
                 font=("Segoe UI", 10), fg="#444").pack(anchor="w", pady=(6, 2))
        var = tk.StringVar(value=valor)
        tk.Entry(parent, textvariable=var,
                 font=("Segoe UI", 11),
                 relief="solid", bd=1,
                 show="*" if oculto else "").pack(fill="x", ipady=5)
        return var

    def guardar_config_edit(self):
        if not all([self.c_org.get(), self.c_project.get(),
                    self.c_pat.get(), self.c_api_key.get()]):
            messagebox.showwarning(
                "Campos incompletos", "Por favor completa todos los campos.")
            return

        config = {
            "azure_org": self.c_org.get().strip(),
            "azure_project": self.c_project.get().strip(),
            "azure_pat": self.c_pat.get().strip(),
            "ia_provider": self.c_provider.get(),
            "anthropic_key": self.c_api_key.get().strip()
        }

        if guardar_config(config):
            self._config = config
            aplicar_config(config)
            messagebox.showinfo("Guardado", "Configuracion actualizada correctamente.")
            self.show_main()
        else:
            messagebox.showerror("Error", "No se pudo guardar la configuracion.")

    def resetear_config(self):
        confirmar = messagebox.askyesno(
            "Restablecer",
            "Esto eliminara la configuracion guardada.\n"
            "La proxima vez tendra que configurar todo de nuevo.\n\n"
            "¿Deseas continuar?"
        )
        if confirmar:
            eliminar_config()
            self._config = None
            self.show_wizard()

    # ── PANTALLA PRINCIPAL ─────────────────────────────────────────────────────

    def show_main(self):
        self._clear_window()
        self.root.geometry("520x620")

        main = tk.Frame(self.root, padx=24, pady=20)
        main.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(main)
        header.pack(fill="x", pady=(0, 4))

        tk.Label(header, text="QA Agent",
                 font=("Segoe UI", 16, "bold")).pack(side="left")

        right = tk.Frame(header)
        right.pack(side="right")
        tk.Label(right,
                 text=self._user.get("name", "Usuario"),
                 font=("Segoe UI", 10, "bold")).pack(anchor="e")
        tk.Label(right,
                 text=self._user.get("email", ""),
                 font=("Segoe UI", 9), fg="gray").pack(anchor="e")

        tk.Frame(main, height=1, bg="#e0e0e0").pack(fill="x", pady=(4, 16))

        # Info de configuración activa
        config_info = tk.Frame(main, bg="#f0f4ff", padx=10, pady=8)
        config_info.pack(fill="x", pady=(0, 16))
        org = self._config.get("azure_org", "")
        project = self._config.get("azure_project", "")
        provider = self._config.get("ia_provider", "Anthropic")
        tk.Label(config_info,
                 text=f"Azure: {org} / {project}   |   IA: {provider}",
                 font=("Segoe UI", 9), fg="#444",
                 bg="#f0f4ff").pack(side="left")
        tk.Button(config_info, text="Editar",
                  font=("Segoe UI", 9), fg="#185FA5",
                  bg="#f0f4ff", relief="flat",
                  cursor="hand2",
                  command=self.show_config).pack(side="right")

        # Campo PBI
        tk.Label(main, text="ID del PBI",
                 font=("Segoe UI", 10), fg="#444").pack(anchor="w", pady=(0, 2))
        self.pbi_var = tk.StringVar()
        tk.Entry(main, textvariable=self.pbi_var,
                 font=("Segoe UI", 11),
                 relief="solid", bd=1).pack(fill="x", ipady=6)

        # Botones
        self.btn_analizar = tk.Button(
            main, text="Analizar PBI",
            font=("Segoe UI", 11, "bold"),
            bg="#185FA5", fg="white",
            relief="flat", cursor="hand2",
            padx=12, pady=10,
            command=self.ejecutar_analisis
        )
        self.btn_analizar.pack(fill="x", pady=(16, 4))

        self.btn_crear = tk.Button(
            main, text="Crear test cases en Azure",
            font=("Segoe UI", 11, "bold"),
            bg="#16A34A", fg="white",
            relief="flat", cursor="hand2",
            padx=12, pady=10,
            state="disabled",
            command=self.ejecutar_creacion
        )
        self.btn_crear.pack(fill="x", pady=(0, 12))

        tk.Label(main, text="Resultado",
                 font=("Segoe UI", 10), fg="gray").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(
            main, height=10, font=("Consolas", 10),
            state="disabled", relief="flat",
            bg="#f4f4f4", bd=1
        )
        self.log.pack(fill="both", expand=True)

        tk.Button(
            main, text="Cerrar sesion",
            font=("Segoe UI", 9), fg="gray",
            bg=self.root.cget("bg"),
            relief="flat", cursor="hand2",
            command=self.cerrar_sesion
        ).pack(anchor="e", pady=(8, 0))

    def cerrar_sesion(self):
        self._user = None
        self._token = None
        self._pbi = None
        self._test_cases = None
        self.show_login()

    # ── HELPERS ────────────────────────────────────────────────────────────────

    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def log_msg(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def log_clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _reset_analizar(self):
        self.btn_analizar.config(state="normal", text="Analizar PBI")

    # ── FASE 1: ANALIZAR ───────────────────────────────────────────────────────

    def ejecutar_analisis(self):
        if not self.pbi_var.get().strip():
            messagebox.showwarning("Campo vacio", "Ingresa el ID del PBI.")
            return
        self._pbi = None
        self._test_cases = None
        self.btn_crear.config(state="disabled")
        self.btn_analizar.config(state="disabled", text="Analizando...")
        self.log_clear()
        self.log_msg(f"Usuario: {self._user.get('name')} ({self._user.get('email')})")
        threading.Thread(target=self._analisis_thread, daemon=True).start()

    def _analisis_thread(self):
        pbi_id = self.pbi_var.get().strip()

        self.log_msg(f"Obteniendo PBI {pbi_id}...")
        try:
            pbi = get_pbi(pbi_id)
        except Exception as e:
            self.log_msg(f"Error inesperado: {str(e)}")
            self._reset_analizar()
            return

        if not pbi:
            self.log_msg("Error: no se pudo obtener el PBI.")
            self.log_msg("Verifica tu conexion y credenciales en Configuracion.")
            self._reset_analizar()
            return

        self.log_msg(f"PBI encontrado: {pbi['titulo']}")

        # V1 — Verificar si ya tiene test cases
        self.log_msg("Verificando test cases existentes...")
        cantidad, error_tc = tiene_test_cases(pbi_id)

        if error_tc:
            self.log_msg(f"Advertencia: no se pudo verificar test cases: {error_tc}")
        elif cantidad and cantidad > 0:
            # Verificar si existe el marcador manual "Test" entre los TCs vinculados
            tc_manual_id, _ = buscar_tc_manual(pbi_id)
            
            if tc_manual_id:
                # Existe el marcador manual — permitir continuar, será sobreescrito
                self.log_msg("TC marcador manual detectado. Será reutilizado.")
            else:
                # No hay marcador manual — son TCs reales, bloquear duplicados
                self.log_msg(f"\nBLOQUEADO: Este PBI ya tiene {cantidad} test case(s) creados.")
                self.log_msg("No se pueden crear test cases duplicados.")
                self.log_msg("Si necesitas regenerarlos, elimina los existentes en Azure primero.")
                self._reset_analizar()
                return

        self.log_msg("Sin test cases previos. Continuando...")

        # V2 — Validar asignacion
        self.log_msg("Verificando asignacion del PBI...")
        email_qa = self._user.get("email", "")
        asignado, nombre_asignado = validar_asignacion(pbi, email_qa)

        if not asignado:
            if nombre_asignado == "Sin asignar":
                self.log_msg("\nBLOQUEADO: El PBI no tiene un QA asignado.")
                self.log_msg("Pide a tu lider que te asigne el PBI antes de continuar.")
            else:
                self.log_msg(f"\nBLOQUEADO: Este PBI esta asignado a: {nombre_asignado}")
                self.log_msg(f"Tu usuario es: {email_qa}")
            self.log_msg("Solo el QA asignado puede crear test cases para este PBI.")
            self._reset_analizar()
            return

        self.log_msg(f"Asignacion verificada: {nombre_asignado}")

        # Resto del flujo (completitud, generacion, etc.)
        nivel = pbi["completitud"]["nivel"]

        if nivel == "completo":
            self.log_msg("Completitud: COMPLETO")
            self.log_msg("\nGenerando test cases con IA...")
            self._generar_y_mostrar(pbi)

        elif nivel == "parcial":
            faltantes = ", ".join(pbi["completitud"]["campos_faltantes"])
            self.log_msg(f"Completitud: PARCIAL — faltan: {faltantes}")
            self.log_msg("Agregando tag 'AC-Pendiente'...")
            try:
                agregar_tag_pbi(pbi_id, "AC-Pendiente")
                self.log_msg("Tag agregado.")
            except Exception as e:
                self.log_msg(f"Advertencia: {str(e)}")
            self.log_msg("\nGenerando test cases con IA...")
            self._generar_y_mostrar(pbi)

        elif nivel == "incompleto":
            self.log_msg("Completitud: INCOMPLETO")
            self.log_msg("Agregando tag 'AC-Pendiente'...")
            try:
                agregar_tag_pbi(pbi_id, "AC-Pendiente")
                self.log_msg("Tag agregado.")
            except Exception as e:
                self.log_msg(f"Advertencia: {str(e)}")
            self.log_msg("\nNO se pueden generar test cases sin criterios de aceptacion.")
            self.log_msg("Pide al Product Owner que complete el PBI.")
            self._reset_analizar()

    def _generar_y_mostrar(self, pbi):
        resultado, error_ia = generate_test_cases(pbi)

        if error_ia:
            self.log_msg(f"Error con IA: {error_ia}")
            self._reset_analizar()
            return

        if not resultado:
            self.log_msg("Error: no se obtuvieron test cases.")
            self._reset_analizar()
            return

        test_cases = resultado["test_cases"]
        self.log_msg(f"\nTest cases propuestos ({len(test_cases)}):")
        for i, tc in enumerate(test_cases, 1):
            self.log_msg(f"  {i}. {tc['titulo']} ({len(tc['pasos'])} pasos)")

        self.log_msg("\nRevisa los test cases y confirma para crear en Azure.")
        self._pbi = pbi
        self._test_cases = test_cases
        self.btn_crear.config(state="normal")
        self._reset_analizar()

    # ── FASE 2: CREAR EN AZURE ─────────────────────────────────────────────────

    def ejecutar_creacion(self):
        if not self._pbi or not self._test_cases:
            messagebox.showwarning("Sin datos", "Primero analiza un PBI.")
            return
        self.btn_crear.config(state="disabled", text="Creando...")
        self.btn_analizar.config(state="disabled")
        threading.Thread(target=self._creacion_thread, daemon=True).start()

    def _creacion_thread(self):
        creados = 0
        errores = []
        total = len(self._test_cases)

        self.log_msg("\nCreando test cases en Azure DevOps...")

        for i, tc in enumerate(self._test_cases):
            # enumerate() da el índice i (0, 1, 2...)
            # es_primero=True solo cuando i==0 — el primer TC del bucle
            # Esto le indica a create_test_case_in_azure que busque
            # el marcador manual y lo sobreescriba en lugar de crear uno nuevo
            tc_id, error = create_test_case_in_azure(
                self._pbi,
                tc,
                es_primero=(i == 0)
            )
            if tc_id:
                creados += 1
                self.log_msg(f"  Creado: {tc['titulo']}")
            else:
                errores.append(tc["titulo"])
                self.log_msg(f"  Error en '{tc['titulo']}': {error}")

        self.log_msg("\n" + "=" * 40)
        if creados == total:
            self.log_msg(f"Completado: {creados}/{total} test cases creados.")
        elif creados > 0:
            self.log_msg(f"Parcial: {creados}/{total} test cases creados.")
            self.log_msg(f"Fallaron: {', '.join(errores)}")
        else:
            self.log_msg(f"Sin exito: 0/{total} test cases creados.")
            self.log_msg("Revisa tu conexion y permisos en Configuracion.")

        self._pbi = None
        self._test_cases = None
        self.btn_crear.config(state="disabled", text="Crear test cases en Azure")
        self.btn_analizar.config(state="normal", text="Analizar PBI")


if __name__ == "__main__":
    root = tk.Tk()
    app = QAAgentApp(root)
    root.mainloop()