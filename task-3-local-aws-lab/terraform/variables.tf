variable "aws_region" {
  description = "AWS region (LocalStack)"
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "LocalStack endpoint URL"
  type        = string
  default     = "http://localhost:4566"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket that triggers the pipeline"
  type        = string
  default     = "devops-lab-uploads"
}

variable "sqs_queue_name" {
  description = "Name of the SQS queue that receives Lambda messages"
  type        = string
  default     = "devops-lab-events"
}

variable "lambda_function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "s3-event-processor"
}
