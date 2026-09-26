terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Bucket, key, and region are supplied by the plan and apply lanes, so this
  # root can be initialised against a different backend without an edit.
  backend "s3" {
    encrypt      = true
    use_lockfile = true
  }
}
