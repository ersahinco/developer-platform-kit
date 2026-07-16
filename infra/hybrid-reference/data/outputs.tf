output "export_bucket_name" {
  description = "Non-secret object-output bucket name consumed at deploy time."
  value       = aws_s3_bucket.exports.bucket
}

output "export_bucket_region" {
  description = "Non-secret object-output bucket region."
  value       = var.aws_region
}

output "supabase_project_ref" {
  description = "Non-secret Supabase project reference. Connection URLs are never Terraform outputs."
  value       = supabase_project.reference.id
}
