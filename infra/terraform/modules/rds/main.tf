terraform {
  required_version = ">= 1.5.0"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-subnets"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name        = "${var.name}-db"
  description = "IncidentFox RDS Postgres"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group_rule" "allow_from_sg" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.this.id
  source_security_group_id = var.allowed_security_group_id
}

resource "aws_db_instance" "this" {
  identifier              = var.name
  engine                  = "postgres"
  engine_version          = var.engine_version
  instance_class          = var.instance_class
  allocated_storage       = var.allocated_storage_gb
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.this.id]
  publicly_accessible     = false
  storage_encrypted       = true
  backup_retention_period = var.backup_retention_days
  deletion_protection     = var.deletion_protection

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  skip_final_snapshot = true
  tags               = var.tags
}


