import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie"]
DIAS_LARGO = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"]
RE_HORA = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")
RE_CREDITO = re.compile(r"^\s*([A-ZÁÉÍÓÚÑÜ][^\t]{2,}?)[\t =:\-]+(\d{1,3}(?:[.,]\d{1,2})?)\s*$",
                        re.IGNORECASE)


def normalizar(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto.upper().strip())
    return " ".join("".join(c for c in nfd if not unicodedata.combining(c)).split())


def fmt_hora(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


@dataclass
class Sesion:
    dia: int      # 0=Lun .. 4=Vie
    inicio: int   # minutos desde medianoche
    fin: int


@dataclass
class MateriaPlan:
    periodo: str
    clave: str
    nombre: str
    tipo: str
    creditos: float
    teoria: float
    practica: float


@dataclass
class Equivalencia:
    clave_a: str      # clave del plan propio (N...)
    nombre_a: str
    clave_b: str      # clave en la otra carrera
    nombre_b: str
    doble: bool       # equivalencia en ambas direcciones


@dataclass
class Opcion:
    grupo: str
    materia: str
    profesor: str
    edificio: str
    salon: str
    sesiones: list[Sesion] = field(default_factory=list)
    propia: bool = False
    nota: str = ""

    @property
    def id(self) -> str:
        return f"{self.grupo}|{self.materia}"

    def resumen_horario(self) -> str:
        return ", ".join(
            f"{DIAS[s.dia]} {fmt_hora(s.inicio)}-{fmt_hora(s.fin)}"
            for s in sorted(self.sesiones, key=lambda s: (s.dia, s.inicio))
        )

    def horas_semana(self) -> float:
        return sum(s.fin - s.inicio for s in self.sesiones) / 60


def chocan(a: Opcion, b: Opcion) -> bool:
    return any(
        sa.dia == sb.dia and sa.inicio < sb.fin and sb.inicio < sa.fin
        for sa in a.sesiones
        for sb in b.sesiones
    )


def _leer_texto(ruta: Path) -> str:
    datos = ruta.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(enc)
        except UnicodeDecodeError:
            continue
    return datos.decode("latin-1", errors="replace")


def _a_numero(campo: str) -> float | None:
    try:
        return float(campo.replace(",", "."))
    except ValueError:
        return None


RE_CLAVE = re.compile(r"^[A-Z]\d{3}$")


def parsear_plan_equiv(texto: str) -> tuple[list[MateriaPlan], list[Equivalencia], set[int]]:
    """Detecta las tablas pegadas del SAES al final del txt:
    - plan de estudios (header con 'Clave asignatura' y 'Creditos'): las
      columnas se ubican por el header, no por posición fija.
    - equivalencias (header 'Materia / Descripcion / Dirección / ...').
    Devuelve (plan, equivalencias, índices de líneas consumidas)."""
    plan: list[MateriaPlan] = []
    equivalencias: list[Equivalencia] = []
    consumidas: set[int] = set()
    modo = None
    cols: dict[str, int] = {}

    def col(campos: list[str], nombre: str, defecto: str = "") -> str:
        i = cols.get(nombre, -1)
        return campos[i].strip() if 0 <= i < len(campos) else defecto

    for num, linea in enumerate(texto.splitlines()):
        limpia = linea.strip()
        baja = normalizar(limpia)
        campos = linea.split("\t")

        if "CLAVE ASIGNATURA" in baja and "CREDIT" in baja:
            modo = "plan"
            cols = {}
            for i, c in enumerate(campos):
                cn = normalizar(c)
                if "PERIODO" in cn:
                    cols["periodo"] = i
                elif "CLAVE" in cn:
                    cols["clave"] = i
                elif "NOMBRE" in cn:
                    cols["nombre"] = i
                elif "TIPO" in cn:
                    cols["tipo"] = i
                elif "CREDIT" in cn:
                    cols["creditos"] = i
                elif "TEORIA" in cn:
                    cols["teoria"] = i
                elif "PRACT" in cn:
                    cols["practica"] = i
            consumidas.add(num)
            continue
        if baja.startswith("MATERIA") and "DESCRIPCION" in baja:
            modo = "equiv"
            consumidas.add(num)
            continue
        if not limpia or set(limpia) <= {"-"}:
            modo = None
            continue

        if modo == "plan":
            clave = col(campos, "clave")
            valor = _a_numero(col(campos, "creditos"))
            if RE_CLAVE.match(clave) and valor is not None:
                plan.append(MateriaPlan(
                    periodo=col(campos, "periodo"), clave=clave,
                    nombre=col(campos, "nombre"), tipo=col(campos, "tipo"),
                    creditos=valor,
                    teoria=_a_numero(col(campos, "teoria")) or 0,
                    practica=_a_numero(col(campos, "practica")) or 0))
                consumidas.add(num)
            else:
                modo = None
        elif modo == "equiv":
            if len(campos) >= 5 and RE_CLAVE.match(campos[0].strip()) \
                    and RE_CLAVE.match(campos[3].strip()):
                direccion = campos[2].strip()
                doble = len(re.findall(r"[?↔←→]", direccion)) >= 2 or "↔" in direccion
                equivalencias.append(Equivalencia(
                    clave_a=campos[0].strip(), nombre_a=campos[1].strip(),
                    clave_b=campos[3].strip(), nombre_b=campos[4].strip(),
                    doble=doble))
                consumidas.add(num)
            else:
                modo = None
    return plan, equivalencias, consumidas


def parsear_creditos(texto: str, ignorar: set[int] | None = None) -> dict[str, float]:
    """Créditos en formato libre ('MATERIA<tab>7.5', con clave, '=', etc.)
    para líneas que no son parte de las tablas del plan ni de grupos.
    Devuelve nombre normalizado -> créditos."""
    ignorar = ignorar or set()
    creditos: dict[str, float] = {}
    for num, linea in enumerate(texto.splitlines()):
        if num in ignorar or RE_HORA.search(linea):
            continue
        campos = [c.strip() for c in re.split(r"\t+|\s{2,}", linea.strip()) if c.strip()]
        if len(campos) < 2:
            m = RE_CREDITO.match(linea.strip())
            if not m:
                continue
            campos = [m.group(1), m.group(2)]
        if len(campos) > 6:
            continue
        numeros = [n for n in (_a_numero(c) for c in campos) if n is not None]
        textos = [c for c in campos if _a_numero(c) is None]
        if not numeros or not textos:
            continue
        valor = numeros[-1]
        if not 0 < valor <= 120:
            continue
        nombre = normalizar(max(textos, key=len))
        if sum(c.isalpha() for c in nombre) < 4 or "CREDIT" in nombre \
                or nombre == "GRUPO":
            continue
        creditos[nombre] = valor
    return creditos


def emparejar_credito(materia: str, creditos_txt: dict[str, float]) -> float | None:
    """Busca los créditos de una materia: nombre exacto, luego contención
    (una dentro de la otra), luego parecido difuso."""
    if not creditos_txt:
        return None
    nombre = normalizar(materia)
    if nombre in creditos_txt:
        return creditos_txt[nombre]
    for clave, valor in creditos_txt.items():
        if len(clave) >= 5 and (clave in nombre or nombre in clave):
            return valor
    cercanos = difflib.get_close_matches(nombre, list(creditos_txt), n=1, cutoff=0.75)
    return creditos_txt[cercanos[0]] if cercanos else None


def parsear(ruta: str | Path) -> tuple[list[Opcion], dict[str, float],
                                       list[MateriaPlan], list[Equivalencia]]:
    """Parsea el txt copiado del SAES: grupos con horarios, y al final las
    tablas opcionales de plan de estudios (créditos) y equivalencias.
    Devuelve (opciones, créditos por nombre normalizado, plan, equivalencias)."""
    texto = _leer_texto(Path(ruta))
    opciones: dict[str, Opcion] = {}
    for linea in texto.splitlines():
        campos = linea.split("\t")
        if len(campos) < 10:
            continue
        grupo = campos[0].strip()
        if not grupo or grupo.lower() == "grupo" or set(grupo) <= {"-"}:
            continue
        op = Opcion(
            grupo=grupo,
            materia=campos[1].strip(),
            profesor=campos[2].strip(),
            edificio=campos[3].strip(),
            salon=campos[4].strip(),
        )
        for dia, celda in enumerate(campos[5:10]):
            for m in RE_HORA.finditer(celda):
                ini = int(m.group(1)) * 60 + int(m.group(2))
                fin = int(m.group(3)) * 60 + int(m.group(4))
                if fin > ini:
                    op.sesiones.append(Sesion(dia, ini, fin))
        if op.sesiones and op.id not in opciones:
            opciones[op.id] = op

    plan, equivalencias, consumidas = parsear_plan_equiv(texto)
    creditos = parsear_creditos(texto, ignorar=consumidas)
    creditos.update({normalizar(p.nombre): p.creditos for p in plan})
    return list(opciones.values()), creditos, plan, equivalencias
