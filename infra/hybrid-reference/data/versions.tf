terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.34, < 6.43.0"
    }
    supabase = {
      source  = "supabase/supabase"
      version = "1.9.1"
    }
  }

  backend "s3" {
    bucket       = "replace-with-tf-state-bucket"
    key          = "replace-with/hybrid/data.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
