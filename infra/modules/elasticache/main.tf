resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-valkey"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-valkey-subnets"
  })
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-valkey"
  description          = "Mealy development Celery broker and cache"

  engine         = "valkey"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = 6379

  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [var.security_group_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"

  snapshot_retention_limit = 0
  apply_immediately        = true

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-valkey"
  })
}
