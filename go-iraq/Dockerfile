ARG BASE_IMAGE=go-iraq-base
FROM ${BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends osmium-tool && rm -rf /var/lib/apt/lists/*
COPY go-iraq /opt/go-iraq
COPY COPYING LICENSE.md /opt/go-iraq/licenses/
ARG DATA_REVISION=2026-11-04
RUN mkdir -p /data/tiles /downloads && python3 /opt/go-iraq/configure.py && \
    curl --fail --location --retry 3 -o /downloads/iraq.osm.pbf https://download.geofabrik.de/asia/iraq-latest.osm.pbf && \
    curl --fail --location --retry 3 -o /downloads/netherlands.osm.pbf https://download.geofabrik.de/europe/netherlands-latest.osm.pbf && \
    osmium extract -b 4.65,51.65,6.35,52.85 -s complete_ways /downloads/netherlands.osm.pbf -o /downloads/nijkerk.osm.pbf && \
    sha256sum /downloads/*.osm.pbf > /data/source-checksums.txt && \
    valhalla_build_admins -c /data/config.json /downloads/iraq.osm.pbf /downloads/nijkerk.osm.pbf && \
    valhalla_build_timezones > /data/tz.sqlite && \
    valhalla_build_tiles -c /data/config.json /downloads/iraq.osm.pbf /downloads/nijkerk.osm.pbf && \
    valhalla_build_extract -c /data/config.json && \
    rm -rf /downloads /data/tiles && \
    python3 -m unittest discover -s /opt/go-iraq -p 'test_*.py' && \
    chmod +x /opt/go-iraq/start.sh && chmod -R a+rX /data /opt/go-iraq
EXPOSE 8080
ENTRYPOINT ["/opt/go-iraq/start.sh"]
