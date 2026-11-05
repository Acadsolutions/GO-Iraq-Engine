import json
from pathlib import Path
p=Path('/data/config.json')
config=json.loads(p.read_text())
config['loki']['actions']=sorted(set(config['loki']['actions'])|{'locate','trace_attributes'})
config['service_limits'].update(min_linear_cost_factor=0,max_linear_cost_edges=1024)
p.write_text(json.dumps(config))
