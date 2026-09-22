output "repository_name" {
  value = aws_ecr_repository.backend.name
}

output "repository_url" {
  value = aws_ecr_repository.backend.repository_url
}
