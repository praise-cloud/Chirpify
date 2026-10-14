output "dns_name" {
  description = "The DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "arn" {
  description = "The ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "target_group_arn" {
  description = "The ARN of the target group for ECS Fargate"
  value       = aws_lb_target_group.api.arn
}
