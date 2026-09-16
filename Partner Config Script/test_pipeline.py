import argparse
import pandas as pd
from pathlib import Path
from src.transformer import VendorTransformer
from src.web_uploader import WebUploader
from src.logger import setup_logger

logger = setup_logger("TestPipeline")

def generate_mock_partners_test_suite() -> pd.DataFrame:
    """
    Genera partners simulando todos los casos de la regla de negocio:
    1. Franchise
    2. Cuisine
    3. Vertical:
       - Restaurants / Courier_business: buscar palabras clave en el nombre. Si no, default 15 min.
       - Otras verticales (ej. Pharmacies, Groceries): asignar tiempo por vertical (no busca palabras clave).
    """
    return pd.DataFrame([
        {
            # CASO 1: Franquicia conocida (McDonald's) -> 15 min
            "partner_id": 1001,
            "partner_name": "McDonald's Mall Plaza",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": "COMIDA RAPIDA",
            "franchise_name": "MCDONALDS",
            "vertical_type": "restaurants"
        },
        {
            # CASO 2: Sin franquicia, pero Cuisine conocida (Sushi) -> 30 min
            "partner_id": 1002,
            "partner_name": "Akira Asian Food",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": "SUSHI",
            "franchise_name": None,
            "vertical_type": "restaurants"
        },
        {
            # CASO 3: Vertical 'restaurants', sin cuisine -> Deduce por palabra clave en nombre ("Pizza") -> 25 min
            "partner_id": 1003,
            "partner_name": "Pizzeria Bella Italia",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": None,
            "franchise_name": None,
            "vertical_type": "restaurants"
        },
        {
            # CASO 4: Vertical 'restaurants', sin cuisine y sin palabras clave conocidas -> Default 15 min
            "partner_id": 1004,
            "partner_name": "Local Gastronomico Nuevo",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": None,
            "franchise_name": None,
            "vertical_type": "restaurants"
        },
        {
            # CASO 5: Vertical 'courier_business' -> Deduce por palabra clave en nombre ("Burger") -> 20 min
            "partner_id": 1005,
            "partner_name": "Burger Express Courier",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": None,
            "franchise_name": None,
            "vertical_type": "courier_business"
        },
        {
            # CASO 6: Vertical 'pharmacies' -> Asigna tiempo de vertical (10 min), NO busca palabra clave en nombre
            "partner_id": 1006,
            "partner_name": "Farmacia Pizza del Doctor", # Tiene "Pizza" en nombre, pero al ser farmacia NO debe dar 25 min
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": None,
            "franchise_name": None,
            "vertical_type": "pharmacies"
        },
        {
            # CASO 7: Vertical 'groceries' -> Asigna tiempo de vertical (15 min)
            "partner_id": 1007,
            "partner_name": "Minimarket El Sol",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": None,
            "franchise_name": None,
            "vertical_type": "groceries"
        }
    ])

def run_test_suite():
    logger.info("=" * 80)
    logger.info("VALIDANDO NUEVA LÓGICA DE NEGOCIO Y JERARQUÍA DE REGLAS")
    logger.info("=" * 80)

    mock_df = generate_mock_partners_test_suite()
    transformer = VendorTransformer()
    seamless_df = transformer.apply_business_rules(mock_df)

    print("\n" + "=" * 80)
    print("RESULTADO DE TRANSFORMACIÓN PARA SEAMLESS:")
    print("=" * 80)
    print(seamless_df.to_string(index=False))
    print("=" * 80 + "\n")

    csv_file = transformer.export_to_csv(seamless_df, filename_prefix="test_rules_suite")
    logger.info(f"Archivo de prueba generado en: {csv_file}")
    return csv_file

def main():
    parser = argparse.ArgumentParser(description="Test de reglas de negocio o carga")
    parser.add_argument(
        "--partner-id",
        type=int,
        default=None,
        help="ID de un partner específico para probar"
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Abre el navegador y ejecuta la carga en Seamless Portal"
    )
    args = parser.parse_args()

    if args.partner_id:
        # Prueba con un partner único
        transformer = VendorTransformer()
        df = pd.DataFrame([{
            "partner_id": args.partner_id,
            "partner_name": f"Pizzeria Test {args.partner_id}",
            "registered_date": "2026-08-27",
            "partner_status": "ON_LINE",
            "cuisine": "PIZZA",
            "franchise_name": None,
            "vertical_type": "restaurants"
        }])
        seamless_df = transformer.apply_business_rules(df)
        csv_file = transformer.export_to_csv(seamless_df, filename_prefix=f"test_seamless_{args.partner_id}")
        if args.upload:
            uploader = WebUploader()
            uploader.upload_csv(csv_file)
    else:
        run_test_suite()

if __name__ == "__main__":
    main()
