# INTENTIONALLY INSECURE - for scanner demonstration only

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# BAD: S3 bucket with public ACL
resource "aws_s3_bucket" "data_bucket" {
  bucket = "my-company-data-bucket"
  acl    = "public-read"          # BAD: publicly readable bucket
}

# BAD: S3 versioning with MFA delete disabled
resource "aws_s3_bucket_versioning" "data_bucket_versioning" {
  bucket = aws_s3_bucket.data_bucket.id
  versioning_configuration {
    status     = "Enabled"
    mfa_delete = "Disabled"        # BAD: MFA delete not required
  }
}

# BAD: Security group open to the entire internet
resource "aws_security_group" "web_sg" {
  name        = "web-security-group"
  description = "Security group for web servers"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]   # BAD: SSH open to the world
  }

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]   # BAD: MySQL open to the world
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# BAD: RDS instance publicly accessible with encryption disabled
resource "aws_db_instance" "app_db" {
  identifier           = "app-database"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.micro"
  username             = "admin"
  password             = "SuperSecret123!"     # BAD: hardcoded password
  publicly_accessible  = true                  # BAD: RDS reachable from internet
  encrypted            = false                 # BAD: no encryption at rest
  skip_final_snapshot  = true

  vpc_security_group_ids = [aws_security_group.web_sg.id]
}

# BAD: EKS cluster with logging disabled
resource "aws_eks_cluster" "app_cluster" {
  name     = "app-cluster"
  role_arn = "arn:aws:iam::123456789012:role/eks-role"

  vpc_config {
    subnet_ids = ["subnet-abc123", "subnet-def456"]
  }

  # BAD: No enabled_cluster_log_types defined → logging = false
  enable_logging = false
}

# BAD: EC2 instance with hardcoded API key in user_data
resource "aws_instance" "app_server" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "t3.micro"

  user_data = <<-EOF
    #!/bin/bash
    export API_KEY="hardcoded-api-key-do-not-use"
    export secret="my-super-secret-value"
    ./start-app.sh
  EOF

  # BAD: TLS verification disabled for internal calls
  skip_tls_verify = true
}
