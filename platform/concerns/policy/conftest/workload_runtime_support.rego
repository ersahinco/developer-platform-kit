package main

import rego.v1

deny contains msg if {
  data.conftest.file.name == "workload-runtime-support.json"
  input.schema_version != "1"
  msg := "platform/workload-runtime-support.json schema_version must be 1"
}

deny contains msg if {
  data.conftest.file.name == "workload-runtime-support.json"
  not is_object(input.targets)
  msg := "platform/workload-runtime-support.json targets must be an object"
}

deny contains msg if {
  data.conftest.file.name == "workload-runtime-support.json"
  some target, profile in input.targets
  object.keys(profile) != {"status", "supported_workloads", "admitted_workloads"}
  msg := sprintf("runtime support target %q has unexpected fields", [target])
}

deny contains msg if {
  data.conftest.file.name == "workload-runtime-support.json"
  some target, profile in input.targets
  some workload in profile.admitted_workloads
  not workload in profile.supported_workloads
  msg := sprintf("runtime %q admits workload %q without support", [target, workload])
}
