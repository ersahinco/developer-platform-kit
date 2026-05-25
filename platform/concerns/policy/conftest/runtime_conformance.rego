package main

import rego.v1

forbidden_workload_shape_keys := {
  "app_path",
  "database",
  "dapr",
  "image",
  "job",
  "kind",
  "metrics",
  "operational",
  "service",
  "traces",
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  not input.schema_version
  msg := "platform/runtime-conformance.json must declare schema_version"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  input.schema_version != "2"
  msg := "platform/runtime-conformance.json schema_version must be 2"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  not is_object(input.defaults)
  msg := "platform/runtime-conformance.json defaults must be an object"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  count(object.keys(input.defaults)) != 2
  msg := "platform/runtime-conformance.json defaults must contain only env and secrets"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  not object.get(input.defaults, "env", null)
  msg := "platform/runtime-conformance.json defaults must contain env"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  not object.get(input.defaults, "secrets", null)
  msg := "platform/runtime-conformance.json defaults must contain secrets"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  some key in object.keys(input.defaults)
  not key in {"env", "secrets"}
  msg := "platform/runtime-conformance.json defaults must contain only env and secrets"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  not is_object(input.workloads)
  msg := "platform/runtime-conformance.json workloads must be an object"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  some workload_name, _ in input.workloads
  workload_name == ""
  msg := "platform/runtime-conformance.json workload names must be non-empty"
}

deny contains msg if {
  data.conftest.file.name == "runtime-conformance.json"
  some workload_name, workload_fixture in input.workloads
  some key in object.keys(workload_fixture)
  key in forbidden_workload_shape_keys
  msg := sprintf(
    "runtime conformance fixture %q must not redefine workload field %q",
    [workload_name, key],
  )
}
