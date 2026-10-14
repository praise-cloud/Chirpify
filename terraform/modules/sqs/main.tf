# ------------------------------------------------------------------------------
# Dead Letter Queue (DLQ)
# ------------------------------------------------------------------------------
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-${var.environment}-events-dlq"
  message_retention_seconds = 1209600 # 14 days maximum retention for forensics
  sqs_managed_sse_enabled   = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-events-dlq"
    Environment = var.environment
    Role        = "DeadLetterQueue"
  }
}

# ------------------------------------------------------------------------------
# Main Ingestion SQS Queue with Redrive Policy
# ------------------------------------------------------------------------------
resource "aws_sqs_queue" "main" {
  name                       = "${var.project_name}-${var.environment}-events-queue"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-events-queue"
    Environment = var.environment
    Role        = "IngestionBuffer"
  }
}
