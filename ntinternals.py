import re, tqdm, requests, os

URL = 'http://undocumented.ntinternals.net/files/treearr.js'

req = requests.get(URL).text
items = re.search(r'var\s+TITEMS\s+=\s+(\[.*\n\];)', req, re.DOTALL | re.MULTILINE)
data = items.group()[4:].strip()[:-1].replace(', null', ', None')
TITEMS = []
exec(data)
print(TITEMS)