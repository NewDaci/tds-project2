# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "matplotlib",
#   "seaborn",
#   "requests",
#   "chardet",
#   "scipy",
#   "python-dotenv",
# ]
# ///

import os
import sys
import json
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import requests
import chardet
import warnings
import urllib.parse
import scipy.stats as stats

# Suppress specific UserWarnings
warnings.filterwarnings("ignore", category=UserWarning)

# Load environment variables
load_dotenv()
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN")

if not AIPROXY_TOKEN:
    print("Error: AIPROXY_TOKEN environment variable not set.")
    sys.exit(1)

AIPROXY_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

def detect_encoding(file_path):
    """Detect file encoding using chardet."""
    with open(file_path, 'rb') as file:
        result = chardet.detect(file.read(10000))
        return result.get('encoding', 'utf-8')

def read_csv_safe(file_path):
    """Safely read CSV file with robust encoding detection and handling."""
    # List of encodings to try
    encodings_to_try = [
        'utf-8', 
        'latin-1',  # Wide support for European languages
        'windows-1252',  # Common for files from Windows
        'iso-8859-1', 
        'cp1252'
    ]
    
    for encoding in encodings_to_try:
        try:
            print(f"Attempting to read file with {encoding} encoding...")
            
            df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
            print(f"Dataset successfully loaded with {df.shape[0]} rows and {df.shape[1]} columns")
            
            return df
        except Exception as e:
            print(f"Failed to load with {encoding} encoding: {e}")
    
    # If all encodings fail
    print("Could not read the file with any of the attempted encodings.")
    sys.exit(1)


def convert_to_serializable(obj):
    """Convert non-serializable objects to serializable formats."""
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.int64, np.float64, np.bool_)):
        return obj.item()
    elif pd.isna(obj):
        return None
    return obj

def analyze_data_structure(df):
    """Perform comprehensive data structure analysis."""
    analysis = {
        "total_rows": int(df.shape[0]),
        "total_columns": int(df.shape[1]),
        "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
        "unique_values": {col: int(df[col].nunique()) for col in df.columns}
    }
    return analysis

def detect_outliers(df):
    """Detect outliers using IQR method for numeric columns."""
    outliers = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers[col] = {
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "outliers_count": int(((df[col] < lower_bound) | (df[col] > upper_bound)).sum())
        }
    
    return outliers

def perform_statistical_tests(df):
    """Perform basic statistical tests."""
    statistical_tests = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        # Shapiro-Wilk test for normality
        if len(df[col]) > 3:  # Minimum requirement for the test
            _, p_value = stats.shapiro(df[col].dropna())
            statistical_tests[col] = {
                "normality_test": {
                    "p_value": float(p_value),
                    "is_normal": bool(p_value > 0.05)
                }
            }
    
    return statistical_tests

def generate_visualizations(df, output_dir):
    """Generate comprehensive visualizations."""
    plt.close('all')
    charts = []
    
    # Set up matplotlib parameters for better aesthetics
    plt.rcParams.update({
        'font.size': 10,
        'axes.titlesize': 12,
        'axes.labelsize': 10
    })
    
    # Correlation Heatmap
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) > 1:
        plt.figure(figsize=(12, 10))
        corr_matrix = numeric_df.corr()
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', linewidths=0.5, fmt=".2f", square=True)
        plt.title("Correlation Heatmap of Numeric Features", fontsize=14)
        corr_path = os.path.join(output_dir, "correlation_heatmap.png")
        plt.tight_layout()
        plt.savefig(corr_path, dpi=300)
        charts.append(corr_path)
        plt.close()
    
    # Box plots for numeric columns
    numeric_cols = numeric_df.columns
    if len(numeric_cols) > 0:
        plt.figure(figsize=(15, 6))
        df[numeric_cols].boxplot()
        plt.title("Box Plot of Numeric Features", fontsize=14)
        plt.xticks(rotation=45)
        box_path = os.path.join(output_dir, "numeric_boxplot.png")
        plt.tight_layout()
        plt.savefig(box_path, dpi=300)
        charts.append(box_path)
        plt.close()
    
    # Categorical feature distribution
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    for col in categorical_cols[:3]:  # Limit to first 3 categorical columns
        plt.figure(figsize=(10, 6))
        value_counts = df[col].value_counts()
        sns.barplot(x=value_counts.index, y=value_counts.values)
        plt.title(f"Distribution of {col}", fontsize=14)
        plt.xlabel(col, fontsize=12)
        plt.ylabel("Count", fontsize=12)
        plt.xticks(rotation=45, ha='right')
        cat_path = os.path.join(output_dir, f"{col}_distribution.png")
        plt.tight_layout()
        plt.savefig(cat_path, dpi=300)
        charts.append(cat_path)
        plt.close()
    
    return charts

def call_llm_with_analysis(data_analysis, charts):
    """Call LLM to generate narrative based on data analysis."""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        
        # Convert data_analysis to JSON-serializable format
        serializable_analysis = convert_to_serializable(data_analysis)
        
        # Prepare a comprehensive prompt
        prompt = (
            "Analyze the following dataset and provide a comprehensive narrative:\n\n"
            f"Dataset Structure:\n{json.dumps(serializable_analysis, indent=2)}\n\n"
            "Key Points to Cover:\n"
            "1. Brief overview of the dataset\n"
            "2. Key characteristics and interesting patterns\n"
            "3. Potential insights and recommendations\n"
            "4. Limitations or areas requiring further investigation\n"
        )
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000
        }
        
        response = requests.post(AIPROXY_URL, headers=headers, json=data)
        response.raise_for_status()
        narrative = response.json()["choices"][0]["message"]["content"]
        
        return narrative
    except Exception as e:
        print(f"Error generating narrative: {e}")
        return "Unable to generate narrative due to an error."

def write_readme(output_dir, narrative, charts):
    """Write comprehensive README.md with narrative and image references."""
    readme_path = os.path.join(output_dir, "README.md")
    
    with open(readme_path, "w") as f:
        f.write("# Automated Data Analysis Report\n\n")
        f.write("## Analysis Narrative\n\n")
        f.write(narrative + "\n\n")
        
        f.write("## Visualizations\n\n")
        for chart in charts:
            chart_name = os.path.basename(chart)
            encoded_chart_name = urllib.parse.quote(chart_name)
            f.write(f"### {chart_name}\n")
            f.write(f"![{chart_name}]({encoded_chart_name})\n\n")

                
    print(f"README.md generated at {readme_path}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <dataset.csv>")
        sys.exit(1)

    file_path = sys.argv[1]
    output_dir = os.path.splitext(file_path)[0]
    os.makedirs(output_dir, exist_ok=True)

    # Load and analyze data
    df = read_csv_safe(file_path)
    
    # Perform comprehensive analysis
    data_analysis = {
        "structure": analyze_data_structure(df),
        "outliers": detect_outliers(df),
        "statistical_tests": perform_statistical_tests(df)
    }
    
    # Generate visualizations
    charts = generate_visualizations(df, output_dir)
    
    # Generate narrative
    narrative = call_llm_with_analysis(data_analysis, charts)
    
    # Write README
    write_readme(output_dir, narrative, charts)

    print("Analysis complete!")

if __name__ == "__main__":
    main()