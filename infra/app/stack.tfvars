# Terraform-owned runtime toggles live here when they differ from defaults.
# Primary-edge image values below are bootstrap or reviewed-exception pins
# only; routine deploy and rollback task-definition revisions are GitHub
# Actions-owned.

bootstrap_image_tag    = "sha-23f61d05d3a0e2f55def6fcdd2b64ce761817963"         # gitleaks:allow
primary_edge_image_tag = "sha-771fd8aedbe6abe6577f1ef8063f5b0f83478669-amd64-2" # gitleaks:allow
