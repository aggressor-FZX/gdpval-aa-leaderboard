import json, re
p='Model_Efficiency_Comparison.ipynb'
nb=json.load(open(p))
cells=nb['cells']

def find(pred):
    for i,c in enumerate(cells):
        if c['cell_type']=='code' and pred(''.join(c['source'])):
            return i
    return None

i317b=find(lambda s: "3.17b SATURATION UTILITY ON AA's OFFICIAL TIME-PER-TASK" in s)
i316=find(lambda s: "3.16 SATURATION-UTILITY WORKHORSE RANKING" in s)
print('cells', i316, i317b)

def src(i): return ''.join(cells[i]['source'])
def setsrc(i,s): cells[i]['source']=s.splitlines(keepends=True)

# ---------- Bug B: strict TPT variant matching ----------
s=src(i317b)
old = """# build lookup: normalized base name + variant -> TPT
_tpt_lookup = {}
for _name, _t in _tpt_map.items():
    _v = _lb_variant(_name)
    _base = _norm_lb(_name)
    _tpt_lookup[(_base, _v)] = _t

def _find_tpt(model):
    v = variant_of(model)
    base = _norm_api(model)
    if (base, v.lower()) in _tpt_lookup:
        return _tpt_lookup[(base, v.lower())]
    if (base, '') in _tpt_lookup and v == '':
        return _tpt_lookup[(base, '')]
    # fallback: unique base match regardless of variant
    cands = [t for (b, vv), t in _tpt_lookup.items() if b == base]
    return cands[0] if len(cands) == 1 else np.nan
"""
new = """# build lookup: normalized base name + LOWERCASE variant -> TPT
# Keys are lowercased so the lookup matches variant_of() output exactly.
_tpt_lookup = {}
for _name, _t in _tpt_map.items():
    _v = _lb_variant(_name).lower()
    _base = _norm_lb(_name)
    _tpt_lookup[(_base, _v)] = _t

def _find_tpt(model):
    \"\"\"Strict variant-aware TPT lookup.

    A row only inherits a Time-per-Task value when the reasoning-effort
    variant matches EXACTLY. No cross-variant imputation: a (Max) row never
    borrows a (Non-reasoning) row's TPT, because the two configurations
    complete tasks in very different wall-clock time.
    \"\"\"
    v = variant_of(model).lower()
    base = _norm_api(model)
    return _tpt_lookup.get((base, v), np.nan)
"""
assert old in s
s=s.replace(old,new)

# ---------- OpenRouter price join ----------
old2 = """_ok = _b17[_b17['TPT'].notna() & _b17['I'].notna() & _b17['R'].notna() & (_b17['C'] > 0)].copy()
_ok['TPT'] = _ok['TPT'].astype(float)
"""
new2 = """_ok = _b17[_b17['TPT'].notna() & _b17['I'].notna() & _b17['R'].notna() & (_b17['C'] > 0)].copy()
_ok['TPT'] = _ok['TPT'].astype(float)

# ── OpenRouter real prices: best-value provider vs cheapest provider ───────
# The score above uses AA's LISTED blended price (C). What you actually pay on
# OpenRouter depends on WHICH endpoint serves the request:
#   * best-value provider = the endpoint with the highest sqrt(tps)/price
#     among endpoints that pass the quality gates (uptime>=95%, ctx>=100k,
#     no fp4/mxfp4 quant)  -> results/provider_value_by_model.json 'chosen'
#   * cheapest provider    = the cheapest blended-price endpoint on the model
#     (what the router tends to pick) -> 'default'
# These are per-endpoint blended $/1M (3:1 input:output) from the OpenRouter
# endpoints API, cached in results/provider_value_by_model.json.
_OR_CACHE = 'results/provider_value_by_model.json'
_or_cache = {}
if os.path.exists(_OR_CACHE):
    with open(_OR_CACHE) as _f:
        _or_cache = json.load(_f)
else:
    print('WARNING: provider_value_by_model.json not found — OpenRouter prices '
          'will show n/a (run 3.11 first).')

def _or_price_fields(model):
    _rec = _or_cache.get(model)
    if not _rec:
        return (np.nan, 'n/a', np.nan, 'n/a')
    _c = _rec.get('chosen') or {}
    _d = _rec.get('default') or _rec.get('default_by_blend') or {}
    _cp = _c.get('price_blend')
    _dp = _d.get('price_blend')
    return (float(_cp) if _cp is not None else np.nan,
            str(_c.get('provider') or 'n/a'),
            float(_dp) if _dp is not None else np.nan,
            str(_d.get('provider') or 'n/a'))

_orv = _ok['Model'].map(_or_price_fields)
_ok['OR_Best_Price'] = _orv.map(lambda t: t[0])
_ok['OR_Best_Provider'] = _orv.map(lambda t: t[1])
_ok['OR_Cheap_Price'] = _orv.map(lambda t: t[2])
_ok['OR_Cheap_Provider'] = _orv.map(lambda t: t[3])
_n_or = int(_ok['OR_Best_Price'].notna().sum())
print(f'OpenRouter prices joined: {_n_or}/{len(_ok)} rows '
      f'(best-value + cheapest provider)')
"""
assert old2 in s
s=s.replace(old2,new2)

# ---------- printed table: add OR price columns ----------
old3 = """    print(f"{'#':<4}{'model (variant)':<46}{'E2':>8}{'U_I':>6}{'U_TPT':>6}"
          f"{'TPT s':>9}{'I':>6}{'R':>5}{'$/1M':>7}  flags")
    print('-' * 122)
    for _i, (_, r) in enumerate(_fr.sort_values('E2', ascending=False).head(25).iterrows(), 1):
        _fl = []
        if r.get('R_fill'): _fl.append('R†')
        if r.get('Default_Effort'): _fl.append('def')
        print(f"{_i:<4}{r['Label']:<46}{r['E2']:>8.2f}{U_I17(r['I']):>6.2f}"
              f"{U_TPT(r['TPT']):>6.2f}{r['TPT']:>9.1f}"
              f"{r['I']:>6.1f}{r['R']:>5.2f}{r['C']:>7.2f}  {','.join(_fl)}")
"""
new3 = """    print(f"{'#':<4}{'model (variant)':<40}{'E2':>8}{'U_I':>6}{'U_TPT':>6}"
          f"{'TPT s':>8}{'I':>6}{'R':>5}{'AA $/M':>8}"
          f"{'OR best $/M':>12}{'OR cheap $/M':>13}  flags")
    print('-' * 140)
    for _i, (_, r) in enumerate(_fr.sort_values('E2', ascending=False).head(25).iterrows(), 1):
        _fl = []
        if r.get('R_fill'): _fl.append('R†')
        if r.get('Default_Effort'): _fl.append('def')
        _bp = ('n/a' if pd.isna(r.get('OR_Best_Price'))
               else f"${r['OR_Best_Price']:.2f} {str(r['OR_Best_Provider'])[:10]}")
        _cp = ('n/a' if pd.isna(r.get('OR_Cheap_Price'))
               else f"${r['OR_Cheap_Price']:.2f} {str(r['OR_Cheap_Provider'])[:10]}")
        print(f"{_i:<4}{r['Label']:<40}{r['E2']:>8.2f}{U_I17(r['I']):>6.2f}"
              f"{U_TPT(r['TPT']):>6.2f}{r['TPT']:>8.1f}"
              f"{r['I']:>6.1f}{r['R']:>5.2f}{r['C']:>8.2f}"
              f"{_bp:>12}{_cp:>13}  {','.join(_fl)}")
"""
assert old3 in s
s=s.replace(old3,new3)

# ---------- Bug A: top-15 selection + OR price annotation in chart ----------
old4 = """    _top = _frame.head(15).sort_values('E2')
    _colors2 = []
    for _, r in _top.iterrows():
        if _ttl.startswith('3.17b RANKING B') and r.get('Any_Imputed', False):
            _colors2.append('#e8833a')
        elif r.get('Default_Effort', False):
            _colors2.append('#7d3c98')
        else:
            _colors2.append('#2f7ed8')
    _xb = np.arange(len(_top))
    _axx.barh(_xb, _top['E2'], color=_colors2, edgecolor='black', linewidth=0.4)
    _xmax2 = float(_top['E2'].max()) if len(_top) and np.isfinite(_top['E2'].max()) else 1.0
    for _yy, (_, r) in enumerate(_top.iterrows()):
        _axx.text(r['E2'] + 0.015 * _xmax2, _yy,
                  f"I={r['I']:.0f} TPT={r['TPT']:.0f}s", va='center', fontsize=7)
"""
new4 = """    # TOP-15 BY E2 (not the first 15 rows of the frame) — Bug A fix.
    _top = _frame.sort_values('E2', ascending=False).head(15).sort_values('E2')
    _colors2 = []
    for _, r in _top.iterrows():
        if _ttl.startswith('3.17b RANKING B') and r.get('Any_Imputed', False):
            _colors2.append('#e8833a')
        elif r.get('Default_Effort', False):
            _colors2.append('#7d3c98')
        else:
            _colors2.append('#2f7ed8')
    _xb = np.arange(len(_top))
    _axx.barh(_xb, _top['E2'], color=_colors2, edgecolor='black', linewidth=0.4)
    _xmax2 = float(_top['E2'].max()) if len(_top) and np.isfinite(_top['E2'].max()) else 1.0
    for _yy, (_, r) in enumerate(_top.iterrows()):
        # annotation: AA listed price + OpenRouter best-value & cheapest prices
        _bp = 'n/a' if pd.isna(r.get('OR_Best_Price')) else f"${r['OR_Best_Price']:.2f}"
        _cp = 'n/a' if pd.isna(r.get('OR_Cheat_Price')) else f"${r['OR_Cheat_Price']:.2f}"
        _axx.text(r['E2'] + 0.015 * _xmax2, _yy,
                  f"I={r['I']:.0f} TPT={r['TPT']:.0f}s | AA ${r['C']:.2f}"
                  f" | OR best {_bp} | OR cheap {_cp}",
                  va='center', fontsize=6)
"""
assert old4 in s
s=s.replace(old4,new4)

# fix typo introduced above
s=s.replace("r.get('OR_Cheat_Price')","r.get('OR_Cheap_Price')")

# widen xlim for longer labels
s=s.replace("    _axx.set_xlim(0, _xmax2 * 1.28)","    _axx.set_xlim(0, _xmax2 * 1.55)")

# note source update
s=s.replace("note_source(SRC_AA + ' Time per Task: AA leaderboard (weighted avg wall-clock per Intelligence Index task), scraped 2026-10-25.')",
            "note_source(SRC_AA + ' Time per Task: AA leaderboard (weighted avg wall-clock per Intelligence Index task), scraped 2026-10-25. '\n          'OR prices: OpenRouter endpoints API per-endpoint blended $/1M (best-value vs cheapest provider).')")

setsrc(i317b,s)

# ---------- 3.16 top-15 fix ----------
s2=src(i316)
old5="    _top = _frame.head(15).sort_values(_col)"
new5="    # TOP-15 BY SCORE (not the first 15 rows of the frame) — Bug A fix.\n    _top = _frame.sort_values(_col, ascending=False).head(15).sort_values(_col)"
assert old5 in s2
s2=s2.replace(old5,new5)
setsrc(i316,s2)

json.dump(nb,open(p,'w'),indent=1)
print('written')
