package main

import rego.v1

deny contains msg if {
  data.conftest.file.name == "workloads.json"
  not input.schema_version
  msg := "platform/workloads.json must declare schema_version"
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
  workload.kind == "service"
  not workload.service.port
  msg := sprintf("service workload %q must declare service.port", [workload.name])
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
