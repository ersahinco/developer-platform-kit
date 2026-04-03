terraform {
  required_version = ">= 1.11.1"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }

  # Remote state: S3 bucket + DynamoDB lock table must exist before first init.
  # Bootstrap once with: aws s3 mb s3://db-migration-example-tfstate-691627364817 --region eu-central-1
  #                       aws dynamodb create-table --table-name terraform-locks \
  #                         --attribute-definitions AttributeName=LockID,AttributeType=S \
  #                         --key-schema AttributeName=LockID,KeyType=HASH \
  #                         --billing-mode PAY_PER_REQUEST --region eu-central-1
  #
  # State key is supplied at init time via -backend-config="key=..." to isolate
  # dev and prod state without Terraform workspaces.
  backend "s3" {
    bucket       = "db-migration-example-tfstate-691627364817"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
    # key is intentionally omitted — pass -backend-config="key=db-migration-example/<env>.tfstate"
  }
}
