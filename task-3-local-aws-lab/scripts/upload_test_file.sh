#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# upload_test_file.sh
# Uploads a sample file to the LocalStack S3 bucket to trigger the pipeline:
#   S3 → Lambda → SQS
#
# Usage:
#   ./scripts/upload_test_file.sh [filename]
#
# Requirements:
#   - AWS CLI v2
#   - LocalStack running on http://localhost:4566
#   - Terraform already applied (bucket must exist)
# -----------------------------------------------------------------------------
set -euo pipefail

# ---------- Config ------------------------------------------------------------
ENDPOINT="http://localhost:4566"
BUCKET="${S3_BUCKET:-devops-lab-uploads}"
QUEUE_NAME="${SQS_QUEUE:-devops-lab-events}"
REGION="us-east-1"

AWS_CMD="aws --endpoint-url $ENDPOINT --region $REGION"

# ---------- Helpers -----------------------------------------------------------
log()  { echo "[$(date +%H:%M:%S)] $*"; }
ok()   { echo "[$(date +%H:%M:%S)] OK  $*"; }
fail() { echo "[$(date +%H:%M:%S)] ERR $*" >&2; exit 1; }

# ---------- Health check ------------------------------------------------------
log "Checking LocalStack health..."
if ! curl -sf "$ENDPOINT/_localstack/health" | grep -q '"s3": "available"'; then
  fail "LocalStack is not ready. Start it with: docker compose up -d"
fi
ok "LocalStack is healthy."

# ---------- Create test file --------------------------------------------------
FILENAME="${1:-test-upload-$(date +%Y%m%d-%H%M%S).txt}"
TMPFILE="$(mktemp)"

cat > "$TMPFILE" <<EOF
LocalStack S3 → Lambda → SQS pipeline test
-------------------------------------------
File      : $FILENAME
Uploaded  : $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Host      : $(hostname)
Purpose   : Validates the event-driven architecture end-to-end.
EOF

log "Created test file: $FILENAME"

# ---------- Upload to S3 ------------------------------------------------------
log "Uploading '$FILENAME' to s3://$BUCKET/ ..."
$AWS_CMD s3 cp "$TMPFILE" "s3://$BUCKET/$FILENAME" \
  --metadata "source=upload_test_file,env=local"

ok "File uploaded to s3://$BUCKET/$FILENAME"
rm -f "$TMPFILE"

# ---------- Wait for Lambda + SQS propagation ---------------------------------
log "Waiting 3 seconds for Lambda to process the event..."
sleep 3

# ---------- Read SQS message --------------------------------------------------
QUEUE_URL="$($AWS_CMD sqs get-queue-url --queue-name "$QUEUE_NAME" \
  --query 'QueueUrl' --output text)"

log "Polling SQS queue: $QUEUE_URL"

MESSAGES=$($AWS_CMD sqs receive-message \
  --queue-url "$QUEUE_URL" \
  --max-number-of-messages 5 \
  --wait-time-seconds 5 \
  --attribute-names All \
  --output json 2>/dev/null || echo '{}')

MSG_COUNT=$(echo "$MESSAGES" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(len(d.get('Messages', [])))")

if [[ "$MSG_COUNT" -eq 0 ]]; then
  echo ""
  echo "  No messages found in SQS yet."
  echo "  The Lambda may still be initialising (cold start)."
  echo "  Re-run the script or check Lambda logs with:"
  echo "    aws --endpoint-url $ENDPOINT logs describe-log-groups"
  echo ""
else
  ok "$MSG_COUNT message(s) received from SQS:"
  echo ""
  echo "$MESSAGES" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for i, msg in enumerate(data.get('Messages', []), 1):
    body = json.loads(msg['Body'])
    print(f'  Message {i}')
    print(f'    MessageId : {msg[\"MessageId\"]}')
    print(f'    File name : {body.get(\"file_name\")}')
    print(f'    Bucket    : {body.get(\"bucket\")}')
    print(f'    Size      : {body.get(\"file_size_bytes\")} bytes')
    print(f'    Status    : {body.get(\"status\")}')
    print(f'    Event time: {body.get(\"event_time\")}')
    print()
"
  echo "Pipeline validated successfully."
fi
