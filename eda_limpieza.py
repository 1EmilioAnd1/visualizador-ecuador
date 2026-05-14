"""
EDA Y LIMPIEZA FORMAL — ENEMDU Ecuador
PUCE · C. Datos, Estudio de Casos · Emilio Andrade

Este script documenta el proceso de análisis exploratorio y depuración
de los archivos CSV de la ENEMDU antes de cargarlos al modelo relacional.

Pasos:
  1. Inspección general de cada archivo
  2. Detección de problemas: nulos, guiones, duplicados, rangos
  3. Limpieza y transformación explícita
  4. Verificación post-limpieza
  5. Comparación con línea base
"""

import pandas as pd
import numpy as np
import sqlite3
import os

# ── Rutas ──────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_enemdu")
DB_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enemdu_ecuador.db")

ARCHIVOS = {
    "poblaciones"    : "1__Poblaciones.csv",
    "tasas"          : "2__Tasas.csv",
    "emp_adecuado"   : "3_2_Caracterización_Adec_pleno.csv",
    "subempleo"      : "3_3_Caracterización_Subempleo.csv",
    "otro_no_pleno"  : "3_4_Caracterización_Ot__no_ple.csv",
    "desempleo_caract": "3_5_Caracterización_Desempleo.csv",
    "sectorizacion"  : "4__Sectorización_del_Empleo.csv",
}

SEP = "─" * 55

# ── Helper: leer CSV raw ───────────────────────────────────────────────────────
def leer_raw(nombre):
    return pd.read_csv(
        os.path.join(DATA_DIR, nombre),
        sep=";", encoding="latin1", header=None, dtype=str
    )

# ══════════════════════════════════════════════════════════
# PASO 1: INSPECCIÓN GENERAL
# ══════════════════════════════════════════════════════════
def paso1_inspeccion():
    print(f"\n{'═'*55}")
    print("PASO 1 · INSPECCIÓN GENERAL DE ARCHIVOS RAW")
    print(f"{'═'*55}")

    reporte = []
    for clave, archivo in ARCHIVOS.items():
        df = leer_raw(archivo)
        total_celdas   = df.shape[0] * df.shape[1]
        nulos          = df.isnull().sum().sum()
        filas_vacias   = int(df.isnull().all(axis=1).sum())
        guiones        = int((df == "-").sum().sum())
        pct_nulos      = round(nulos / total_celdas * 100, 1)

        reporte.append({
            "archivo"      : clave,
            "filas"        : df.shape[0],
            "columnas"     : df.shape[1],
            "celdas_nulas" : nulos,
            "pct_nulos"    : pct_nulos,
            "filas_vacias" : filas_vacias,
            "guiones"      : guiones,
        })
        print(f"\n  {clave.upper()} ({archivo})")
        print(f"    Dimensiones    : {df.shape[0]} filas x {df.shape[1]} columnas")
        print(f"    Celdas nulas   : {nulos} / {total_celdas} ({pct_nulos}%)")
        print(f"    Filas vacías   : {filas_vacias}")
        print(f"    Celdas con '-' : {guiones}  (representan dato no disponible)")

    return pd.DataFrame(reporte)


# ══════════════════════════════════════════════════════════
# PASO 2: DETECCIÓN DE PROBLEMAS
# ══════════════════════════════════════════════════════════
def paso2_problemas():
    print(f"\n{'═'*55}")
    print("PASO 2 · DETECCIÓN DE PROBLEMAS")
    print(f"{'═'*55}")

    problemas = []

    for clave, archivo in ARCHIVOS.items():
        df = leer_raw(archivo)
        prob = {"archivo": clave, "problemas": []}

        # P1: Filas completamente vacías
        n_vacias = int(df.isnull().all(axis=1).sum())
        if n_vacias > 0:
            prob["problemas"].append(f"P1: {n_vacias} fila(s) completamente vacía(s)")

        # P2: Guiones como valor (dato no disponible, no es nulo real)
        n_guiones = int((df == "-").sum().sum())
        if n_guiones > 0:
            prob["problemas"].append(f"P2: {n_guiones} celda(s) con '-' (dato no disponible)")

        # P3: Inconsistencia de formato numérico
        # Verificar si hay mezcla de ',' y '.' en los valores
        vals_numericos = []
        for col in df.columns[2:]:
            sample = df[col].dropna().tolist()
            vals_numericos += [v for v in sample if isinstance(v, str) and v not in ("-", "")]
        tiene_coma  = any("," in v for v in vals_numericos)
        tiene_punto = any("." in v for v in vals_numericos[:20])
        if tiene_coma:
            prob["problemas"].append("P3: Decimales con coma (ej. '29,1') — requieren conversión")
        if tiene_punto and clave in ("poblaciones",):
            prob["problemas"].append("P3b: Miles con punto (ej. '12.050.049') — requieren limpieza")

        # P4: Signos de porcentaje
        tiene_pct = any("%" in v for v in vals_numericos[:30])
        if tiene_pct:
            prob["problemas"].append("P4: Valores con '%' — requieren stripping")

        # P5: Encabezados dobles (estructura INEC)
        prob["problemas"].append("P5: Encabezados dobles del INEC — requieren parseo manual")

        problemas.append(prob)
        print(f"\n  {clave.upper()}")
        for p in prob["problemas"]:
            print(f"    ⚠  {p}")

    return problemas


# ══════════════════════════════════════════════════════════
# PASO 3: LIMPIEZA EXPLÍCITA
# ══════════════════════════════════════════════════════════
def limpiar_valor(v):
    """
    Reglas de limpieza aplicadas:
      R1: Nulos y cadenas vacías          -> None
      R2: Guión '-'                       -> None (dato no disponible)
      R3: Porcentaje '29,1%' o '29.1%'   -> float 29.1
      R4: Miles con punto '12.050.049'    -> float 12050049.0
      R5: Coma decimal '29,1'             -> float 29.1
    """
    if pd.isna(v):                          return None   # R1
    v = str(v).strip()
    if v in ("", "nan", "-"):               return None   # R1 + R2
    if v.endswith("%"):                                    # R3
        return float(v[:-1].replace(",", ".").strip())
    # R4: número con puntos de miles Y posible coma decimal
    # detectar si hay más de un punto -> miles
    if v.count(".") > 1:
        v = v.replace(".", "").replace(",", ".")
    else:
        v = v.replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def paso3_limpieza():
    print(f"\n{'═'*55}")
    print("PASO 3 · APLICACIÓN DE REGLAS DE LIMPIEZA")
    print(f"{'═'*55}")

    print("""
  Reglas aplicadas a todos los archivos:
    R1: Celdas vacías o 'nan'       → NULL
    R2: Guiones '-'                 → NULL (dato no disponible)
    R3: '29,1%' o '29.1%'          → 29.1 (float)
    R4: '12.050.049'                → 12050049.0 (miles con punto)
    R5: '29,1'                      → 29.1 (coma decimal)
    R6: Filas completamente vacías  → eliminadas
    R7: Columna 23 (trailing NaN)   → eliminada si está vacía
    """)

    # Verificación con muestra
    casos_prueba = [
        ("29,1%",       29.1),
        ("12.050.049",  12050049.0),
        ("61,7",        61.7),
        ("-",           None),
        ("",            None),
        ("3,8%",        3.8),
        ("100,0",       100.0),
        ("0,0%",        0.0),
    ]

    print("  Verificación de función limpiar_valor():")
    print(f"  {'Input':<20} {'Esperado':<15} {'Obtenido':<15} {'OK'}")
    print(f"  {'-'*60}")
    todos_ok = True
    for entrada, esperado in casos_prueba:
        obtenido = limpiar_valor(entrada)
        ok = obtenido == esperado
        if not ok: todos_ok = False
        estado = "✓" if ok else "✗ ERROR"
        print(f"  {repr(entrada):<20} {str(esperado):<15} {str(obtenido):<15} {estado}")

    print(f"\n  Resultado: {'Todas las reglas OK ✓' if todos_ok else 'HAY ERRORES — revisar'}")
    return todos_ok


# ══════════════════════════════════════════════════════════
# PASO 4: VERIFICACIÓN POST-LIMPIEZA SOBRE LA BD
# ══════════════════════════════════════════════════════════
def paso4_verificacion():
    print(f"\n{'═'*55}")
    print("PASO 4 · VERIFICACIÓN POST-LIMPIEZA SOBRE SQLITE")
    print(f"{'═'*55}")

    con = sqlite3.connect(DB_PATH)

    # 4.1 Conteo y nulos
    print("\n  4.1 Conteo de filas y nulos por tabla de hechos")
    tablas = {
        "hechos_tasas":           "valor",
        "hechos_poblaciones":     "valor",
        "hechos_sectorizacion":   "valor_pct",
        "hechos_caracterizacion": "valor_pct",
    }
    for tabla, col in tablas.items():
        total = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        nulos = con.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {col} IS NULL").fetchone()[0]
        pct   = round(nulos/total*100, 2) if total else 0
        print(f"    {tabla:<35} {total:>6} filas | nulos: {nulos} ({pct}%)")

    # 4.2 Rango lógico tasas [0, 100]
    print("\n  4.2 Validación de rango lógico [0, 100] en hechos_tasas")
    fuera = con.execute("SELECT COUNT(*) FROM hechos_tasas WHERE valor < 0 OR valor > 100").fetchone()[0]
    print(f"    Valores fuera de rango: {fuera}  {'✓ OK' if fuera==0 else '✗ REVISAR'}")

    # 4.3 Duplicados
    print("\n  4.3 Duplicados en hechos_tasas")
    dups = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT id_tiempo, id_indicador, id_desagregacion, COUNT(*) as n
            FROM hechos_tasas
            GROUP BY id_tiempo, id_indicador, id_desagregacion
            HAVING n > 1
        )
    """).fetchone()[0]
    print(f"    Combinaciones duplicadas: {dups}  {'✓ OK' if dups==0 else '✗ REVISAR'}")

    # 4.4 Consistencia temporal
    print("\n  4.4 Cobertura temporal")
    periodos = con.execute("SELECT MIN(trimestre_label), MAX(trimestre_label), COUNT(*) FROM dim_tiempo").fetchone()
    print(f"    Primer periodo : {periodos[0]}")
    print(f"    Último periodo : {periodos[1]}")
    print(f"    Total periodos : {periodos[2]}")

    # 4.5 Estadísticas descriptivas tasas nacionales
    print("\n  4.5 Estadísticas descriptivas — tasas nacionales (Total)")
    q = """
        SELECT i.indicador,
               ROUND(MIN(ht.valor),1)  AS min,
               ROUND(MAX(ht.valor),1)  AS max,
               ROUND(AVG(ht.valor),2)  AS promedio,
               COUNT(*)                AS n
        FROM   hechos_tasas ht
        JOIN   dim_indicador    i ON i.id_indicador     = ht.id_indicador
        JOIN   dim_desagregacion d ON d.id_desagregacion = ht.id_desagregacion
        WHERE  i.indicador LIKE '%(%)' AND d.desagregacion_valor = 'Total'
        GROUP  BY i.indicador
        ORDER  BY promedio DESC
    """
    print(pd.read_sql(q, con).to_string(index=False))

    con.close()


# ══════════════════════════════════════════════════════════
# PASO 5: COMPARACIÓN CON LÍNEA BASE
# ══════════════════════════════════════════════════════════
def paso5_comparacion():
    print(f"\n{'═'*55}")
    print("PASO 5 · COMPARACIÓN CON LÍNEA BASE")
    print(f"{'═'*55}")

    LINEA_BASE = {
        ("Desempleo (%)",            "Total")              : 3.4,
        ("Desempleo (%)",            "Hombre")             : 2.6,
        ("Desempleo (%)",            "Mujer")              : 4.6,
        ("Empleo Adecuado/Pleno (%)", "Total")             : 35.7,
        ("Subempleo (%)",            "Total")              : 18.4,
        ("Desempleo (%)",            "Urbana")             : 4.2,
        ("Desempleo (%)",            "Rural")              : 1.7,
        ("Desempleo (%)",            "Quito")              : 8.9,
        ("Desempleo (%)",            "Guayaquil")          : 2.3,
        ("Desempleo (%)",            "Entre 15 y 24 años") : 8.5,
    }

    con = sqlite3.connect(DB_PATH)

    print(f"\n  {'Indicador':<40} {'Base':>6}  {'Actual':>7}  {'Δ':>6}  Estado")
    print(f"  {'-'*70}")

    cambios = 0
    for (ind, desag), base in LINEA_BASE.items():
        val = con.execute("""
            SELECT ht.valor FROM hechos_tasas ht
            JOIN dim_tiempo t       ON t.id_tiempo        = ht.id_tiempo
            JOIN dim_indicador i    ON i.id_indicador     = ht.id_indicador
            JOIN dim_desagregacion d ON d.id_desagregacion = ht.id_desagregacion
            WHERE t.trimestre_label='I-2026' AND i.indicador=? AND d.desagregacion_valor=?
        """, (ind, desag)).fetchone()

        actual = val[0] if val else None
        delta  = round(actual - base, 2) if actual is not None else None
        estado = "✓ Sin cambio" if delta == 0.0 else (f"⚠ Cambió {delta:+.2f}" if delta else "✗ No encontrado")
        if delta != 0.0: cambios += 1

        nombre = f"{ind[:25]} / {desag}"
        print(f"  {nombre:<40} {base:>6.1f}  {str(actual):>7}  {str(delta) if delta is not None else 'N/A':>6}  {estado}")

    # Sector informal
    inf = con.execute("""
        SELECT hs.valor_pct FROM hechos_sectorizacion hs
        JOIN dim_tiempo t ON t.id_tiempo=hs.id_tiempo
        WHERE t.trimestre_label='I-2026' AND hs.sector='Sector Informal' AND hs.ambito='Nacional'
    """).fetchone()
    actual_inf = inf[0] if inf else None
    delta_inf  = round(actual_inf - 53.5, 2) if actual_inf else None
    print(f"  {'Sector Informal / Nacional':<40} {53.5:>6.1f}  {str(actual_inf):>7}  {str(delta_inf):>6}  {'✓ Sin cambio' if delta_inf==0 else '⚠'}")

    con.close()

    print(f"\n  Resultado: {cambios} cifra(s) cambiaron respecto a la línea base.")
    if cambios == 0:
        print("  ✓ Los datos del visualizador son consistentes y no requieren actualización.")
    else:
        print("  ⚠ Revisar los cambios antes de actualizar el visualizador.")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("EDA Y LIMPIEZA FORMAL — ENEMDU Ecuador")
    print("PUCE · C. Datos, Estudio de Casos")
    print("=" * 55)

    paso1_inspeccion()
    paso2_problemas()
    reglas_ok = paso3_limpieza()
    paso4_verificacion()
    paso5_comparacion()

    print(f"\n{'='*55}")
    print("EDA completado.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
