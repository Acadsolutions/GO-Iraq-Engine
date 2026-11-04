# GO Iraq Engine

Managed routing fork for GO Iraq. Upstream base: valhalla/valhalla at 2085e78a517a0680a39d3b89efb7eff1f5cf9201 (2026-11-03). Original MIT notices and COPYING remain intact. Road data: OpenStreetMap contributors, ODbL, distributed by Geofabrik.

Changes: safe empty alternate filtering; reserve edge-set capacity to avoid repeated rehashing; up to three alternatives (four routes total); bounded two-worker serving; authenticated routing gateway without coordinate/body logging; prebuilt Iraq and Netherlands test-area tiles; tests and immutable image digest delivery. These are targeted changes, not a rewrite or a measured speedup claim.

Build with `docker build -f docker/Dockerfile -t go-iraq-base .` followed by `docker build -f go-iraq/Dockerfile --build-arg BASE_IMAGE=go-iraq-base -t go-iraq-engine .` from a recursive checkout. CI performs both and publishes a commit-tagged image. Set GO_ROUTING_KEY to a random service credential, PORT=8080. Only the application backend receives that credential. The mobile app never receives it.

POST /route and /sources_to_targets use the upstream JSON schema. GET /health exposes readiness only. Request bodies, coordinates and credentials are not logged. Route generation remains subject to graph coverage, access restrictions and engine viability checks; requesting four never promises four.

Update the upstream base using a reviewed merge and rerun native route tests, region route/reverse-heading checks and the application suite. Image publication is separate from deployment and physical driving acceptance.
