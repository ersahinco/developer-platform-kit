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

required_adapter_seam_keys := {
  "adapter_seam",
  "capability",
  "contract_surface",
  "current_implementation",
  "runtime_seam",
  "runtime_target",
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
  object.get(input, "candidate_runtime_capabilities", []) != []
  not is_array(input.candidate_runtime_capabilities)
  msg := "platform/platform-inventory.json candidate_runtime_capabilities must be an array when present"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  some row in object.get(input, "candidate_runtime_capabilities", [])
  object.keys(row) != required_runtime_capability_keys
  msg := "every candidate runtime capability row must contain only capability, contract_surface, runtime_target, maturity, implementation, and replacement_seam"
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

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  some row in object.get(input, "candidate_runtime_capabilities", [])
  row.maturity != "candidate"
  msg := sprintf("candidate runtime capability %s/%s must have candidate maturity", [row.runtime_target, row.capability])
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  not is_array(input.adapter_seams)
  msg := "platform/platform-inventory.json adapter_seams must be an array"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  count(input.adapter_seams) == 0
  msg := "platform/platform-inventory.json must declare at least one adapter seam"
}

deny contains msg if {
  data.conftest.file.name == "platform-inventory.json"
  some row in input.adapter_seams
  object.keys(row) != required_adapter_seam_keys
  msg := "every adapter seam row must contain only capability, contract_surface, adapter_seam, runtime_target, current_implementation, and runtime_seam"
}
