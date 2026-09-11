from google.cloud import bigquery
import pandas as pd

# --- CONFIGURACIÓN ---
PROJECT_ID_BQ = "peya-chile"  # Reemplaza con el proyecto objetivo
QUERY_INPUT = """
SELECT country_id, COUNT(*) as orders_count
FROM `peya-bi-tools-pro.il_core.fact_orders` as country
WHERE registered_date = "2026-04-01"
GROUP BY 1
"""

try:
    print("Inicializando cliente de BigQuery con credenciales impersonadas...")
    client = bigquery.Client(project=PROJECT_ID_BQ)

    print("Ejecutando consulta SQL en BigQuery...")
    df = client.query(QUERY_INPUT).to_dataframe()

    if df.empty:
        print("La consulta no devolvió registros.")
    else:
        print("\n--- RESULTADOS (Primeras filas) ---")
        print(df.head())
except Exception as e:
    print(f"Error al ejecutar la query: {e}")

