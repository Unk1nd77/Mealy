output "terraform_state_bucket" {
  description = "S3 bucket used by the development Terraform backend."
  value       = aws_s3_bucket.terraform_state.id
}
