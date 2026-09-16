-- Detalle de ordenes con AWT NULL, con non_seamless_reasons expandido.
-- No crea categorias ni metricas. Una orden puede ocupar varias filas cuando
-- existen varios registros en non_seamless_reasons.

WITH params AS (
  SELECT DATE '2026-08-01' AS start_date, DATE '2026-08-31' AS end_date
),
logistics_order_level AS (
  SELECT
    l.order_sk AS logistics_order_sk,
    l.peya_order_id,
    l.platform_order_id,
    l.platform_order_code,
    l.created_date_local,
    l.created_at,
    l.order_status,
    l.is_preorder,
    l.city.city_name AS city_name,
    l.vendor.id AS vendor_id,
    l.vendor.vendor_code,
    l.vendor.name AS vendor_name,
    l.vendor.vertical_type,
    l.cancellation.source AS cancellation_source,
    l.cancellation.performed_by AS cancellation_performed_by,
    l.cancellation.reason AS cancellation_reason,
    d.delivery_sk,
    d.delivery_id,
    d.created_at AS delivery_created_at,
    d.delivery_status,
    d.delivery_reason,
    d.delivery_completed,
    d.delivery_cancelled,
    d.is_primary,
    d.is_returning,
    d.is_redelivery,
    d.is_stacked,
    d.is_stacked_intravendor,
    l.sent_to_vendor_at,
    l.vendor_accepted_at,
    d.rider_dispatched_at,
    d.rider_notified_at,
    d.rider_accepted_at,
    d.rider_near_restaurant_at,
    d.rider_picked_up_at,
    d.rider_near_customer_at,
    d.rider_dropped_off_at,
    l.timings.avoidable_wait_time,
    l.estimated_prep_time,
    l.estimated_prep_buffer,
    l.timings.at_vendor_time,
    l.timings.at_vendor_time_cleaned,
    l.timings.vendor_late,
    l.timings.rider_late,
    l.timings.order_delay,
    l.timings.vendor_arriving_time,
    l.timings.vendor_leaving_time,
    l.timings.assumed_actual_preparation_time
  FROM `peya-bi-tools-pro.il_logistics.fact_logistic_orders` AS l
  CROSS JOIN params AS p
  CROSS JOIN UNNEST(l.deliveries) AS d
  WHERE l.country_code = 'cl'
    AND l.peya_order_id IS NOT NULL
    AND l.is_preorder = FALSE
    AND COALESCE(LOWER(TRIM(l.vendor.vertical_type)), '') != 'darkstores'
    AND DATE(l.created_date_local) BETWEEN p.start_date AND p.end_date
    AND d.is_primary = TRUE
    AND l.timings.avoidable_wait_time IS NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY l.peya_order_id
    ORDER BY l.created_at DESC, d.created_at DESC, d.delivery_id DESC
  ) = 1
),
non_seamless_raw AS (
  SELECT
    n.*
  FROM `peya-delivery-and-support.automated_tables_reports.non_seamless_reasons` AS n
  CROSS JOIN params AS p
  WHERE n.country_name = 'Chile'
    AND n.order_id IS NOT NULL
    AND DATE(n.created_date_local) BETWEEN p.start_date AND p.end_date
)
SELECT
  l.*,
  n.created_date_local AS non_seamless_created_date_local,
  n.SEAMLESS,
  n.is_slow_order,
  n.is_late_order,
  n.is_session_order,
  n.is_rejected_order,
  n.is_forced_preorder,
  n.is_modified_order,
  n.actual_delivery_time,
  n.is_time_related_failrate,
  n.reject_reason,
  n.accionador_level1,
  n.inaccuracy_reason,
  n.undispatch_reason,
  n.staffing_affection_minutes,
  n.undispatch_impact,
  n.awt_impact,
  n.eta_too_long_causals,
  n.contact_reason_l2,
  n.is_time_related_session,
  n.modification_detailed_reason
FROM logistics_order_level AS l
LEFT JOIN non_seamless_raw AS n
  ON n.order_id = l.peya_order_id
ORDER BY l.created_date_local, l.peya_order_id;
