terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "1.66.1"
    }
  }

  backend "s3" {
    bucket       = "replace-with-tf-state-bucket"
    key          = "replace-with/hybrid/compute.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
