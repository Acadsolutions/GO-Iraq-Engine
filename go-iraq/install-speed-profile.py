"""Install the pinned road speed profile and record the policy for future tile builds."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

DATA = Path("/data")
REVISION = "c9c6872d5ec656f5d290944b44eb1a103ed539fa"
URL = f"https://raw.githubusercontent.com/OpenStreetMapSpeeds/schema/{REVISION}"
PROFILE = DATA / "default_speeds.json"
with urlopen(URL + "/default_speeds.json", timeout=60) as response:
    payload = response.read()
fingerprint = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
if fingerprint != "39b0aa9638cd75238d8d11c188f580a123d7dc9f":
    raise ValueError("Unexpected road speed profile")
PROFILE.write_bytes(payload)
config_path = DATA / "config.json"
config = json.loads(config_path.read_text())
config["mjolnir"]["default_speeds_config"] = str(PROFILE)
config_path.write_text(json.dumps(config))
