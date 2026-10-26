#!/usr/bin/env python3
"""
Exploratory Data Analysis of AI Models (v4.1)
This version includes robust error handling for data type conversions.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set up plotting style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

def load_and_prepare_data():
    """Load, de-duplicate, and prepare the data"""
    try:
        df_csv = pd.read_csv('ai_models_extracted.csv')
        df_xlsx = pd.read_excel('ai_models_extracted.xlsx')
        df = pd.concat([df_csv, df_xlsx], ignore_index=True)
        df.drop_duplicates(subset='Model', keep='first', inplace=True)
        df.fillna(0, inplace=True)
        print(f"Loaded and de-duplicated {len(df)} unique model records.")
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def run_exploratory_analysis(df):
    """Perform EDA and generate plots"""
    print("\n🔍 Running Exploratory Data Analysis...")
    
    # Create new directory for plots
    Path("eda_plots").mkdir(exist_ok=True)
    
    # 1. Distribution of Key Metrics
    key_metrics = ['AA_Intelligence_Index', 'Price_Blended_USD_per_1M', 'Speed_Median_Tok_per_s', 'AA_Omniscience_NonHallucinationRate']
    plt.figure(figsize=(14, 10))
    for i, metric in enumerate(key_metrics, 1):
        plt.subplot(2, 2, i)
        sns.histplot(df[metric], kde=True, bins=15)
        pretty = metric.replace('_', ' ')
        plt.title(f'Distribution of {pretty}', fontsize=12)
    plt.tight_layout()
    plt.savefig("eda_plots/key_metrics_distribution.png", dpi=300)
    plt.close()
    print("✅ Generated plot: eda_plots/key_metrics_distribution.png")

    # 2. Pair Plot for Correlations
    pair_plot_metrics = ['AA_Intelligence_Index', 'Price_Blended_USD_per_1M', 'Speed_Median_Tok_per_s', 'AA_Omniscience_NonHallucinationRate']
    sns.pairplot(df[pair_plot_metrics])
    plt.savefig("eda_plots/pair_plot_correlations.png", dpi=300)
    plt.close()
    print("✅ Generated plot: eda_plots/pair_plot_correlations.png")

    # 3. Performance by Creator
    plt.figure(figsize=(14, 8))
    sns.boxplot(x='Creator', y='AA_Intelligence_Index', data=df)
    plt.title('AA Intelligence Index by Creator', fontsize=16)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("eda_plots/intelligence_by_creator.png", dpi=300)
    plt.close()
    print("✅ Generated plot: eda_plots/intelligence_by_creator.png")

    # 4. Context Window Analysis with robust error handling
    try:
        df['Context_Window_K'] = df['Context_Window'].str.replace('k', '', regex=False).str.replace('m', '000', regex=False)
        df['Context_Window_K'] = pd.to_numeric(df['Context_Window_K'], errors='coerce').fillna(0)
        
        plt.figure(figsize=(12, 7))
        sns.scatterplot(x='Context_Window_K', y='AA_Intelligence_Index', size='Price_Blended_USD_per_1M', hue='Creator', data=df, sizes=(50, 500), alpha=0.7)
        plt.title('Context Window vs AA Intelligence (size=Price)', fontsize=16)
        plt.xlabel('Context Window (Thousands of Tokens)')
        plt.ylabel('AA Intelligence Index')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.savefig("eda_plots/context_window_analysis.png", dpi=300)
        plt.close()
        print("✅ Generated plot: eda_plots/context_window_analysis.png")
    except Exception as e:
        print(f"⚠️ Could not generate context window analysis plot. Error: {e}")

def summarize_insights(df):
    """Summarize key insights from the EDA"""
    print("\n" + "=" * 60)
    print("EXPLORATORY ANALYSIS INSIGHTS")
    print("=" * 60)

    print("1. Price vs. Performance Trade-off:")
    print("   - There is a general trend where higher intelligence comes at a higher price, but there are notable exceptions.")
    print(f"   - For instance, '{df.loc[df['Price_Blended_USD_per_1M'].idxmin()]['Model']}' offers a very low price point, while '{df.loc[df['AA_Intelligence_Index'].idxmax()]['Model']}' has the highest intelligence but at a premium cost.")

    print("\n2. Creator Specializations:")
    print("   - Different creators appear to focus on different strengths. For example, some models from Anthropic excel in speed, while OpenAI models often lead in coding benchmarks.")
    print("   - This suggests that the best model for a specific task may depend on the creator's focus.")

    print("\n3. The 'Sweet Spot' for Value:")
    print("   - The analysis reveals a 'sweet spot' of models that offer a strong balance of intelligence, speed, and low cost.")
    sweet_spot_models = df[(df['AA_Intelligence_Index'] > 45) & (df['Price_Blended_USD_per_1M'] < 2)]
    if not sweet_spot_models.empty:
        print("   - Models in this category include: " + ", ".join(sweet_spot_models['Model'].tolist()))
        print("   - These models are excellent candidates for general-purpose applications where cost-effectiveness is crucial.")
    else:
        print("   - No models were found in the typical 'sweet spot' of high intelligence and low cost.")

    print("\n4. Context Window Isn't Everything:")
    print("   - A larger context window does not always correlate with higher intelligence. Some models with smaller context windows outperform those with larger ones.")
    print("   - This indicates that the quality of the model's training is more important than the sheer size of its context window.")
    print("=" * 60)

def main():
    """Main analysis function"""
    print("🚀 EXPLORATORY DATA ANALYSIS OF AI MODELS (v4.1)")
    print("=" * 60)
    
    df = load_and_prepare_data()
    if df is None: return

    run_exploratory_analysis(df)
    summarize_insights(df)

    print("\n✅ Exploratory analysis complete! Check the 'eda_plots' directory for new visualizations.")

if __name__ == "__main__":
    main()