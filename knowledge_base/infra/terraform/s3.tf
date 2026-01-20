# S3 Bucket for RAPTOR tree files
# Trees are stored here and downloaded by the container at startup
resource "aws_s3_bucket" "trees" {
  bucket = "${local.app_name}-trees-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${local.app_name}-trees"
  }
}

resource "aws_s3_bucket_versioning" "trees" {
  bucket = aws_s3_bucket.trees.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "trees" {
  bucket = aws_s3_bucket.trees.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "trees" {
  bucket = aws_s3_bucket.trees.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule to clean up old versions
resource "aws_s3_bucket_lifecycle_configuration" "trees" {
  bucket = aws_s3_bucket.trees.id

  rule {
    id     = "cleanup-old-versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

