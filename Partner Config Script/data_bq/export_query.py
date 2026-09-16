import os
from google.cloud import bigquery

query = """
select p.partner_id, p.partner_name, date(p.registered_date) registered_date, p.partner_status , p.main_cousine_category_name cuisine, p.franchise.franchise_name 
,v.vertical_type 
from `peya-bi-tools-pro.il_core.dim_partner` p
left join (
  SELECT vendor_code, vertical_type 
FROM `fulfillment-dwh-production.curated_data_shared_vendor.growth_vendors`
where entity_id ="PY_CL"
) v on safe_cast(v.vendor_code as int64) =  p.partner_id 
where p.country_id = 2
and date(p.registered_date) >= current_date()-1
and p.partner_status ="ON_LINE"
"""

def main():
    print("Iniciando consulta en BigQuery...")
    client = bigquery.Client(project="peya-chile")
    job_config = bigquery.QueryJobConfig(
        labels={"datacloud": "antigravity"}
    )
    query_job = client.query(query, job_config=job_config)
    df = query_job.to_dataframe()
    
    output_file = "partners_online.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Consulta completada exitosamente. Se guardaron {len(df)} registros en '{output_file}'.")

if __name__ == "__main__":
    main()
