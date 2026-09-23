resource "aws_secretsmanager_secret" "openrouter_api_key" {
  name                    = "mealy/${var.environment}/openrouter-api-key"
  description             = "OpenRouter API key used by ${var.name_prefix}"
  recovery_window_in_days = 7

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-openrouter-api-key"
  })
}

resource "aws_secretsmanager_secret" "app_secret_key" {
  name                    = "mealy/${var.environment}/app-secret-key"
  description             = "JWT signing key used by ${var.name_prefix}"
  recovery_window_in_days = 7

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-app-secret-key"
  })
}
