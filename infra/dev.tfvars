environment        = "dev"
az_count           = 2    # AWS requires subnet groups in 2 AZs minimum; RDS instance remains single-AZ (rds_multi_az = false)
single_nat_gateway = true # one shared NAT — saves ~$32/mo vs one-per-AZ
rds_instance_class = "db.t4g.small"
rds_multi_az       = false
app_desired_count  = 1

# Run `make tls-import-dev` once before the first apply to generate and import
# the self-signed cert. The ARN is written to infra/.tls-cert-arn-dev.
api_token_secret_name = "db-migration-example/api-token"
