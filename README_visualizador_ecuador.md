# Visualizador Ecuador - Mercado Laboral ENEMDU

## Información general

**Estudiante:** Emilio Andrade  
**Nivel:** Sexto nivel  
**Materia:** C. Datos - Estudio de Casos  
**Curso:** H - P3283-TEÓRICO-PRACTICO-N0228-05-N06  
**Docente:** Kevin Ricardo Rojas Satián  
**Correo docente:** krrojas@puce.edu.ec  
**Fuente de datos:** ENEMDU - INEC  
**Periodo analizado:** IV-2020 a I-2026  

## Descripción del proyecto

Este repositorio contiene un proyecto académico de análisis, limpieza, transformación y visualización de datos sobre el mercado laboral ecuatoriano. El trabajo utiliza información de la Encuesta Nacional de Empleo, Desempleo y Subempleo (ENEMDU), publicada por el Instituto Nacional de Estadística y Censos (INEC).

El objetivo del proyecto es presentar, de manera visual y comprensible, la evolución de indicadores laborales relevantes para Ecuador, tales como desempleo, empleo adecuado, subempleo, informalidad, brechas de género, diferencias territoriales, comportamiento por ciudades principales y grupos de edad.

## Enlaces principales

- **Repositorio de GitHub:** <https://github.com/1EmilioAnd1/visualizador-ecuador>
- **Archivo principal del visualizador:** `index.html`

> Nota: si se activa GitHub Pages desde la configuración del repositorio, el visualizador puede publicarse en línea usando la rama `main` y la carpeta raíz `/root`.

## Archivos incluidos

| Archivo | Descripción |
|---|---|
| `index.html` | Visualizador web principal del proyecto. Presenta indicadores, secciones narrativas y gráficos sobre el mercado laboral ecuatoriano. |
| `etl_enemdu.py` | Script de transformación de datos ENEMDU hacia un modelo relacional en SQLite. |
| `eda_limpieza.py` | Script de análisis exploratorio, limpieza, detección de problemas y verificación de los datos antes del proceso ETL. |
| `2026_I_trimestre_Tabulados_Mercado_Laboral_CSV (2).zip` | Archivo comprimido con los datos base utilizados para el análisis. |
| `README.md` | Documento explicativo del repositorio, metodología, instrucciones de uso y estructura del proyecto. |

## Metodología aplicada

El desarrollo del proyecto siguió una secuencia ordenada de trabajo:

1. Revisión de los archivos originales de la ENEMDU.
2. Inspección general de la estructura de los datos.
3. Detección de valores nulos, guiones, duplicados y formatos inconsistentes.
4. Limpieza de porcentajes, números con separadores de miles y valores no válidos.
5. Transformación de los datos desde formato ancho hacia formato largo.
6. Construcción de dimensiones y tablas de hechos.
7. Generación de una base relacional en SQLite.
8. Validación de indicadores principales.
9. Desarrollo del visualizador web en HTML.
10. Interpretación narrativa de los resultados principales.

## Indicadores analizados

El visualizador presenta información relacionada con:

- Desempleo nacional.
- Empleo adecuado o pleno.
- Subempleo.
- Sector formal e informal.
- Desempleo por sexo.
- Desempleo urbano y rural.
- Desempleo por ciudades principales.
- Desempleo por grupos de edad.
- Brechas territoriales y socioeconómicas.

## Requisitos para ejecutar el proyecto

Para ejecutar los scripts de Python se recomienda tener instalado:

- Python 3.10 o superior.
- `pandas`.
- `sqlite3`, incluido por defecto en Python.

Instalación básica de dependencias:

```bash
pip install pandas
```

## Instrucciones de uso

Clonar el repositorio:

```bash
git clone https://github.com/1EmilioAnd1/visualizador-ecuador.git
cd visualizador-ecuador
```

Descomprimir el archivo de datos dentro de una carpeta llamada `data_enemdu`:

```bash
mkdir data_enemdu
```

Luego colocar dentro de esa carpeta los archivos CSV extraídos del ZIP de datos.

Ejecutar el análisis exploratorio y limpieza:

```bash
python eda_limpieza.py
```

Ejecutar el proceso ETL:

```bash
python etl_enemdu.py
```

Abrir el visualizador:

```bash
index.html
```

También se puede abrir el archivo `index.html` directamente desde el navegador.

## Resultados principales presentados en el visualizador

El visualizador resume que, para I-2026, el mercado laboral ecuatoriano presenta una tasa de desempleo nacional relativamente baja, pero conserva problemas estructurales importantes. Entre ellos se destacan la alta informalidad, el peso del subempleo, las brechas de género, las diferencias entre territorios urbanos y rurales, y la mayor vulnerabilidad laboral de los jóvenes.

## Conclusión

El proyecto permite observar que la recuperación del mercado laboral no debe evaluarse únicamente por la tasa de desempleo. Aunque el desempleo nacional se reduce en el periodo analizado, los indicadores de calidad del empleo muestran que gran parte de la población ocupada continúa enfrentando condiciones de informalidad, subempleo o baja estabilidad laboral. Por ello, el visualizador busca presentar los datos de forma clara, visual y narrativa para facilitar su interpretación académica.

## Autor

Emilio Andrade  
Pontificia Universidad Católica del Ecuador  
Ciencia de Datos  
Mayo de 2026
