# GO Iraq Engine — 4 November 2026 verification

Service-layer source: `71f51ef0ed99e9a16a282d652b79c409bdf09ed5`.
Native core and road-data base: `c06733089a48efb78b41e14cbc4c8b9df744e9f8`.
Final image: `ghcr.io/acadsolutions/go-iraq-engine@sha256:4091a372601ea8108947b2d0b9f53a87b73a1b603b747bce7fa67fd032b08326`.

- [Native build](https://github.com/Acadsolutions/GO-Iraq-Engine/actions/runs/41915408888): four alternate-path tests passed; Iraq and Nijkerk-area road image built.
- [Service-layer build](https://github.com/Acadsolutions/GO-Iraq-Engine/actions/runs/41919229484): 12 gateway tests passed; immutable image published.
- [Isolated acceptance](https://github.com/Acadsolutions/GO-Iraq-Engine/actions/runs/41919376208): passed with networking disabled except container loopback, 1 CPU / 1 GiB.

| Public road fixture | Distinct choices | First request | Return-direction recovery | Warm median (5) | Warm maximum (5) |
|---|---:|---:|---:|---:|---:|
| Baghdad | 4 | 59.00 ms | 9.10 ms | 12.57 ms | 14.26 ms |
| Nijkerk | 1 | 7.65 ms | 6.63 ms | 4.06 ms | 5.78 ms |

Both legal return-route cases retained the original destination B. Anonymous
requests returned 401; requesting more than three alternatives returned 400.
The Baghdad one-way-carriageway reverse-heading fixture returned 422
`direction_unavailable`, rather than a silently opposing departure. The Nijkerk
fixture could return a compatible route normally. Tests also reject fabricated
alternatives and duplicate geometry. Post-test memory was 76.72 MiB; peak memory
and sustained concurrent capacity were not measured.

The initial reverse test flipped heading on an outgoing one-way carriageway.
It exposed that heading is a preference in upstream correlation and can be
relaxed. It was not a valid simulation of a legal U-turn onto the return
carriageway. Acceptance now tests both: legal return-road recovery must produce
a compatible route, while an incompatible fallback must not be published as
ordinary forward guidance. The gateway may promote an already-computed compatible
alternate or return an explicit failure; it never invents road geometry or turns.

These results are CI loopback samples, not physical driving, cellular latency,
production load guarantees, or a performance comparison against upstream.
The phone backend activation and field acceptance are separate delivery steps.
Original source and data notices remain in the repository and runtime image.
