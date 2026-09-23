variable "aws_region" {
  description = "AWS region for the Mealy development environment."
  type        = string
  default     = "eu-north-1"
}

variable "environment" {
  description = "Environment name used in resource names and tags."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block assigned to the Mealy VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "budget_notification_email" {
  description = "Email address that receives AWS budget notifications."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly development budget in USD."
  type        = number
  default     = 100

  validation {
    condition     = var.monthly_budget_usd >= 10
    error_message = "monthly_budget_usd must be at least 10."
  }
}

variable "backend_image_tag" {
  description = "ECR tag used by ECS maintenance tasks."
  type        = string
  default     = "rag-v1"
}

variable "admin_emails" {
  description = "Comma-separated catalog administrator emails."
  type        = string
}
