WITH params AS (
  SELECT
    DATE_SUB(
      DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)),
      INTERVAL 7 DAY
    ) AS week_start,
    DATE_SUB(
      DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)),
      INTERVAL 1 DAY
    ) AS week_end
),
orders AS (
  -- Una fila por orden para evitar duplicarla antes de agregar.
  SELECT
    CAST(l.peya_order_id AS STRING) AS order_id,
    MAX(SAFE_DIVIDE(l.timings.avoidable_wait_time, 60.0)) AS awt_min,
    MAX(SAFE_DIVIDE(l.estimated_prep_time, 60.0)) AS ept_min
  FROM `peya-bi-tools-pro.il_logistics.fact_logistic_orders` AS l
  CROSS JOIN params AS p
  WHERE l.country_code = 'cl'
    AND l.peya_order_id IS NOT NULL
    AND EXISTS (
      SELECT 1
      FROM UNNEST(l.deliveries) AS d
      WHERE d.is_primary = TRUE
    )
    AND l.is_preorder = FALSE
    AND LOWER(l.vendor.vertical_type) = 'restaurants'
    AND DATE(l.created_date_local) BETWEEN p.week_start AND p.week_end
  GROUP BY order_id
),
seamless_by_order AS (
  -- Si una orden tiene etiquetas contradictorias, se deja sin clasificar.
  SELECT
    CAST(n.order_id AS STRING) AS order_id,
    IF(
      COUNT(DISTINCT SAFE_CAST(n.SEAMLESS AS INT64)) = 1,
      MAX(SAFE_CAST(n.SEAMLESS AS INT64)),
      NULL
    ) AS seamless
  FROM `peya-delivery-and-support.automated_tables_reports.non_seamless_reasons` AS n
  CROSS JOIN params AS p
  WHERE n.country_name = 'Chile'
    AND DATE(n.created_date_local) BETWEEN p.week_start AND p.week_end
  GROUP BY order_id
),
metrics AS (
  SELECT
    CAST(CEIL(o.awt_min) AS INT64) AS awt_ceil_min,
    CASE
      WHEN o.ept_min IS NULL THEN 'NULL'
      WHEN o.ept_min < 1 THEN '<1'
      WHEN o.ept_min < 5 THEN '[1,5)'
      WHEN o.ept_min < 10 THEN '[5,10)'
      WHEN o.ept_min >= 60 THEN '60+'
      ELSE FORMAT(
        '[%d,%d)',
        CAST(FLOOR(o.ept_min / 10) * 10 AS INT64),
        CAST(FLOOR(o.ept_min / 10) * 10 + 10 AS INT64)
      )
    END AS ept_bucket,
    CASE
      WHEN o.ept_min IS NULL THEN -2
      WHEN o.ept_min < 1 THEN -1
      WHEN o.ept_min < 5 THEN 1
      WHEN o.ept_min < 10 THEN 5
      WHEN o.ept_min >= 60 THEN 60
      ELSE CAST(FLOOR(o.ept_min / 10) * 10 AS INT64)
    END AS ept_bucket_start,
    COUNT(*) AS total_orders,
    COUNTIF(s.seamless = 1) AS seamless_orders,
    COUNTIF(s.seamless IN (0, 1)) AS classified_orders
  FROM orders AS o
  LEFT JOIN seamless_by_order AS s USING (order_id)
  GROUP BY awt_ceil_min, ept_bucket, ept_bucket_start
)
SELECT
  p.week_start,
  p.week_end,
  m.awt_ceil_min,
  m.ept_bucket,
  m.ept_bucket_start,
  m.total_orders,
  m.seamless_orders,
  m.classified_orders,
  ROUND(100 * SAFE_DIVIDE(m.seamless_orders, m.classified_orders), 2)
    AS seamless_pct,
  ROUND(100 * SAFE_DIVIDE(m.classified_orders, m.total_orders), 2)
    AS classification_coverage_pct
FROM metrics AS m
CROSS JOIN params AS p
ORDER BY m.awt_ceil_min IS NULL, m.awt_ceil_min, m.ept_bucket_start
