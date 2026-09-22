# Mealy AWS infrastructure

Terraform manages a separate low-cost `dev` environment in `eu-north-1`. The
existing EC2 instance and Elastic IP are intentionally outside this state and
remain available as a rollback environment during the migration.

## 1. Authenticate AWS CLI

Use the browser-based AWS CLI login flow and verify the account:

```bash
aws login
aws sts get-caller-identity
```

The expected AWS account ID is `294615681551`.

## 2. Create the remote state bucket once

The bootstrap stack keeps local state. Do not delete its state file.

```bash
cd infra/bootstrap
terraform init
terraform plan -out=bootstrap.tfplan
terraform apply bootstrap.tfplan
```

## 3. Configure the development environment

```bash
cd ../environments/dev
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl
```

Replace the notification email in `terraform.tfvars`, then initialize and
review the plan:

```bash
terraform init -backend-config=backend.hcl
terraform fmt -check -recursive ../../
terraform validate
terraform plan -out=dev.tfplan
```

Apply only after confirming that the plan creates the budget, one VPC, four
subnets, route tables, and four security groups. It must not modify the
existing EC2 instance or Elastic IP.

```bash
terraform apply dev.tfplan
```

The development network intentionally has no NAT Gateway. Fargate tasks use
public subnets for outbound access while their security group accepts inbound
API traffic only from the ALB. RDS and ElastiCache use the isolated data
subnets.

## 4. Catalog migration tasks

Terraform creates `mealy-dev-cluster` and the
`mealy-dev-maintenance` Fargate task definition. No task runs continuously, so
this layer has no ongoing Fargate compute charge. Use it for Alembic migrations,
catalog imports, embedding backfills, and smoke checks inside the private VPC.

The runtime image is ARM64 and is stored at:

```text
294615681551.dkr.ecr.eu-north-1.amazonaws.com/mealy-dev-backend:rag-v1
```

The repeatable vector smoke command inside the image is:

```bash
python scripts/verify_vector_search.py --query "полезный рыбный ужин"
```

It fails unless every recipe has a current embedding, the HNSW index exists,
and hybrid retrieval returns semantic scores.

The development RDS instance keeps one day of automatic backups because AWS
Free plan accounts reject longer retention periods. Independent PostgreSQL
dumps will be stored in S3. Set `backup_retention_days` to `7` after upgrading
the AWS account plan.
