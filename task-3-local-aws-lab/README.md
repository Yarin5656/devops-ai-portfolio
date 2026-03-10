# Task 3 — Local AWS Infrastructure Lab

A fully local, event-driven AWS architecture built with **LocalStack** and **Terraform**.
No real AWS account is needed — everything runs inside Docker on your machine.

---

## Architecture

```
┌─────────────┐    ObjectCreated     ┌──────────────────┐    SendMessage    ┌─────────────┐
│  S3 Bucket  │ ──────────────────► │  Lambda Function  │ ────────────────► │  SQS Queue  │
│             │                      │  (Python 3.12)    │                   │             │
│ devops-lab- │                      │  s3-event-        │                   │ devops-lab- │
│ uploads     │                      │  processor        │                   │ events      │
└─────────────┘                      └──────────────────┘                   └─────────────┘
```

**Flow:**
1. A file is uploaded to the S3 bucket.
2. S3 fires an `ObjectCreated` event to the Lambda function.
3. Lambda extracts the bucket name, file name, and file size.
4. Lambda sends a structured JSON message to the SQS queue.
5. The SQS queue holds the message for downstream consumers.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Docker & Docker Compose | 24.x |
| Terraform | 1.5.x |
| AWS CLI | 2.x |
| Python | 3.10+ (for the test script) |

---

## Quick Start

### 1. Start LocalStack

```bash
docker compose up -d
```

Wait until LocalStack is healthy:

```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
```

All three services (`s3`, `lambda`, `sqs`) should show `"available"`.

---

### 2. Deploy Infrastructure with Terraform

```bash
cd terraform

terraform init
terraform plan
terraform apply -auto-approve
```

Terraform will create:
- `devops-lab-uploads` — S3 bucket
- `s3-event-processor` — Lambda function (Python 3.12)
- `devops-lab-events` — SQS queue
- IAM role + policy for Lambda
- S3 bucket notification wiring Lambda to ObjectCreated events

Expected output after apply:

```
Outputs:

lambda_function_arn  = "arn:aws:lambda:us-east-1:000000000000:function:s3-event-processor"
lambda_function_name = "s3-event-processor"
s3_bucket_name       = "devops-lab-uploads"
sqs_queue_arn        = "arn:aws:sqs:us-east-1:000000000000:devops-lab-events"
sqs_queue_url        = "http://localhost:4566/000000000000/devops-lab-events"
```

---

### 3. Test the Pipeline

```bash
chmod +x scripts/upload_test_file.sh
./scripts/upload_test_file.sh
```

The script:
1. Generates a timestamped test file.
2. Uploads it to the S3 bucket via AWS CLI.
3. Waits for Lambda to process the event.
4. Polls SQS and prints the resulting message.

Example output:

```
[10:23:01] Checking LocalStack health...
[10:23:01] OK  LocalStack is healthy.
[10:23:01] Created test file: test-upload-20260310-102301.txt
[10:23:01] Uploading 'test-upload-20260310-102301.txt' to s3://devops-lab-uploads/ ...
[10:23:02] OK  File uploaded to s3://devops-lab-uploads/test-upload-20260310-102301.txt
[10:23:02] Waiting 3 seconds for Lambda to process the event...
[10:23:05] Polling SQS queue: http://localhost:4566/000000000000/devops-lab-events
[10:23:10] OK  1 message(s) received from SQS:

  Message 1
    MessageId : a3f8c2d1-...
    File name : test-upload-20260310-102301.txt
    Bucket    : devops-lab-uploads
    Size      : 312 bytes
    Status    : uploaded
    Event time: 2026-03-10T10:23:02.000Z

Pipeline validated successfully.
```

---

## Manual AWS CLI Commands

```bash
export AWS_CMD="aws --endpoint-url http://localhost:4566 --region us-east-1"

# List S3 buckets
$AWS_CMD s3 ls

# List objects in the bucket
$AWS_CMD s3 ls s3://devops-lab-uploads/

# Read a message from SQS manually
$AWS_CMD sqs receive-message \
  --queue-url http://localhost:4566/000000000000/devops-lab-events \
  --max-number-of-messages 1

# View Lambda logs (LocalStack Community stores logs in CloudWatch)
$AWS_CMD logs describe-log-groups
$AWS_CMD logs describe-log-streams \
  --log-group-name /aws/lambda/s3-event-processor
```

---

## Teardown

```bash
# Destroy Terraform-managed resources
cd terraform && terraform destroy -auto-approve

# Stop and remove LocalStack container + volume
docker compose down -v
```

---

## Project Structure

```
task-3-local-aws-lab/
├── docker-compose.yml          # LocalStack service definition
├── terraform/
│   ├── main.tf                 # All AWS resources (S3, Lambda, SQS, IAM)
│   ├── variables.tf            # Configurable parameters
│   └── outputs.tf              # Key resource identifiers
├── lambda/
│   └── handler.py              # Python Lambda — S3 event → SQS message
├── scripts/
│   └── upload_test_file.sh     # End-to-end pipeline test
└── README.md
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| LocalStack Community (free tier) | Zero cost, no AWS account required |
| Terraform `s3_use_path_style = true` | Required for LocalStack compatibility |
| Lambda packaged via `archive_file` | Self-contained; no separate CI step needed |
| Python 3.12 runtime | Latest stable runtime supported by LocalStack |
| IAM role scoped to SQS + CloudWatch Logs | Least-privilege, mirrors production patterns |
