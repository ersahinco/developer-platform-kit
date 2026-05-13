# Terraform-owned runtime toggles live here when they differ from defaults.
# App image values below are bootstrap or reviewed-exception pins only; routine
# app deploy and rollback task-definition revisions are GitHub Actions-owned.

initial_image_tag = "sha-23f61d05d3a0e2f55def6fcdd2b64ce761817963"
app_image_tag     = "sha-771fd8aedbe6abe6577f1ef8063f5b0f83478669-amd64-2"
