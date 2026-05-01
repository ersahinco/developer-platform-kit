terraform {
  required_version = ">= 1.15.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.34, < 6.43.0"
    }
  }

  backend "s3" {
    bucket       = "aws-sdlc-containers-tfstate-691627364817"
    key          = "aws-sdlc-containers/platform.tfstate"
    region       = "eu-central-1"
    use_lockfile = true
    encrypt      = true
  }
}
