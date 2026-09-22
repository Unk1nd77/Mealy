resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-postgres"
  subnet_ids = var.data_subnet_ids

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-postgres-subnets"
  })
}

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = "nutriagent"
  username = "mealy_admin"
  port     = 5432

  manage_master_user_password = true

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period    = var.backup_retention_days
  backup_window              = "01:00-02:00"
  maintenance_window         = "sun:02:30-sun:03:30"
  auto_minor_version_upgrade = true
  apply_immediately          = true

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-postgres-final"
  copy_tags_to_snapshot     = true

  performance_insights_enabled = false
  monitoring_interval          = 0

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-postgres"
  })
}
