# Horario SAES

Armador de horarios para estudiantes del IPN. Carga los grupos del SAES y arma
tu horario ideal: ramas alternativas, choques automáticos, créditos, checklist
y export a PDF/PNG.

## Instalar

- **Sin Python**: descarga el ejecutable de tu sistema en
  [Releases](https://github.com/leostriker111/horario-saes/releases).
- **Con Python 3.10+**: `pip install git+https://github.com/leostriker111/horario-saes`
  y corre `horario`.

## Uso

1. Copia del SAES los horarios (y opcionalmente plan de créditos y
   equivalencias) a un `.txt` — texto plano con tabuladores.
2. **📂 Cargar TXT** y arma tu horario picando grupos en la lista.

Funciones: filtros (texto, profe favorito ★, turno, días, horas, check,
cursadas), ramas con bifurcación y árbol, candados 🔒 + generador 🎲 sin
repetir, bloques propios con reloj, créditos con equivalencias entre carreras,
checklist ✅ y cursadas 🎓, export 📤 a PDF/PNG/JPG/SVG.

Tu sesión se guarda sola en `~/.horario_saes/`.

## Contribuir

Trabaja sobre la rama `dev` y abre un Pull Request a `master`.

## Licencia

[GPL-3.0](LICENSE): úsalo, estúdialo y modifícalo libremente — las
modificaciones distribuidas deben seguir siendo software libre.
