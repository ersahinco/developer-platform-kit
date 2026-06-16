package main

import rego.v1

known_runtime_targets := {"local-compose", "local-kubernetes", "aws-ecs"}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  not input.schema_version
  msg := "platform/workloads.json must declare schema_version"
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  input.schema_version != "8"
  msg := "platform/workloads.json schema_version must be 8"
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  not is_array(input.workloads)
  msg := "platform/workloads.json workloads must be an array"
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  count(input.workloads) == 0
  msg := "platform/workloads.json must declare at least one workload"
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.name
  msg := "every workload must declare name"
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.kind in {"service", "job"}
  msg := sprintf("workload %q kind must be service or job", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not is_array(workload.use_cases)
  msg := sprintf("workload %q use_cases must be an array", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  count(workload.use_cases) == 0
  msg := sprintf("workload %q must declare at least one use case", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.patterns
  msg := sprintf(
    "workload %q must not declare patterns; use operational.class and use_cases",
    [workload.name],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.owner
  msg := sprintf("workload %q must declare owner", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not regex.match("^[a-z0-9]+(-[a-z0-9]+)*$", workload.owner)
  msg := sprintf(
    "workload %q owner %q must use lowercase kebab-case",
    [workload.name, workload.owner],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  some use_case in workload.use_cases
  not regex.match("^[a-z0-9]+(-[a-z0-9]+)*$", use_case)
  msg := sprintf(
    "workload %q use case %q must use lowercase kebab-case",
    [workload.name, use_case],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not startswith(workload.app_path, "apps/")
  msg := sprintf("workload %q app_path must stay under apps/", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not is_array(workload.runtime.supported)
  msg := sprintf("workload %q runtime.supported must be an array", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  count(workload.runtime.supported) == 0
  msg := sprintf("workload %q must declare at least one supported runtime", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not is_array(workload.runtime.admitted)
  msg := sprintf("workload %q runtime.admitted must be an array", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  some runtime_target in workload.runtime.supported
  not runtime_target in known_runtime_targets
  msg := sprintf("workload %q declares unknown supported runtime %q", [workload.name, runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  some runtime_target in workload.runtime.admitted
  not runtime_target in known_runtime_targets
  msg := sprintf("workload %q declares unknown admitted runtime %q", [workload.name, runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  some runtime_target in workload.runtime.admitted
  not runtime_target in workload.runtime.supported
  msg := sprintf(
    "workload %q admits runtime %q without declaring support",
    [workload.name, runtime_target],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.operational.class
  msg := sprintf("workload %q must declare operational.class", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.image.repository
  msg := sprintf("workload %q must declare image.repository", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.image.package
  msg := sprintf("workload %q must declare image.package", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.image.command
  msg := sprintf("workload %q must declare image.command", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "service"
  not workload.operational.class in {"edge-service", "internal-service"}
  msg := sprintf(
    "service workload %q operational.class must be edge-service or internal-service",
    [workload.name],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "service"
  not workload.service.port
  msg := sprintf("service workload %q must declare service.port", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "service"
  not is_array(workload.metrics.required_names)
  msg := sprintf("service workload %q must declare metrics.required_names", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "service"
  count(workload.metrics.required_names) == 0
  msg := sprintf("service workload %q must declare at least one metrics.required_names entry", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "edge-service"
  not workload.edge.hostname_label
  msg := sprintf("edge-service workload %q must declare edge.hostname_label", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "edge-service"
  not workload.edge.hostname_label_convention
  msg := sprintf("edge-service workload %q must declare edge.hostname_label_convention", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "edge-service"
  not workload.edge.auth_mode
  msg := sprintf("edge-service workload %q must declare edge.auth_mode", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "edge-service"
  not workload.verification.profile
  msg := sprintf("edge-service workload %q must declare verification.profile", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "internal-service"
  is_object(workload.dapr)
  not workload.dapr.app_id
  msg := sprintf("internal-service workload %q with Dapr must declare dapr.app_id", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "internal-service"
  is_object(workload.dapr)
  not workload.dapr.pubsub_name
  msg := sprintf("internal-service workload %q with Dapr must declare dapr.pubsub_name", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.operational.class == "internal-service"
  is_object(workload.dapr)
  not workload.dapr.topic
  msg := sprintf("internal-service workload %q with Dapr must declare dapr.topic", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "job"
  not workload.operational.class in {"operator-job", "scheduled-job"}
  msg := sprintf(
    "job workload %q operational.class must be operator-job or scheduled-job",
    [workload.name],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "job"
  not workload.job.idempotency
  msg := sprintf("job workload %q must declare job.idempotency", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  workload.kind == "job"
  not workload.operational.trigger
  msg := sprintf("job workload %q must declare operational.trigger", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not workload.traces.supported in {true, false}
  msg := sprintf("workload %q traces.supported must be boolean", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not is_array(workload.config.env)
  msg := sprintf("workload %q config.env must be an array", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  not is_array(workload.config.secrets)
  msg := sprintf("workload %q config.secrets must be an array", [workload.name])
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  some forbidden in ["arn:", ".amazonaws.com", "aws_", "s3://"]
  walk_contains_string(workload, forbidden)
  msg := sprintf(
    "workload %q must not encode runtime value %q",
    [workload.name, forbidden],
  )
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  some workload in input.workloads
  forbidden := workload_choreography_key[_]
  walk_contains_key(workload, forbidden)
  msg := sprintf(
    "workload %q must not encode deployment choreography key %q",
    [workload.name, forbidden],
  )
}

workload_choreography_key contains "aws"
workload_choreography_key contains "ecs"
workload_choreography_key contains "terraform"
workload_choreography_key contains "workflow"
workload_choreography_key contains "cluster"
workload_choreography_key contains "subnet"
workload_choreography_key contains "security_group"
workload_choreography_key contains "task_definition"
workload_choreography_key contains "service_name"
workload_choreography_key contains "desired_count"
workload_choreography_key contains "cpu"
workload_choreography_key contains "memory"
workload_choreography_key contains "iam"
workload_choreography_key contains "role_arn"
workload_choreography_key contains "policy_arn"
workload_choreography_key contains "bucket"
workload_choreography_key contains "queue"
workload_choreography_key contains "topic_arn"
workload_choreography_key contains "load_balancer"
workload_choreography_key contains "target_group"
workload_choreography_key contains "schedule_expression"
workload_choreography_key contains "cron"

walk_contains_string(value, needle) if {
  some _, item in walk(value)
  is_string(item)
  contains(lower(item), lower(needle))
}

walk_contains_key(value, needle) if {
  some _, item in walk(value)
  is_object(item)
  _ = item[needle]
}
