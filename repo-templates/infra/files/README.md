# __STACK_NAME__ infrastructure

Terraform root for `__STACK_NAME__`. Scaffolded from the developer platform kit `infra`
template. Modules come from `__TOOLKIT_REPOSITORY__` at `__TOOLKIT_REF__`.

## Owns

Network, ECR, ECS cluster, public load balancer, PostgreSQL, a data bucket, one
service per `services` entry, one migration task family per `data_pipelines`
entry, one Spark application, and the CI role.

It does not own which image is running. That is each repo's delivery workflow,
which is why the ECS service ignores `task_definition` here.

## Bootstrap, once

```bash
aws s3api create-bucket --bucket __STATE_BUCKET__ \
  --region __AWS_REGION__ --create-bucket-configuration LocationConstraint=__AWS_REGION__
aws s3api put-bucket-versioning --bucket __STATE_BUCKET__ \
  --versioning-configuration Status=Enabled
```

If the account has no GitHub OIDC provider, set `create_oidc_provider = true` on
`delivery_identity` and keep it true while this root owns that provider. Switching it off would
remove the managed resource. If moving ownership, use an explicit state migration.

## Local

```bash
terraform init -backend=false
terraform fmt -recursive
terraform validate
```

A real plan needs the backend and credentials, so run it through the workflow.

## Delivery

`.github/workflows/infra.yml`, calling the toolkit's infra lane.

| Trigger | Does |
|---|---|
| Pull request, push to main | fmt, validate, TFLint, Checkov, plan, comment the diff |
| Manual with `plan_run_id` and `confirm: apply` | Applies that plan |

Apply refuses a plan that failed, ran on another branch, or planned a commit
that is no longer head. If it refuses, re-plan.

## Wiring a repo to this stack

Terraform first, then the repo. The service or task family must exist before its
workflow can revise it.

| Output | Goes to | As |
|---|---|---|
| `ecs_cluster` | app and data repos | variable `ECS_CLUSTER` |
| `delivery_role_arn` | this infra repo's apply job only | repository secret `AWS_ROLE_ARN` |
| Existing limited planning role ARN | this infra repo's plan job only | repository secret `AWS_PLAN_ROLE_ARN` |
| `private_subnet_ids` | data repos | variable `PRIVATE_SUBNET_IDS` |
| `migration_security_group_ids["<pipeline>"]` | that data repo | variable `MIGRATION_SECURITY_GROUP_IDS` |
| `emr_application_id` | data repos | variable `EMR_APPLICATION_ID` |
| `emr_job_role_arn` | data repos | secret `EMR_JOB_ROLE_ARN` |
| `data_code_bucket` | data repos | variable `DATA_CODE_BUCKET` |

Bootstrap the first stack with an existing administrator session: initialize the
S3 backend, save a plan, review it, and apply that saved file. The workflow cannot
assume an IAM role that it has not created yet. Commit `.terraform.lock.hcl` after
initialization. The bucket creation example needs no LocationConstraint in us-east-1.
Enable bucket public-access blocking and use a private repository for saved plans,
which can contain sensitive values. Never attach plan artifacts to public issues.

The root intentionally requires a certificate before exposing HTTP publicly.
Set `certificate_arn`, or explicitly set `allow_public_http = true` for development.
Only one public service is supported until you add target groups and routing.

Create separate OIDC roles for the app and data repositories with their own
repository subjects and least-privilege policies. The infra role does not trust
those repos. Plan uses `AWS_PLAN_ROLE_ARN` and the `aws-plan` environment. Supply an
existing role with the read and state-lock permissions needed to plan; the sample
`delivery_identity` module is the apply role and does not provision this planning
role. Its trust subject is `repo:__REPOSITORY__:environment:aws-plan`.
Apply uses `AWS_ROLE_ARN` and `aws`, whose trust subject is
`repo:__REPOSITORY__:environment:aws`. Restrict `aws` to the default branch and
configure required reviewers in GitHub where supported. Fork PRs cannot use
cloud credentials and therefore cannot run a cloud-backed plan.

The stack creates billable networking, database, and load-balancer resources.
Delete unused module blocks and their corresponding variables/outputs before the
first plan. A service initially references `bootstrap`; build its image, then run
the app deploy mode. Do not expect healthy tasks until that first deployment.
