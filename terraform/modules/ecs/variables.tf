variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "fargate_security_group_id" {
  type = string
}

variable "target_group_arn" {
  type = string
}

variable "api_image" {
  type    = string
  default = "chirpify-api:latest"
}

variable "worker_image" {
  type    = string
  default = "chirpify-worker:latest"
}

variable "app_port" {
  type    = number
  default = 8000
}

variable "sqs_queue_url" {
  type = string
}

variable "sqs_queue_arn" {
  type = string
}

variable "s3_bucket_name" {
  type = string
}

variable "s3_bucket_arn" {
  type = string
}

variable "database_host" {
  type = string
}

variable "database_port" {
  type = number
}

variable "database_name" {
  type = string
}

variable "database_user" {
  type = string
}

variable "database_password" {
  type      = string
  sensitive = true
}

variable "redis_host" {
  type = string
}

variable "redis_port" {
  type = number
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 1
}
