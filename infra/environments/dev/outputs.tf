output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "data_subnet_ids" {
  value = module.network.data_subnet_ids
}

output "security_group_ids" {
  value = {
    alb   = module.network.alb_security_group_id
    ecs   = module.network.ecs_security_group_id
    rds   = module.network.rds_security_group_id
    redis = module.network.redis_security_group_id
  }
}

output "rds" {
  value = {
    identifier             = module.rds.identifier
    address                = module.rds.address
    port                   = module.rds.port
    database_name          = module.rds.database_name
    master_user_secret_arn = module.rds.master_user_secret_arn
  }
}

output "elasticache" {
  value = {
    replication_group_id     = module.elasticache.replication_group_id
    primary_endpoint_address = module.elasticache.primary_endpoint_address
    port                     = module.elasticache.port
  }
}

output "secret_arns" {
  value = {
    openrouter_api_key = module.secrets.openrouter_api_key_arn
    app_secret_key     = module.secrets.app_secret_key_arn
  }
}

output "ecr" {
  value = {
    repository_name = module.ecr.repository_name
    repository_url  = module.ecr.repository_url
  }
}

output "ecs_maintenance" {
  value = {
    cluster_name        = module.ecs_maintenance.cluster_name
    task_definition_arn = module.ecs_maintenance.task_definition_arn
    log_group_name      = module.ecs_maintenance.log_group_name
  }
}
