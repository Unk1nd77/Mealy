variable "name_prefix" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "image_uri" {
  type = string
}

variable "rds_secret_arn" {
  type = string
}

variable "rds_host" {
  type = string
}

variable "rds_port" {
  type = number
}

variable "openrouter_secret_arn" {
  type = string
}

variable "app_secret_arn" {
  type = string
}

variable "redis_endpoint" {
  type = string
}

variable "admin_emails" {
  type = string
}

variable "common_tags" {
  type    = map(string)
  default = {}
}
