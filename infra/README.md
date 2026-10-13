# infra/

Infrastructure configuration for non-Docker deployment targets.

This directory is reserved for production infrastructure configuration:
Terraform, Kubernetes manifests, or cloud-provider-specific configuration.

**Current status:** Empty. Local development uses docker-compose.yml at the
repository root. Production infrastructure is out of scope until Phase 07
confirms requirements.

Do not add infrastructure here without a documented requirement and an
accompanying or updated ADR.
