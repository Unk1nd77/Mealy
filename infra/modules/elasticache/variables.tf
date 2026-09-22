variable "name_prefix" {
  description = "Prefix used for ElastiCache resource names."
  type        = string
}

variable "data_subnet_ids" {
  description = "Private subnet IDs used by the cache subnet group."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group that controls access to Valkey."
  type        = string
}

variable "common_tags" {
  description = "Tags applied to all ElastiCache resources."
  type        = map(string)
  default     = {}
}

variable "node_type" {
  description = "ElastiCache node type used by the development cache."
  type        = string
  default     = "cache.t4g.micro"
}

variable "engine_version" {
  description = "Valkey engine version."
  type        = string
  default     = "8.2"
}
