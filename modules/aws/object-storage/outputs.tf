output "bucket_name" {
  description = "Bucket name."
  value       = aws_s3_bucket.this.id
}

output "bucket_arn" {
  description = "Bucket ARN."
  value       = aws_s3_bucket.this.arn
}

output "read_write_policy_json" {
  description = "Least-privilege policy for a workload that reads and writes this bucket. Attach it to a task role."
  value       = data.aws_iam_policy_document.read_write.json
}
