import argparse
import sys
import pandas as pd
from google.cloud import bigquery
from config.config import Config
from src.logger import setup_logger
from src.bq_client import BigQueryExtractor

logger = setup_logger("TestBigQuery")

def test_bigquery_connection_and_query(days_lookback: int = 1, test_isolated_query: bool = False):
    logger.info("=" * 80)
    logger.info("PRUEBA AISLADA DE CONEXIÓN Y CONSULTA A BIGQUERY")
    logger.info("=" * 80)
    logger.info(f"Proyecto GCP: {Config.GCP_PROJECT_ID}")
    logger.info(f"País ID: {Config.GCP_COUNTRY_ID} (Chile / PY_CL)")
    logger.info(f"Días de lookback: {days_lookback}")
    logger.info("=" * 80)

    try:
        extractor = BigQueryExtractor()
        
        if test_isolated_query:
            # Query simple a dim_partner para aislar si el problema es el JOIN
            logger.info("--- Probando consulta básica a dim_partner (sin JOIN) ---")
            query = f"""
            SELECT 
                p.partner_id, 
                p.partner_name, 
                DATE(p.registered_date) AS registered_date, 
                p.partner_status, 
                p.main_cousine_category_name AS cuisine, 
                p.franchise.franchise_name AS franchise_name
            FROM 
                `{Config.GCP_PROJECT_ID}.il_core.dim_partner` p
            WHERE 
                p.country_id = {Config.GCP_COUNTRY_ID}
                AND DATE(p.registered_date) >= CURRENT_DATE() - {days_lookback}
                AND p.partner_status = "ON_LINE"
            ORDER BY 
                p.registered_date DESC
            LIMIT 10
            """
        else:
            # Query completa con JOIN a growth_vendors
            logger.info("--- Probando consulta completa (con LEFT JOIN a growth_vendors) ---")
            query = f"""
            SELECT 
                p.partner_id, 
                p.partner_name, 
                DATE(p.registered_date) AS registered_date, 
                p.partner_status, 
                p.main_cousine_category_name AS cuisine, 
                p.franchise.franchise_name AS franchise_name,
                v.vertical_type
            FROM 
                `{Config.GCP_PROJECT_ID}.il_core.dim_partner` p
            LEFT JOIN (
                SELECT 
                    vendor_code, 
                    vertical_type 
                FROM 
                    `fulfillment-dwh-production.curated_data_shared_vendor.growth_vendors`
                WHERE 
                    entity_id = "{Config.SEAMLESS_COUNTRY}"
            ) v 
                ON SAFE_CAST(v.vendor_code AS INT64) = p.partner_id 
            WHERE 
                p.country_id = {Config.GCP_COUNTRY_ID}
                AND DATE(p.registered_date) >= CURRENT_DATE() - {days_lookback}
                AND p.partner_status = "ON_LINE"
            ORDER BY 
                p.registered_date DESC
            """

        print(f"\nSQL ejecutándose:\n{query}\n")
        
        logger.info("Enviando query a BigQuery...")
        query_job = extractor.client.query(query)
        df = query_job.to_dataframe()

        print("\n" + "=" * 80)
        print(f"¡ÉXITO! REGISTROS OBTENIDOS DE BIGQUERY: {len(df)}")
        print("=" * 80)
        
        if df.empty:
            logger.warning(
                f"La consulta no retornó registros para los últimos {days_lookback} días.\n"
                f"Prueba ejecutando con más días de lookback: python test_bigquery.py --days 7"
            )
        else:
            print("\nPrimeros registros obtenidos:")
            print(df.head(10).to_string(index=False))
            print("=" * 80)
            
            # Mostrar resumen por vertical y franchise
            if "vertical_type" in df.columns:
                print("\nDistribución por Vertical:")
                print(df["vertical_type"].fillna("SIN_VERTICAL").value_counts())

        return df

    except Exception as e:
        logger.critical(f"\n[ERROR] Falló la consulta a BigQuery: {e}\n", exc_info=True)
        print("\n" + "=" * 80)
        print("DIAGNÓSTICO Y SOLUCIÓN RECOMENDADA:")
        print("=" * 80)
        err_str = str(e)
        if "invalid_grant" in err_str or "RefreshError" in err_str or "credentials" in err_str.lower():
            print("👉 El token de Google Cloud ha expirado o no está configurado.")
            print("   Solución: Ejecuta en tu terminal:")
            print("   gcloud auth application-default login")
        elif "Access Denied" in err_str or "403" in err_str:
            print("👉 Error de permisos en BigQuery o proyecto de cuotas.")
            print("   Solución: Intenta configurar el proyecto de cuotas con:")
            print("   gcloud auth application-default set-quota-project peya-bi-tools-pro")
        else:
            print(f"👉 Detalle del error: {err_str}")
        print("=" * 80)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Prueba aislada de consulta a BigQuery")
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Días hacia atrás para consultar (por defecto: 1)"
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Prueba solo dim_partner sin hacer el JOIN a growth_vendors"
    )
    args = parser.parse_args()
    test_bigquery_connection_and_query(days_lookback=args.days, test_isolated_query=args.simple)

if __name__ == "__main__":
    main()
