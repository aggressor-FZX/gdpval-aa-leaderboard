#!/usr/bin/env python3
"""
AI Models Analysis Script
Analyzes AI models from CSV and XLSX files to generate meaningful statistics
about their value, cost, and usefulness for VS Code and Cogito Metric.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set up plotting style
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

def load_data():
    """Load data from both CSV and XLSX files"""
    try:
        df_csv = pd.read_csv('ai_models_extracted.csv')
        print(f"Loaded CSV: {len(df_csv)} rows, {len(df_csv.columns)} columns")
        
        df_xlsx = pd.read_excel('ai_models_extracted.xlsx')
        print(f"Loaded XLSX: {len(df_xlsx)} rows, {len(df_xlsx.columns)} columns")
        
        # Combine both datasets
        df_combined = pd.concat([df_csv, df_xlsx], ignore_index=True)
        print(f"Combined dataset: {len(df_combined)} rows, {len(df_combined.columns)} columns")
        
        return df_combined
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def analyze_model_value_cost(df):
    """Analyze value vs cost relationships"""
    print("\n=== VALUE AND COST ANALYSIS ===")
    
    # Basic statistics
    print("\nPrice Statistics (USD per 1M tokens):")
    price_cols = ['Price_Input_USD_per_1M', 'Price_Output_USD_per_1M', 'Price_Blended_USD_per_1M']
    for col in price_cols:
        if col in df.columns:
            print(f"{col}:")
            print(f"  Mean: ${df[col].mean():.2f}")
            print(f"  Median: ${df[col].median():.2f}")
            print(f"  Range: ${df[col].min():.2f} - ${df[col].max():.2f}")
    
    # Intelligence vs Cost analysis
    if 'AA_Intelligence_Index' in df.columns and 'Price_Blended_USD_per_1M' in df.columns:
        print(f"\nIntelligence vs Cost Correlation: {df['AA_Intelligence_Index'].corr(df['Price_Blended_USD_per_1M']):.3f}")
        
        # Best value models (high intelligence, low cost)
        df['Value_Score'] = df['AA_Intelligence_Index'] / df['Price_Blended_USD_per_1M']
        best_value = df.nlargest(5, 'Value_Score')[['Model', 'AA_Intelligence_Index', 'Price_Blended_USD_per_1M', 'Value_Score']]
        print("\nTop 5 Best Value Models (Intelligence per Dollar):")
        print(best_value.to_string(index=False))

def analyze_performance_metrics(df):
    """Analyze performance and speed metrics"""
    print("\n=== PERFORMANCE ANALYSIS ===")
    
    # Speed analysis
    speed_cols = ['Speed_Median_Tok_per_s', 'Speed_P5', 'Speed_P95']
    for col in speed_cols:
        if col in df.columns:
            print(f"\n{col}:")
            print(f"  Mean: {df[col].mean():.1f} tokens/sec")
            print(f"  Median: {df[col].median():.1f} tokens/sec")
            print(f"  Fastest: {df[col].max():.1f} tokens/sec")
            print(f"  Slowest: {df[col].min():.1f} tokens/sec")
    
    # Intelligence benchmarks
    intel_cols = ['AA_Intelligence_Index', 'AA_Omniscience_Index', 'Humanitys_Last_Exam', 'GPQA_Diamond']
    for col in intel_cols:
        if col in df.columns:
            print(f"\n{col}:")
            print(f"  Mean: {df[col].mean():.1f}")
            print(f"  Best: {df[col].max():.1f}")
            print(f"  Model: {df.loc[df[col].idxmax(), 'Model'] if not df.empty else 'N/A'}")

def analyze_usefulness_for_vscode(df):
    """Analyze usefulness for VS Code as coding agent"""
    print("\n=== VS CODE CODING AGENT ANALYSIS ===")
    
    # Models good for coding (high LiveCodeBench, SciCode scores)
    coding_cols = ['LiveCodeBench', 'SciCode']
    for col in coding_cols:
        if col in df.columns:
            top_coding = df.nlargest(5, col)[['Model', col, 'Price_Blended_USD_per_1M']]
            print(f"\nTop 5 models for {col}:")
            print(top_coding.to_string(index=False))
    
    # Fast models for interactive coding
    if 'Speed_Median_Tok_per_s' in df.columns:
        fast_models = df.nlargest(5, 'Speed_Median_Tok_per_s')[['Model', 'Speed_Median_Tok_per_s', 'AA_Intelligence_Index']]
        print("\nTop 5 Fastest Models for Interactive Coding:")
        print(fast_models.to_string(index=False))

def analyze_cogito_metric_suitability(df):
    """Analyze suitability for Cogito Metric site"""
    print("\n=== COGITO METRIC SUITABILITY ANALYSIS ===")
    
    # Models good for data analysis and business intelligence
    business_cols = ['Tau2_Bench_Telecom', 'AA_LCR', 'AA_Omniscience_Accuracy']
    for col in business_cols:
        if col in df.columns:
            top_business = df.nlargest(5, col)[['Model', col, 'Price_Blended_USD_per_1M']]
            print(f"\nTop 5 models for {col} (business intelligence):")
            print(top_business.to_string(index=False))
    
    # Cost-effective models for production use
    if 'Price_Blended_USD_per_1M' in df.columns and 'AA_Intelligence_Index' in df.columns:
        # Models with intelligence > 40 and cost < $5 per 1M tokens
        cost_effective = df[(df['AA_Intelligence_Index'] > 40) & (df['Price_Blended_USD_per_1M'] < 5)]
        if not cost_effective.empty:
            print("\nCost-Effective Models for Production (Intelligence > 40, Cost < $5/1M tokens):")
            production_models = cost_effective[['Model', 'AA_Intelligence_Index', 'Price_Blended_USD_per_1M']].sort_values('Price_Blended_USD_per_1M')
            print(production_models.to_string(index=False))

def generate_recommendations(df):
    """Generate specific recommendations"""
    print("\n=== RECOMMENDATIONS ===")
    
    print("\nFor VS Code Coding Agent:")
    print("1. Best Overall: Claude Sonnet 4.6 (max) - Good balance of intelligence and speed")
    print("2. Budget Option: GLM-5 - Open source, very cost-effective")
    print("3. Premium Option: Claude Opus 4.6 (max) - Highest intelligence for complex tasks")
    
    print("\nFor Cogito Metric Site:")
    print("1. Production: Gemini 3 Flash - Fast, cost-effective for high volume")
    print("2. Complex Analysis: GPT-5.2 (xhigh) - Best for detailed business intelligence")
    print("3. Real-time: Kimi K2.5 - Good speed and accuracy balance")
    
    print("\nCost Analysis:")
    if 'Price_Blended_USD_per_1M' in df.columns:
        cheap_models = df.nsmallest(3, 'Price_Blended_USD_per_1M')[['Model', 'Price_Blended_USD_per_1M', 'AA_Intelligence_Index']]
        print("\nMost Affordable Models:")
        print(cheap_models.to_string(index=False))
        
        expensive_models = df.nlargest(3, 'Price_Blended_USD_per_1M')[['Model', 'Price_Blended_USD_per_1M', 'AA_Intelligence_Index']]
        print("\nMost Expensive Models:")
        print(expensive_models.to_string(index=False))

def create_visualizations(df):
    """Create visualization plots"""
    print("\n=== CREATING VISUALIZATIONS ===")
    
    # Create plots directory
    Path("plots").mkdir(exist_ok=True)
    
    # Intelligence vs Cost scatter plot
    if 'AA_Intelligence_Index' in df.columns and 'Price_Blended_USD_per_1M' in df.columns:
        plt.figure(figsize=(10, 6))
        plt.scatter(df['Price_Blended_USD_per_1M'], df['AA_Intelligence_Index'], 
                   s=100, alpha=0.7, c=df['Speed_Median_Tok_per_s'] if 'Speed_Median_Tok_per_s' in df.columns else None)
        plt.xlabel('Price (USD per 1M tokens, blended 3:1)')
        plt.ylabel('AA Intelligence Index')
        plt.title('AA Intelligence Index vs Price (USD per 1M, blended 3:1)')
        
        # Add model names for interesting points
        for idx, row in df.iterrows():
            if row['AA_Intelligence_Index'] > 50 or row['Price_Blended_USD_per_1M'] < 2:
                plt.annotate(row['Model'], (row['Price_Blended_USD_per_1M'], row['AA_Intelligence_Index']), 
                           xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        plt.tight_layout()
        plt.savefig("plots/intelligence_vs_cost.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("Created: plots/intelligence_vs_cost.png")
    
    # Speed comparison
    if 'Speed_Median_Tok_per_s' in df.columns:
        plt.figure(figsize=(12, 6))
        speed_data = df.nlargest(10, 'Speed_Median_Tok_per_s')[['Model', 'Speed_Median_Tok_per_s']]
        plt.barh(speed_data['Model'], speed_data['Speed_Median_Tok_per_s'])
        plt.xlabel('Speed (tokens/second)')
        plt.title('Top 10 Fastest AI Models (tokens/sec)')
        plt.tight_layout()
        plt.savefig("plots/top_speed_models.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("Created: plots/top_speed_models.png")

def main():
    """Main analysis function"""
    print("AI Models Analysis for VS Code and Cogito Metric")
    print("=" * 50)
    
    # Load data
    df = load_data()
    if df is None:
        return
    
    # Run all analyses
    analyze_model_value_cost(df)
    analyze_performance_metrics(df)
    analyze_usefulness_for_vscode(df)
    analyze_cogito_metric_suitability(df)
    generate_recommendations(df)
    create_visualizations(df)
    
    print("\n" + "=" * 50)
    print("Analysis complete! Check the 'plots' directory for visualizations.")
    
    # Save summary to CSV
    summary = df[['Model', 'AA_Intelligence_Index', 'Price_Blended_USD_per_1M', 'Speed_Median_Tok_per_s']].copy()
    summary = summary.sort_values('AA_Intelligence_Index', ascending=False)
    summary.to_csv('ai_models_summary.csv', index=False)
    print("Summary saved to: ai_models_summary.csv")

if __name__ == "__main__":
    main()