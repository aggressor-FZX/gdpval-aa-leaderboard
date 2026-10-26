import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
try:
    import seaborn as sns
    sns.set_style("whitegrid")
except Exception:
    sns = None
    # fallback to a stable matplotlib style
    plt.style.use('ggplot')
from pathlib import Path

if sns is not None:
    sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10

PLOTS_DIR = Path('plots')
PLOTS_DIR.mkdir(exist_ok=True)

# Load data (prefer local CSV fallback)
CSV = 'ai_models_extracted.csv'
if os.path.exists(CSV):
    df = pd.read_csv(CSV)
else:
    # try API fetch as a fallback (uses same API from notebook)
    try:
        import requests
        API_KEY = "aa_SsolJBCEakryDOtmPGuLmpJiohdZMFFF"
        BASE_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
        headers = {"x-api-key": API_KEY}
        resp = requests.get(BASE_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and 'data' in data:
            raw = data['data']
        elif isinstance(data, list):
            raw = data
        elif isinstance(data, dict) and 'models' in data:
            raw = data['models']
        else:
            raise RuntimeError('Unexpected API response structure')
        df = pd.json_normalize(raw, sep='_')
        print(f"Loaded {len(df)} rows from Artificial Analysis API")
    except Exception as e:
        raise FileNotFoundError(f"Could not find local CSV and API fetch failed: {e}")

# Normalize columns with safe fallbacks
get = df.get

# Map core metrics
if 'name' in df.columns:
    df = df.rename(columns={'name': 'Model'})

df['AA_Intelligence_Index'] = get('AA_Intelligence_Index', get('evaluations_artificial_analysis_intelligence_index', np.nan))
df['GDPval_AA'] = df['AA_Intelligence_Index']
df['TerminalBench_Hard'] = get('TerminalBench_Hard', get('evaluations_artificial_analysis_coding_index', 0)).fillna(0)
df['AA_Omniscience_Index'] = get('AA_Omniscience_Index', get('evaluations_mmlu_pro', 0)).fillna(0)

# Pricing: prefer API blended 3:1
price_input = get('pricing_price_1m_input_tokens', get('Price_Input_USD_per_1M', 0)).fillna(0)
price_output = get('pricing_price_1m_output_tokens', get('Price_Output_USD_per_1M', 0)).fillna(0)
api_blended = get('pricing_price_1m_blended_3_to_1', get('Price_Blended_USD_per_1M', np.nan))

# Derived blended
try:
    derived = (price_input * 3 + price_output) / 4
except Exception:
    derived = pd.Series(0, index=df.index)

# Use API blended where derived is zero or NaN
df['Price_Blended_USD_per_1M'] = derived.where((derived > 0) & (~derived.isna()), api_blended)
# fallback to any named column
if df['Price_Blended_USD_per_1M'].isna().all():
    if 'Price_Blended_USD_per_1M' in df.columns:
        df['Price_Blended_USD_per_1M'] = df['Price_Blended_USD_per_1M'].fillna(0)
    else:
        df['Price_Blended_USD_per_1M'] = 0

# Cost
df['Cost_to_Run_Index'] = df['AA_Intelligence_Index'] * df['Price_Blended_USD_per_1M']

# Basic filtered set
int_threshold = 30
df_filtered = df[(df['AA_Intelligence_Index'] > int_threshold) & (df['Price_Blended_USD_per_1M'] > 0)].copy()
if df_filtered.empty:
    print('Warning: filtered dataframe is empty after applying thresholds; relaxing price filter')
    df_filtered = df[df['AA_Intelligence_Index'] > int_threshold].copy()

# 1) GDPval-AA Leaderboard plot (Intelligence vs ELO)
plt.figure(figsize=(14,8))
if 'GDPval_AA' not in df_filtered.columns:
    df_filtered['GDPval_AA'] = df_filtered['AA_Intelligence_Index']

# tier
def get_tier(score):
    if score >= 55:
        return 'Elite'
    elif score >= 50:
        return 'Advanced'
    elif score >= 45:
        return 'Competitive'
    else:
        return 'Standard'

df_filtered['Tier'] = df_filtered['GDPval_AA'].apply(get_tier)

colors = {'Elite':'#2E7D32','Advanced':'#1976D2','Competitive':'#F57C00','Standard':'#C62828'}
for tier in ['Elite','Advanced','Competitive','Standard']:
    sub = df_filtered[df_filtered['Tier']==tier]
    if not sub.empty:
        plt.scatter(sub['AA_Intelligence_Index'], sub['GDPval_AA'], s=200, color=colors[tier], label=tier, alpha=0.8, edgecolors='black')

for _, r in df_filtered.iterrows():
    plt.annotate(r.get('Model', ''), (r['AA_Intelligence_Index'], r['GDPval_AA']), xytext=(4,4), textcoords='offset points', fontsize=8)

plt.xlabel('AA Intelligence Index')
plt.ylabel('Agentic ELO (GDPval_AA)')
plt.title(f'GDPval-AA Leaderboard: Agentic Performance vs Intelligence (Intelligence > {int_threshold})')
plt.legend(title='Performance Tier')
plt.grid(alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'gdpval_aa_leaderboard_fixed.png', dpi=300, bbox_inches='tight')
plt.close()
print('Saved: plots/gdpval_aa_leaderboard_fixed.png')

# 2) Enhanced agentic map
fig, ax = plt.subplots(figsize=(16,9))
if df_filtered['Cost_to_Run_Index'].max() == 0:
    df_filtered['MarkerSize'] = 200
else:
    df_filtered['MarkerSize'] = (df_filtered['Cost_to_Run_Index'] / (df_filtered['Cost_to_Run_Index'].max())) * 1500 + 100

sc = ax.scatter(df_filtered['AA_Intelligence_Index'], df_filtered['GDPval_AA'], s=df_filtered['MarkerSize'], c=df_filtered['TerminalBench_Hard'], cmap='plasma', alpha=0.6, edgecolors='black')
cbar = fig.colorbar(sc, ax=ax)
cbar.set_label('TerminalBench Hard Performance')
ax.set_xlabel('AA Intelligence Index')
ax.set_ylabel('Agentic ELO (GDPval_AA)')
ax.set_title('Agentic Skills Over Intelligence (Bubble size = Cost to Run Test, Color = TerminalBench Hard)')
ax.grid(True, alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'enhanced_agentic_map_fixed.png', dpi=300, bbox_inches='tight')
plt.close()
print('Saved: plots/enhanced_agentic_map_fixed.png')

# 3) ELO vs Cost Analysis (models > 30)
df_cost_analysis = df[df['AA_Intelligence_Index'] > int_threshold].copy()
if 'Price_Blended_USD_per_1M' not in df_cost_analysis.columns:
    df_cost_analysis['Price_Blended_USD_per_1M'] = df_cost_analysis['Price_Blended_USD_per_1M']

df_cost_analysis = df_cost_analysis[df_cost_analysis['Price_Blended_USD_per_1M'].notna()].copy()
if df_cost_analysis.empty:
    print('Warning: cost analysis dataframe empty; skipping elo_vs_cost_analysis')
else:
    df_cost_analysis['BubbleSize'] = (df_cost_analysis['Price_Blended_USD_per_1M'] * 50).clip(lower=100, upper=800)
    fig, ax = plt.subplots(figsize=(15,9))
    sc = ax.scatter(df_cost_analysis['GDPval_AA'], df_cost_analysis['AA_Intelligence_Index'], s=df_cost_analysis['BubbleSize'], c=df_cost_analysis['Price_Blended_USD_per_1M'], cmap='YlOrRd', alpha=0.7, edgecolors='black', linewidth=1)
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label('Price (USD per 1M tokens, blended 3:1)')
    ax.set_xlabel('Agentic ELO (GDPval_AA)')
    ax.set_ylabel('AA Intelligence Index')
    ax.set_title('ELO Score vs Cost Analysis (Intelligence on Y-axis, Bubble size = Cost)')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / 'elo_vs_cost_analysis_fixed.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('Saved: plots/elo_vs_cost_analysis_fixed.png')

# 4) Top 30 Intelligence vs Cost_to_Run_Index
if len(df_filtered) > 0:
    df_top30 = df_filtered.sort_values('AA_Intelligence_Index', ascending=False).head(30).copy()
    df_top30['Efficiency'] = df_top30['AA_Intelligence_Index'] / df_top30['Price_Blended_USD_per_1M'].replace(0, np.nan)
    df_top30['MarkerSize'] = (df_top30['AA_Omniscience_Index'] / (df_top30['AA_Omniscience_Index'].max() if df_top30['AA_Omniscience_Index'].max()>0 else 1)) * 1000 + 100
    fig, ax = plt.subplots(figsize=(16,9))
    sc = ax.scatter(df_top30['AA_Intelligence_Index'], df_top30['Cost_to_Run_Index'], s=df_top30['MarkerSize'], c=df_top30['Efficiency'], cmap='YlOrRd', alpha=0.7, edgecolors='black')
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label('Intelligence per Dollar (Value Efficiency Index)')
    ax.set_xlabel('AA Intelligence Index')
    ax.set_ylabel('Total Cost to Run Test Suite (Intelligence * Blended Price) (USD)')
    ax.set_title('Top 30 Models: Intelligence vs Cost to Run Intelligence Test Suite')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / 'intelligence_weighted_test_cost_top30_fixed.png', dpi=300, bbox_inches='tight')
    plt.close()
    print('Saved: plots/intelligence_weighted_test_cost_top30_fixed.png')

print('\nAll specified plots regenerated with standardized titles/axis labels.')
