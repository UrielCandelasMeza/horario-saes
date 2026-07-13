import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from horario_saes.modulos.dialogos import (DialogoBloque, DialogoCheck, DialogoExportar,
                              DialogoFiltro, VistaArbol, VistaPlan, VistaProfesores)
from horario_saes.modulos.modelo import Estado
from horario_saes.modulos.parser_saes import DIAS_LARGO

RUTA_SESION = Path.home() / ".horario_saes" / "sesion.json"
_vieja = Path(__file__).resolve().parent.parent / "datos" / "sesion.json"
if not RUTA_SESION.exists() and _vieja.exists():
    RUTA_SESION.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_vieja, RUTA_SESION)
HORA_INI, HORA_FIN = 7, 22
GRIS = "#78909C"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Horarios SAES")
        self.geometry("1280x760")
        self.minsize(980, 600)

        self.estado = Estado(RUTA_SESION)
        self.filtros = {"texto": "", "solo_favoritos": False,
                        "ocultar_incompatibles": False, "turno": "todos"}

        self._construir_toolbar()
        self._construir_cuerpo()
        self._construir_barra_ramas()

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        if self.estado.cargar_sesion():
            self.after(50, self.refresh)

    # ------------------------------------------------------------ layout
    def _construir_toolbar(self) -> None:
        barra = ttk.Frame(self, padding=(8, 6))
        barra.pack(fill="x")
        ttk.Button(barra, text="📂 Cargar TXT", command=self._cargar_txt).pack(side="left", padx=2)
        ttk.Button(barra, text="🔍 Filtrar", command=self._abrir_filtro).pack(side="left", padx=2)
        ttk.Button(barra, text="🌿 Bifurcar", command=self._bifurcar).pack(side="left", padx=2)
        ttk.Button(barra, text="🌳 Árbol", command=self._abrir_arbol).pack(side="left", padx=2)
        ttk.Button(barra, text="➕ Bloque propio", command=self._abrir_bloque).pack(side="left", padx=2)
        ttk.Button(barra, text="📋 Plan/Equiv", command=self._abrir_plan).pack(side="left", padx=2)
        ttk.Button(barra, text="✅ Check", command=self._abrir_check).pack(side="left", padx=2)
        ttk.Button(barra, text="📤 Exportar", command=self._abrir_exportar).pack(side="left", padx=2)

        ttk.Label(barra, text="  Créditos máx:").pack(side="left")
        self.var_max = tk.StringVar()
        ent_max = ttk.Entry(barra, textvariable=self.var_max, width=7)
        ent_max.pack(side="left")
        ent_max.bind("<Return>", self._aplicar_max)
        ent_max.bind("<FocusOut>", self._aplicar_max)

        self.lbl_contadores = ttk.Label(barra, font=("Segoe UI", 10, "bold"))
        self.lbl_contadores.pack(side="right", padx=8)
        self.lbl_check = ttk.Label(barra, font=("Segoe UI", 10, "bold"))
        self.lbl_check.pack(side="right")

    def _construir_cuerpo(self) -> None:
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True)

        # panel lateral: canvas dibujado (mucho más rápido que cientos de widgets)
        lateral = ttk.Frame(cuerpo, width=330)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        self.canvas_lista = tk.Canvas(lateral, highlightthickness=0, bg="#FAFAFA",
                                      yscrollincrement=24)
        barra = ttk.Scrollbar(lateral, orient="vertical", command=self.canvas_lista.yview)
        self.canvas_lista.configure(yscrollcommand=barra.set)
        self.canvas_lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self._acciones_lista: dict[str, tuple[str, str]] = {}
        self.canvas_lista.bind("<Button-1>", self._click_lista)
        self.canvas_lista.bind("<Button-3>", self._click_der_lista)
        self.canvas_lista.bind("<Enter>", lambda e: self._activar_rueda(True))
        self.canvas_lista.bind("<Leave>", lambda e: self._activar_rueda(False))

        # panel derecho: materias que estás inscribiendo
        self.panel_insc = ttk.Frame(cuerpo, width=235)
        self.panel_insc.pack(side="right", fill="y")
        self.panel_insc.pack_propagate(False)

        # horario central (redibujo con retardo para no trabarse al redimensionar)
        self.canvas_horario = tk.Canvas(cuerpo, bg="white", highlightthickness=0)
        self.canvas_horario.pack(side="left", fill="both", expand=True)
        self._redibujo_pendiente: str | None = None
        self.canvas_horario.bind("<Configure>", lambda e: self._redibujar_pronto())

    def _construir_barra_ramas(self) -> None:
        pie = ttk.Frame(self, padding=(8, 4))
        pie.pack(fill="x")
        self.lbl_rama = ttk.Label(pie, font=("Segoe UI", 10, "bold"))
        self.lbl_rama.pack(side="left", padx=(0, 10))
        self.marco_ramas = ttk.Frame(pie)
        self.marco_ramas.pack(side="left", fill="x")

    def _activar_rueda(self, activo: bool) -> None:
        if activo:
            self.canvas_lista.bind_all("<MouseWheel>", self._rueda_lista)
        else:
            self.canvas_lista.unbind_all("<MouseWheel>")

    def _rueda_lista(self, evento) -> None:
        self.canvas_lista.yview_scroll(-3 if evento.delta > 0 else 3, "units")

    def _redibujar_pronto(self) -> None:
        if self._redibujo_pendiente:
            self.after_cancel(self._redibujo_pendiente)
        self._redibujo_pendiente = self.after(50, self._redibujo)

    def _redibujo(self) -> None:
        self._redibujo_pendiente = None
        self._dibujar_horario()

    # ----------------------------------------------------------- acciones
    def _cargar_txt(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona el txt copiado del SAES",
            initialdir=str(Path.home() / "Downloads"),
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            n = self.estado.cargar_txt(ruta)
        except OSError as e:
            messagebox.showerror("Error al leer", str(e))
            return
        if n == 0:
            messagebox.showwarning(
                "Sin datos",
                "No encontré grupos en ese archivo. ¿Seguro que es el formato "
                "del SAES con tabuladores?")
        self.refresh()

    def _abrir_filtro(self) -> None:
        DialogoFiltro(self, self.filtros, self.refresh)

    def _bifurcar(self) -> None:
        nombre = simpledialog.askstring(
            "Bifurcar", "Nombre de la nueva rama (vacío = automático):", parent=self)
        if nombre is None:
            return
        self.estado.bifurcar(nombre.strip())
        self.refresh()

    def _abrir_arbol(self) -> None:
        VistaArbol(self, self.estado, self.refresh)

    def _abrir_bloque(self) -> None:
        DialogoBloque(self, self.estado, self.refresh)

    def _abrir_exportar(self) -> None:
        if not self.estado.seleccionadas():
            messagebox.showinfo("Nada que exportar",
                                "Agrega materias al horario primero.")
            return
        DialogoExportar(self, self.estado)

    def _abrir_plan(self) -> None:
        VistaPlan(self, self.estado)

    def _abrir_check(self) -> None:
        DialogoCheck(self, self.estado, self.refresh)

    def _ver_profesores(self, materia: str) -> None:
        VistaProfesores(self, self.estado, materia, self.refresh)

    def _aplicar_max(self, *_):
        texto = self.var_max.get().strip().replace(",", ".")
        try:
            self.estado.max_creditos = float(texto) if texto else None
        except ValueError:
            self.var_max.set("" if self.estado.max_creditos is None
                             else f"{self.estado.max_creditos:g}")
            return
        self.refresh()

    def _editar_creditos(self, materia: str) -> None:
        actual = self.estado.creditos.get(materia)
        nuevo = simpledialog.askfloat(
            "Créditos", f"Créditos de {materia} (ahora: "
            f"{'SN' if actual is None else f'{actual:g}'})\n"
            f"Escribe -1 para regresarla a SN:",
            initialvalue=actual or 0, parent=self)
        if nuevo is not None:
            self.estado.fijar_creditos(materia, None if nuevo < 0 else nuevo)
            self.refresh()

    def _confirmar(self, titulo: str, mensaje: str) -> bool:
        """Diálogo con botones Continuar / Cancelar."""
        dlg = tk.Toplevel(self)
        dlg.title(titulo)
        dlg.resizable(False, False)
        dlg.grab_set()
        respuesta = {"ok": False}
        ttk.Label(dlg, text=mensaje, padding=16, justify="center").pack()
        botones = ttk.Frame(dlg)
        botones.pack(pady=(0, 12))

        def responder(ok: bool):
            respuesta["ok"] = ok
            dlg.destroy()

        ttk.Button(botones, text="Continuar",
                   command=lambda: responder(True)).pack(side="left", padx=6)
        ttk.Button(botones, text="Cancelar",
                   command=lambda: responder(False)).pack(side="left", padx=6)
        dlg.bind("<Escape>", lambda e: responder(False))
        dlg.transient(self)
        self.wait_window(dlg)
        return respuesta["ok"]

    def _toggle_opcion(self, op_id: str) -> None:
        e = self.estado
        if op_id in e.rama().seleccion:
            e.quitar(op_id)
        else:
            op = e.opciones[op_id]
            cred = e.creditos.get(op.materia) or 0
            total, _ = e.total_creditos()
            if e.max_creditos is not None and total + cred > e.max_creditos:
                if not self._confirmar(
                        "Créditos excedidos",
                        f"Estás superando tus créditos autorizados:\n"
                        f"{total + cred:g} de {e.max_creditos:g} permitidos.\n\n"
                        f"¿Quieres continuar?"):
                    return
            e.agregar(op_id)
        self.refresh()

    def _toggle_favorito(self, profesor: str) -> None:
        if profesor in self.estado.favoritos:
            self.estado.favoritos.discard(profesor)
        else:
            self.estado.favoritos.add(profesor)
        self.refresh()

    def _quitar_propia(self, op_id: str) -> None:
        if messagebox.askyesno("Eliminar bloque", "¿Eliminar este bloque propio?"):
            self.estado.quitar_propia(op_id)
            self.refresh()

    def _cambiar_rama(self, rama_id: int) -> None:
        self.estado.rama_actual = rama_id
        self.refresh()

    def _cerrar(self) -> None:
        self.estado.guardar()
        self.destroy()

    # ------------------------------------------------------------ refresh
    def refresh(self) -> None:
        self.estado.guardar()
        self._refrescar_contadores()
        self._refrescar_lista()
        self._refrescar_inscritos()
        self._dibujar_horario()
        self._refrescar_ramas()

    def _refrescar_inscritos(self) -> None:
        for w in self.panel_insc.winfo_children():
            w.destroy()
        e = self.estado
        sel = sorted(e.seleccionadas(), key=lambda o: o.materia)
        ttk.Label(self.panel_insc, text=f"Inscribiendo ({len(sel)})",
                  font=("Segoe UI", 11, "bold"), padding=(8, 6)).pack(anchor="w")

        for op in sel:
            color = e.colores.get(op.materia, "#DDD")
            fila = tk.Frame(self.panel_insc, bg="white", bd=1, relief="solid")
            fila.pack(fill="x", padx=6, pady=2)
            tk.Frame(fila, bg=color, width=6).pack(side="left", fill="y")
            btn_x = tk.Label(fila, text="✕", bg="white", fg="#C62828",
                             font=("Segoe UI", 10, "bold"), cursor="hand2", padx=6)
            btn_x.pack(side="right")
            btn_x.bind("<Button-1>", lambda ev, i=op.id: self._toggle_opcion(i))
            marco = tk.Frame(fila, bg="white")
            marco.pack(side="left", fill="x", expand=True, padx=4, pady=2)
            nombre = op.materia if len(op.materia) < 30 else f"{op.materia[:29]}…"
            tk.Label(marco, text=nombre, bg="white", anchor="w",
                     font=("Segoe UI", 9, "bold")).pack(fill="x")
            cred = e.creditos.get(op.materia)
            detalle = f"{op.grupo} · {'SN' if cred is None else f'{cred:g} cr'}"
            tk.Label(marco, text=detalle, bg="white", anchor="w", fg="#546E7A",
                     font=("Segoe UI", 8)).pack(fill="x")

        if e.necesarias:
            faltan = e.faltantes()
            ttk.Separator(self.panel_insc).pack(fill="x", padx=6, pady=6)
            if faltan:
                ttk.Label(self.panel_insc, text=f"⚠ Faltan del check ({len(faltan)}):",
                          foreground="#C62828", font=("Segoe UI", 10, "bold"),
                          padding=(8, 0)).pack(anchor="w")
                for m in faltan:
                    nombre = m if len(m) < 32 else f"{m[:31]}…"
                    ttk.Label(self.panel_insc, text=f"• {nombre}",
                              foreground="#C62828", font=("Segoe UI", 8),
                              padding=(14, 0)).pack(anchor="w")
            else:
                ttk.Label(self.panel_insc, text="✔ Check completo",
                          foreground="#2E7D32", font=("Segoe UI", 10, "bold"),
                          padding=(8, 0)).pack(anchor="w")

    def _refrescar_contadores(self) -> None:
        e = self.estado
        sel = e.seleccionadas()
        total, sin_cred = e.total_creditos()
        cred = f"Créditos: {total:g}"
        excedido = False
        if e.max_creditos is not None:
            cred += f" / {e.max_creditos:g}"
            excedido = total > e.max_creditos
        if sin_cred:
            cred += f"  (⚠ {sin_cred} materia{'s' if sin_cred > 1 else ''} SN)"
        self.lbl_contadores.config(
            foreground="#C62828" if excedido else "#212121",
            text=(f"Opciones disponibles: {len(e.disponibles())}   |   "
                  f"Materias: {len(sel)}   |   {cred}   |   "
                  f"Horas/sem: {e.total_horas():g}"))
        if not e.necesarias:
            self.lbl_check.config(text="")
        else:
            faltan = len(e.faltantes())
            if faltan:
                self.lbl_check.config(text=f"⚠ Faltan {faltan} del check   |",
                                      foreground="#C62828")
            else:
                self.lbl_check.config(text="Check ✔   |", foreground="#2E7D32")
        if self.focus_get() is None or self.focus_get().winfo_class() != "TEntry":
            self.var_max.set("" if e.max_creditos is None else f"{e.max_creditos:g}")

    # ------------------------------------------------------- lista lateral
    def _pasa_filtro(self, op) -> bool:
        f = self.filtros
        texto = f["texto"].lower().strip()
        if texto and texto not in f"{op.materia} {op.profesor} {op.grupo}".lower():
            return False
        if f["solo_favoritos"] and not op.propia and op.profesor not in self.estado.favoritos:
            return False
        if f["turno"] != "todos" and op.sesiones:
            inicio_min = min(s.inicio for s in op.sesiones)
            if f["turno"] == "mat" and inicio_min >= 15 * 60:
                return False
            if f["turno"] == "vesp" and inicio_min < 15 * 60:
                return False
        return True

    def _click_lista(self, _evento) -> None:
        accion = self._accion_bajo_cursor()
        if not accion:
            return
        tipo, dato = accion
        if tipo == "op":
            self._toggle_opcion(dato)
        elif tipo == "fav":
            self._toggle_favorito(dato)
        elif tipo == "del":
            self._quitar_propia(dato)
        elif tipo == "prof":
            self._ver_profesores(dato)
        elif tipo == "hdr":
            if dato in self.estado.colapsadas:
                self.estado.colapsadas.discard(dato)
            else:
                self.estado.colapsadas.add(dato)
            self._refrescar_lista()

    def _click_der_lista(self, _evento) -> None:
        accion = self._accion_bajo_cursor()
        if accion and accion[0] in ("hdr", "prof"):
            self._editar_creditos(accion[1])

    def _accion_bajo_cursor(self) -> tuple[str, str] | None:
        for item in self.canvas_lista.find_withtag("current"):
            for tag in self.canvas_lista.gettags(item):
                if tag in self._acciones_lista:
                    return self._acciones_lista[tag]
        return None

    def _refrescar_lista(self) -> None:
        cv = self.canvas_lista
        vista_y = cv.yview()[0]
        cv.delete("all")
        self._acciones_lista.clear()
        e = self.estado
        seleccion = set(e.rama().seleccion)
        ancho = max(cv.winfo_width(), 200)

        if not e.opciones:
            cv.create_text(ancho / 2, 60, text="Carga el TXT del SAES\npara empezar 📂",
                           fill=GRIS, font=("Segoe UI", 11), justify="center")
            return

        y = 4
        n = 0
        for materia in e.orden_materias:
            ops = [op for op in e.opciones_de(materia) if self._pasa_filtro(op)]
            compatibles = [op for op in ops
                           if op.id in seleccion or e.es_compatible(op)]
            if self.filtros["ocultar_incompatibles"]:
                ops = compatibles
            if not ops:
                continue
            color = e.colores.get(materia, "#DDD")
            cred = e.creditos.get(materia)
            etiqueta_cred = "SN" if cred is None else f"{cred:g} cr"

            # cabecera de materia (click = plegar/desplegar)
            plegada = materia in e.colapsadas
            tag_h, tag_p = f"h{n}", f"p{n}"
            n += 1
            self._acciones_lista[tag_h] = ("hdr", materia)
            self._acciones_lista[tag_p] = ("prof", materia)
            y += 6
            cv.create_rectangle(4, y, ancho - 4, y + 26, fill=color, outline=color,
                                tags=(tag_h,))
            flecha = "▸" if plegada else "▾"
            texto_h = f"{flecha} {materia}  ({len(compatibles)}/{len(ops)}) · {etiqueta_cred}"
            if len(texto_h) > 42:
                texto_h = f"{texto_h[:41]}…"
            cv.create_text(10, y + 13, text=texto_h, anchor="w",
                           font=("Segoe UI", 9, "bold"), tags=(tag_h,))
            cv.create_text(ancho - 18, y + 13, text="👥", font=("Segoe UI", 10),
                           tags=(tag_p,))
            y += 26
            if plegada:
                continue

            for op in sorted(ops, key=lambda o: o.grupo):
                elegida = op.id in seleccion
                compatible = elegida or e.es_compatible(op)
                if elegida:
                    bg, fg, borde, grosor = color, "#212121", "#455A64", 2
                elif compatible:
                    bg, fg, borde, grosor = "white", "#212121", "#B0BEC5", 1
                else:
                    bg, fg, borde, grosor = "#ECEFF1", "#B0BEC5", "#CFD8DC", 1

                tag_op = f"o{n}"
                n += 1
                if compatible:
                    self._acciones_lista[tag_op] = ("op", op.id)
                y += 2
                cv.create_rectangle(10, y, ancho - 8, y + 46, fill=bg,
                                    outline=borde, width=grosor, tags=(tag_op,))
                marca = "✔ " if elegida else ("" if compatible else "✖ ")
                cv.create_text(16, y + 9, text=f"{marca}{op.grupo}", anchor="w",
                               fill=fg, font=("Segoe UI", 9, "bold"), tags=(tag_op,))
                cv.create_text(16, y + 23, text=op.profesor[:46], anchor="w",
                               fill=fg, font=("Segoe UI", 8), tags=(tag_op,))
                cv.create_text(16, y + 36, text=op.resumen_horario()[:48], anchor="w",
                               fill=fg, font=("Segoe UI", 8), tags=(tag_op,))

                tag_ex = f"x{n}"
                n += 1
                if op.propia:
                    self._acciones_lista[tag_ex] = ("del", op.id)
                    cv.create_text(ancho - 22, y + 10, text="🗑",
                                   font=("Segoe UI", 9), tags=(tag_ex,))
                else:
                    fav = op.profesor in self.estado.favoritos
                    self._acciones_lista[tag_ex] = ("fav", op.profesor)
                    cv.create_text(ancho - 22, y + 10, text="★" if fav else "☆",
                                   fill="#F9A825" if fav else "#90A4AE",
                                   font=("Segoe UI", 11), tags=(tag_ex,))
                y += 46

        cv.configure(scrollregion=(0, 0, ancho, y + 8))
        cv.yview_moveto(vista_y)

    # ---------------------------------------------------------- horario
    def _dibujar_horario(self, canvas: tk.Canvas | None = None,
                         rama=None, mini: bool = False,
                         dims: tuple[int, int] | None = None) -> None:
        cv = canvas or self.canvas_horario
        rama = rama or self.estado.rama()
        if not cv.winfo_exists():
            return
        cv.delete("all")
        ancho, alto = dims or (cv.winfo_width(), cv.winfo_height())
        if ancho < 10 or alto < 10:
            return

        m_izq = 8 if mini else 46
        m_sup = 4 if mini else 30
        m_inf = 4 if mini else 10
        col = (ancho - m_izq - 6) / 5
        total_min = (HORA_FIN - HORA_INI) * 60
        escala = (alto - m_sup - m_inf) / total_min

        def y_de(minutos: int) -> float:
            return m_sup + (minutos - HORA_INI * 60) * escala

        # rejilla
        for h in range(HORA_INI, HORA_FIN + 1):
            y = y_de(h * 60)
            cv.create_line(m_izq, y, ancho - 6, y, fill="#E0E0E0")
            if not mini:
                cv.create_text(m_izq - 6, y, text=f"{h}:00", anchor="e",
                               font=("Segoe UI", 8), fill=GRIS)
        for d in range(6):
            x = m_izq + d * col
            cv.create_line(x, m_sup, x, alto - m_inf, fill="#BDBDBD")
        if not mini:
            for d, nombre in enumerate(DIAS_LARGO):
                cv.create_text(m_izq + d * col + col / 2, m_sup / 2, text=nombre,
                               font=("Segoe UI", 10, "bold"), fill="#37474F")

        # bloques
        for op in self.estado.seleccionadas(rama):
            color = self.estado.colores.get(op.materia, "#DDD")
            for s in op.sesiones:
                x1 = m_izq + s.dia * col + 2
                x2 = m_izq + (s.dia + 1) * col - 2
                y1, y2 = y_de(s.inicio), y_de(s.fin)
                extra = {"dash": (4, 2)} if op.propia else {}
                cv.create_rectangle(x1, y1, x2, y2, fill=color,
                                    outline="#455A64", **extra)
                if not mini:
                    lugar = f" · {op.salon}" if op.salon and op.salon != "000" else ""
                    texto = f"{op.grupo}-{op.materia}\n{op.profesor}{lugar}"
                    if op.propia:
                        texto = f"{op.materia}\n{op.nota or ''}{lugar}"
                    cv.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=texto,
                                   font=("Segoe UI", 8), justify="center",
                                   width=x2 - x1 - 6)

    # ------------------------------------------------------------- ramas
    def _refrescar_ramas(self) -> None:
        for w in self.marco_ramas.winfo_children():
            w.destroy()
        e = self.estado
        actual = e.rama()
        self.lbl_rama.config(text=f"Rama: {actual.nombre}")

        for rama in e.familia():
            es_actual = rama.id == e.rama_actual
            if rama.padre is None and rama.id != actual.id:
                relacion = "padre" if actual.padre == rama.id else "raíz"
            elif rama.padre == actual.padre and not es_actual:
                relacion = "hermana"
            elif rama.padre == actual.id:
                relacion = "hija"
            elif actual.padre == rama.id:
                relacion = "padre"
            else:
                relacion = "actual"
            celda = tk.Frame(self.marco_ramas,
                             highlightthickness=2,
                             highlightbackground="#33691E" if es_actual else "#CFD8DC")
            celda.pack(side="left", padx=3)
            mini = tk.Canvas(celda, width=180, height=112, bg="white",
                             highlightthickness=0, cursor="hand2")
            mini.pack()
            tk.Label(celda, text=f"{rama.nombre} ({relacion})",
                     font=("Segoe UI", 8, "bold" if es_actual else "normal")).pack()
            mini.bind("<Button-1>", lambda ev, r=rama.id: self._cambiar_rama(r))
            self._dibujar_horario(mini, rama, mini=True, dims=(180, 112))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
