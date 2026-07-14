"""Scraper del SAES (beta): login con captcha y descarga de horarios.

El SAES es ASP.NET WebForms: cada página exige __VIEWSTATE/__EVENTVALIDATION,
por eso todo va sobre una misma sesión de requests. Las rutas de descarga se
afinan contra el SAES real de cada escuela.
"""
import requests
from bs4 import BeautifulSoup

ESCUELAS = {
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
    "ENCB": "https://www.saes.encb.ipn.mx",
    "ESM": "https://www.saes.esm.ipn.mx",
    "ESEO": "https://www.saes.eseo.ipn.mx",
    "ESE (Economía)": "https://www.saes.ese.ipn.mx",
    "EST": "https://www.saes.est.ipn.mx",
    "EST (Turismo)": "https://www.saes.est.ipn.mx",
    "UPIBI": "https://www.saes.upibi.ipn.mx",
    "UPIITA": "https://www.saes.upiita.ipn.mx",
    "CICS Sto. Tomás": "https://www.saes.cicsst.ipn.mx",
    "CICS Milpa Alta": "https://www.saes.cicsma.ipn.mx",
}


class SesionSaes:
    def __init__(self, escuela: str):
        self.base = ESCUELAS[escuela]
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0"
        self._campos: dict[str, str] = {}

    def _forma(self, html: str) -> dict[str, str]:
        sopa = BeautifulSoup(html, "html.parser")
        return {i["name"]: i.get("value", "")
                for i in sopa.find_all("input", {"type": "hidden"}) if i.get("name")}

    def captcha(self) -> bytes:
        """Abre la página de login y devuelve la imagen del captcha."""
        r = self.s.get(f"{self.base}/", timeout=20, verify=False)
        self._campos = self._forma(r.text)
        sopa = BeautifulSoup(r.text, "html.parser")
        img = sopa.find("img", src=lambda s: s and "captcha" in s.lower())
        if img is None:
            raise RuntimeError("No encontré el captcha en la página de login")
        url = img["src"]
        if not url.startswith("http"):
            url = f"{self.base}/{url.lstrip('/')}"
        return self.s.get(url, timeout=20, verify=False).content

    def login(self, boleta: str, contrasena: str, captcha: str) -> bool:
        datos = dict(self._campos)
        datos.update({
            "ctl00$leftColumn$LoginUser$UserName": boleta,
            "ctl00$leftColumn$LoginUser$Password": contrasena,
            "ctl00$leftColumn$LoginUser$CampoDinamico": captcha,
            "ctl00$leftColumn$LoginUser$LoginButton": "Entrar",
        })
        r = self.s.post(f"{self.base}/", data=datos, timeout=20, verify=False)
        return "Bienvenido" in r.text or "alumnos" in r.url.lower()

    # --- pendientes de afinar contra el SAES real (estructura por escuela) ---
    def carrera_alumno(self) -> str:
        raise NotImplementedError("Se afina con una sesión real")

    def descargar_horarios(self) -> str:
        """Devuelve el contenido tipo txt (tabs) de la ocupabilidad de horarios."""
        raise NotImplementedError("Se afina con una sesión real")
