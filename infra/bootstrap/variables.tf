variable "aws_region" {
  description = "AWS region used by the Mealy development environment."
  type        = string
  default     = "eu-north-1"
}

variable "environment" {
  description = "Environment name used in resource names and tags."
  type        = string
  default     = "dev"
}

variable "aws_account_id" {
  description = "AWS account ID used to make the Terraform state bucket globally unique."
  type        = string
  default     = "294615681551"

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must contain exactly 12 digits."
  }
}
