# Deployment Notes

The detailed operator runbook remains in `../DEPLOYMENT.md`. This page records
the stable deployment model that future restructuring must preserve.
Terraform root organization is documented in `../infra/README.md`.

## Deployment Contract

- One shared AWS stack.
- One Terraform state object.
- One ECS cluster.
- One app service.
- One Postgres database.
- Liquibase and worker run as one-off ECS tasks.
- Cloud-changing GitHub Actions jobs require manual confirmation.

Safe rollout is achieved inside the stack through additive migrations, immutable
images, ECS rolling deploys, runtime switches, and backfill tasks.

## Pipeline Shape

Application deployment:

1. Validate locally in GitHub Actions.
2. Build app, worker, and Liquibase images.
3. Scan images with Trivy.
4. Push immutable `sha-<commit>` tags to ECR.
5. Run Liquibase as a one-off ECS task.
6. Deploy the app ECS service.
7. Run the backfill worker as a one-off ECS task when needed.

Infrastructure deployment:

1. Run Terraform fmt, validate, tflint, and checkov.
2. Run Terraform plan on pull requests.
3. Apply manually through `workflow_dispatch`.

## Future Work

- Keep GitHub Actions as the primary CI/CD implementation.
- Add Bitbucket Pipelines notes as documentation only.
- Keep rollback checkpoints aligned with the migration phases in `../DEPLOYMENT.md`.
- Keep deployment scripts thin and visible. They should not become a hidden platform.
