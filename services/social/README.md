# Threshold social service

FastAPI service for Slice 3 groups, posts, comments, reactions, and feed.

All `/v1/*` routes require `X-Threshold-Internal-Token`. Public reads are public
only in the product sense: they do not require `X-Threshold-User-Id`, but they
still must be called through the trusted BFF.

Writes require:

- `X-Threshold-Internal-Token`
- `X-Threshold-User-Id`
- `X-Threshold-Username`
- `X-Threshold-Display-Name`

The browser must never send author snapshot fields directly to `social`.
