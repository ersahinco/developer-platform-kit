environment        = "prod"
az_count           = 2    # 2 AZs is sufficient for HA; add a third only if a regulatory or availability requirement demands it
single_nat_gateway = true # single NAT to reduce cost
rds_instance_class = "db.t4g.small"
rds_multi_az       = false
app_desired_count  = 1
root_domain        = "ersahinco-sandbox.eu"

api_token_secret_name = "db-migration-example/api-token"
