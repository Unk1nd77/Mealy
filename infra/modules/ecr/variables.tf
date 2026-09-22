variable "name_prefix" {
  description = "Prefix used for ECR resource names."
  type        = string
}

variable "common_tags" {
  description = "Tags applied to the ECR repository."
  type        = map(string)
  default     = {}
}
