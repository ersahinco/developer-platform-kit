locals {
  tags = {
    Project   = var.stack_name
    ManagedBy = "terraform"
    Root      = "hybrid-data"
    Lane      = "starter"
  }
}

resource "supabase_project" "reference" {
  organization_id   = var.supabase_organization_id
  name              = var.supabase_project_name
  region            = var.supabase_region
  database_password = var.supabase_database_password
  instance_size     = var.supabase_instance_size

  lifecycle {
    ignore_changes = [database_password]
  }
}

resource "aws_s3_bucket" "exports" {
  #checkov:skip=CKV_AWS_18:Starter export evidence uses versioning and integrity manifests; access logging would need another shared bucket.
  #checkov:skip=CKV_AWS_144:Cross-region replication is an enterprise-lane recovery control, not a starter default.
  #checkov:skip=CKV_AWS_145:S3-managed AES256 encryption avoids a starter-only KMS lifecycle.
  #checkov:skip=CKV2_AWS_62:No downstream event consumer exists for this reference bucket.
  bucket        = var.export_bucket_name
  force_destroy = var.export_bucket_force_destroy
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "exports" {
  bucket = aws_s3_bucket.exports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "exports" {
  bucket = aws_s3_bucket.exports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    id     = "expire-noncurrent-export-versions"
    status = "Enabled"

    filter { prefix = "" }

    noncurrent_version_expiration {
      noncurrent_days = var.export_noncurrent_version_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.exports]
}

resource "aws_iam_group" "export_writers" {
  name = "${var.stack_name}-hybrid-export-writers"
}

resource "aws_iam_group_policy" "export_writer" {
  name  = "write-export-objects"
  group = aws_iam_group.export_writers.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject"]
      Resource = "${aws_s3_bucket.exports.arn}/*"
    }]
  })
}

resource "aws_iam_group_membership" "export_writer" {
  #checkov:skip=CKV2_AWS_14:Static analysis cannot resolve the non-empty variable-driven users list on this membership resource.
  #checkov:skip=CKV2_AWS_21:The existing export-writer user is explicitly attached to the export_writers group below.
  name  = "${var.stack_name}-hybrid-export-writer"
  users = [var.export_writer_user_name]
  group = aws_iam_group.export_writers.name
}
