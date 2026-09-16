import os
import sys
import subprocess
import pandas as pd
from typing import Optional
from google.cloud import bigquery
from google.oauth2 import service_account
from google.auth.exceptions import RefreshError, DefaultCredentialsError
from config.config import Config
from src.logger import setup_logger

logger = setup_logger("BigQueryExtractor")

class BigQueryExtractor:
    def __init__(
        self,
        project_id: Optional[str] = None,
        country_id: Optional[int] = None,
        entity_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        self.project_id = project_id or Config.GCP_PROJECT_ID
        self.country_id = country_id or Config.GCP_COUNTRY_ID
        self.entity_id = entity_id or Config.SEAMLESS_COUNTRY
        self.credentials_path = credentials_path or Config.GOOGLE_APPLICATION_CREDENTIALS
        self.client = self._init_client()

    def _ensure_gcloud_auth(self):
        """
        Ejecuta interactivamente 'gcloud auth application-default login'
        para autenticar la cuenta de Google Cloud en el navegador.
        """
        logger.warning("=" * 70)
        logger.warning("[AUTH] Se requiere autenticacion en Google Cloud (gcloud ADC).")
        logger.warning("Abriendo el navegador para iniciar sesion con tu cuenta corporativa...")
        logger.warning("=" * 70)

        try:
            result = subprocess.run(
                ["gcloud", "auth", "application-default", "login"],
                shell=True,
                check=True
            )
            if result.returncode == 0:
                logger.info("Autenticacion en Google Cloud completada con exito.")
                return True
        except subprocess.CalledProcessError as e:
            logger.error(f"La autenticacion con gcloud fallo: {e}")
            raise
        except Exception as e:
            logger.error(f"Error al ejecutar gcloud auth: {e}")
            raise
        return False

    def _init_client(self, retry_on_auth_fail: bool = True) -> bigquery.Client:
        """Inicializa el cliente de BigQuery con ADC o Service Account Key."""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                logger.info(f"Autenticando con Service Account Key: {self.credentials_path}")
                credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
                return bigquery.Client(project=self.project_id or credentials.project_id, credentials=credentials)
            
            logger.info(f"Autenticando con Application Default Credentials (ADC) en proyecto: {self.project_id}")
            return bigquery.Client(project=self.project_id)
        except (DefaultCredentialsError, RefreshError) as e:
            if retry_on_auth_fail:
                logger.warning(f"Credenciales de GCP no disponibles ({e}). Iniciando login con gcloud...")
                self._ensure_gcloud_auth()
                return self._init_client(retry_on_auth_fail=False)
            raise
        except Exception as e:
            logger.error(f"Error al inicializar cliente de BigQuery: {e}")
            raise

    def get_latest_vendors(self, custom_query: Optional[str] = None, days_lookback: Optional[int] = None) -> pd.DataFrame:
        """
        Ejecuta la consulta para extraer partners ON_LINE con su vertical_type.
        Si las credenciales han expirado (invalid_grant), solicita autenticación y reintenta automáticamente.
        """
        lookback = days_lookback if days_lookback is not None else Config.DAYS_LOOKBACK

        if custom_query:
            query = custom_query
        else:
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
                `{self.project_id}.il_core.dim_partner` p
            LEFT JOIN (
                SELECT 
                    vendor_code, 
                    vertical_type 
                FROM 
                    `fulfillment-dwh-production.curated_data_shared_vendor.growth_vendors`
                WHERE 
                    entity_id = "{self.entity_id}"
            ) v 
                ON SAFE_CAST(v.vendor_code AS INT64) = p.partner_id 
            WHERE 
                p.country_id = {self.country_id}
                AND DATE(p.registered_date) >= CURRENT_DATE() - {lookback}
                AND p.partner_status = "ON_LINE"
            ORDER BY 
                p.registered_date DESC
            """

        logger.info(f"Ejecutando consulta en BigQuery (Pais: {self.country_id}, Status: ON_LINE, Lookback: {lookback} dias)...")
        logger.debug(f"Query SQL:\n{query}")

        try:
            query_job = self.client.query(query)
            df = query_job.to_dataframe()
            logger.info(f"Consulta completada exitosamente. Se obtuvieron {len(df)} partners ON_LINE.")
            return df
        except Exception as e:
            err_msg = str(e)
            if "invalid_grant" in err_msg or "RefreshError" in err_msg or "Credentials" in err_msg:
                logger.warning("Token de credenciales de Google Cloud expirado. Solicitando re-autenticacion...")
                self._ensure_gcloud_auth()
                self.client = self._init_client(retry_on_auth_fail=False)
                logger.info("Reintentando consulta a BigQuery...")
                query_job = self.client.query(query)
                df = query_job.to_dataframe()
                logger.info(f"Consulta completada exitosamente tras autenticacion. Se obtuvieron {len(df)} partners ON_LINE.")
                return df
            else:
                logger.error(f"Error al ejecutar la consulta en BigQuery: {e}")
                raise
