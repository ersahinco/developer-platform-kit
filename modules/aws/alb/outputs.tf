output "dns_name" {
  description = "Load balancer DNS name."
  value       = aws_lb.this.dns_name
}

output "zone_id" {
  description = "Hosted zone ID, for an alias record."
  value       = aws_lb.this.zone_id
}

output "arn" {
  description = "Load balancer ARN."
  value       = aws_lb.this.arn
}

output "security_group_id" {
  description = "Load balancer security group, to allow as source on task security groups."
  value       = aws_security_group.alb.id
}

output "default_target_group_arn" {
  description = "Target group the primary service registers with."
  value       = aws_lb_target_group.default.arn
}

output "https_listener_arn" {
  description = "HTTPS listener ARN, or null when no certificate is configured."
  value       = try(aws_lb_listener.https[0].arn, null)
}

output "http_listener_arn" {
  description = "HTTP listener ARN."
  value       = aws_lb_listener.http.arn
}
