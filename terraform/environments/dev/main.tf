# ==============================================================================
# Chirpify Analytics Platform — Development Environment Root Configuration
# ==============================================================================

# 1. Networking Tier: Multi-AZ VPC with Public & Private Subnets
module "vpc" {
  source = "../../modules/vpc"

  project_name       = var.project_name
  environment        = var.environment
  enable_nat_gateway = var.use_local_floci ? false : true # Floci emulates endpoints locally; real AWS uses NAT GW
}

# 2. Security Tier: Principle of Least Privilege Security Groups
module "security_groups" {
  source = "../../modules/security_groups"

  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.vpc.vpc_id
  app_port     = 8000
}

# 3. Buffer Tier: SQS Ingestion Queue with Dead Letter Queue (DLQ)
module "sqs" {
  source = "../../modules/sqs"

  project_name = var.project_name
  environment  = var.environment
}

# 4. Storage Tier: S3 Raw Event Data Lake with Lifecycle Tiering
module "s3" {
  source = "../../modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

# 5. Database Tier: RDS PostgreSQL Multi-AZ
module "rds" {
  source = "../../modules/rds"

  project_name          = var.project_name
  environment           = var.environment
  private_subnet_ids    = module.vpc.private_subnet_ids
  rds_security_group_id = module.security_groups.rds_security_group_id
  db_password           = var.db_password
  multi_az              = var.use_local_floci ? false : true
}

# 6. Cache Tier: ElastiCache Redis Cluster
module "elasticache" {
  source = "../../modules/elasticache"

  project_name            = var.project_name
  environment             = var.environment
  private_subnet_ids      = module.vpc.private_subnet_ids
  redis_security_group_id = module.security_groups.redis_security_group_id
  num_cache_clusters      = var.use_local_floci ? 1 : 2
}

# 7. Ingress Tier: Application Load Balancer
module "alb" {
  source = "../../modules/alb"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  alb_security_group_id = module.security_groups.alb_security_group_id
  app_port              = 8000
  health_check_path     = "/healthz"
}

# 8. Compute Tier: ECS Fargate Serverless Containers (API & Worker)
module "ecs" {
  source = "../../modules/ecs"

  project_name              = var.project_name
  environment               = var.environment
  private_subnet_ids        = module.vpc.private_subnet_ids
  fargate_security_group_id = module.security_groups.fargate_security_group_id
  target_group_arn          = module.alb.target_group_arn

  sqs_queue_url  = module.sqs.main_queue_id
  sqs_queue_arn  = module.sqs.main_queue_arn
  s3_bucket_name = module.s3.bucket_id
  s3_bucket_arn  = module.s3.bucket_arn

  database_host     = module.rds.address
  database_port     = module.rds.port
  database_name     = "chirpify_analytics"
  database_user     = "chirpify_user"
  database_password = var.db_password

  redis_host = module.elasticache.primary_endpoint_address
  redis_port = module.elasticache.port

  api_desired_count    = var.use_local_floci ? 1 : 2
  worker_desired_count = 1
}
