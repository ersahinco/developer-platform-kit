################################################################################
# Data export storage
#
# S3 is the AWS implementation for exported raw files and manifests. Prefixes
# are virtual, so Terraform owns the durable bucket guardrails while the data
# export job writes objects at runtime.
################################################################################

locals {
  data_hub_bucket_name = "${local.name}-data-hub-${local.account_id}"

  data_hub_prefixes = {
    raw       = "raw/"
    curated   = "curated/"
    manifests = "manifests/"
  }
}

resource "aws_s3_bucket" "data_hub" {
  #checkov:skip=CKV_AWS_18:Access log buckets add unrelated storage/cost for this sandbox export landing zone.
  #checkov:skip=CKV_AWS_144:Cross-region replication is a production recovery control, not needed for this disposable sandbox bucket.
  #checkov:skip=CKV_AWS_145:S3-managed AES256 encryption is sufficient here; KMS adds cost and key operations for no sandbox benefit.
  #checkov:skip=CKV2_AWS_62:No downstream event consumer exists yet; adding notifications would be placeholder infrastructure.
  bucket = local.data_hub_bucket_name

  tags = merge(local.tags, {
    Purpose = "data-hub"
  })
}

resource "aws_s3_bucket_public_access_block" "data_hub" {
  bucket = aws_s3_bucket.data_hub.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data_hub" {
  bucket = aws_s3_bucket.data_hub.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_hub" {
  bucket = aws_s3_bucket.data_hub.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "data_hub" {
  bucket = aws_s3_bucket.data_hub.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_hub" {
  bucket = aws_s3_bucket.data_hub.id

  rule {
    id     = "expire-noncurrent-export-versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.data_hub]
}
