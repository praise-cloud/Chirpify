variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where security groups will reside"
  type        = string
}

variable "app_port" {
  description = "Application listening port"
  type        = number
  default     = 8000
}
