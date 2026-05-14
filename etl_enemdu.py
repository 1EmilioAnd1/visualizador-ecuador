"""
ETL - ENEMDU Ecuador
Fuente: INEC - Encuesta Nacional de Empleo, Desempleo y Subempleo
Transformacion de archivos CSV a modelo relacional en SQLite

Tablas resultantes:
  dim_tiempo          - dimension de periodos trimestrales
  dim_indicador       - dimension de indicadores unicos
  dim_desagregacion   - dimension de categorias de desagregacion (sexo, edad, etnia, etc.)
  hechos_tasas        - tasas por trimestre y desagregacion (archivo 2)
  hechos_poblaciones  - poblaciones por trimestre y desagregacion (archivo 1)
  hechos_sectorizacion - formal vs informal por trimestre (archivo 4)
  hechos_caracterizacion - porcentajes de caracterizacion por tipo de empleo (archivos 3_x)
"""

import pandas as pd
import sqlite3
import re
import os

# ── Rutas ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data_enemdu")
DB_PATH    = os.path.join(BASE_DIR, "enemdu_ecuador.db")

# Si se corre desde Google Colab apuntando a los CSV subidos, cambiar DATA_DIR:
# DATA_DIR = "/content/"

ARCHIVOS = {
    "poblaciones"    : "1__Poblaciones.csv",
    "tasas"          : "2__Tasas.csv",
    "emp_adecuado"   : "3_2_Caracterización_Adec_pleno.csv",
    "subempleo"      : "3_3_Caracterización_Subempleo.csv",
    "otro_no_pleno"  : "3_4_Caracterización_Ot__no_ple.csv",
    "desempleo_caract": "3_5_Caracterización_Desempleo.csv",
    "sectorizacion"  : "4__Sectorización_del_Empleo.csv",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def leer_csv(nombre_archivo):
    """Lee CSV con separador ; y encoding latin1."""
    ruta = os.path.join(DATA_DIR, nombre_archivo)
    return pd.read_csv(ruta, sep=";", encoding="latin1", header=None, dtype=str)


def limpiar_valor(v):
    """Convierte '29,1%' -> 29.1 | '12.050.049' -> 12050049 | '-' -> None."""
    if pd.isna(v) or str(v).strip() in ("", "-", "nan"):
        return None
    v = str(v).strip()
    # Porcentaje
    if v.endswith("%"):
        return float(v.replace("%", "").replace(",", ".").strip())
    # Numero con puntos de miles y coma decimal (1.234.567)
    v_clean = v.replace(".", "").replace(",", ".")
    try:
        return float(v_clean)
    except ValueError:
        return None


def parsear_trimestre(texto):
    """'IV - 2020' -> {'trimestre_label':'IV-2020', 'anio':2020, 'trimestre_num':4}"""
    texto = str(texto).strip()
    mapa  = {"I": 1, "II": 2, "III": 3, "IV": 4}
    m = re.match(r"(I{1,3}V?|IV)\s*[-–]\s*(\d{4})", texto)
    if not m:
        return None
    roman, anio = m.group(1).strip(), int(m.group(2))
    return {
        "trimestre_label": f"{roman}-{anio}",
        "anio"           : anio,
        "trimestre_num"  : mapa.get(roman, 0),
    }


def forward_fill_col(series):
    """Rellena NaN hacia adelante en una columna (para categorias de desagregacion)."""
    result, last = [], None
    for v in series:
        if pd.notna(v) and str(v).strip() not in ("", "nan"):
            last = str(v).strip()
        result.append(last)
    return result


# ── Parsear archivos de tasas / poblaciones (estructura wide con desagregaciones) ──

def parsear_wide(df_raw):
    """
    Convierte la estructura wide del INEC en formato largo:
    columnas: trimestre_label | desagregacion_tipo | desagregacion_valor | indicador | valor
    """
    # Fila 1 (indice 1): encabezados de desagregacion (Nacional, Area, Dominios, Sexo, Edad, Etnia)
    # Fila 2 (indice 2): subvalores (Total, Urbano, Rural, Quito, ...)
    # Desde fila 3: datos

    # Construir mapeo columna -> (tipo_desag, valor_desag)
    tipos = list(df_raw.iloc[1])   # Nacional, Area, Dominios...
    vals  = list(df_raw.iloc[2])   # Total, Urbano, Rural...

    col_map = {}
    tipo_actual = None
    for i, (t, v) in enumerate(zip(tipos, vals)):
        t = str(t).strip() if pd.notna(t) and str(t).strip() not in ("nan","") else None
        v = str(v).strip() if pd.notna(v) and str(v).strip() not in ("nan","") else None
        if t:
            tipo_actual = t
        col_map[i] = (tipo_actual, v)

    registros = []
    for _, row in df_raw.iloc[3:].iterrows():
        row = list(row)
        trimestre_raw = str(row[0]).strip() if pd.notna(row[0]) else None
        indicador     = str(row[1]).strip() if pd.notna(row[1]) and str(row[1]).strip() not in ("nan","") else None

        if not trimestre_raw or trimestre_raw in ("nan", "") or not indicador:
            continue
        t_info = parsear_trimestre(trimestre_raw)
        if not t_info:
            continue

        for i in range(2, len(row)):
            tipo_desag, val_desag = col_map.get(i, (None, None))
            if not val_desag:
                continue
            valor = limpiar_valor(row[i])
            registros.append({
                **t_info,
                "desagregacion_tipo" : tipo_desag,
                "desagregacion_valor": val_desag,
                "indicador"          : indicador,
                "valor"              : valor,
            })
    return pd.DataFrame(registros)


# ── Parsear archivos de caracterizacion (estructura con categorias en col 0 y 1) ──

def parsear_caracterizacion(df_raw, tipo_empleo):
    """
    Convierte archivos 3_x en formato largo:
    columnas: trimestre_label | tipo_empleo | categoria | subcategoria | valor_pct
    """
    # Fila 1: trimestres en columnas 2..n
    trimestres_raw = list(df_raw.iloc[1, 2:])

    registros = []
    cats  = forward_fill_col(df_raw.iloc[3:, 0].reset_index(drop=True))
    subcats = list(df_raw.iloc[3:, 1])

    for fila_i, (cat, subcat) in enumerate(zip(cats, subcats)):
        subcat = str(subcat).strip() if pd.notna(subcat) and str(subcat).strip() not in ("nan","") else None
        if not subcat:
            continue
        for col_i, t_raw in enumerate(trimestres_raw):
            t_info = parsear_trimestre(str(t_raw).strip())
            if not t_info:
                continue
            valor_raw = df_raw.iloc[fila_i + 3, col_i + 2]
            valor = limpiar_valor(valor_raw)
            registros.append({
                **t_info,
                "tipo_empleo": tipo_empleo,
                "categoria"  : str(cat).strip() if cat else None,
                "subcategoria": subcat,
                "valor_pct"  : valor,
            })
    return pd.DataFrame(registros)


# ── Parsear sectorizacion ──────────────────────────────────────────────────────

def parsear_sectorizacion(df_raw):
    """
    Convierte archivo 4 en formato largo:
    columnas: trimestre_label | ambito | sector | valor_pct
    """
    trimestres_raw = list(df_raw.iloc[1, 2:])

    registros = []
    ambitos  = forward_fill_col(df_raw.iloc[2:, 0].reset_index(drop=True))
    sectores = list(df_raw.iloc[2:, 1])

    for fila_i, (ambito, sector) in enumerate(zip(ambitos, sectores)):
        sector = str(sector).strip() if pd.notna(sector) and str(sector).strip() not in ("nan","") else None
        if not sector:
            continue
        for col_i, t_raw in enumerate(trimestres_raw):
            t_info = parsear_trimestre(str(t_raw).strip())
            if not t_info:
                continue
            valor_raw = df_raw.iloc[fila_i + 2, col_i + 2]
            valor = limpiar_valor(valor_raw)
            registros.append({
                **t_info,
                "ambito" : str(ambito).strip() if ambito else "Nacional",
                "sector" : sector,
                "valor_pct": valor,
            })
    return pd.DataFrame(registros)


# ── Construir dimensiones ──────────────────────────────────────────────────────

def construir_dimensiones(df_tasas, df_pob, df_caract, df_sect):
    # dim_tiempo
    todos_trimestres = pd.concat([
        df_tasas[["trimestre_label","anio","trimestre_num"]],
        df_pob  [["trimestre_label","anio","trimestre_num"]],
        df_caract[["trimestre_label","anio","trimestre_num"]],
        df_sect [["trimestre_label","anio","trimestre_num"]],
    ]).drop_duplicates().sort_values(["anio","trimestre_num"])
    todos_trimestres = todos_trimestres.reset_index(drop=True)
    todos_trimestres.insert(0, "id_tiempo", range(1, len(todos_trimestres)+1))

    # dim_indicador
    indicadores = pd.concat([
        df_tasas["indicador"],
        df_pob  ["indicador"],
    ]).drop_duplicates().dropna().sort_values().reset_index(drop=True)
    df_indicador = pd.DataFrame({
        "id_indicador": range(1, len(indicadores)+1),
        "indicador"   : indicadores,
    })

    # dim_desagregacion
    desag = pd.concat([
        df_tasas[["desagregacion_tipo","desagregacion_valor"]],
        df_pob  [["desagregacion_tipo","desagregacion_valor"]],
    ]).drop_duplicates().dropna(subset=["desagregacion_valor"]).sort_values(
        ["desagregacion_tipo","desagregacion_valor"]
    ).reset_index(drop=True)
    desag.insert(0, "id_desagregacion", range(1, len(desag)+1))

    return todos_trimestres, df_indicador, desag


# ── Main ETL ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("ETL ENEMDU Ecuador -> SQLite")
    print("=" * 55)

    # 1. Leer y parsear
    print("\n[1/5] Leyendo y parseando archivos CSV...")
    df_tasas_raw = leer_csv(ARCHIVOS["tasas"])
    df_pob_raw   = leer_csv(ARCHIVOS["poblaciones"])
    df_sect_raw  = leer_csv(ARCHIVOS["sectorizacion"])

    df_tasas = parsear_wide(df_tasas_raw)
    df_pob   = parsear_wide(df_pob_raw)
    df_sect  = parsear_sectorizacion(df_sect_raw)

    caract_frames = []
    for clave, nombre in [
        ("Empleo Adecuado/Pleno", ARCHIVOS["emp_adecuado"]),
        ("Subempleo",             ARCHIVOS["subempleo"]),
        ("Otro Empleo no Pleno",  ARCHIVOS["otro_no_pleno"]),
        ("Desempleo",             ARCHIVOS["desempleo_caract"]),
    ]:
        raw = leer_csv(nombre)
        caract_frames.append(parsear_caracterizacion(raw, clave))
    df_caract = pd.concat(caract_frames, ignore_index=True)

    print(f"   Tasas:          {len(df_tasas):>6} registros")
    print(f"   Poblaciones:    {len(df_pob):>6} registros")
    print(f"   Sectorizacion:  {len(df_sect):>6} registros")
    print(f"   Caracterizacion:{len(df_caract):>6} registros")

    # 2. Construir dimensiones
    print("\n[2/5] Construyendo dimensiones...")
    dim_tiempo, dim_indicador, dim_desag = construir_dimensiones(
        df_tasas, df_pob, df_caract, df_sect
    )
    print(f"   dim_tiempo:        {len(dim_tiempo)} periodos")
    print(f"   dim_indicador:     {len(dim_indicador)} indicadores")
    print(f"   dim_desagregacion: {len(dim_desag)} categorias")

    # 3. Enriquecer hechos con FK
    print("\n[3/5] Aplicando claves foraneas a tablas de hechos...")

    t_map  = dict(zip(dim_tiempo["trimestre_label"],  dim_tiempo["id_tiempo"]))
    i_map  = dict(zip(dim_indicador["indicador"],     dim_indicador["id_indicador"]))
    d_map  = {(r.desagregacion_tipo, r.desagregacion_valor): r.id_desagregacion
               for _, r in dim_desag.iterrows()}

    for df in [df_tasas, df_pob]:
        df["id_tiempo"]        = df["trimestre_label"].map(t_map)
        df["id_indicador"]     = df["indicador"].map(i_map)
        df["id_desagregacion"] = df.apply(
            lambda r: d_map.get((r["desagregacion_tipo"], r["desagregacion_valor"])), axis=1)

    df_sect["id_tiempo"]  = df_sect["trimestre_label"].map(t_map)
    df_caract["id_tiempo"] = df_caract["trimestre_label"].map(t_map)

    # Columnas finales para cada tabla de hechos
    hechos_tasas = df_tasas[["id_tiempo","id_indicador","id_desagregacion","valor"]].dropna()
    hechos_pob   = df_pob  [["id_tiempo","id_indicador","id_desagregacion","valor"]].dropna()
    hechos_sect  = df_sect [["id_tiempo","ambito","sector","valor_pct"]].dropna()
    hechos_car   = df_caract[["id_tiempo","tipo_empleo","categoria","subcategoria","valor_pct"]].dropna()

    # 4. Cargar en SQLite
    print(f"\n[4/5] Cargando en base de datos: {DB_PATH}")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)

    # Dimensiones
    dim_tiempo   .to_sql("dim_tiempo",         con, index=False, if_exists="replace")
    dim_indicador.to_sql("dim_indicador",      con, index=False, if_exists="replace")
    dim_desag    .to_sql("dim_desagregacion",  con, index=False, if_exists="replace")

    # Hechos
    hechos_tasas.to_sql("hechos_tasas",          con, index=False, if_exists="replace")
    hechos_pob  .to_sql("hechos_poblaciones",    con, index=False, if_exists="replace")
    hechos_sect .to_sql("hechos_sectorizacion",  con, index=False, if_exists="replace")
    hechos_car  .to_sql("hechos_caracterizacion",con, index=False, if_exists="replace")

    # Claves primarias y foraneas (DDL explicito para evidenciar normalizacion)
    con.executescript("""
        CREATE INDEX IF NOT EXISTS idx_ht_tiempo ON hechos_tasas(id_tiempo);
        CREATE INDEX IF NOT EXISTS idx_ht_indic  ON hechos_tasas(id_indicador);
        CREATE INDEX IF NOT EXISTS idx_hp_tiempo ON hechos_poblaciones(id_tiempo);
        CREATE INDEX IF NOT EXISTS idx_hs_tiempo ON hechos_sectorizacion(id_tiempo);
        CREATE INDEX IF NOT EXISTS idx_hc_tiempo ON hechos_caracterizacion(id_tiempo);
    """)
    con.commit()

    # 5. Verificacion
    print("\n[5/5] Verificacion del modelo relacional:")
    print("-" * 45)
    tablas = [
        "dim_tiempo", "dim_indicador", "dim_desagregacion",
        "hechos_tasas", "hechos_poblaciones",
        "hechos_sectorizacion", "hechos_caracterizacion",
    ]
    for t in tablas:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"   {t:<30} {n:>6} filas")

    print("\n--- Consulta de prueba: tasa de desempleo nacional por trimestre ---")
    q = """
        SELECT t.trimestre_label, t.anio, t.trimestre_num, ht.valor AS tasa_desempleo_pct
        FROM   hechos_tasas ht
        JOIN   dim_tiempo       t  ON t.id_tiempo        = ht.id_tiempo
        JOIN   dim_indicador    i  ON i.id_indicador     = ht.id_indicador
        JOIN   dim_desagregacion d ON d.id_desagregacion = ht.id_desagregacion
        WHERE  i.indicador = 'Desempleo (%)'
        AND    d.desagregacion_valor = 'Total'
        ORDER  BY t.anio, t.trimestre_num
    """
    resultado = pd.read_sql(q, con)
    print(resultado.to_string(index=False))

    con.close()
    print(f"\nBase de datos generada: {DB_PATH}")
    print("ETL completado.")


if __name__ == "__main__":
    main()
