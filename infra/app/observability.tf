################################################################################
# Observability
#
# Cloud runtime observability is intentionally lean: ECS writes workload stdout
# to CloudWatch Logs, the API can send OTLP traces to a same-task ADOT sidecar,
# and the portable Prometheus/Loki/Tempo/Grafana learning surface stays local
# under observability/ instead of being reimplemented as ECS services.
################################################################################

locals {
  ecs_container_defaults = {
    environment    = []
    mountPoints    = []
    portMappings   = []
    systemControls = []
    volumesFrom    = []
  }

  default_adot_collector_config = trimspace(<<-YAML
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318
      prometheus:
        config:
          scrape_configs:
            - job_name: app
              metrics_path: /metrics
              static_configs:
                - targets: ["127.0.0.1:8000"]
    exporters:
      debug:
        verbosity: basic
    service:
      pipelines:
        metrics:
          receivers: [prometheus]
          exporters: [debug]
        traces:
          receivers: [otlp]
          exporters: [debug]
  YAML
  )

  adot_collector_container = var.enable_adot_sidecar ? {
    adot = {
      name      = "adot"
      image     = var.adot_collector_image
      essential = true
      command   = ["--config=env:ADOT_COLLECTOR_CONFIG"]

      environment = [
        { name = "AWS_REGION", value = local.region },
        { name = "ADOT_COLLECTOR_CONFIG", value = coalesce(var.adot_collector_config, local.default_adot_collector_config) },
      ]

      portMappings = [
        { containerPort = 4317, hostPort = 4317, protocol = "tcp" },
        { containerPort = 4318, hostPort = 4318, protocol = "tcp" },
      ]
      systemControls = []
      volumesFrom    = []

      readonlyRootFilesystem = false

      enable_cloudwatch_logging              = true
      cloudwatch_log_group_retention_in_days = 14
      cloudwatch_log_group_kms_key_id        = aws_kms_key.cloudwatch_logs.arn
      cloudwatch_log_group_name              = "/ecs/${local.name}/adot"
    }
  } : {}
}
