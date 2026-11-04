import json, pathlib, subprocess
config = json.loads(subprocess.check_output(["valhalla_build_config"]))
config["mjolnir"].update(tile_dir="/data/tiles", tile_extract="/data/tiles.tar",
    admin="/data/admin.sqlite", timezone="/data/tz.sqlite", concurrency=2,
    max_cache_size=134217728, use_lru_mem_cache=True, lru_mem_cache_hard_control=True)
config["httpd"]["service"]["listen"] = "tcp://127.0.0.1:8002"
config["loki"]["actions"] = ["route", "sources_to_targets", "status"]
config["service_limits"]["max_alternates"] = 3
config["service_limits"]["max_exclude_locations"] = 20
config["service_limits"]["max_distance_disable_hierarchy_culling"] = 2000000
for mode in ["auto", "pedestrian"]:
    config["service_limits"][mode].update(max_locations=6, max_matrix_location_pairs=36)
config["logging"] = {"type": "std_out", "color": False}
pathlib.Path("/data/config.json").write_text(json.dumps(config))
