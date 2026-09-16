import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
from config.config import Config
from src.logger import setup_logger

logger = setup_logger("DriveVendorReader")

class DriveVendorReader:
    def __init__(self, drive_dir: Optional[Path] = None):
        self.drive_dir = drive_dir or Config.DRIVE_VENDORS_DIR
        self._ensure_directory()

    def _ensure_directory(self):
        """Crea la carpeta de origen si no existe."""
        if not self.drive_dir.exists():
            self.drive_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Carpeta de origen creada: {self.drive_dir}")

    def find_todays_file(self) -> Optional[Path]:
        """
        Busca el archivo creado con fecha de hoy en la carpeta data_vendors_drive.
        Verifica tanto el nombre del archivo (YYYYMMDD, YYYY-MM-DD, etc.)
        como la fecha de creación/modificación en el sistema de archivos.
        """
        today = date.today()
        today_str_compact = today.strftime("%Y%m%d")      # Ej: 20260904
        today_str_hyphen = today.strftime("%Y-%m-%d")     # Ej: 2026-09-04
        today_str_reverse = today.strftime("%d-%m-%Y")    # Ej: 04-09-2026
        today_str_reverse_c = today.strftime("%d%m%Y")    # Ej: 04092026

        date_patterns = [today_str_compact, today_str_hyphen, today_str_reverse, today_str_reverse_c]

        valid_extensions = {".csv", ".xlsx", ".xls", ".txt"}
        candidate_files = []

        for file_path in self.drive_dir.iterdir():
            if not file_path.is_file() or file_path.suffix.lower() not in valid_extensions:
                continue

            file_name = file_path.name
            
            # Criterio 1: El nombre del archivo contiene la fecha de hoy
            has_today_in_name = any(dp in file_name for dp in date_patterns)

            # Criterio 2: La fecha de modificación del archivo es hoy
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime).date()
            is_modified_today = (file_mtime == today)

            if has_today_in_name or is_modified_today:
                candidate_files.append((file_path, file_path.stat().st_mtime))

        if not candidate_files:
            logger.info(f"No se encontraron archivos creados con fecha de hoy ({today_str_hyphen}) en: {self.drive_dir}")
            return None

        # Si hay más de uno, tomar el más reciente
        candidate_files.sort(key=lambda x: x[1], reverse=True)
        selected_file = candidate_files[0][0]
        logger.info(f"Archivo de hoy encontrado: {selected_file.name} (Ruta: {selected_file})")
        return selected_file

    def read_vendors_file(self, file_path: Path) -> pd.DataFrame:
        """
        Lee el archivo de vendors (CSV o Excel) y estandariza los nombres de columnas.
        """
        logger.info(f"Leyendo archivo de vendors: {file_path.name}...")
        
        try:
            if file_path.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
            else:
                # Intentar leer CSV detectando delimitador (coma, punto y coma, tab)
                try:
                    df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, sep=None, engine="python", encoding="latin-1")

            logger.info(f"Archivo leido correctamente. Filas encontradas: {len(df)}")
            return self._standardize_columns(df)

        except Exception as e:
            logger.error(f"Error al leer el archivo {file_path}: {e}")
            raise

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza y mapea los nombres de columnas a los nombres esperados por el transformador:
        partner_id, partner_name, cuisine, franchise_name, vertical_type, partner_status
        """
        standard_mapping = {}

        for col in df.columns:
            clean_col = str(col).strip().lower().replace(" ", "_").replace("-", "_")

            if clean_col in ["partner_id", "partnerid", "code", "vendor_code", "vendor_id", "id", "codigo", "vendor"]:
                standard_mapping[col] = "partner_id"
            elif clean_col in ["partner_name", "partnername", "vendor_name", "vendorname", "nombre", "razon_social", "name"]:
                standard_mapping[col] = "partner_name"
            elif clean_col in ["cuisine", "main_cousine_category_name", "main_cuisine_category_name", "cocina", "tipo_cocina"]:
                standard_mapping[col] = "cuisine"
            elif clean_col in ["franchise_name", "franchisename", "franchise", "franquicia"]:
                standard_mapping[col] = "franchise_name"
            elif clean_col in ["vertical_type", "verticaltype", "vertical", "tipo_vertical"]:
                standard_mapping[col] = "vertical_type"
            elif clean_col in ["partner_status", "partnerstatus", "status", "estado"]:
                standard_mapping[col] = "partner_status"
            elif clean_col in ["registered_date", "registereddate", "date", "fecha", "fecha_alta"]:
                standard_mapping[col] = "registered_date"

        df_renamed = df.rename(columns=standard_mapping)
        logger.info(f"Columnas mapeadas para procesamiento: {list(standard_mapping.values())}")
        return df_renamed
