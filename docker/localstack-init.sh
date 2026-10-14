#!/bin/bash
# ==============================================================================
# LocalStack Initialization Script
# Automatically creates SQS queues and S3 data lake bucket upon container start
# ==============================================================================

echo "Initializing LocalStack AWS simulated resources for Chirpify..."

# 1. Create Dead Letter Queue (DLQ)
awslocal sqs create-queue --queue-name chirpify-events-dlq --region us-east-1
echo "Created SQS DLQ: chirpify-events-dlq"

# Get DLQ ARN
DLQ_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url http://localhost:4566/000000000000/chirpify-events-dlq \
    --attribute-names QueueArn \
    --query 'Attributes.QueueArn' \
    --output text)

# 2. Create Main Ingestion Queue with RedrivePolicy pointing to DLQ
REDRIVE_POLICY="{\"deadLetterTargetArn\":\"${DLQ_ARN}\",\"maxReceiveCount\":3}"

awslocal sqs create-queue \
    --queue-name chirpify-events-queue \
    --attributes "{\"RedrivePolicy\":${REDRIVE_POLICY}}" \
    --region us-east-1
echo "Created SQS Main Queue: chirpify-events-queue with DLQ attached"

# 3. Create S3 Raw Events Bucket
awslocal s3 mb s3://chirpify-raw-events-bucket --region us-east-1
echo "Created S3 Bucket: chirpify-raw-events-bucket"

echo "LocalStack initialization complete!"
