resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "maintenance" {
  name              = "/ecs/${var.name_prefix}/maintenance"
  retention_in_days = 14
  tags              = var.common_tags
}

resource "aws_iam_role" "execution" {
  name = "${var.name_prefix}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "${var.name_prefix}-read-runtime-secrets"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        var.rds_secret_arn,
        var.openrouter_secret_arn,
        var.app_secret_arn,
      ]
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.name_prefix}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
  tags = var.common_tags
}

resource "aws_ecs_task_definition" "maintenance" {
  family                   = "${var.name_prefix}-maintenance"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "maintenance"
      image     = var.image_uri
      essential = true
      command   = ["python", "-c", "print('Override the maintenance command when running the task')"]
      environment = [
        { name = "DB_NAME", value = "nutriagent" },
        { name = "DB_HOST", value = var.rds_host },
        { name = "DB_PORT", value = tostring(var.rds_port) },
        { name = "ADMIN_EMAILS", value = var.admin_emails },
        { name = "REDIS_URL", value = "rediss://${var.redis_endpoint}:6379/0?ssl_cert_reqs=none" },
        { name = "DEBUG", value = "false" },
      ]
      secrets = [
        { name = "DB_USER", valueFrom = "${var.rds_secret_arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${var.rds_secret_arn}:password::" },
        { name = "OPENROUTER_API_KEY", valueFrom = var.openrouter_secret_arn },
        { name = "SECRET_KEY", valueFrom = var.app_secret_arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.maintenance.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "task"
        }
      }
    }
  ])

  tags = var.common_tags
}
