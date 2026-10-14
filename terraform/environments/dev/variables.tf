variable "aws_region" {
  description = "AWS region for infrastructure deployment"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix identifier for all resources"
  type        = string
  default     = "chirpify"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "use_local_floci" {
  description = "Set to true to target local Floci cloud emulator (port 4566)"
  type        = bool
  default     = true
}

variable "floci_endpoint" {
  description = "Endpoint URL for local Floci cloud emulator"
  type        = string
  default     = "http://localhost:4566"
}

variable "db_password" {
  description = "Master password for PostgreSQL database"
  type        = string
  sensitive   = true
  default     = "chirpify_secure_pass_2026"
}
