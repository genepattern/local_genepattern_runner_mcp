import sys; 
sys.path.insert(0, 'runner'); 
sys.path.insert(0, '.')
from tools import parse_gp_module
print(parse_gp_module('/Users/liefeld/GenePattern/modules/tfsites.GenerateMotifDatabase/build/tfsites.GenerateMotifDatabase.zip'))
