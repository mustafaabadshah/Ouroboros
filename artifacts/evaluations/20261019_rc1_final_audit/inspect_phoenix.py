import urllib.request
import json
import sys

url = "http://127.0.0.1:6006/v1/projects/ouroboros-swarm/spans"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))

print("Data type:", type(data))
if isinstance(data, dict):
    print("Dict keys:", list(data.keys()))
    for k, v in data.items():
        if isinstance(v, list):
            print(f"Key '{k}' is list of len {len(v)}")
            if len(v) > 0:
                print(f"  First element type: {type(v[0])}")
                if isinstance(v[0], dict):
                    print(f"  Sample keys: {list(v[0].keys())}")
        else:
            print(f"Key '{k}': {type(v)}")
elif isinstance(data, list):
    print("List len:", len(data))
    if len(data) > 0:
        print("First element type:", type(data[0]))
        if isinstance(data[0], dict):
            print("First item keys:", list(data[0].keys()))
