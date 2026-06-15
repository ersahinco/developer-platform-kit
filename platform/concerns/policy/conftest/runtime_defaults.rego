package main

import rego.v1

required_runtime_target_keys := {
  "defaults",
  "implementation",
  "maturity",
  "owner",
  "purpose",
  "role",
  "status",
}

runtime_target_maturity_levels := {
  "active-local-proof",
  "active-production-runtime",
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  input.schema_version != "1"
  msg := "platform/runtime-defaults.json schema_version must be 1"
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  not is_object(input.runtime_targets)
  msg := "platform/runtime-defaults.json runtime_targets must be an object"
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  count(input.runtime_targets) == 0
  msg := "platform/runtime-defaults.json must declare active runtime_targets"
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  not input.runtime_targets[input.current_runtime_target]
  msg := "platform/runtime-defaults.json current_runtime_target must name an active runtime target"
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  object.keys(profile) != required_runtime_target_keys
  msg := sprintf("runtime target %s must contain only status, owner, role, maturity, implementation, purpose, and defaults", [runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  profile.status != "active"
  msg := sprintf("runtime target %s status must be active", [runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  not profile.maturity in runtime_target_maturity_levels
  msg := sprintf("runtime target %s has unsupported maturity %s", [runtime_target, profile.maturity])
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  trim_space(profile.owner) == ""
  msg := sprintf("runtime target %s must declare owner", [runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  trim_space(profile.role) == ""
  msg := sprintf("runtime target %s must declare role", [runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  trim_space(profile.implementation) == ""
  msg := sprintf("runtime target %s must declare implementation", [runtime_target])
}

deny contains msg if {
  data.conftest.file.name == "runtime-defaults.json"
  some runtime_target, profile in input.runtime_targets
  trim_space(profile.purpose) == ""
  msg := sprintf("runtime target %s must declare purpose", [runtime_target])
}
