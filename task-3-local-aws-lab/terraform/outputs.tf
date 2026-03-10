output "s3_bucket_name" {
  description = "Name of the S3 upload bucket"
  value       = aws_s3_bucket.uploads.bucket
}

output "sqs_queue_url" {
  description = "URL of the SQS events queue"
  value       = aws_sqs_queue.events.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS events queue"
  value       = aws_sqs_queue.events.arn
}

output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = aws_lambda_function.s3_processor.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function"
  value       = aws_lambda_function.s3_processor.arn
}
