variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "glacier_transition_days" {
  description = "Days before transitioning raw event batches to Glacier cold storage"
  type        = number
  default     = 90
}

variable "expiration_days" {
  description = "Days before permanent deletion of raw event batches"
  type        = number
  default     = 365
}
