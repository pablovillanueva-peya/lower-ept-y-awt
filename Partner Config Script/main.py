import argparse
import sys
from datetime import date
from pathlib import Path
import pandas as pd
from config.config import Config
from src.logger import setup_logger
from src.file_reader import DriveVendorReader
from src.bq_client import BigQueryExtractor
from src.transformer import VendorTransformer
from src.web_uploader import WebUploader

logger = setup_logger("MainPipeline")

def run_pipeline(
    dry_run: bool = False,
    skip_upload: bool = False,
    days_lookback: int = 1,
    test_partner_id: int = None,
    source: str = None
):
    """
    Ejecuta el flujo completo de automatizacion para Seamless Bulk Updates:
    1. Obtencion de datos:
       - Si test_partner_id: Usa partner de prueba.
       - Si source == 'drive_folder': Lee el archivo de hoy en data_vendors_drive.
       - Si source == 'bigquery': Consulta directamente BigQuery.
    2. Transformacion con reglas de negocio (Franchise -> Cuisine -> Vertical -> Keywords -> Default 15m)
    3. Generacion de 2 archivos:
       - CSV para Seamless Bulk Updates (CODE, DAY-RANGE, HOUR-RANGE, PREPARATION-BUFFER, PREPARATION-TIME, STRATEGY)
       - Archivo de Auditoria Completo (Data de origen + PREPTIME_CARGADO + CRITERIO_ASIGNACION)
    4. Carga en Seamless Dashboard (PedidosYa Portal) con Playwright.
    """
    logger.info("=" * 70)
    logger.info("INICIANDO PROCESO DIARIO DE PREPTIME (SEAMLESS BULK UPDATES)")
    logger.info("=" * 70)

    try:
        Config.ensure_directories()
        data_source = source or Config.DATA_SOURCE

        # -------------------------------------------------------------
        # PASO 1: Obtención de datos de Vendors
        # -------------------------------------------------------------
        if test_partner_id:
            logger.info(f"--- MODO TEST ACTIVADO: Procesando EXCLUSIVAMENTE Partner ID {test_partner_id} ---")
            df_raw = pd.DataFrame([{
                "partner_id": test_partner_id,
                "partner_name": f"Pizzeria Test {test_partner_id}",
                "registered_date": str(date.today()),
                "partner_status": "ON_LINE",
                "cuisine": "PIZZA",
                "franchise_name": None,
                "vertical_type": "restaurants"
            }])

        elif data_source == "drive_folder":
            logger.info(f"--- PASO 1: Buscando archivo del dia de hoy en '{Config.DRIVE_VENDORS_DIR.name}' ---")
            reader = DriveVendorReader()
            todays_file = reader.find_todays_file()

            if todays_file is None:
                logger.info("=" * 70)
                logger.info(f"[INFO] No hay archivos nuevos con fecha de hoy ({date.today()}) en '{Config.DRIVE_VENDORS_DIR}'.")
                logger.info("El proceso finaliza sin realizar cambios.")
                logger.info("=" * 70)
                return

            df_raw = reader.read_vendors_file(todays_file)

        else:
            logger.info(f"--- PASO 1: Consulta a BigQuery peya-bi-tools-pro (Lookback: {days_lookback} dias) ---")
            extractor = BigQueryExtractor()
            df_raw = extractor.get_latest_vendors(days_lookback=days_lookback)

        if df_raw.empty:
            logger.info("No se encontraron registros de vendors para procesar. Finalizando ejecucion.")
            return

        # -------------------------------------------------------------
        # PASO 2: Transformacion, Asignacion de Reglas y Generacion de CSVs
        # -------------------------------------------------------------
        logger.info("--- PASO 2: Aplicando Reglas de Preptime y Generando Resultados ---")
        transformer = VendorTransformer()
        seamless_df, audit_df = transformer.apply_business_rules(df_raw)

        if seamless_df.empty:
            logger.warning("No quedaron registros validos tras la transformacion.")
            return

        # Exportar ambos archivos
        seamless_csv_path = transformer.export_to_csv(seamless_df, filename_prefix="seamless_bulk_upload")
        audit_csv_path = transformer.export_audit_csv(audit_df, filename_prefix="reporte_auditoria_vendors")

        logger.info("=" * 70)
        logger.info("ARCHIVOS GENERADOS:")
        logger.info(f"1. CSV para Seamless: {seamless_csv_path}")
        logger.info(f"2. Reporte de Auditoria Completo: {audit_csv_path}")
        logger.info("=" * 70)

        if dry_run or skip_upload:
            logger.info("[DRY RUN / SKIP UPLOAD] Omitiendo carga en el portal web.")
            print("\n" + "=" * 90)
            print("VISTA PREVIA DEL REPORTE FINAL DE AUDITORIA:")
            print("=" * 90)
            print(audit_df.to_string(index=False))
            print("=" * 90 + "\n")
            return

        # -------------------------------------------------------------
        # PASO 3: Carga en Seamless Portal (Playwright)
        # -------------------------------------------------------------
        logger.info("--- PASO 3: Carga en Seamless Dashboard (PedidosYa Portal) ---")
        uploader = WebUploader()
        uploader.upload_csv(seamless_csv_path)

        logger.info("=" * 70)
        logger.info("PROCESO COMPLETADO EXITOSAMENTE")
        logger.info("=" * 70)

    except Exception as e:
        logger.critical(f"El proceso fallo con error: {e}", exc_info=True)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline diario de Preptime para Seamless Bulk Updates"
    )
    parser.add_argument(
        "--source",
        choices=["drive_folder", "bigquery"],
        default=None,
        help="Origen de datos: 'drive_folder' (por defecto) o 'bigquery'"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta lectura y transformacion sin subir a la web."
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Genera los CSVs pero no abre el navegador."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Dias hacia atras para consultar en BigQuery (si se usa BigQuery)."
    )
    parser.add_argument(
        "--test-partner",
        type=int,
        default=None,
        help="Ejecuta una prueba con un ID de partner especifico (ej. 634433) sin leer archivos ni BigQuery."
    )

    args = parser.parse_args()
    run_pipeline(
        dry_run=args.dry_run,
        skip_upload=args.skip_upload,
        days_lookback=args.days,
        test_partner_id=args.test_partner,
        source=args.source
    )

if __name__ == "__main__":
    main()
