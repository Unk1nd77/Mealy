variable "name_prefix" {
  description = "Prefix used for RDS resource names."
  type        = string
}

variable "data_subnet_ids" {
  description = "Private subnet IDs used by the RDS subnet group."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group that controls access to PostgreSQL."
  type        = string
}

variable "common_tags" {
  description = "Tags applied to all RDS resources."
  type        = map(string)
  default     = {}
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "engine_version" {
  description = "Full PostgreSQL engine version."
  type        = string
  default     = "16.15"
}

variable "allocated_storage_gb" {
  description = "Initial gp3 storage allocation in GiB."
  type        = number
  default     = 20
}

variable "backup_retention_days" {
  description = "Automatic backup retention. Free plan accounts are limited to one day."
  type        = number
  default     = 1

  validation {
    condition     = var.backup_retention_days >= 0 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 0 and 35."
  }
}
