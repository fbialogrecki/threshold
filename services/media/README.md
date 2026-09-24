# Threshold media service

FastAPI service for image metadata and the SeaweedFS/S3-backed media pipeline.

MVP boundaries:
- owns `MediaAsset` metadata and backend-generated object keys,
- reads S3 runtime settings from OpenBao/ESO materialized env vars,
- never accepts client-controlled bucket or object keys,
- later slices add binary upload, validation, and WebP derivatives.
