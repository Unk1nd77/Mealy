variable "name_prefix" {
  description = "Prefix used for network resource names."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block assigned to the VPC."
  type        = string
}

variable "common_tags" {
  description = "Tags applied to all network resources."
  type        = map(string)
  default     = {}
}
