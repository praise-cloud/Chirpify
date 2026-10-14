variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "visibility_timeout_seconds" {
  description = "Worker processing timeout before message becomes visible again"
  type        = number
  default     = 60
}

variable "message_retention_seconds" {
  description = "Duration to retain messages in queue (4 days default)"
  type        = number
  default     = 345600
}

variable "max_receive_count" {
  description = "Number of delivery failures before routing to Dead Letter Queue"
  type        = number
  default     = 3
}
