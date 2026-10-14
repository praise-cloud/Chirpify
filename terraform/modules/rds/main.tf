# ------------------------------------------------------------------------------
# DB Subnet Group (Private Subnets across 2 AZs)
# ------------------------------------------------------------------------------
resource "aws_db_subnet_group" "main" {
  name        = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids  = var.private_subnet_ids
  description = "Database subnet group restricted to private subnets"

  tags = {
    Name        = "${var.project_name}-${var.environment}-db-subnet-group"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# DB Parameter Group (PostgreSQL 16 Performance & Slow Query Logging)
# ------------------------------------------------------------------------------
resource "aws_db_parameter_group" "pg16" {
  name   = "${var.project_name}-${var.environment}-pg16-params"
  family = "postgres16"

  parameter {
    name  = "log_min_duration_statement"
    value = "200" # Log statements exceeding 200ms
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }
}

# ------------------------------------------------------------------------------
# RDS PostgreSQL Multi-AZ Instance
# ------------------------------------------------------------------------------
resource "aws_db_instance" "postgres" {
  identifier            = "${var.project_name}-${var.environment}-postgres"
  engine                = "postgres"
  engine_version        = "16.3"
  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = 100 # Storage autoscaling up to 100GB
  storage_type          = "gp3"
  storage_encrypted     = true
  multi_az              = var.multi_az
  publicly_accessible   = false

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  parameter_group_name   = aws_db_parameter_group.pg16.name
  vpc_security_group_ids = [var.rds_security_group_id]

  backup_retention_period    = var.environment == "dev" ? 1 : 7
  backup_window              = "03:00-04:00"
  maintenance_window         = "Mon:04:30-Mon:05:30"
  auto_minor_version_upgrade = true
  skip_final_snapshot        = var.environment == "dev" ? true : false
  deletion_protection        = var.environment == "dev" ? false : true

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres"
    Environment = var.environment
  }
}
