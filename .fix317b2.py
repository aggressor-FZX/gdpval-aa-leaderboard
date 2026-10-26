import json
p='Model_Efficiency_Comparison.ipynb'
nb=json.load(open(p))
cells=nb['cells']
i=46
s=''.join(cells[i]['source'])
if 'import json' not in s.split('\n')[0]:
    s=s.replace("import numpy as np, pandas as pd, matplotlib.pyplot as plt, re, os, requests",
                "import numpy as np, pandas as pd, matplotlib.pyplot as plt, re, os, requests, json")
cells[i]['source']=s.splitlines(keepends=True)

j=45
md=''.join(cells[j]['source'])
old="- **Paired rankings** mirror 3.16: A = measured only, B = expanded (R\u2026 flags). Default-effort"
if old not in md:
    old="- **Paired rankings** mirror 3.16: A = measured only, B = expanded (R† flags). Default-effort"
assert old in md, md[:400]
new = old + """
- **OpenRouter real prices are shown on every bar**: `OR best` = the best-value endpoint
  (highest √tok/s ÷ price among endpoints passing the quality gates) and `OR cheap` = the
  cheapest blended-price endpoint on that model (what the router tends to pick). Both are
  per-endpoint blended $/1M from the OpenRouter endpoints API, cached in
  `results/provider_value_by_model.json`. The score itself still divides by AA's **listed**
  price (`AA $/M`), so the annotation shows how far real-world cost can drift from the
  listed figure.
- **Strict variant matching**: a row only inherits a Time-per-Task value when its
  reasoning-effort variant matches exactly — a `(Max)` row never borrows a
  `(Non-reasoning)` row's TPT."""
md=md.replace(old,new)
cells[j]['source']=md.splitlines(keepends=True)
json.dump(nb,open(p,'w'),indent=1)
print('ok')
