stack_name   = "__STACK_NAME__"
aws_region   = "__AWS_REGION__"
environment  = "production"
state_bucket = "__STATE_BUCKET__"

# Add a service here before its repo tries to deploy. The key is the contract
# between this root and that repo's delivery workflow.
services = {
  # "orders-api" = {
  #   public         = true
  #   needs_database = true
  #   desired_count  = 2
  # }
}

# Add a pipeline here before its repo tries to migrate. The key must equal
# PIPELINE_NAME in the data repo.
data_pipelines = {
  # "orders-daily" = {}
}
