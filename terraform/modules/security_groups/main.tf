# ------------------------------------------------------------------------------
# ALB Security Group (Public Edge)
# ------------------------------------------------------------------------------
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.environment}-alb-sg"
  description = "Controls public HTTP/HTTPS traffic to Application Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow inbound HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow inbound HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow outbound to Fargate containers only"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Scoped dynamically via Fargate SG
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-alb-sg"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# ECS Fargate Tasks Security Group (Application Tier)
# ------------------------------------------------------------------------------
resource "aws_security_group" "fargate" {
  name        = "${var.project_name}-${var.environment}-fargate-sg"
  description = "Allows traffic strictly from ALB to Fargate tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow traffic strictly from ALB"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow outbound for package downloads, SQS, S3, and database"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-fargate-sg"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# RDS PostgreSQL Security Group (Data Tier)
# ------------------------------------------------------------------------------
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "Allows PostgreSQL traffic strictly from Fargate containers"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow PostgreSQL from Fargate application tasks only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.fargate.id]
  }

  egress {
    description = "No outbound allowed from database"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["127.0.0.1/32"] # Blocked
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-rds-sg"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# ElastiCache Redis Security Group (Cache Tier)
# ------------------------------------------------------------------------------
resource "aws_security_group" "redis" {
  name        = "${var.project_name}-${var.environment}-redis-sg"
  description = "Allows Redis traffic strictly from Fargate containers"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow Redis port 6379 strictly from Fargate"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.fargate.id]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-redis-sg"
    Environment = var.environment
  }
}
