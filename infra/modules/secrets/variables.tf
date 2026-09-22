variable "name_prefix" {
  description = "Prefix used for secret descriptions and tags."
  type        = string
}

variable "environment" {
  description = "Environment segment used in secret names."
  type        = string
}

variable "common_tags" {
  description = "Tags applied to all secrets."
  type        = map(string)
  default     = {}
}
