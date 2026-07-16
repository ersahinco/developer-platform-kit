output "hostname" {
  description = "Public workload hostname."
  value       = var.hostname
}

output "record_id" {
  description = "Cloudflare DNS record identifier."
  value       = cloudflare_dns_record.workload.id
}

output "origin_ipv4" {
  description = "Origin address currently published by this root."
  value       = var.origin_ipv4
}
