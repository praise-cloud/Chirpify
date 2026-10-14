# ------------------------------------------------------------------------------
# ElastiCache Subnet Group (Private Subnets)
# ------------------------------------------------------------------------------
resource "aws_elasticache_subnet_group" "main" {
  name        = "${var.project_name}-${var.environment}-redis-subnet-group"
  subnet_ids  = var.private_subnet_ids
  description = "Subnet group for Redis cluster restricted to private subnets"
}

# ------------------------------------------------------------------------------
# Redis Parameter Group
# ------------------------------------------------------------------------------
resource "aws_elasticache_parameter_group" "redis7" {
  name   = "${var.project_name}-${var.environment}-redis7-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru" # Least Recently Used eviction when cache fills up
  }
}

# ------------------------------------------------------------------------------
# ElastiCache Redis Replication Group
# ------------------------------------------------------------------------------
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.project_name}-${var.environment}-redis"
  description          = "Redis in-memory cache for real-time Chirpify analytics counters"
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_clusters
  port                 = 6379

  subnet_group_name    = aws_elasticache_subnet_group.main.name
  parameter_group_name = aws_elasticache_parameter_group.redis7.name
  security_group_ids   = [var.redis_security_group_id]

  automatic_failover_enabled = var.num_cache_clusters > 1 ? true : false
  multi_az_enabled           = var.num_cache_clusters > 1 ? true : false

  at_rest_encryption_enabled = true
  transit_encryption_enabled = false # Set true in production with auth_token

  tags = {
    Name        = "${var.project_name}-${var.environment}-redis"
    Environment = var.environment
  }
}
