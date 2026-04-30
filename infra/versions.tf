terraform {
  required_version = ">= 1.15.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }

  # Remote state: the S3 bucket must exist before first init.
  # Bootstrap once with: make bootstrap
  #
  # This backend uses Terraform's S3 native lockfile (`use_lockfile = true`).
  # `make bootstrap` also creates the `terraform-locks` DynamoDB table for
  # compatibility with older runbooks and IAM policy surfaces, but this backend
  # does not currently set `dynamodb_table`.
  #
  # Single stack state key. CI and Makefile still pass the same value via
  # -backend-config so operators can see the selected state key explicitly.
  backend "s3" {
    bucket       = "aws-sdlc-containers-tfstate-691627364817"
    key          = "aws-sdlc-containers/stack.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
