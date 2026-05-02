# App-owned overrides live here when they need to differ from defaults.
# CI plans and applies this file directly, so deployed feature toggles belong
# here instead of one-off Terraform CLI flags.

enable_observability_stack = true
initial_image_tag          = "sha-23f61d05d3a0e2f55def6fcdd2b64ce761817963"
app_image_tag              = "sha-771fd8aedbe6abe6577f1ef8063f5b0f83478669-amd64-2"
firelens_image_tag         = "sha-771fd8aedbe6abe6577f1ef8063f5b0f83478669-amd64-2"
