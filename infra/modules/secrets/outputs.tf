output "openrouter_api_key_arn" {
  value = aws_secretsmanager_secret.openrouter_api_key.arn
}

output "app_secret_key_arn" {
  value = aws_secretsmanager_secret.app_secret_key.arn
}
