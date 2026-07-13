import math
import tkinter as tk
from tkinter import ttk

ACENTO = "#5C6BC0"
FONDO_CARA = "#ECEFF4"


class RelojPicker(ttk.Frame):
    """Selector de hora estilo reloj (como Android): primero la hora en dos
    anillos (exterior 1-12, interior 13-00), luego los minutos en pasos de 5."""

    def __init__(self, master, titulo: str, minutos: int = 7 * 60,
                 al_cambiar=None):
        super().__init__(master)
        self.hora = minutos // 60
        self.minuto = minutos % 60
        self.modo = "hora"
        self.al_cambiar = al_cambiar

        ttk.Label(self, text=titulo, font=("Segoe UI", 10, "bold")).pack()
        marco = ttk.Frame(self)
        marco.pack()
        self.lbl_hora = tk.Label(marco, font=("Segoe UI", 16, "bold"),
                                 fg=ACENTO, cursor="hand2")
        self.lbl_hora.pack(side="left")
        self.lbl_min = tk.Label(marco, font=("Segoe UI", 16), cursor="hand2")
        self.lbl_min.pack(side="left")
        self.lbl_hora.bind("<Button-1>", lambda e: self._cambiar_modo("hora"))
        self.lbl_min.bind("<Button-1>", lambda e: self._cambiar_modo("min"))

        self.tam = 190
        self.canvas = tk.Canvas(self, width=self.tam, height=self.tam,
                                highlightthickness=0)
        self.canvas.pack(pady=4)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<B1-Motion>", self._click)
        self._dibujar()

    # ------------------------------------------------------------- api
    def get_minutos(self) -> int:
        return self.hora * 60 + self.minuto

    def set_minutos(self, minutos: int) -> None:
        self.hora, self.minuto = minutos // 60, minutos % 60
        self._dibujar()

    # ---------------------------------------------------------- interno
    def _cambiar_modo(self, modo: str) -> None:
        self.modo = modo
        self._dibujar()

    def _pos(self, indice: int, radio: float) -> tuple[float, float]:
        ang = math.radians(indice * 30 - 90)
        c = self.tam / 2
        return c + radio * math.cos(ang), c + radio * math.sin(ang)

    def _dibujar(self) -> None:
        cv = self.canvas
        cv.delete("all")
        c = self.tam / 2
        cv.create_oval(4, 4, self.tam - 4, self.tam - 4,
                       fill=FONDO_CARA, outline="#C5CAE9", width=2)
        r_ext, r_int = c - 22, c - 52

        if self.modo == "hora":
            sel = self.hora
            radio_sel = r_ext if 1 <= self.hora <= 12 else r_int
            idx_sel = self.hora % 12
            for i in range(12):
                h_ext = 12 if i == 0 else i
                h_int = 0 if i == 0 else i + 12
                for h, radio, tam_f in ((h_ext, r_ext, 11), (h_int, r_int, 9)):
                    x, y = self._pos(i, radio)
                    activo = h == sel
                    if activo:
                        cv.create_oval(x - 13, y - 13, x + 13, y + 13,
                                       fill=ACENTO, outline="")
                    cv.create_text(x, y, text=f"{h:02d}" if radio == r_int else str(h),
                                   font=("Segoe UI", tam_f, "bold" if activo else "normal"),
                                   fill="white" if activo else "#37474F")
            x, y = self._pos(idx_sel, radio_sel)
        else:
            idx_sel = round(self.minuto / 5) % 12
            for i in range(12):
                m = i * 5
                x, y = self._pos(i, r_ext)
                activo = i == idx_sel
                if activo:
                    cv.create_oval(x - 13, y - 13, x + 13, y + 13,
                                   fill=ACENTO, outline="")
                cv.create_text(x, y, text=f"{m:02d}",
                               font=("Segoe UI", 11, "bold" if activo else "normal"),
                               fill="white" if activo else "#37474F")
            x, y = self._pos(idx_sel, r_ext)

        cv.create_line(c, c, x, y, fill=ACENTO, width=2)
        cv.create_oval(c - 3, c - 3, c + 3, c + 3, fill=ACENTO, outline="")

        activo_h = self.modo == "hora"
        self.lbl_hora.config(text=f"{self.hora:02d}:",
                             fg=ACENTO if activo_h else "#37474F")
        self.lbl_min.config(text=f"{self.minuto:02d}",
                            fg="#37474F" if activo_h else ACENTO)

    def _click(self, evento) -> None:
        c = self.tam / 2
        dx, dy = evento.x - c, evento.y - c
        dist = math.hypot(dx, dy)
        if dist < 15:
            return
        ang = math.degrees(math.atan2(dy, dx)) + 90
        indice = round(ang / 30) % 12
        if self.modo == "hora":
            r_ext, r_int = c - 22, c - 52
            exterior = dist > (r_ext + r_int) / 2
            if exterior:
                self.hora = 12 if indice == 0 else indice
            else:
                self.hora = 0 if indice == 0 else indice + 12
            self._dibujar()
            self.after(350, lambda: self._cambiar_modo("min"))
        else:
            self.minuto = indice * 5
            self._dibujar()
        if self.al_cambiar:
            self.al_cambiar()
