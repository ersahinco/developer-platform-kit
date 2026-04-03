environment        = "dev"
az_count           = 2
single_nat_gateway = true # one shared NAT — saves ~$32/mo vs one-per-AZ
rds_instance_class = "db.t4g.small"
rds_multi_az       = false
app_desired_count  = 1

# Restrict ALB ingress to your IP — prevents public exposure in dev.
# Remove or widen when running CI smoke tests against the ALB directly.
alb_ingress_cidr = "89.0.2.102/32"
