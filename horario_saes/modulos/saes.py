"""Scraper del SAES (beta): login con captcha y descarga de horarios,
equivalencias, kardex (cursadas) y mapa curricular.

El SAES es ASP.NET WebForms: cada página exige __VIEWSTATE/__EVENTVALIDATION,
por eso todo va sobre una misma sesión de requests. Las rutas son iguales en
casi todas las escuelas; algunas agregan o quitan pestañas.
"""
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Rutas conocidas del SAES (relativas a la base de cada escuela)
RUTA_LOGIN = "/"
RUTA_HORARIOS = "/Academica/horarios.aspx"
RUTA_EQUIVALENCIAS = "/Academica/Equivalencias.aspx"
RUTA_MAPA = "/Academica/mapa_curricular.aspx"
RUTA_KARDEX = "/Alumnos/boleta/kardex.aspx"

# Superior (NS)
ESCUELAS_NS = {
    "UPIICSA": "https://www.saes.upiicsa.ipn.mx",
    "ESCA Sto. Tomás": "https://www.saes.escasto.ipn.mx",
    "ESCA Tepepan": "https://www.saes.escatep.ipn.mx",
    "ESCOM": "https://www.saes.escom.ipn.mx",
    "ESIME Zacatenco": "https://www.saes.esimez.ipn.mx",
    "ESIME Culhuacán": "https://www.saes.esimecu.ipn.mx",
    "ESIME Azcapotzalco": "https://www.saes.esimeazc.ipn.mx",
    "ESIME Ticomán": "https://www.saes.esimetic.ipn.mx",
    "ESIA Zacatenco": "https://www.saes.esiaz.ipn.mx",
    "ESIA Tecamachalco": "https://www.saes.esiatec.ipn.mx",
    "ESIA Ticomán": "https://www.saes.esiatic.ipn.mx",
    "ESIQIE": "https://www.saes.esiqie.ipn.mx",
    "ESFM": "https://www.saes.esfm.ipn.mx",
    "ESIT": "https://www.saes.esit.ipn.mx",
    "ENCB": "https://www.saes.encb.ipn.mx",
    "ENMH": "https://www.saes.enmh.ipn.mx",
    "ENBA": "https://www.saes.enba.ipn.mx",
    "ESM": "https://www.saes.esm.ipn.mx",
    "ESEO": "https://www.saes.eseo.ipn.mx",
    "ESE (Economía)": "https://www.saes.ese.ipn.mx",
    "EST": "https://www.saes.est.ipn.mx",
    "UPIBI": "https://www.saes.upibi.ipn.mx",
    "UPIITA": "https://www.saes.upiita.ipn.mx",
    "UPIEM": "https://www.saes.upiem.ipn.mx",
    "UPIIG": "https://www.saes.upiig.ipn.mx",
    "UPIIH": "https://www.saes.upiih.ipn.mx",
    "UPIIT": "https://www.saes.upiit.ipn.mx",
    "UPIIP": "https://www.saes.upiip.ipn.mx",
    "UPIIZ": "https://www.saes.upiiz.ipn.mx",
    "UPIIC": "https://www.saes.upiic.ipn.mx",
    "CICS Sto. Tomás": "https://www.saes.cicsst.ipn.mx",
    "CICS Milpa Alta": "https://www.saes.cicsma.ipn.mx",
}

# Medio superior (NMS)
ESCUELAS_NMS = {
    f"CECyT {n}": f"https://www.saes.cecyt{n}.ipn.mx" for n in range(1, 20)
}
ESCUELAS_NMS["CET 1"] = "https://www.saes.cet1.ipn.mx"

ESCUELAS = {**ESCUELAS_NS, **ESCUELAS_NMS}


class ErrorSaes(Exception):
    pass


class SesionSaes:
    def __init__(self, escuela: str):
        if escuela not in ESCUELAS:
            raise ErrorSaes(f"Escuela desconocida: {escuela}")
        self.base = ESCUELAS[escuela].rstrip("/")
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0"
        self._campos: dict[str, str] = {}

    # ------------------------------------------------------------- helpers
    def _url(self, ruta: str) -> str:
        return f"{self.base}{ruta}"

    def _get(self, ruta: str) -> str:
        r = self.s.get(self._url(ruta), timeout=25, verify=False)
        r.raise_for_status()
        return r.text

    def _hidden(self, html: str) -> dict[str, str]:
        """__VIEWSTATE, __EVENTVALIDATION, etc. de la página actual."""
        sopa = BeautifulSoup(html, "html.parser")
        return {i["name"]: i.get("value", "")
                for i in sopa.find_all("input", {"type": "hidden"}) if i.get("name")}

    # -------------------------------------------------------------- login
    def captcha(self) -> bytes:
        """Abre el login y devuelve los bytes de la imagen del captcha."""
        html = self._get(RUTA_LOGIN)
        self._campos = self._hidden(html)
        sopa = BeautifulSoup(html, "html.parser")
        img = sopa.find("img", src=lambda s: s and "captcha" in s.lower())
        if img is None:
            raise ErrorSaes("No encontré el captcha en el login")
        url = img["src"]
        if not url.startswith("http"):
            url = f"{self.base}/{url.lstrip('/')}"
        return self.s.get(url, timeout=25, verify=False).content

    def login(self, boleta: str, contrasena: str, captcha: str) -> bool:
        datos = dict(self._campos)
        datos.update({
            "ctl00$leftColumn$LoginUser$UserName": boleta,
            "ctl00$leftColumn$LoginUser$Password": contrasena,
            "ctl00$leftColumn$LoginUser$CampoDinamico": captcha,
            "ctl00$leftColumn$LoginUser$LoginButton": "Entrar",
        })
        r = self.s.post(self._url(RUTA_LOGIN), data=datos, timeout=25, verify=False)
        ok = "default.aspx" in r.url.lower() or "cerrar" in r.text.lower()
        if not ok and ("incorrecto" in r.text.lower() or "captcha" in r.text.lower()):
            raise ErrorSaes("Boleta, contraseña o captcha incorrectos")
        return ok

    # ------------------------------------------------- descarga (parseo)
    def _tablas(self, html: str) -> list[list[list[str]]]:
        """Todas las tablas de la página como listas de filas de celdas."""
        sopa = BeautifulSoup(html, "html.parser")
        tablas = []
        for t in sopa.find_all("table"):
            filas = []
            for tr in t.find_all("tr"):
                celdas = [td.get_text(" ", strip=True)
                          for td in tr.find_all(["td", "th"])]
                if celdas:
                    filas.append(celdas)
            if filas:
                tablas.append(filas)
        return tablas

    def horarios_txt(self) -> str:
        """Convierte la página de horarios al formato txt (tabs) que ya parsea
        la app: Grupo, Asignatura, Profesor, Edificio, Salón, Lun..Vie."""
        html = self._get(RUTA_HORARIOS)
        lineas = []
        for tabla in self._tablas(html):
            for fila in tabla:
                if len(fila) >= 7:
                    lineas.append("\t".join(fila))
        return "\n".join(lineas)

    def equivalencias_txt(self) -> str:
        html = self._get(RUTA_EQUIVALENCIAS)
        lineas = []
        for tabla in self._tablas(html):
            for fila in tabla:
                lineas.append("\t".join(fila))
        return "\n".join(lineas)

    def kardex_cursadas(self) -> list[str]:
        """Materias con calificación aprobatoria en el kardex."""
        html = self._get(RUTA_KARDEX)
        cursadas = []
        for tabla in self._tablas(html):
            for fila in tabla:
                if len(fila) < 3:
                    continue
                nombre = max(fila, key=len)
                nota = None
                for celda in fila:
                    c = celda.replace(",", ".").strip()
                    try:
                        nota = float(c)
                    except ValueError:
                        continue
                if nota is not None and nota >= 6 and len(nombre) > 5:
                    cursadas.append(nombre)
        return cursadas

    def mapa_txt(self) -> str:
        return self._get(RUTA_MAPA)
