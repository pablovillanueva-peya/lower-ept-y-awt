-- Comparacion diaria de Fiestas Patrias: 08-21 sep 2025 vs 08-13 sep 2026.
-- Alcance: Chile, Restaurants, ordenes no preorder y delivery primario.
-- HPT y AWT10 son atribuciones ponderadas y por eso sus numeradores pueden
-- ser decimales. Todas las fuentes se consolidan primero a nivel orden.

WITH params AS (
  SELECT
    DATE '2025-09-08' AS start_2025,
    DATE '2025-09-21' AS end_2025,
    DATE '2026-09-08' AS start_2026,
    DATE '2026-09-13' AS end_2026
),
calendar AS (
  SELECT comparison_date
  FROM params,
  UNNEST(
    ARRAY_CONCAT(
      GENERATE_DATE_ARRAY(start_2025, end_2025),
      GENERATE_DATE_ARRAY(start_2026, end_2026)
    )
  ) AS comparison_date
),
hdm_by_order AS (
  SELECT
    CAST(order_code AS STRING) AS order_id,
    MAX(SAFE_CAST(high_demand_mode.minutes_added AS FLOAT64))
      AS hdm_minutes_added
  FROM `fulfillment-dwh-production.curated_data_shared_vendor.growth_vendor_orders`
  CROSS JOIN params
  WHERE country_code = 'cl'
    AND high_demand_mode.is_hd_order IS TRUE
    AND requested_pickup_at IS NULL
    AND order_code IS NOT NULL
    AND (
      created_date BETWEEN DATE_SUB(start_2025, INTERVAL 1 DAY)
                       AND DATE_ADD(end_2025, INTERVAL 1 DAY)
      OR created_date BETWEEN DATE_SUB(start_2026, INTERVAL 1 DAY)
                          AND DATE_ADD(end_2026, INTERVAL 1 DAY)
    )
  GROUP BY order_id
),
classification_by_order AS (
  SELECT
    CAST(n.order_id AS STRING) AS order_id,
    IF(
      COUNT(DISTINCT SAFE_CAST(n.SEAMLESS AS INT64)) = 1,
      MAX(SAFE_CAST(n.SEAMLESS AS INT64)),
      NULL
    ) AS seamless,
    SUM(
      COALESCE(SAFE_CAST(n.TR_HIGH_PREP_TIME AS FLOAT64), 0.0)
      + COALESCE(
          SAFE_CAST(n.TR_HIGH_PREP_TIME_AND_DISTANCE AS FLOAT64),
          0.0
        ) / 2.0
      + COALESCE(
          SAFE_CAST(
            n.TR_HIGH_PREP_TIME_AND_DISTANCE_COMBINATION AS FLOAT64
          ),
          0.0
        ) / 2.0
    ) AS hpt_attributed_orders,
    SUM(
      IF(
        IFNULL(n.undispatch_reason, '') != 'Late Order Preparation',
        COALESCE(
          SAFE_CAST(n.TR_STAFFING_AND_PARTNER_PERFO AS FLOAT64),
          0.0
        ) / 2.0
        + COALESCE(
            SAFE_CAST(
              n.TR_STAFFING_RIDER_AND_PARTNER_PERFO AS FLOAT64
            ),
            0.0
          ) / 3.0
        + COALESCE(
            SAFE_CAST(n.TR_RIDER_AND_PARTNER_PERFO AS FLOAT64),
            0.0
          ) / 2.0
        + COALESCE(SAFE_CAST(n.TR_PARTNER_PERFO AS FLOAT64), 0.0),
        0.0
      )
    ) AS awt10_attributed_orders
  FROM `peya-delivery-and-support.automated_tables_reports.non_seamless_reasons` AS n
  CROSS JOIN params
  WHERE n.country_name = 'Chile'
    AND n.order_id IS NOT NULL
    AND (
      DATE(n.created_date_local) BETWEEN start_2025 AND end_2025
      OR DATE(n.created_date_local) BETWEEN start_2026 AND end_2026
    )
  GROUP BY order_id
),
orders AS (
  SELECT
    DATE(l.created_date_local) AS comparison_date,
    CAST(l.peya_order_id AS STRING) AS order_id,
    MAX(SAFE_DIVIDE(l.timings.avoidable_wait_time, 60.0)) AS awt_minutes,
    MAX(SAFE_DIVIDE(l.estimated_prep_time, 60.0)) AS ept_minutes,
    MAX(
      CASE
        WHEN l.food_is_ready_at IS NOT NULL
          AND l.created_at IS NOT NULL
          AND TIMESTAMP_DIFF(l.food_is_ready_at, l.created_at, SECOND) >= 0
        THEN SAFE_DIVIDE(
          TIMESTAMP_DIFF(l.food_is_ready_at, l.created_at, SECOND),
          60.0
        )
      END
    ) AS fir_minutes
  FROM `peya-bi-tools-pro.il_logistics.fact_logistic_orders` AS l
  CROSS JOIN params
  WHERE l.country_code = 'cl'
    AND l.peya_order_id IS NOT NULL
    AND l.is_preorder = FALSE
    AND LOWER(TRIM(l.vendor.vertical_type)) = 'restaurants'
    AND EXISTS (
      SELECT 1
      FROM UNNEST(l.deliveries) AS d
      WHERE d.is_primary = TRUE
    )
    AND (
      DATE(l.created_date_local) BETWEEN start_2025 AND end_2025
      OR DATE(l.created_date_local) BETWEEN start_2026 AND end_2026
    )
  GROUP BY comparison_date, order_id
),
order_level AS (
  SELECT
    o.*,
    c.seamless,
    COALESCE(c.hpt_attributed_orders, 0.0) AS hpt_attributed_orders,
    COALESCE(c.awt10_attributed_orders, 0.0) AS awt10_attributed_orders,
    h.hdm_minutes_added
  FROM orders AS o
  LEFT JOIN classification_by_order AS c USING (order_id)
  LEFT JOIN hdm_by_order AS h USING (order_id)
),
daily AS (
  SELECT
    comparison_date,
    COUNT(*) AS orders,
    COUNTIF(seamless = 1) AS seamless_orders,
    COUNTIF(seamless IN (0, 1)) AS classified_orders,
    COUNTIF(awt_minutes IS NOT NULL) AS awt_orders,
    AVG(awt_minutes) AS avg_awt_min,
    COUNTIF(hdm_minutes_added IS NOT NULL) AS hdm_orders,
    AVG(IF(hdm_minutes_added IS NOT NULL, hdm_minutes_added, NULL))
      AS avg_hdm_min,
    AVG(ept_minutes - COALESCE(hdm_minutes_added, 0.0))
      AS avg_ept_without_hdm_min,
    COUNTIF(ept_minutes IS NOT NULL) AS ept_orders,
    AVG(fir_minutes) AS avg_fir_min,
    COUNTIF(fir_minutes IS NOT NULL) AS fir_orders,
    SUM(hpt_attributed_orders) AS hpt_attributed_orders,
    SUM(awt10_attributed_orders) AS awt10_attributed_orders
  FROM order_level
  GROUP BY comparison_date
)
SELECT
  c.comparison_date AS date,
  EXTRACT(YEAR FROM c.comparison_date) AS year,
  EXTRACT(DAY FROM c.comparison_date) AS day,
  FORMAT_DATE('%a', c.comparison_date) AS weekday,
  COALESCE(d.orders, 0) AS orders,
  ROUND(100 * SAFE_DIVIDE(d.seamless_orders, d.classified_orders), 2)
    AS seamless_pct,
  ROUND(100 * SAFE_DIVIDE(d.classified_orders, d.orders), 2)
    AS classification_coverage_pct,
  ROUND(d.avg_awt_min, 2) AS awt_min,
  ROUND(100 * SAFE_DIVIDE(d.hdm_orders, d.orders), 2) AS hdm_pct,
  ROUND(d.avg_hdm_min, 2) AS hdm_min,
  ROUND(100 * SAFE_DIVIDE(d.hpt_attributed_orders, d.orders), 2)
    AS hpt_pct,
  ROUND(100 * SAFE_DIVIDE(d.awt10_attributed_orders, d.orders), 2)
    AS awt10_pct,
  ROUND(d.avg_ept_without_hdm_min, 2) AS ept_without_hdm_min,
  ROUND(d.avg_fir_min, 2) AS fir_min,
  d.seamless_orders,
  d.classified_orders,
  d.awt_orders,
  d.hdm_orders,
  d.ept_orders,
  d.fir_orders,
  ROUND(d.hpt_attributed_orders, 2) AS hpt_attributed_orders,
  ROUND(d.awt10_attributed_orders, 2) AS awt10_attributed_orders
FROM calendar AS c
LEFT JOIN daily AS d USING (comparison_date)
ORDER BY year, day;
