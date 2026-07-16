terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "5.22.0"
    }
  }

  backend "s3" {
    bucket       = "replace-with-tf-state-bucket"
    key          = "replace-with/hybrid/dns.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
