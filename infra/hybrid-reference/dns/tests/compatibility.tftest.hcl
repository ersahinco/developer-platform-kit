mock_provider "cloudflare" {}

run "starter_dns_plan" {
  command = plan

  variables {
    cloudflare_zone_id = "zone-proof"
    hostname           = "api.example.com"
    origin_ipv4        = "192.0.2.20"
  }

  assert {
    condition     = cloudflare_dns_record.workload.name == "api.example.com"
    error_message = "The Cloudflare record address or hostname intent changed."
  }

  assert {
    condition     = cloudflare_dns_record.workload.proxied == false
    error_message = "The reference must retain provider-compatible origin TLS."
  }
}
