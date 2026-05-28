package main

import rego.v1

workflow_dispatch_only := {
  "app-deploy.yml",
  "data-backfill.yml",
  "data-runtime-switch.yml",
  "data-schema-apply.yml",
  "data-support-deploy.yml",
  "infra-apply.yml",
}

pull_request_gated := {
  "app-build.yml",
  "infra-plan.yml",
  "security.yml",
  "semgrep.yml",
}

release_evidence_required := {
  "app-build.yml": "Upload build evidence",
  "app-deploy.yml": "Upload app deploy evidence",
  "data-backfill.yml": "Upload data backfill evidence",
  "data-runtime-switch.yml": "Upload data runtime switch evidence",
  "data-schema-apply.yml": "Upload data schema apply evidence",
  "data-support-deploy.yml": "Upload data support deploy evidence",
  "infra-apply.yml": "Upload infra apply evidence",
}

aws_environment_required := {
  "app-build.yml": "build-scan-push",
  "app-deploy.yml": "deploy",
  "data-backfill.yml": "run_backfill",
  "data-runtime-switch.yml": "switch_runtime",
  "data-schema-apply.yml": "apply_schema",
  "data-support-deploy.yml": "deploy_support",
  "infra-apply.yml": "apply",
}

deny contains msg if {
  file := data.conftest.file.name
  file in workflow_dispatch_only
  triggers := object.keys(workflow_triggers(input))
  count(triggers) != 1
  msg := sprintf("%s must use workflow_dispatch only", [file])
}

deny contains msg if {
  file := data.conftest.file.name
  file in workflow_dispatch_only
  not workflow_triggers(input).workflow_dispatch
  msg := sprintf("%s must declare workflow_dispatch", [file])
}

deny contains msg if {
  file := data.conftest.file.name
  file in pull_request_gated
  not workflow_triggers(input).pull_request
  msg := sprintf("%s must declare pull_request", [file])
}

deny contains msg if {
  file := data.conftest.file.name
  required_step := release_evidence_required[file]
  not workflow_has_step(input, required_step)
  msg := sprintf("%s must include step %q", [file, required_step])
}

deny contains msg if {
  file := data.conftest.file.name
  job_name := aws_environment_required[file]
  not job_uses_environment(input, job_name, "aws")
  msg := sprintf("%s job %q must use environment aws", [file, job_name])
}

deny contains msg if {
  some job_name, job in input.jobs
  some step in job.steps
  object.get(step, "continue-on-error", false)
  msg := sprintf("%s job %q step %q must not use continue-on-error", [
    data.conftest.file.name,
    job_name,
    object.get(step, "name", "<unnamed>"),
  ])
}

workflow_has_step(workflow, step_name) if {
  some _, job in workflow.jobs
  some step in job.steps
  step.name == step_name
}

job_uses_environment(workflow, job_name, environment_name) if {
  workflow.jobs[job_name].environment == environment_name
}

workflow_triggers(workflow) = triggers if {
  triggers := object.get(workflow, "on", null)
  triggers != null
} else = triggers if {
  triggers := object.get(workflow, true, null)
  triggers != null
}
