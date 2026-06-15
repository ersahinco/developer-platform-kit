package main

import rego.v1

required_stable_center_keys := {
  "catalog_root",
  "platform_concerns_root",
  "workload_contract",
}

required_runtime_capability_keys := {
  "capability",
  "contract_surface",
  "implementation",
  "maturity",
  "replacement_seam",
  "runtime_target",
}

allowed_maturity_levels := {
  "candidate",
  "active-local-proof",
  "active-production-runtime",
  "deprecated",
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  not input.schema_version
  msg := "platform/platform-inventory.json must declare schema_version"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  input.schema_version != "1"
  msg := "platform/platform-inventory.json schema_version must be 1"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  not is_object(input.stable_center)
  msg := "platform/platform-inventory.json stable_center must be an object"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  object.keys(input.stable_center) != required_stable_center_keys
  msg := "platform/platform-inventory.json stable_center must contain only workload_contract, platform_concerns_root, and catalog_root"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  input.stable_center.workload_contract != "platform/workloads.json"
  msg := "platform/platform-inventory.json stable_center.workload_contract must be platform/workloads.json"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  input.stable_center.platform_concerns_root != "platform/concerns"
  msg := "platform/platform-inventory.json stable_center.platform_concerns_root must be platform/concerns"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  input.stable_center.catalog_root != "infra/catalog"
  msg := "platform/platform-inventory.json stable_center.catalog_root must be infra/catalog"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  not is_string(input.current_runtime_target)
  msg := "platform/platform-inventory.json current_runtime_target must be a string"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  trim_space(input.current_runtime_target) == ""
  msg := "platform/platform-inventory.json current_runtime_target must be non-empty"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  not is_array(input.runtime_capabilities)
  msg := "platform/platform-inventory.json runtime_capabilities must be an array"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  count(input.runtime_capabilities) == 0
  msg := "platform/platform-inventory.json must declare at least one runtime capability"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  some row in input.runtime_capabilities
  object.keys(row) != required_runtime_capability_keys
  msg := "every runtime capability row must contain only capability, contract_surface, runtime_target, maturity, implementation, and replacement_seam"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  object.get(input, "candidate_runtime_capabilities", null) != null
  msg := "platform/platform-inventory.json must not own candidate_runtime_capabilities; use platform/runtime-defaults.json"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  some row in input.runtime_targets
  not row.maturity in allowed_maturity_levels
  msg := sprintf("runtime target %s has unsupported maturity %s", [row.id, row.maturity])
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  some row in input.runtime_capabilities
  not row.maturity in allowed_maturity_levels
  msg := sprintf("runtime capability %s/%s has unsupported maturity %s", [row.runtime_target, row.capability, row.maturity])
}
