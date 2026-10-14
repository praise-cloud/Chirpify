# ------------------------------------------------------------------------------
# S3 Raw Event Data Lake Bucket
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "raw_events" {
  bucket        = "${var.project_name}-${var.environment}-raw-events-data-lake"
  force_destroy = var.environment == "dev" ? true : false

  tags = {
    Name        = "${var.project_name}-${var.environment}-raw-events-data-lake"
    Environment = var.environment
    Role        = "DataLake"
  }
}

# ------------------------------------------------------------------------------
# S3 Public Access Block (Strict Security: Prevent Data Leaks)
# ------------------------------------------------------------------------------
resource "aws_s3_bucket_public_access_block" "block_public" {
  bucket = aws_s3_bucket.raw_events.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ------------------------------------------------------------------------------
# S3 Versioning (Protects Against Accidental Deletion or Ransomware)
# ------------------------------------------------------------------------------
resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.raw_events.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ------------------------------------------------------------------------------
# S3 Server-Side Encryption
# ------------------------------------------------------------------------------
resource "aws_s3_bucket_server_side_encryption_configuration" "encryption" {
  bucket = aws_s3_bucket.raw_events.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ------------------------------------------------------------------------------
# S3 Lifecycle Rules: Transition to Glacier Cold Storage & Auto-Expiration
# ------------------------------------------------------------------------------
resource "aws_s3_bucket_lifecycle_configuration" "lifecycle" {
  bucket = aws_s3_bucket.raw_events.id

  rule {
    id     = "archive-and-expire-raw-events"
    status = "Enabled"

    filter {
      prefix = "events/"
    }

    transition {
      days          = var.glacier_transition_days
      storage_class = "GLACIER"
    }

    expiration {
      days = var.expiration_days
    }
  }
}
