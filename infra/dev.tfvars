environment        = "dev"
az_count           = 2
single_nat_gateway = true   # one shared NAT — saves ~$32/mo vs one-per-AZ
rds_instance_class = "db.t4g.small"
rds_multi_az       = false
app_desired_count  = 1
