output "alb_dns_name" {
  description = "The public DNS endpoint of the Application Load Balancer"
  value       = module.alb.dns_name
}

output "sqs_main_queue_url" {
  description = "URL of the main event ingestion queue"
  value       = module.sqs.main_queue_id
}

output "sqs_dlq_url" {
  description = "URL of the Dead Letter Queue for failed events"
  value       = module.sqs.dlq_id
}

output "s3_raw_events_bucket" {
  description = "Name of the S3 Data Lake bucket"
  value       = module.s3.bucket_id
}

output "rds_endpoint" {
  description = "Endpoint address for PostgreSQL"
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "Primary endpoint address for Redis"
  value       = module.elasticache.primary_endpoint_address
}
