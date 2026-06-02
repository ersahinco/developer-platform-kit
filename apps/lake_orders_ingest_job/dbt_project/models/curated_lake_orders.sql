WITH raw_orders AS (
  SELECT
    CAST(order_id AS VARCHAR) AS order_id,
    CAST(customer_id AS VARCHAR) AS customer_id,
    CAST(order_ts AS TIMESTAMP) AS order_ts,
    CAST(updated_at AS TIMESTAMP) AS updated_at,
    CAST(status AS VARCHAR) AS status,
    CAST(amount AS DOUBLE) AS amount,
    CAST(source_file AS VARCHAR) AS source_file
  FROM read_parquet('{{ var("raw_parquet_path") }}')
),
deduplicated AS (
  SELECT
    order_id,
    customer_id,
    order_ts,
    updated_at,
    status,
    amount,
    source_file
  FROM (
    SELECT
      *,
      ROW_NUMBER() OVER (
        PARTITION BY order_id
        ORDER BY updated_at DESC, source_file DESC
      ) AS latest_record_rank
    FROM raw_orders
  )
  WHERE latest_record_rank = 1
)
SELECT
  order_id,
  customer_id,
  order_ts,
  CAST(order_ts AS DATE) AS order_date,
  updated_at,
  status,
  amount,
  ROW_NUMBER() OVER (
    PARTITION BY customer_id
    ORDER BY order_ts, order_id
  ) AS customer_order_sequence,
  SUM(amount) OVER (
    PARTITION BY customer_id
    ORDER BY order_ts, order_id
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS customer_running_amount,
  LAG(order_ts) OVER (
    PARTITION BY customer_id
    ORDER BY order_ts, order_id
  ) AS previous_order_ts,
  CAST(order_ts AS DATE) < CAST('{{ var("ingest_date") }}' AS DATE)
    AS is_late_arrival
FROM deduplicated
