variable "project_name" {
  description = "Prefix for all resource naming tags"
  type        = string
  default     = "chirpify"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the entire VPC (provides 65,536 private IPs)"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AWS Availability Zones for Multi-AZ redundancy"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (ALB & NAT Gateways)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (Fargate, RDS, Redis)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "enable_nat_gateway" {
  description = "Whether to provision NAT Gateways (can be disabled for local Floci dev to save resources)"
  type        = bool
  default     = true
}
