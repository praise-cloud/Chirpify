# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | ✅ Active development |

## Reporting a Vulnerability

We take the security of Chirpify seriously. If you believe you have found a security vulnerability, please report it to us as described below.

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report them via email to: **security@chirpify.dev**

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

### What to include

- Type of issue (e.g., SQL injection, cross-site scripting, privilege escalation)
- Full paths of source file(s) related to the manifestation of the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

## Security Architecture

### Data Protection

- **In Transit:** All API traffic is encrypted via TLS 1.3 through CloudFront and ALB
- **At Rest:** RDS PostgreSQL, ElastiCache Redis, and S3 data lake are encrypted using AWS KMS
- **Event Data:** Raw events stored in S3 are encrypted at rest with server-side encryption (SSE-S3 or SSE-KMS)

### Access Control

- **Network:** All resources (Fargate, RDS, Redis, Lambda) reside in private subnets — no direct internet access
- **IAM:** Least-privilege IAM policies for all services. No hardcoded credentials in code or configuration
- **API Authentication:** Event ingestion and analytics APIs require valid API keys or JWT tokens

### Infrastructure Security

- **WAF:** Web Application Firewall blocks common attack patterns (SQL injection, XSS, DDoS)
- **Security Groups:** Database and cache security groups only allow traffic from the application tier
- **VPC Flow Logs:** Enabled for network traffic monitoring and anomaly detection

### Event Processing Security

- **SQS:** All messages are encrypted at rest (SSE-SQS) and in transit
- **Lambda:** Runs in VPC with minimal IAM permissions — only SQS read, RDS/Redis write, S3 write
- **Input Validation:** All event data is validated against Pydantic schemas before processing

## Responsible Disclosure

We ask that you:

- Give us reasonable time to investigate and fix the issue before publicly disclosing it
- Make a good faith effort to avoid privacy violations, destruction of data, and interruption of our service
- Do not exploit the vulnerability beyond what is necessary to demonstrate the issue

## Recognition

We maintain a hall of fame for security researchers who help us improve Chirpify's security. If you report a valid vulnerability, we will acknowledge your contribution (with your permission).
