import json, sys
sys.path.insert(0, '.')
from gp_runner.manifest_parser import extract_module_info
info = extract_module_info('/Users/liefeld/GenePattern/modules/tfsites.GenerateMotifDatabase/build/tfsites.GenerateMotifDatabase.zip')
print(json.dumps(info, indent=2))

