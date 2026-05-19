# Infrastructure Catalog

`infra/catalog/` is the extraction boundary for reusable infrastructure building
blocks.

Do not force module creation for its own sake. Extract into the catalog only
when a cloud primitive or runtime pattern is stable enough to reuse without
hiding the underlying standard tool.
