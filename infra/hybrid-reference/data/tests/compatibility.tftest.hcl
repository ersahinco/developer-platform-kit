mock_provider "aws" {}
mock_provider "supabase" {}

run "starter_data_plan" {
  command = plan

  variables {
    stack_name                 = "compatibility-proof"
    export_bucket_name         = "compatibility-proof-exports"
    export_writer_user_name    = "existing-export-writer"
    supabase_organization_id   = "organization-proof"
    supabase_project_name      = "compatibility-proof"
    supabase_database_password = "not-a-live-secret" # gitleaks:allow -- mocked provider input
  }

  assert {
    condition     = aws_s3_bucket.exports.bucket == "compatibility-proof-exports"
    error_message = "The object-output bucket address or intent changed."
  }

  assert {
    condition     = supabase_project.reference.name == "compatibility-proof"
    error_message = "The Supabase project address or intent changed."
  }
}
