output "primary_endpoint_address" {
  description = "The address of the endpoint for the primary node in the replication group"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "port" {
  description = "The port number on which each of the cache nodes will accept connections"
  value       = aws_elasticache_replication_group.redis.port
}
