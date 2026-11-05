FROM ghcr.io/acadsolutions/go-iraq-engine@sha256:4091a372601ea8108947b2d0b9f53a87b73a1b603b747bce7fa67fd032b08326 AS profile
USER root
COPY go-iraq/install-speed-profile.py /opt/go-iraq/
RUN python3 /opt/go-iraq/install-speed-profile.py && mkdir -p /data/tiles && \
    tar xf /data/tiles.tar -C /data/tiles && valhalla_assign_speeds -c /data/config.json -j 1 && \
    rm /data/tiles.tar && valhalla_build_extract -c /data/config.json

FROM ghcr.io/acadsolutions/go-iraq-engine@sha256:4091a372601ea8108947b2d0b9f53a87b73a1b603b747bce7fa67fd032b08326
COPY --from=profile /data/tiles.tar /data/config.json /data/default_speeds.json /data/
COPY go-iraq/OpenStreetMapSpeeds-LICENSE /opt/go-iraq/licenses/OpenStreetMapSpeeds-LICENSE
