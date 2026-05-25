package main

import rego.v1

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  not input.schema_version
  msg := "platform/workloads.json must declare schema_version"
}

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  input.schema_version != "5"
  msg := "platform/workloads.json schema_version must be 5"
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

walk_contains_string(value, needle) if {
  some _, item in walk(value)
  is_string(item)
  contains(lower(item), lower(needle))
}
