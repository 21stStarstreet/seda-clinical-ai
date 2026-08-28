import json
from enum import Enum
class Color(str, Enum): RED = 'red'
print(json.dumps({'c': Color.RED}))
