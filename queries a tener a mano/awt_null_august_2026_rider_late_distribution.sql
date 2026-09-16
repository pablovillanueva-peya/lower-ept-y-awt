-- Distribucion de rider_late para ordenes AWT NULL de agosto 2026.
-- rider_late proviene directamente de fact_logistic_orders.timings y se
-- expresa en segundos. Los intervalos de cinco minutos solo se usan para
-- construir el histograma; el denominador es el total de ordenes AWT NULL.

WITH params AS (
  SELECT DATE '2026-08-01' AS start_date, DATE '2026-08-31' AS end_date
),
order_level AS (
  SELECT
    CAST(l.peya_order_id AS STRING) AS order_id,
    MAX(l.timings.avoidable_wait_time) AS avoidable_wait_time,
    ARRAY_AGG(
      STRUCT(
        l.timings.rider_late AS rider_late_seconds
      )
      ORDER BY l.created_at DESC
      LIMIT 1
    )[OFFSET(0)] AS timings
  FROM `peya-bi-tools-pro.il_logistics.fact_logistic_orders` AS l
  CROSS JOIN params AS p
  WHERE l.country_code = 'cl'
    AND l.peya_order_id IS NOT NULL
    AND l.is_preorder = FALSE
    AND COALESCE(LOWER(TRIM(l.vendor.vertical_type)), '') != 'darkstores'
    AND DATE(l.created_date_local) BETWEEN p.start_date AND p.end_date
    AND EXISTS (
      SELECT 1
      FROM UNNEST(l.deliveries) AS d
      WHERE d.is_primary = TRUE
    )
  GROUP BY order_id
),
awt_null_orders AS (
  SELECT
    order_id,
    timings.rider_late_seconds AS rider_late_seconds
  FROM order_level
  WHERE avoidable_wait_time IS NULL
),
bucketed AS (
  SELECT
    order_id,
    rider_late_seconds,
    CASE
      WHEN rider_late_seconds IS NULL THEN -1
      WHEN rider_late_seconds < 0 THEN 0
      WHEN rider_late_seconds >= 3600 THEN 13
      ELSE 1 + CAST(FLOOR(rider_late_seconds / 300) AS INT64)
    END AS bucket_order
  FROM awt_null_orders
),
distribution AS (
  SELECT
    bucket_order,
    CASE
      WHEN bucket_order = -1 THEN 'Sin dato'
      WHEN bucket_order = 0 THEN '<0'
      WHEN bucket_order = 13 THEN '60+'
      ELSE FORMAT(
        '%d-%d',
        (bucket_order - 1) * 5,
        bucket_order * 5
      )
    END AS rider_late_bucket_minutes,
    COUNT(*) AS orders
  FROM bucketed
  GROUP BY bucket_order, rider_late_bucket_minutes
),
totals AS (
  SELECT COUNT(*) AS awt_null_orders
  FROM awt_null_orders
)
SELECT
  p.start_date,
  p.end_date,
  d.bucket_order,
  d.rider_late_bucket_minutes,
  d.orders,
  t.awt_null_orders,
  ROUND(100 * SAFE_DIVIDE(d.orders, t.awt_null_orders), 4)
    AS share_of_awt_null_orders_pct
FROM distribution AS d
CROSS JOIN totals AS t
CROSS JOIN params AS p
ORDER BY d.bucket_order;
