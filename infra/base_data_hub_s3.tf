################################################################################
# Base data hub - S3 export bucket
#
# This bucket is the first AWS landing zone for the local data export job. S3
# prefixes are virtual, so Terraform only owns the durable bucket guardrails here;
# the data export job writes raw files and manifests when the ECS job is added.
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
