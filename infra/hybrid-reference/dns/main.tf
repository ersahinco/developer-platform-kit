resource "cloudflare_dns_record" "workload" {
  zone_id = var.cloudflare_zone_id
  name    = var.hostname
  content = var.origin_ipv4
  type    = "A"
  ttl     = var.ttl
  proxied = false
  comment = "Managed by the aws-sdlc-containers hybrid reference DNS root"
}
