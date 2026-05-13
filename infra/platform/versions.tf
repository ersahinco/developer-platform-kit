terraform {
  required_version = ">= 1.15.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.34, < 6.43.0"
    }
  }

  backend "s3" {
    bucket       = "replace-with-tf-state-bucket"
    key          = "replace-with/platform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
