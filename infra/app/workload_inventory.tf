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

  aws_admitted_workloads = [
    for workload in local.workload_contract.workloads : workload
    if contains(try(workload.runtime.admitted, []), "aws-ecs")
  ]

  workloads_by_name = {
    for workload in local.aws_admitted_workloads : workload.name => workload
  }

  workload_capabilities = {
    for name, workload in local.workloads_by_name :
    name => {
      edge_exposure       = try(workload.operational.exposure, null)
      edge_service        = workload.kind == "service" && workload.operational.class == "edge-service"
      internal_service    = workload.kind == "service" && workload.operational.class == "internal-service"
      scheduled_execution = workload.kind == "job" && workload.operational.class == "scheduled-job"
      operator_execution  = workload.kind == "job" && workload.operational.class == "operator-job"
      async_eventing      = can(workload.dapr)
      has_database        = can(workload.database)
      pooled_database     = try(workload.database.pooling == "transaction_pool", false)
      direct_database     = try(workload.database.pooling == "direct", false)
      tracing             = workload.traces.supported
    }
  }

  primary_edge_workload_name = one([
    for name, capabilities in local.workload_capabilities : name
    if capabilities.edge_service && capabilities.edge_exposure == "public"
  ])
  primary_edge_workload     = local.workloads_by_name[local.primary_edge_workload_name]
  primary_edge_repository   = local.primary_edge_workload.image.repository
  primary_edge_service_port = local.primary_edge_workload.service.port
  primary_async_eventing_workload_name = one([
    for name, capabilities in local.workload_capabilities : name
    if capabilities.async_eventing
  ])
  primary_async_eventing_dapr       = local.workloads_by_name[local.primary_async_eventing_workload_name].dapr
  primary_async_eventing_repository = local.workloads_by_name[local.primary_async_eventing_workload_name].image.repository
  primary_async_eventing_service_port = (
    local.workloads_by_name[local.primary_async_eventing_workload_name].service.port
  )
  primary_async_eventing_topic_name = "${local.name}-${local.primary_async_eventing_dapr.topic}"
  primary_async_eventing_pubsub_name = (
    local.primary_async_eventing_dapr.pubsub_name
  )
  trace_endpoint = (
    var.enable_adot_sidecar
    ? "http://127.0.0.1:4318/v1/traces"
    : var.otel_exporter_otlp_traces_endpoint
  )

  database_runtime_values_by_pooling = {
    transaction_pool = {
      DB_HOST = "127.0.0.1"
      DB_PORT = "5432"
    }
    direct = {
      DB_HOST = module.rds.db_instance_address
      DB_PORT = tostring(module.rds.db_instance_port)
    }
  }

  database_runtime_defaults = {
    DB_USER = local.default_db_user
    DB_NAME = local.default_db_name
  }

  workload_log_group_names = {
    for name, workload in local.workloads_by_name :
    name => "/ecs/${local.name}/${workload.image.repository}"
  }

  workload_log_configuration = {
    for name, stream_prefix in merge(
      {
        for workload_name, workload in local.workloads_by_name :
        workload_name => workload.image.repository
        if workload.kind == "job"
      },
      {
        (local.primary_async_eventing_workload_name) = local.primary_async_eventing_repository
      }
    ) :
    name => {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.workload_log_group_names[name]
        "awslogs-region"        = local.region
        "awslogs-stream-prefix" = stream_prefix
      }
    }
  }

  sidecar_log_configuration = {
    dapr_config_loader = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.workload_log_group_names[local.primary_async_eventing_workload_name]
        "awslogs-region"        = local.region
        "awslogs-stream-prefix" = "dapr-config-loader"
      }
    }
    daprd = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.workload_log_group_names[local.primary_async_eventing_workload_name]
        "awslogs-region"        = local.region
        "awslogs-stream-prefix" = "daprd"
      }
    }
  }

  workload_trace_env_overrides = {
    for name, workload in local.workloads_by_name :
    name => local.workload_capabilities[name].tracing && local.trace_endpoint != null ? {
      OTEL_TRACES_ENABLED                = "true"
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = local.trace_endpoint
      OTEL_SERVICE_NAME                  = "${local.name}-${workload.image.repository}"
      OTEL_DEPLOYMENT_ENVIRONMENT        = "aws"
    } : {}
  }

  workload_async_eventing_env_defaults = {
    for name, capabilities in local.workload_capabilities :
    name => capabilities.async_eventing ? {
      DAPR_HTTP_ENDPOINT = "http://localhost:3500"
      DAPR_HTTP_PORT     = "3500"
    } : {}
  }

  workload_static_env_overrides = {
    (local.primary_edge_workload_name) = {
      ROLLOUT_DRILL_FAULT_MODE          = "off"
      ROLLOUT_DRILL_FAULT_PATHS         = "/ready"
      ROLLOUT_DRILL_FAULT_DELAY_SECONDS = "3"
      ROLLOUT_DRILL_FAULT_STATUS_CODE   = "503"
    }
    backfill_worker = {
      BACKFILL_BATCH_SIZE = tostring(var.backfill_batch_size)
      BACKFILL_SLEEP_MS   = "100"
    }
    data_export_job = {
      DATA_EXPORT_OUTPUT_DIR = "/tmp/aws-sdlc-containers-data-hub"
      DATA_EXPORT_S3_BUCKET  = aws_s3_bucket.data_hub.bucket
    }
    (local.primary_async_eventing_workload_name) = {
      EVENT_CONSUMER_APP_PORT           = tostring(local.primary_async_eventing_service_port)
      EVENT_CONSUMER_WORKER_MODE        = "both"
      EVENT_CONSUMER_PUBSUB_NAME        = local.primary_async_eventing_pubsub_name
      EVENT_CONSUMER_TOPIC              = local.primary_async_eventing_topic_name
      EVENT_CONSUMER_RELAY_BATCH_SIZE   = "10"
      EVENT_CONSUMER_IDLE_SLEEP_SECONDS = "1"
    }
  }

  shared_secret_value_from = {
    DB_PASSWORD             = "${module.rds.db_instance_master_user_secret_arn}:password::"
    PRIMARY_EDGE_AUTH_TOKEN = local.primary_edge_auth_token_secret_arn
  }

  workload_env_values = {
    for name, workload in local.workloads_by_name :
    name => merge(
      local.workload_capabilities[name].has_database ? local.database_runtime_defaults : {},
      local.workload_capabilities[name].has_database ? try(local.database_runtime_values_by_pooling[workload.database.pooling], {}) : {},
      local.workload_trace_env_overrides[name],
      local.workload_async_eventing_env_defaults[name],
      lookup(local.workload_static_env_overrides, name, {})
    )
  }

  workload_secret_values = {
    for name, workload in local.workloads_by_name :
    name => {
      for secret_name in workload.config.secrets :
      secret_name => local.shared_secret_value_from[secret_name]
      if contains(keys(local.shared_secret_value_from), secret_name)
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
