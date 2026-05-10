# Observability Plan

Prometheus, Loki, Tempo, and Grafana are the preferred observability target for
this project. CloudWatch remains active for AWS-native logs and alarms while
the Grafana stack dual-runs.

For the shortest operator path from a local request to AWS edge, ECS workloads,
database rows, downstream events, and S3 objects, use
[Operator Observability Map](operator-observability-map.md).

Grafana intentionally uses Loki for workload logs, Prometheus for application
and observability-stack metrics, and Tempo for API traces. It does not provision
the CloudWatch datasource by default. Parity means app-owned signals are emitted
or shipped to both AWS-native and portable Grafana-stack backends where
practical; Grafana should not depend on CloudWatch queries to be useful.

## Current State

- Application liveness endpoint exists at `/health`.
- Application readiness endpoint exists at `/ready` and checks database
  connectivity separately from process liveness.
- Application metrics endpoint exists at `/metrics`.
- HTTP responses include an `X-Request-ID` header, preserving a caller-supplied
  value when present or generating one when absent.
- App and task logs are emitted through ECS and Docker.
- Successful `/health` and `/metrics` access logs are suppressed at the API
  logger because they are high-volume probe/scrape noise. Non-2xx responses
  still pass through.
- Terraform creates CloudWatch log groups for ECS workloads.
- ECS workloads can dual-ship logs through FireLens to CloudWatch Logs and the
  private Loki service when the optional observability stack is enabled.
- The API can emit OpenTelemetry traces over OTLP/HTTP to self-hosted Tempo.
  Successful `/health` and `/metrics` requests are excluded from tracing by
  default so Tempo is not dominated by probe/scrape traffic.
- App and observability service metrics are scraped by Prometheus for Grafana.
  AWS-native ALB, RDS, SQS, Scheduler, and alarm-state metrics remain in
  CloudWatch unless an explicit metric fan-out is added.
- Terraform creates a CloudWatch alarm for EventBridge Scheduler target
  delivery failures on the scheduled data export job.
- Terraform creates a CloudWatch Logs metric filter that counts successful data
  export manifest log lines.
- Terraform creates a CloudWatch alarm when no successful data export is
  observed for two daily evaluation windows.
- Terraform creates a CloudWatch alarm for unhealthy ALB targets behind the app
  service.
- Terraform creates CloudWatch alarms for app target 5xx responses and elevated
  target response time behind the ALB.
- Long-running ECS services use native ECS deployment circuit breaker rollback.
  The app ECS service also uses ECS deployment CloudWatch alarms for app target
  5xx and latency rollback practice. The app rolling deployment keeps a
  five-minute bake window so delayed ALB latency datapoints can still trigger
  ECS rollback.
- Terraform creates CloudWatch alarms for RDS CPU, free storage, and database
  connection pressure.
- Terraform creates a CloudWatch alarm when the order events DLQ has visible
  messages.
- Local Prometheus, Loki, Tempo, Promtail, and Grafana run through the optional
  `observability` Docker Compose profile.

## CloudWatch Inventory

CloudWatch Logs are intentionally limited to the stack-scoped
`/ecs/aws-sdlc-containers/*` groups below. These names are part of the Terraform
contract and are tested by `tests/contracts/test_observability_contract.py`; a
log group with the same prefix that is not listed here should be treated as
stale until proven otherwise.

Grafana does not read CloudWatch log groups directly. The equivalent Grafana
experience is backed by Loki labels: FireLens adds a `log_group` label whose
value mirrors the CloudWatch log group name. The provisioned
`AWS SDLC Containers / Log Groups` dashboard uses that label to provide a
CloudWatch-like group list and raw log view without adding a Grafana CloudWatch
datasource.

| Log group | Writer | Grafana-stack twin | Freshness expectation |
|---|---|---|---|
| `/ecs/aws-sdlc-containers/app` | API container through FireLens | Loki labels `service="app",container="app"` | Always-on; recent events expected. |
| `/ecs/aws-sdlc-containers/pgbouncer` | PgBouncer sidecar through FireLens | Loki labels `service="pgbouncer",container="pgbouncer"` | Always-on; recent events expected when the app is running. |
| `/ecs/aws-sdlc-containers/order-event-consumer` | Order event relay/consumer through FireLens | Loki labels `service="order-event-consumer"` | Always-on; recent events expected. |
| `/ecs/aws-sdlc-containers/firelens` | Log-router container through `awslogs` | CloudWatch-only router diagnostics | Always-on when FireLens is deployed. |
| `/ecs/aws-sdlc-containers/grafana` | Grafana process and config-loader logs | Loki labels `service="grafana"` for the Grafana container | Always-on when the optional stack is enabled. |
| `/ecs/aws-sdlc-containers/loki` | Loki process and config-loader logs | Loki labels `service="loki"` for the Loki container | Always-on when the optional stack is enabled. |
| `/ecs/aws-sdlc-containers/prometheus` | Prometheus process and config-loader logs | Loki labels `service="prometheus"` for the Prometheus container | Always-on when the optional stack is enabled. |
| `/ecs/aws-sdlc-containers/tempo` | Tempo process and config-loader logs | Loki labels `service="tempo"` for the Tempo container | Always-on when the optional stack is enabled. |
| `/ecs/aws-sdlc-containers/data-export-job` | Scheduled data export task through FireLens, or `awslogs` before the optional stack starts | Loki labels `service="data-export-job"` | Batch; recent events follow the schedule, not a continuous freshness check. |
| `/ecs/aws-sdlc-containers/liquibase` | One-off migration task through FireLens, or `awslogs` before the optional stack starts | Loki labels `service="liquibase"` | One-off; old events are expected between migrations. |
| `/ecs/aws-sdlc-containers/worker` | One-off backfill worker through FireLens, or `awslogs` before the optional stack starts | Loki labels `service="worker"` | One-off; old events are expected between backfills. |

The FireLens router's own diagnostics group, `/ecs/aws-sdlc-containers/firelens`,
is CloudWatch-only. The router can report its own startup and delivery problems
there, while every routed workload and observability-service container receives
the matching Loki `log_group` label.

CloudWatch metrics remain AWS-native for platform and managed-service signals.
Prometheus is the Grafana-stack metrics backend for app-owned `/metrics` and
observability component metrics; CloudWatch is not provisioned as a Grafana
datasource.

| CloudWatch namespace | Metric names used by this stack | Terraform consumer | Grafana-stack twin |
|---|---|---|---|
| `AWS/ApplicationELB` | `UnHealthyHostCount`, `HTTPCode_Target_5XX_Count`, `TargetResponseTime` | App health, 5xx, and latency alarms | Prometheus app `/metrics` counters/histograms and dashboard panels. |
| `AWS/RDS` | `CPUUtilization`, `FreeStorageSpace`, `DatabaseConnections` | RDS pressure alarms | Readiness failures and request latency in Prometheus; RDS metrics stay CloudWatch-native until a metrics exporter is added. |
| `AWS/SQS` | `ApproximateNumberOfMessagesVisible` on the order events DLQ | Order event DLQ alarm | Dapr relay/consume JSON logs in Loki and the `App Overview` worker outcomes panel. |
| `AWS/Scheduler` | `TargetErrorCount` for the default schedule group | Data export scheduler delivery alarm | Data export job logs in Loki; add job metrics before removing the CloudWatch alarm. |
| `aws-sdlc-containers/DataExport` | `SuccessCount` from the data export success log metric filter | Data export freshness alarm | Data export success logs in Loki; durable Grafana freshness needs a job metric or Loki ruler path. |
| `ECS/ContainerInsights` | Cluster, service, and task utilization/count metrics for app and observability services | Inspection and AWS-native troubleshooting | Prometheus scrapes app, Prometheus, Loki, and Tempo runtime metrics for Grafana. |
| `AWS/WAFV2` | Allowed/blocked/sampled request metrics for the public Web ACL | AWS-native edge security inspection | No Grafana twin by default. |

## Local Stack

Start the app first, then start the observability profile:

```bash
docker compose build app
docker compose up -d app
make observability
```

Open:

| Tool | URL |
|---|---|
| App liveness | `http://localhost:8000/health` |
| App readiness | `http://localhost:8000/ready` |
| App metrics | `http://localhost:8000/metrics` |
| Prometheus | `http://localhost:9090` |
| Loki | `http://127.0.0.1:3100/ready` |
| Tempo | `http://localhost:3200` |
| Grafana | `http://127.0.0.1:3000` |

Grafana credentials default to `admin` / `admin` and can be overridden through
`.env`. The provisioned dashboard is `AWS SDLC Containers / App Overview`.

The local stack contains:

- Prometheus scraping the app `/metrics` endpoint.
- Prometheus scraping its own runtime metrics and Loki runtime metrics, enabling
  upstream/community component dashboards when imported.
- Prometheus loading local app alert rules from
  `observability/prometheus/rules/`.
- Loki storing local container logs.
- Promtail reading Docker container logs through the Docker socket and applying
  the same `stack`, `environment`, `service`, and `container` labels used in
  AWS.
- Tempo storing local OTLP traces from the API when `OTEL_TRACES_ENABLED=true`.
  The app defaults `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` to `/health,/metrics`;
  set it explicitly if a drill needs probe/scrape traces.
- Grafana data sources and dashboard provisioning, including a readiness-failure
  stat for `/ready` 5xx responses and a `Log Groups` dashboard for
  Loki-backed CloudWatch-like log browsing.

Community Grafana dashboards are a good fit for standard components such as
Prometheus, Loki, and Grafana itself. When a community dashboard becomes part of
the project contract, commit the provisioned JSON under
`observability/grafana/dashboards/` and let the AWS stack reuse it.

Promtail requires read-only access to `/var/run/docker.sock`, so the
observability profile is opt-in and not started by default.

Distributed tracing uses OpenTelemetry in the API and self-hosted Tempo in both
local Compose and the optional ECS observability stack. X-Ray is intentionally
not part of this path. `/ready`, admin endpoints, order requests, and database
spans remain traced; `/health` and `/metrics` are excluded by default because
they create high-volume low-diagnostic spans during normal operation.

## AWS Extension

The first AWS-native signal is intentionally small: a CloudWatch alarm watches
`AWS/Scheduler` `TargetErrorCount` for the default schedule group, where the
stack currently has one scheduled job. Its runbook is
[Data Export Job Failure](runbooks/data-export-job-failure.md).
The data export job also emits a JSON manifest on success; a CloudWatch Logs
metric filter turns that log line into the custom
`aws-sdlc-containers/DataExport` `SuccessCount` metric. A freshness alarm uses
that metric and fires after two consecutive daily evaluation windows without a
successful export, which avoids paging on small schedule delays.

The app service health signal watches the ALB target group's
`UnHealthyHostCount` metric. Its runbook is
[App Service Unhealthy](runbooks/app-service-unhealthy.md).

The app edge symptom signals watch target-generated 5xx responses and p95 target
response time. Their runbook is
[App Edge Errors Or Latency](runbooks/app-edge-errors-latency.md).
The local Grafana dashboard also surfaces `/ready` 5xx responses separately so
operators can distinguish dependency-readiness symptoms from general request
traffic before following the app or RDS runbooks. Rehearse this path with
[App Dependency Readiness Drill](drills/app-dependency-readiness.md).
Prometheus also loads local alert rules for readiness failures, app request 5xx
symptoms, and p95 request latency so the same `/metrics` contract can back local
Grafana-stack alerting before any CloudWatch app-level reduction.

The RDS pressure signals watch `CPUUtilization`, `FreeStorageSpace`, and
`DatabaseConnections`. Their runbook is [RDS Pressure](runbooks/rds-pressure.md).

The async order event signal watches visible messages in the SQS DLQ for
`order.created.v1`. Its runbook is
[Order Event Queue Failure](runbooks/order-event-queue-failure.md). The default
relay path runs in the Dapr-enabled `order-event-consumer` service, so `App
Overview` uses Loki JSON log events from that service for the order event worker
outcomes panel.

## Delivery Tests

Static CI coverage lives in `tests/contracts/test_observability_contract.py`
and checks:

- Every expected workload and observability service has both a CloudWatch Logs
  and Loki FireLens output with a CloudWatch-mirroring `log_group` label.
- Terraform declares only the expected stack log groups under
  `/ecs/aws-sdlc-containers/*`.
- Grafana provisions Prometheus, Loki, and Tempo only; it does not depend on a
  CloudWatch datasource.
- Grafana provisions the `Log Groups` dashboard from the same S3-backed
  dashboard path as `App Overview`.
- API traces point at Tempo and no X-Ray path is configured.
- Prometheus scrapes the app plus Prometheus, Loki, and Tempo runtime metrics.

Helper-script behavior is covered in
`tests/scripts/test_observability_scripts.py`, keeping AWS/Loki client fakes and
bounded cloud-probe behavior separate from static Terraform/dashboard
contracts.

Live delivery verification is available after deployment:

```bash
make observability-delivery-verify
```

By default this verifies the CloudWatch log-group inventory, rejects unexpected
stack-prefixed log groups, checks retention on every expected group, and checks
recent CloudWatch events for the always-on groups. Batch groups
`data-export-job`, `liquibase`, and `worker` are inventoried but excluded from
the default freshness check because old streams are normal between scheduled or
manual runs.

To verify Loki as well, open a private path to Loki or Grafana's network and set
`LOKI_URL`:

```bash
make loki-tunnel
LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify
```

Useful overrides:

| Environment variable | Purpose |
|---|---|
| `CLOUDWATCH_LOG_FRESHNESS_SECONDS` | Recent-event window for always-on CloudWatch log groups. Defaults to `86400`. |
| `CLOUDWATCH_FRESH_LOG_GROUPS` | Comma-separated suffixes to freshness-check, for example `app,pgbouncer,order-event-consumer`. |
| `LOKI_URL` | Enables Loki `log_group` inventory and delivery checks through `/loki/api/v1/series` and `/loki/api/v1/query_range`. |
| `LOKI_LABEL_LOOKBACK_SECONDS` | Lookback window for expected Loki `log_group` labels. Defaults to `2592000`. |
| `LOKI_FRESH_LOG_GROUPS` | Comma-separated log-group suffixes to freshness-check in Loki. Defaults to `app,loki`; add quiet or batch groups after generating representative traffic for them. |

Loki label values are observed from existing streams, not declared like
CloudWatch log groups. A quiet service may be selectable in the Grafana Log
Groups dashboard but absent from Loki's `label/log_group/values` response until
it emits at least one post-rollout line. The live verifier therefore hard-fails
only when no `log_group` labels are observed at all, or when a freshness-checked
group has no recent lines.

To generate a small amount of representative cloud traffic from a developer
machine:

```bash
make observability-cloud-traffic
```

This target has two phases. First, it reads the API bearer token from Secrets
Manager unless `TOKEN` or `AUTH_TOKEN` is already set. It performs readiness and
mode reads, discovers an existing customer, and if the deployed dataset is empty
it calls the idempotent `POST /admin/observability-fixture` endpoint to create a
single `Observability Smoke Customer`. It then creates a few orders, reads those
orders back, triggers one controlled order 404, and fetches `/metrics`.

Second, it runs bounded cloud probes for quiet log groups:

- `worker`: starts the latest worker task with `BACKFILL_MAX_BATCHES=1`.
- `data-export-job`: starts one export task with an `observability-smoke-*`
  run id.
- `liquibase`: starts the latest Liquibase task with the read-only `status`
  command, not `update`.
- `prometheus` and `tempo`: force-roll the services so startup logs are emitted
  with the current FireLens labels.

The combined run is intentionally small but should make these surfaces visible
shortly after Prometheus and Loki refresh:

- App access logs in the `Log Groups` dashboard under
  `/ecs/aws-sdlc-containers/app`.
- Request rate, latency, and readiness panels in `App Overview`.
- Order event relay/consumer logs under
  `/ecs/aws-sdlc-containers/order-event-consumer` after the async worker relays
  and consumes the created orders.

Useful overrides:

| Environment variable | Purpose |
|---|---|
| `BASE_URL` | API base URL. Defaults to `https://api.ersahinco-sandbox.eu` through the Make target. |
| `CUSTOMER_ID` | Exact existing customer used for order creation. When unset, the script probes candidates instead. |
| `CUSTOMER_ID_CANDIDATES` | Comma-separated customer ids to probe when `CUSTOMER_ID` is unset. Defaults to `1..200`. |
| `ORDER_COUNT` | Number of orders to create. Defaults to `3`; max `20`. |
| `OBSERVABILITY_CLOUD_JOB_TARGETS` | Comma-separated cloud probe targets. Defaults to `worker,data-export-job,liquibase,prometheus,tempo`. |
| `OBSERVABILITY_RESTART_QUIET_DAEMONS` | Whether the cloud probe phase force-rolls Prometheus and Tempo. Defaults to `true`. |
| `OBSERVABILITY_TASK_WAIT_TIMEOUT_SECONDS` | Max wait for each one-off ECS probe task. Defaults to `300`. |
| `BACKFILL_MAX_BATCHES` | Worker probe batch limit. Defaults to `1`. |

To run only the quiet cloud log-group probes:

```bash
make observability-cloud-jobs
```

After this target finishes, include the exercised groups in the Loki freshness
check. Keep `grafana` out unless you have just rolled or otherwise exercised the
Grafana service; it can be legitimately quiet in Loki.

```bash
LOKI_FRESH_LOG_GROUPS=app,loki,order-event-consumer,pgbouncer,worker,data-export-job,liquibase,prometheus,tempo \
LOKI_URL=http://127.0.0.1:3100 \
make observability-delivery-verify
```

The traffic job depends on the current API image containing
`POST /admin/observability-fixture`. Build, scan, and push the app image through
the App Build workflow, then deploy the reviewed immutable `sha-*` tag through
the App Deploy workflow.

## Optional ECS Grafana Stack

`infra/app` contains an opt-in ECS/Fargate Grafana, Loki, Tempo, and Prometheus stack.
It is app-owned, disabled by the variable default, and enabled for this sandbox
through `infra/app/stack.tfvars`. It reuses the local dashboard, datasource,
and Prometheus rule files from `observability/`.
AWS-specific templates under `infra/app/templates/observability/` adapt only
the parts that differ in ECS, such as Cloud Map service names and S3-backed
Loki/Tempo storage.

In ECS, Loki log chunks/index data and Tempo trace blocks use the existing
observability S3 bucket. Grafana provisioning assets are also loaded from that
bucket at task startup. Prometheus uses task-local TSDB storage in this sandbox;
durable S3-backed metrics would require adding a metrics store such as Thanos
or Mimir, not a Grafana CloudWatch datasource.

Enable it only after the app images have been pushed and the base app services
are healthy:

```bash
aws secretsmanager create-secret \
  --name aws-sdlc-containers/grafana-admin \
  --secret-string '<strong-password>' \
  --region eu-central-1

terraform -chdir=infra/app apply \
  -var-file=stack.tfvars
```

The stack is private inside the VPC. Use the SSM/ECS Exec Grafana tunnel:

```bash
make grafana-tunnel
```

Then open `http://127.0.0.1:3000`. Do not make Grafana public as the default.
Use `make loki-tunnel` in a second terminal when running live Loki delivery
checks from a developer machine. Loki tunneling depends on ECS Exec being
enabled on the Loki service and `ssmmessages` permissions on the Loki task role;
run the app Terraform apply after changing this configuration before expecting
the tunnel to connect.

### ECS App-Layer Smoke

Use this flow after a deploy when you want to prove the application layer is
emitting useful logs, metrics, and traces into the private ECS Grafana stack.

1. Verify the deployed app surface first:

   ```bash
   make post-deploy-verify
   ```

2. Open Grafana through the private ECS Exec tunnel:

   ```bash
   make grafana-tunnel
   ```

   Keep that command running and open `http://127.0.0.1:3000`.

3. Generate representative app-layer traffic:

   ```bash
   make observability-cloud-traffic
   ```

   This exercises `/ready`, admin mode reads, customer lookup, order creation,
   order readback, a controlled order 404, `/metrics`, the order event consumer,
   and bounded one-off workload probes.

4. In Grafana, use `AWS SDLC Containers / App Overview` for Prometheus-backed
   app metrics. The request rate, latency, readiness, and order-event panels
   should move within the dashboard refresh window.

5. Use `AWS SDLC Containers / Log Groups` for Loki-backed logs. Start with
   `/ecs/aws-sdlc-containers/app`, then check
   `/ecs/aws-sdlc-containers/order-event-consumer` after order traffic has had
   time to relay and consume. Use Explore for ad hoc LogQL:

   ```logql
   {stack="aws-sdlc-containers", log_group="/ecs/aws-sdlc-containers/app"}
   ```

   ```logql
   {stack="aws-sdlc-containers", service="app"} |~ "(?i)error|exception|failed"
   ```

6. Use the `Tempo` datasource in Grafana Explore to search for service
   `aws-sdlc-containers-api`. `/ready`, admin endpoints, order requests, and
   SQLAlchemy spans should appear when `OTEL_TRACES_ENABLED=true` is deployed.
   `/health` and `/metrics` are intentionally excluded from tracing by default.

7. For a machine-readable delivery check, open the Loki tunnel in a second
   terminal and run the verifier:

   ```bash
   make loki-tunnel
   ```

   ```bash
   LOKI_URL=http://127.0.0.1:3100 make observability-delivery-verify
   ```

For deeper freshness checks after `make observability-cloud-traffic`, include
the quiet groups that the traffic helper exercised. Keep `grafana` out unless
you have just rolled or otherwise exercised the Grafana service; it can be
legitimately quiet in Loki.

```bash
LOKI_FRESH_LOG_GROUPS=app,loki,order-event-consumer,pgbouncer,worker,data-export-job,liquibase,prometheus,tempo \
LOKI_URL=http://127.0.0.1:3100 \
make observability-delivery-verify
```

The same Loki label contract is used locally and in AWS. In AWS, `log_group`
matches the CloudWatch log group name; locally, Promtail maps the Docker Compose
service to the same `/ecs/aws-sdlc-containers/<service>` shape:

- `stack`: `aws-sdlc-containers`.
- `environment`: `local` or `aws`.
- `service`: app or workload name.
- `container`: container name.
- `log_group`: CloudWatch-like group name, for example
  `/ecs/aws-sdlc-containers/app`.

AWS and local LogQL examples:

```logql
{stack="aws-sdlc-containers", service="app", container="app"}
```

```logql
{stack="aws-sdlc-containers", log_group="/ecs/aws-sdlc-containers/app"}
```

```logql
{stack="aws-sdlc-containers", service="pgbouncer", container="pgbouncer"}
```

```logql
{stack="aws-sdlc-containers", service="data-export-job"}
```

```logql
{stack="aws-sdlc-containers"} |~ "(?i)error|exception|traceback|failed"
```

The Loki and Prometheus datasources are provisioned with Grafana-managed alert
editing disabled. Alert and ruler endpoints are not part of this sandbox
contract; use provisioned Prometheus rules and CloudWatch alarms instead.

Use `AWS SDLC Containers / Log Groups` when you want a CloudWatch-like list of
log groups in Grafana. Select or click a group to view raw logs for that group,
then use the dashboard's Explore link for deeper Loki search and scroll/load-more
browsing. This intentionally follows Grafana's native logs UX instead of
numbered CloudWatch-style pages.

The `log_group` and `container` dashboard variables are explicit expected-value
lists, not only Loki-discovered labels. This keeps quiet or newly deployed groups
selectable even before Loki has recent lines for them. The top table still shows
line counts only for groups that actually produced Loki logs in the selected time
range; a selectable group with an empty logs panel means delivery or freshness
needs investigation, not that the group is outside the contract.

After changing FireLens labels or Grafana dashboard JSON, rebuild and push the
FireLens image with the App Build workflow, deploy with the matching immutable
`sha-*` image tag, and apply the app Terraform root so the Grafana dashboard S3
objects are refreshed. Restart or roll the Grafana task after the S3 object
changes so the config-loader copies the new dashboard JSON into the container.
Use `make observability-stack-deploy` after Terraform apply to force-roll the
Grafana, Loki, Prometheus, and Tempo tasks.

For FireLens label/config corrections, use the App Build workflow to build and
scan the FireLens image alongside the app images, then deploy the reviewed
immutable `sha-*` tag through App Deploy. This keeps log-router changes on the
same build/scan/review path as workload images.

Historical old-schema Loki streams can remain visible until the Loki retention or
delete path removes the old chunks. CloudWatch stale log streams can be deleted
with `aws logs delete-log-stream` when they are confirmed dead. Loki label-based
deletion should use Loki's delete API only after the stack is explicitly
configured for deletes; do not delete Loki S3 objects by hand because chunk and
index cleanup must stay consistent.

## CloudWatch Reduction Rules

Do not reduce CloudWatch until the matching Grafana-stack signal has dual-run in
ECS. Keep these AWS/platform signals in CloudWatch:

- ALB target health.
- RDS CPU, storage, and connection pressure.
- EventBridge Scheduler delivery failures.
- SQS DLQ visibility for the Dapr-backed SNS/SQS order event transport.
- CloudWatch logs for workload and observability diagnostics.

CloudWatch is the AWS-native break-glass path and remains the source of truth
for ALB, RDS, SQS, Scheduler, and CloudWatch alarm state. Grafana matches
workload log content through Loki and app metrics through Prometheus. When the
project needs the same app metric series in CloudWatch and Grafana, prefer an
OpenTelemetry Collector/ADOT fan-out that exports app metrics to CloudWatch
while Prometheus continues to serve Grafana; do not make Grafana portable
dashboards depend on the CloudWatch datasource.

Only these app-level CloudWatch surfaces have reduction toggles, and both
default to `true`:

| Variable | CloudWatch surface | Disable only after |
|---|---|---|
| `enable_app_symptom_cloudwatch_alarms` | ALB target 5xx and latency symptom alarms | Prometheus/Grafana app 5xx and latency alerts have dual-run through at least one deploy cycle. |
| `enable_data_export_success_cloudwatch_alarm` | Data-export success metric filter and freshness alarm | A Grafana-stack freshness signal from job metrics or Loki has dual-run. |

## Acceptance Criteria

- Prometheus target is healthy.
- Grafana dashboard loads from provisioning and includes the readiness-failure
  stat.
- Grafana `Log Groups` dashboard loads from provisioning, lists Loki
  `log_group` values, and shows raw logs for the selected group.
- Loki shows app, PgBouncer, support workload, and observability service logs
  under CloudWatch-like `log_group` labels.
- Tempo shows API traces.
- Prometheus loads local app alert rules.
- `/metrics` does not change `/health`, `/ready`, request ID propagation, or API
  behavior.
- Observability remains optional for the base app rollout.
