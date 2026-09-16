-- AWT NULL agrupado por la combinacion exacta de cancellation_reason y
-- undispatch_reason. No se crean categorias nuevas.
-- Una orden con multiples valores puede aparecer en multiples combinaciones.

WITH params AS (
  SELECT DATE '2026-08-01' AS start_date, DATE '2026-08-31' AS end_date
),
logistics_source AS (
  SELECT
    CAST(l.peya_order_id AS STRING) AS order_id,
    l.timings.avoidable_wait_time,
    l.cancellation.reason AS cancellation_reason
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
),
orders_by_order AS (
  SELECT
    order_id,
    MAX(avoidable_wait_time) AS avoidable_wait_time
  FROM logistics_source
  GROUP BY order_id
),
cancellation_reason_by_order AS (
  SELECT DISTINCT
    order_id,
    cancellation_reason
  FROM logistics_source
  WHERE cancellation_reason IS NOT NULL
),
non_seamless_source AS (
  SELECT
    CAST(n.order_id AS STRING) AS order_id,
    SAFE_CAST(n.SEAMLESS AS INT64) AS seamless,
    n.undispatch_reason
  FROM `peya-delivery-and-support.automated_tables_reports.non_seamless_reasons` AS n
  CROSS JOIN params AS p
  WHERE n.country_name = 'Chile'
    AND n.order_id IS NOT NULL
    AND DATE(n.created_date_local) BETWEEN p.start_date AND p.end_date
),
seamless_by_order AS (
  SELECT
    order_id,
    IF(
      COUNT(DISTINCT seamless) = 1,
      MAX(seamless),
      NULL
    ) AS seamless
  FROM non_seamless_source
  GROUP BY order_id
),
undispatch_reason_by_order AS (
  SELECT DISTINCT
    order_id,
    undispatch_reason
  FROM non_seamless_source
  WHERE undispatch_reason IS NOT NULL
),
order_level AS (
  SELECT
    o.order_id,
    o.avoidable_wait_time,
    s.seamless
  FROM orders_by_order AS o
  LEFT JOIN seamless_by_order AS s USING (order_id)
),
awt_null_orders AS (
  SELECT *
  FROM order_level
  WHERE avoidable_wait_time IS NULL
),
combination_order_rows AS (
  SELECT DISTINCT
    o.order_id,
    o.seamless,
    c.cancellation_reason,
    u.undispatch_reason
  FROM awt_null_orders AS o
  LEFT JOIN cancellation_reason_by_order AS c USING (order_id)
  LEFT JOIN undispatch_reason_by_order AS u USING (order_id)
),
totals AS (
  SELECT
    COUNT(*) AS total_orders,
    COUNTIF(avoidable_wait_time IS NULL) AS awt_null_orders
  FROM order_level
),
report_rows AS (
  SELECT
    1 AS sort_order,
    'TOTAL_ORDERS' AS row_type,
    CAST(NULL AS STRING) AS cancellation_reason,
    CAST(NULL AS STRING) AS undispatch_reason,
    COUNT(*) AS orders,
    COUNTIF(seamless = 1) AS seamless_orders,
    COUNTIF(seamless IN (0, 1)) AS classified_orders
  FROM order_level

  UNION ALL

  SELECT
    2 AS sort_order,
    'AWT_NULL_TOTAL' AS row_type,
    CAST(NULL AS STRING) AS cancellation_reason,
    CAST(NULL AS STRING) AS undispatch_reason,
    COUNT(*) AS orders,
    COUNTIF(seamless = 1) AS seamless_orders,
    COUNTIF(seamless IN (0, 1)) AS classified_orders
  FROM awt_null_orders

  UNION ALL

  SELECT
    3 AS sort_order,
    'COMBINATION' AS row_type,
    cancellation_reason,
    undispatch_reason,
    COUNT(DISTINCT order_id) AS orders,
    COUNT(DISTINCT IF(seamless = 1, order_id, NULL)) AS seamless_orders,
    COUNT(DISTINCT IF(seamless IN (0, 1), order_id, NULL))
      AS classified_orders
  FROM combination_order_rows
  GROUP BY cancellation_reason, undispatch_reason
)
SELECT
  p.start_date,
  p.end_date,
  r.row_type,
  r.cancellation_reason,
  r.undispatch_reason,
  r.orders,
  ROUND(100 * SAFE_DIVIDE(r.orders, t.total_orders), 2)
    AS share_of_total_orders_pct,
  IF(
    r.row_type = 'TOTAL_ORDERS',
    NULL,
    ROUND(100 * SAFE_DIVIDE(r.orders, t.awt_null_orders), 2)
  ) AS share_of_awt_null_orders_pct,
  r.seamless_orders,
  r.classified_orders,
  ROUND(100 * SAFE_DIVIDE(r.seamless_orders, r.classified_orders), 2)
    AS seamless_pct,
  ROUND(100 * SAFE_DIVIDE(r.classified_orders, r.orders), 2)
    AS classification_coverage_pct
FROM report_rows AS r
CROSS JOIN totals AS t
CROSS JOIN params AS p
ORDER BY
  r.sort_order,
  r.orders DESC,
  r.cancellation_reason,
  r.undispatch_reason;
