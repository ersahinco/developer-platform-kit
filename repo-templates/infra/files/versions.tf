terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Plan and apply supply the bucket, key, and region.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
