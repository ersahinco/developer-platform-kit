environment        = "prod"
az_count           = 2     # 2 AZs is sufficient for HA; add a third only if a regulatory or availability requirement demands it
single_nat_gateway = false # one NAT per AZ — required for HA
rds_instance_class = "db.t4g.medium"
rds_multi_az       = true
app_desired_count  = 2
