terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  # In production, use remote S3 backend with DynamoDB state locking
  # backend "s3" {
  #   bucket         = "chirpify-tf-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "chirpify-tf-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = var.use_local_floci ? "test" : null
  secret_key                  = var.use_local_floci ? "test" : null
  skip_credentials_validation = var.use_local_floci
  skip_metadata_api_check     = var.use_local_floci
  skip_requesting_account_id  = var.use_local_floci
  s3_use_path_style           = var.use_local_floci

  # When targeting local Floci/LocalStack emulator, redirect service endpoints to port 4566
  dynamic "endpoints" {
    for_each = var.use_local_floci ? [1] : []
    content {
      s3          = var.floci_endpoint
      sqs         = var.floci_endpoint
      rds         = var.floci_endpoint
      elasticache = var.floci_endpoint
      ec2         = var.floci_endpoint
      iam         = var.floci_endpoint
      ecs         = var.floci_endpoint
      elbv2       = var.floci_endpoint
      cloudwatch  = var.floci_endpoint
    }
  }

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
