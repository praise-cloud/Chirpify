variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "rds_security_group_id" {
  type = string
}

variable "db_name" {
  type    = string
  default = "chirpify_analytics"
}

variable "db_username" {
  type    = string
  default = "chirpify_user"
}

variable "db_password" {
  description = "Database master password (injected via secret/variable)"
  type        = string
  sensitive   = true
  default     = "chirpify_secure_pass_2026"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "multi_az" {
  description = "Enable Multi-AZ high availability replica"
  type        = bool
  default     = true
}

variable "allocated_storage" {
  type    = number
  default = 20
}
