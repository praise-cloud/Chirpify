output "main_queue_id" {
  description = "URL of the main ingestion SQS queue"
  value       = aws_sqs_queue.main.id
}

output "main_queue_arn" {
  description = "ARN of the main ingestion SQS queue"
  value       = aws_sqs_queue.main.arn
}

output "dlq_id" {
  description = "URL of the Dead Letter Queue"
  value       = aws_sqs_queue.dlq.id
}

output "dlq_arn" {
  description = "ARN of the Dead Letter Queue"
  value       = aws_sqs_queue.dlq.arn
}
