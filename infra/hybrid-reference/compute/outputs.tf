output "server_ipv4" {
  description = "Non-secret origin address passed explicitly to the DNS root."
  value       = hcloud_server.runtime.ipv4_address
}

output "ssh_user" {
  description = "Hardened operator account created by cloud-init."
  value       = "platform"
}

output "runtime_directory" {
  description = "Server-side Compose runtime directory."
  value       = "/opt/aws-sdlc-containers"
}
