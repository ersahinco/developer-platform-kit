# Preserve existing resources when adopting workload-driven module instances.

moved {
  from = module.network
  to   = module.network[0]
}

moved {
  from = module.cluster
  to   = module.cluster[0]
}

moved {
  from = module.edge
  to   = module.edge[0]
}

moved {
  from = module.database
  to   = module.database[0]
}

moved {
  from = module.artifacts
  to   = module.artifacts[0]
}

moved {
  from = module.spark
  to   = module.spark[0]
}
