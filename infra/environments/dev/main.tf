locals {
  name_prefix = "mealy-${var.environment}"
  common_tags = {
    Project     = "Mealy"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

module "network" {
  source = "../../modules/network"

  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  common_tags = local.common_tags
}

module "rds" {
  source = "../../modules/rds"

  name_prefix       = local.name_prefix
  data_subnet_ids   = module.network.data_subnet_ids
  security_group_id = module.network.rds_security_group_id
  common_tags       = local.common_tags
}

module "elasticache" {
  source = "../../modules/elasticache"

  name_prefix       = local.name_prefix
  data_subnet_ids   = module.network.data_subnet_ids
  security_group_id = module.network.redis_security_group_id
  common_tags       = local.common_tags
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix = local.name_prefix
  environment = var.environment
  common_tags = local.common_tags
}

module "ecr" {
  source = "../../modules/ecr"

  name_prefix = local.name_prefix
  common_tags = local.common_tags
}

module "ecs_maintenance" {
  source = "../../modules/ecs-maintenance"

  name_prefix           = local.name_prefix
  aws_region            = var.aws_region
  image_uri             = "${module.ecr.repository_url}:${var.backend_image_tag}"
  rds_secret_arn        = module.rds.master_user_secret_arn
  rds_host              = module.rds.address
  rds_port              = module.rds.port
  openrouter_secret_arn = module.secrets.openrouter_api_key_arn
  app_secret_arn        = module.secrets.app_secret_key_arn
  redis_endpoint        = module.elasticache.primary_endpoint_address
  admin_emails          = var.admin_emails
  common_tags           = local.common_tags
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = toset([30, 60, 100])

    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "FORECASTED"
      subscriber_email_addresses = [var.budget_notification_email]
    }
  }
}
