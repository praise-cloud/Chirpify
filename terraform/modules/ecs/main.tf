# ------------------------------------------------------------------------------
# ECS Cluster (Fargate Serverless)
# ------------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-cluster"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# CloudWatch Log Groups for Container Logging
# ------------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}-${var.environment}-api"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-${var.environment}-worker"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# IAM Roles: Task Execution Role (Pull image, stream CloudWatch logs)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.project_name}-${var.environment}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ------------------------------------------------------------------------------
# IAM Roles: Task Role (Least Privilege Application Permissions)
# ------------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-${var.environment}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Least privilege IAM policy for SQS and S3
resource "aws_iam_policy" "task_permissions" {
  name        = "${var.project_name}-${var.environment}-task-policy"
  description = "Allows ECS tasks to interact strictly with project SQS queue and S3 data lake"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSPermissions"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.sqs_queue_arn
      },
      {
        Sid    = "S3DataLakePermissions"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${var.s3_bucket_arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "task_permissions_attach" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.task_permissions.arn
}

# ------------------------------------------------------------------------------
# Fargate Task Definition: Ingestion API Service
# ------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [
        {
          containerPort = var.app_port
          hostPort      = var.app_port
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
        { name = "POSTGRES_HOST", value = var.database_host },
        { name = "POSTGRES_PORT", value = tostring(var.database_port) },
        { name = "POSTGRES_DB", value = var.database_name },
        { name = "POSTGRES_USER", value = var.database_user },
        { name = "POSTGRES_PASSWORD", value = var.database_password },
        { name = "REDIS_HOST", value = var.redis_host },
        { name = "REDIS_PORT", value = tostring(var.redis_port) }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

# ------------------------------------------------------------------------------
# Fargate Task Definition: Event Worker Consumer
# ------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-${var.environment}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.worker_image
      essential = true
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
        { name = "S3_BUCKET_NAME", value = var.s3_bucket_name },
        { name = "POSTGRES_HOST", value = var.database_host },
        { name = "POSTGRES_PORT", value = tostring(var.database_port) },
        { name = "POSTGRES_DB", value = var.database_name },
        { name = "POSTGRES_USER", value = var.database_user },
        { name = "POSTGRES_PASSWORD", value = var.database_password },
        { name = "REDIS_HOST", value = var.redis_host },
        { name = "REDIS_PORT", value = tostring(var.redis_port) }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])
}

# ------------------------------------------------------------------------------
# ECS Service: Ingestion API (With Rolling Updates & ALB Attachment)
# ------------------------------------------------------------------------------
resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-${var.environment}-api-svc"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.fargate_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "api"
    container_port   = var.app_port
  }
}

# ------------------------------------------------------------------------------
# ECS Service: Event Worker Service (Running in Private Subnets)
# ------------------------------------------------------------------------------
resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-${var.environment}-worker-svc"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.fargate_security_group_id]
    assign_public_ip = false
  }
}
