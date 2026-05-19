################################################################################
# Workload inventory
#
# The platform contract remains the single inventory for workload identity,
# image repositories, and declared runtime config names. Terraform stays the
# AWS implementation layer by supplying runtime-specific values here.
################################################################################

locals {
  workload_contract = jsondecode(file("${path.module}/../../platform/workloads.json"))
  default_db_user   = "app"
  default_db_name   = "aws_sdlc_containers"

  workloads_by_name = {
    for workload in local.workload_contract.workloads : workload.name => workload
  }

  workload_log_group_names = {
    for name, workload in local.workloads_by_name :
    name => "/ecs/${local.name}/${workload.image.repository}"
  }

  api_otel_service_name = "${local.name}-api"

  workload_env_values = {
    api = merge(
      {
        DB_HOST                           = "127.0.0.1"
        DB_PORT                           = "5432"
        DB_USER                           = local.default_db_user
        DB_NAME                           = local.default_db_name
        ROLLOUT_DRILL_FAULT_MODE          = "off"
        ROLLOUT_DRILL_FAULT_PATHS         = "/ready"
        ROLLOUT_DRILL_FAULT_DELAY_SECONDS = "3"
        ROLLOUT_DRILL_FAULT_STATUS_CODE   = "503"
      },
      var.enable_adot_sidecar ? {
        OTEL_TRACES_ENABLED                = "true"
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "http://127.0.0.1:4318/v1/traces"
        OTEL_SERVICE_NAME                  = local.api_otel_service_name
        OTEL_DEPLOYMENT_ENVIRONMENT        = "aws"
      } : {},
      (!var.enable_adot_sidecar && var.otel_exporter_otlp_traces_endpoint != null) ? {
        OTEL_TRACES_ENABLED                = "true"
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = var.otel_exporter_otlp_traces_endpoint
        OTEL_SERVICE_NAME                  = local.api_otel_service_name
        OTEL_DEPLOYMENT_ENVIRONMENT        = "aws"
      } : {}
    )
    backfill_worker = {
      DB_HOST             = module.rds.db_instance_address
      DB_PORT             = tostring(module.rds.db_instance_port)
      DB_USER             = local.default_db_user
      DB_NAME             = local.default_db_name
      BACKFILL_BATCH_SIZE = tostring(var.backfill_batch_size)
      BACKFILL_SLEEP_MS   = "100"
    }
    data_export_job = {
      DB_HOST                = module.rds.db_instance_address
      DB_PORT                = tostring(module.rds.db_instance_port)
      DB_USER                = local.default_db_user
      DB_NAME                = local.default_db_name
      DATA_EXPORT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-data-hub"
      DATA_EXPORT_S3_BUCKET  = aws_s3_bucket.data_hub.bucket
    }
    order_event_consumer = {
      DB_HOST                  = module.rds.db_instance_address
      DB_PORT                  = tostring(module.rds.db_instance_port)
      DB_USER                  = local.default_db_user
      DB_NAME                  = local.default_db_name
      DAPR_HTTP_ENDPOINT       = "http://localhost:3500"
      ORDER_EVENTS_APP_PORT    = tostring(local.workloads_by_name["order_event_consumer"].service.port)
      ORDER_EVENTS_WORKER_MODE = "both"
      ORDER_EVENTS_PUBSUB_NAME = local.workloads_by_name["order_event_consumer"].dapr.pubsub_name
      ORDER_EVENTS_TOPIC       = local.order_events_topic_name
    }
  }

  workload_secret_values = {
    api = {
      DB_PASSWORD = "${module.rds.db_instance_master_user_secret_arn}:password::"
    }
    backfill_worker = {
      DB_PASSWORD = "${module.rds.db_instance_master_user_secret_arn}:password::"
    }
    data_export_job = {
      DB_PASSWORD = "${module.rds.db_instance_master_user_secret_arn}:password::"
    }
    order_event_consumer = {
      DB_PASSWORD = "${module.rds.db_instance_master_user_secret_arn}:password::"
    }
  }

  workload_environment = {
    for name, workload in local.workloads_by_name :
    name => [
      for env_name in workload.config.env : {
        name  = env_name
        value = tostring(local.workload_env_values[name][env_name])
      }
      if contains(keys(local.workload_env_values[name]), env_name)
    ]
  }

  workload_secrets = {
    for name, workload in local.workloads_by_name :
    name => [
      for secret_name in workload.config.secrets : {
        name      = secret_name
        valueFrom = local.workload_secret_values[name][secret_name]
      }
      if contains(keys(local.workload_secret_values[name]), secret_name)
    ]
  }
}
