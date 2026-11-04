# GO Iraq Engine

Managed routing engine for [GO Iraq](https://github.com/Acadsolutions/GO-Iraq), maintained by ACAD Solutions. This fork gives the project control over routing configuration, map-data builds, service capacity and targeted algorithm changes.

[Build and service configuration](go-iraq/README.md). [Native build and isolated route acceptance](https://github.com/Acadsolutions/GO-Iraq-Engine/actions).

The initial changes guard empty alternate candidates, reserve edge-set capacity, bound responses to four distinct actual paths, and provide an authenticated service with no request-coordinate logging. Automated acceptance covers Baghdad and the Nijkerk test area, including reverse-heading requests that retain the destination. Test definitions alone are not passing results; inspect the workflow for the exact image commit before deployment.

This is a maintained fork of Valhalla, based initially on `2085e78a517a0680a39d3b89efb7eff1f5cf9201` (3 November 2026). Original MIT notices, `LICENSE.md` and `COPYING` are preserved. No complete rewrite or measured performance superiority is claimed. OpenStreetMap road data is subject to ODbL attribution. [Upstream documentation](UPSTREAM-README.md).
