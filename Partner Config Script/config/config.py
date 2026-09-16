import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Config:
    # Rutas base
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / os.getenv("CSV_OUTPUT_DIR", "data/output")
    LOGS_DIR = BASE_DIR / os.getenv("LOGS_DIR", "data/logs")
    BROWSER_SESSION_DIR = DATA_DIR / "browser_session"
    RULES_FILE = BASE_DIR / os.getenv("RULES_FILE_PATH", "config/rules_preptime.csv")

    # Origen de datos (drive_folder o bigquery)
    DATA_SOURCE = os.getenv("DATA_SOURCE", "drive_folder")
    
    # Carpeta de entrada con los archivos diarios de vendors
    raw_drive_path = os.getenv("DRIVE_VENDORS_DIR", "data_vendors_drive")
    DRIVE_VENDORS_DIR = Path(raw_drive_path) if Path(raw_drive_path).is_absolute() else BASE_DIR / raw_drive_path

    # BigQuery / GCP (opcional si se usa bigquery)
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "peya-bi-tools-pro")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    GCP_COUNTRY_ID = int(os.getenv("GCP_COUNTRY_ID", "2"))
    DAYS_LOOKBACK = int(os.getenv("DAYS_LOOKBACK", "1"))

    # Reglas de negocio (por defecto 15 minutos)
    DEFAULT_PREPTIME = int(os.getenv("DEFAULT_PREPTIME", "15"))

    # Formato CSV para Seamless Bulk Updates
    CSV_DAY_RANGE = os.getenv("CSV_DAY_RANGE", "MONDAY-SUNDAY")
    CSV_HOUR_RANGE = os.getenv("CSV_HOUR_RANGE", "0-23")
    CSV_PREPARATION_BUFFER = int(os.getenv("CSV_PREPARATION_BUFFER", "2"))
    CSV_STRATEGY = os.getenv("CSV_STRATEGY", "OPS_TEMPORARY")

    # Seamless Dashboard / PedidosYa Portal
    WEB_APP_URL = os.getenv("WEB_APP_URL", "https://ops-portal.pedidosya.com/pv2/cl/p/logistics-seamless#/main")
    WEB_USERNAME = os.getenv("WEB_USERNAME", "cristian.alvarez@pedidosya.com")
    WEB_PASSWORD = os.getenv("WEB_PASSWORD", "")
    BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
    BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "60000"))

    # Opciones fijas del wizard de Seamless
    SEAMLESS_COUNTRY = os.getenv("SEAMLESS_COUNTRY", "PY_CL")
    SEAMLESS_VENDOR_TYPE = os.getenv("SEAMLESS_VENDOR_TYPE", "OD Vendors")
    SEAMLESS_ACTION_TYPE = os.getenv("SEAMLESS_ACTION_TYPE", "Preparations times")

    @classmethod
    def ensure_directories(cls):
        """Crea los directorios necesarios si no existen."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.BROWSER_SESSION_DIR.mkdir(parents=True, exist_ok=True)
        cls.DRIVE_VENDORS_DIR.mkdir(parents=True, exist_ok=True)

# Asegurar existencia de carpetas al importar
Config.ensure_directories()
