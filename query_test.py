from IPython import display
import sys
from google.cloud import bigquery

print(sys.executable)

bq_client = bigquery.Client(project="peya-chile")
bq_test = bq_client.query("SELECT 1 AS ok").to_dataframe()

display(bq_test)
