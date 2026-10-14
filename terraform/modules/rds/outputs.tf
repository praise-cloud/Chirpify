output "endpoint" {
  description = "The connection endpoint for the PostgreSQL database"
  value       = aws_db_instance.postgres.endpoint
}

output "address" {
  description = "The hostname of the database"
  value       = aws_db_instance.postgres.address
}

output "port" {
  description = "The database port"
  value       = aws_db_instance.postgres.port
}
