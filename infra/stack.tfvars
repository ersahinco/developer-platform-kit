root_domain        = "ersahinco-sandbox.eu"
az_count           = 2
single_nat_gateway = true
rds_instance_class = "db.t4g.small"
rds_multi_az       = false
app_desired_count  = 1

api_token_secret_name = "aws-sdlc-containers/api-token"
