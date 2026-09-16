import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
from config.config import Config
from src.logger import setup_logger

logger = setup_logger("VendorTransformer")

def normalize_text(text: Optional[str]) -> str:
    """Normaliza texto eliminando acentos, espacios extra y convirtiendo a mayúsculas."""
    if text is None or pd.isna(text):
        return ""
    text_str = str(text).strip().upper()
    normalized = unicodedata.normalize("NFD", text_str)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")

class VendorTransformer:
    def __init__(self, rules_file: Optional[Path] = None, output_dir: Optional[Path] = None):
        self.rules_file = rules_file or Config.RULES_FILE
        self.output_dir = output_dir or Config.OUTPUT_DIR
        self.franchise_rules: Dict[str, int] = {}
        self.cuisine_rules: Dict[str, int] = {}
        self.vertical_rules: Dict[str, int] = {}
        self.keyword_rules: List[Tuple[str, int]] = []
        self.default_preptime: int = Config.DEFAULT_PREPTIME
        self._load_rules()

    def _load_rules(self):
        """Carga las reglas de negocio desde el archivo CSV de configuración."""
        if not self.rules_file.exists():
            logger.warning(f"No se encontró el archivo de reglas en {self.rules_file}. Se usará el valor default ({self.default_preptime} min).")
            return

        try:
            rules_df = pd.read_csv(self.rules_file)
            logger.info(f"Cargando reglas de negocio desde {self.rules_file.name} ({len(rules_df)} reglas)...")

            for _, row in rules_df.iterrows():
                rtype = str(row.get("rule_type", "")).strip().lower()
                val = normalize_text(row.get("match_value", ""))
                try:
                    preptime = int(row.get("preptime_minutes", self.default_preptime))
                except (ValueError, TypeError):
                    preptime = self.default_preptime

                if rtype == "franchise" and val:
                    self.franchise_rules[val] = preptime
                elif rtype == "cuisine" and val:
                    self.cuisine_rules[val] = preptime
                elif rtype == "vertical" and val:
                    self.vertical_rules[val] = preptime
                elif rtype == "keyword" and val:
                    self.keyword_rules.append((val, preptime))
                elif rtype == "default":
                    self.default_preptime = preptime

            logger.info(
                f"Reglas activas: {len(self.franchise_rules)} franquicias, "
                f"{len(self.cuisine_rules)} cuisines, {len(self.vertical_rules)} verticales, "
                f"{len(self.keyword_rules)} palabras clave. Default: {self.default_preptime} min."
            )
        except Exception as e:
            logger.error(f"Error al leer el archivo de reglas: {e}. Se utilizará preptime default ({self.default_preptime} min).")

    def calculate_partner_preptime(
        self,
        franchise_name: Optional[str],
        cuisine: Optional[str],
        vertical_type: Optional[str],
        partner_name: str
    ) -> Tuple[int, str]:
        """
        Calcula el preptime y la regla aplicada en cascada según las reglas de negocio:
        1. Franchise Match
        2. Cuisine Match
        3. Vertical:
           - Si la vertical es 'restaurants' o 'courier_business' (o vacía):
             -> Buscar palabras clave en partner_name para asociar a una cuisine.
             -> Si no coincide ninguna palabra clave, asignar valor default (15 min).
           - En las demás verticales (ej. pharmacies, groceries, drinks, darkstores, etc.):
             -> Asignar por regla de vertical directamente (no se evalúan palabras clave).
             -> Si no coincide, asignar valor default (15 min).
        """
        norm_franchise = normalize_text(franchise_name)
        norm_cuisine = normalize_text(cuisine)
        norm_vertical = normalize_text(vertical_type)
        norm_name = normalize_text(partner_name)

        # 1. Regla Franquicia
        if norm_franchise and norm_franchise not in ("NONE", "NULL", "NAN", ""):
            for f_key, ptime in self.franchise_rules.items():
                if f_key in norm_franchise or norm_franchise in f_key:
                    return ptime, f"FRANCHISE ({f_key})"

        # 2. Regla Cuisine
        if norm_cuisine and norm_cuisine not in ("NONE", "NULL", "NAN", ""):
            for c_key, ptime in self.cuisine_rules.items():
                if c_key in norm_cuisine or norm_cuisine in c_key:
                    return ptime, f"CUISINE ({c_key})"

        # 3. Regla según Vertical
        is_restaurant_or_courier = False
        if not norm_vertical or norm_vertical in ("NONE", "NULL", "NAN", ""):
            is_restaurant_or_courier = True
        else:
            food_vertical_keywords = ["RESTAURANT", "RESTAURANTS", "COURIER", "COURIER_BUSINESS", "FOOD", "COMIDA"]
            if any(vk in norm_vertical for vk in food_vertical_keywords):
                is_restaurant_or_courier = True

        if is_restaurant_or_courier:
            # 4. Vertical Restaurants / Courier -> Revisar palabras clave del nombre
            if norm_name:
                for keyword, ptime in self.keyword_rules:
                    if keyword in norm_name:
                        return ptime, f"KEYWORD ({keyword})"
            
            # Si no coincide palabra clave en restaurants/courier: default 15 min
            return self.default_preptime, "DEFAULT (RESTAURANTS/COURIER 15 MIN)"
        else:
            # Para las demás verticales (ej. pharmacies, groceries, etc.) NO se buscan palabras clave
            for v_key, ptime in self.vertical_rules.items():
                if v_key in norm_vertical or norm_vertical in v_key:
                    return ptime, f"VERTICAL ({v_key})"

            # Si no coincide con regla de vertical: default 15 min
            return self.default_preptime, f"DEFAULT (VERTICAL {norm_vertical} 15 MIN)"

    def apply_business_rules(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Aplica las reglas de asignación de preptime y genera dos DataFrames:
        1. seamless_df: Archivo con las 6 columnas exactas requeridas para la carga en Seamless:
           CODE,DAY-RANGE,HOUR-RANGE,PREPARATION-BUFFER,PREPARATION-TIME,STRATEGY
        2. audit_df: Archivo completo de resultados con TODA la data de origen +
           PREPTIME_CARGADO + CRITERIO_ASIGNACION
        """
        if df.empty:
            logger.warning("El DataFrame recibido está vacío.")
            return pd.DataFrame(), pd.DataFrame()

        logger.info(f"Aplicando reglas de preptime sobre {len(df)} partners...")
        processed = df.copy()

        codes: List[str] = []
        preptimes: List[int] = []
        rules_applied: List[str] = []

        for _, row in processed.iterrows():
            code = str(row.get("partner_id", "")).strip()
            f_name = row.get("franchise_name")
            cuis = row.get("cuisine")
            vert = row.get("vertical_type")
            p_name = str(row.get("partner_name", ""))

            ptime, rule = self.calculate_partner_preptime(f_name, cuis, vert, p_name)
            codes.append(code)
            preptimes.append(ptime)
            rules_applied.append(rule)

        # 1. Crear el DataFrame para Seamless
        seamless_df = pd.DataFrame({
            "CODE": codes,
            "DAY-RANGE": Config.CSV_DAY_RANGE,
            "HOUR-RANGE": Config.CSV_HOUR_RANGE,
            "PREPARATION-BUFFER": Config.CSV_PREPARATION_BUFFER,
            "PREPARATION-TIME": preptimes,
            "STRATEGY": Config.CSV_STRATEGY
        })

        # 2. Crear el DataFrame de Auditoría (Toda la data original + Preptime + Criterio)
        audit_df = processed.copy()
        audit_df["PREPTIME_CARGADO"] = preptimes
        audit_df["CRITERIO_ASIGNACION"] = rules_applied

        # Resumen estadístico para el log
        rule_summary = {}
        for r in rules_applied:
            prefix = r.split(" ")[0]
            rule_summary[prefix] = rule_summary.get(prefix, 0) + 1
        logger.info(f"Distribución de asignación de preptime: {rule_summary}")

        return seamless_df, audit_df

    def export_to_csv(self, df: pd.DataFrame, filename_prefix: str = "seamless_bulk_upload") -> Path:
        """
        Exporta el DataFrame al archivo CSV en el formato exacto requerido por Seamless.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.csv"
        file_path = self.output_dir / filename

        df.to_csv(file_path, index=False, sep=",", encoding="utf-8")
        logger.info(f"CSV de Seamless generado exitosamente: {file_path}")
        return file_path

    def export_audit_csv(self, df: pd.DataFrame, filename_prefix: str = "reporte_auditoria_vendors") -> Path:
        """
        Exporta el archivo de resultados detallado con toda la data de origen,
        el preptime asignado y el criterio utilizado.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.csv"
        file_path = self.output_dir / filename

        # Exportar con codificación utf-8-sig para compatibilidad nativa con Excel
        df.to_csv(file_path, index=False, sep=",", encoding="utf-8-sig")
        logger.info(f"Archivo de auditoría/resultados generado exitosamente: {file_path}")
        return file_path
