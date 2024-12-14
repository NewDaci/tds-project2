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
#   "tenacity",
#   "rich"
# ]
# ///

import os
import sys
import json
import logging
from typing import List, Dict, Any

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import scipy.stats as stats
import requests
import chardet
import urllib.parse
import warnings
from PIL import Image
import base64
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type
)
from rich.console import Console
from rich.logging import RichHandler
warnings.filterwarnings("ignore", category=UserWarning)

# Configure logging with rich
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("data_analysis")

# Load environment variables
load_dotenv()
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN")

class DataReadError(Exception):
    """Specific exception for data reading errors."""
    pass

class DataAnalysisError(Exception):
    """Specific exception for data analysis errors."""
    pass

def convert_to_serializable(obj):
    """
    Recursively convert non-serializable objects to serializable formats.
    """
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

def detect_outliers(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Detect outliers using IQR method for numeric columns.
    """
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

def perform_statistical_tests(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Perform basic statistical tests on numeric columns.
    """
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

def read_csv_safe(file_path: str) -> pd.DataFrame:
    """
    Safely read CSV file with multiple encoding attempts.
    """
    encodings_to_try = [
        'utf-8', 'latin-1', 'windows-1252', 
        'iso-8859-1', 'cp1252'
    ]
    
    for encoding in encodings_to_try:
        try:
            logger.info(f"Attempting to read file with {encoding} encoding...")
            # Limit number of rows to prevent memory issues with large files
            df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip', nrows=50000)
            logger.info(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
            return df
        except Exception as e:
            logger.warning(f"Failed to load with {encoding} encoding: {e}")
    
    raise DataReadError("Could not read the file with any attempted encodings")

def analyze_data_structure(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Perform comprehensive data structure analysis.
    """
    analysis = {
        "total_rows": int(df.shape[0]),
        "total_columns": int(df.shape[1]),
        "column_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "missing_percentage": (df.isnull().sum() / len(df) * 100).to_dict(),
        "unique_values": {col: int(df[col].nunique()) for col in df.columns}
    }
    return analysis

def batch_resize_and_compress(images: List[Dict], size=(512, 512), quality=75):
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                resize_and_compress_image, image['input_path'], image['output_path'], size, quality
            )
            for image in images
        ]
        for future in futures:
            future.result()  # Ensure all tasks complete

def resize_and_compress_image(input_path: str, output_path: str, size: tuple = (512, 512), quality: int = 75):
    """
    Resize and compress image to smaller size with reduced quality.
    
    Args:
        input_path (str): Path to input image
        output_path (str): Path to save compressed image
        size (tuple): Desired image size (width, height)
        quality (int): JPEG compression quality (1-95)
    """
    try:
        with Image.open(input_path) as img:
            # Resize image while maintaining aspect ratio
            img.thumbnail(size, Image.LANCZOS)
            
            # Convert to RGB mode if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save with compression
            img.save(output_path, 'JPEG', optimize=True, quality=quality)
        
        logger.info(f"Image compressed: {input_path} -> {output_path}")
    except Exception as e:
        logger.error(f"Error compressing image {input_path}: {e}")

def generate_visualizations(df: pd.DataFrame, output_dir: str) -> List[str]:
    """
    Generate compact visualizations for the dataset.
    """
    plt.close('all')
    charts = []
    
    plt.rcParams.update({
        'font.size': 8,
        'axes.titlesize': 10,
        'axes.labelsize': 8
    })
    
    # Set figure size to be more compact
    figsize = (6, 4)
    
    numeric_df = df.select_dtypes(include=[np.number])
    
    # Correlation Heatmap
    if len(numeric_df.columns) > 1:
        plt.figure(figsize=figsize, dpi=100)
        corr_matrix = numeric_df.corr()
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', 
                    linewidths=0.5, fmt=".2f", square=True, 
                    cbar=False)
        plt.title("Correlation Heatmap", fontsize=10)
        corr_path = os.path.join(output_dir, "correlation_heatmap.png")
        plt.tight_layout()
        plt.savefig(corr_path, bbox_inches='tight')
        plt.close()
        
        # Compress the image
        compressed_corr_path = os.path.join(output_dir, "correlation_heatmap_compressed.jpg")
        resize_and_compress_image(corr_path, compressed_corr_path)
        charts.append(compressed_corr_path)
    
    # Box plots for numeric columns
    if len(numeric_df.columns) > 0:
        plt.figure(figsize=figsize, dpi=100)
        df[numeric_df.columns].boxplot()
        plt.title("Numeric Features Boxplot", fontsize=10)
        plt.xticks(rotation=45, fontsize=8)
        plt.ylabel("Values", fontsize=8)
        box_path = os.path.join(output_dir, "numeric_boxplot.png")
        plt.tight_layout()
        plt.savefig(box_path, bbox_inches='tight')
        plt.close()
        
        # Compress the image
        compressed_box_path = os.path.join(output_dir, "numeric_boxplot_compressed.jpg")
        resize_and_compress_image(box_path, compressed_box_path)
        charts.append(compressed_box_path)
    
    # Categorical feature distribution
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    for col in categorical_cols[:1]:  # Limit to first categorical column
        plt.figure(figsize=figsize, dpi=100)
        value_counts = df[col].value_counts().head(5)  # Top 5 categories
        sns.barplot(x=value_counts.index, y=value_counts.values)
        plt.title(f"{col} Distribution", fontsize=10)
        plt.xlabel(col, fontsize=8)
        plt.ylabel("Count", fontsize=8)
        plt.xticks(rotation=45, ha='right', fontsize=8)
        cat_path = os.path.join(output_dir, f"{col}_distribution.png")
        plt.tight_layout()
        plt.savefig(cat_path, bbox_inches='tight')
        plt.close()
        
        # Compress the image
        compressed_cat_path = os.path.join(output_dir, f"{col}_distribution_compressed.jpg")
        resize_and_compress_image(cat_path, compressed_cat_path)
        charts.append(compressed_cat_path)
    
    return charts

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(requests.RequestException)
)
def call_llm_with_analysis(data_analysis: Dict[str, Any], charts: List[str]) -> str:
    """
    Call LLM with retry mechanism for generating narrative.
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        
        serializable_analysis = convert_to_serializable(data_analysis)
        
        prompt = (
            "Analyze the following dataset and provide a comprehensive narrative:\n\n"
            f"Dataset Structure:\n{json.dumps(serializable_analysis, indent=2)}\n\n"
            "Key Points:\n"
            "1. Dataset overview\n"
            "2. Key characteristics\n"
            "3. Insights and recommendations\n"
            "4. Limitations for further investigation\n"
        )
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000
        }
        
        response = requests.post("https://aiproxy.sanand.workers.dev/openai/v1/chat/completions", 
                                 headers=headers, json=data)
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    except requests.RequestException as e:
        logger.error(f"LLM API request failed: {e}")
        raise

def write_readme(output_dir: str, narrative: str, charts: List[str]) -> None:
    """
    Write comprehensive README.md with narrative and image references.
    """
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

    logger.info(f"README.md generated at {readme_path}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <dataset.csv>")
        sys.exit(1)

    file_path = sys.argv[1]
    # output_dir = os.path.splitext(file_path)[0]
    # os.makedirs(output_dir, exist_ok=True)
    output_dir = "."


    try:
        df = read_csv_safe(file_path)
        
        data_analysis = {
            "structure": analyze_data_structure(df),
            "outliers": detect_outliers(df),
            "statistical_tests": perform_statistical_tests(df)
        }
        
        charts = generate_visualizations(df, output_dir)
        
        # Ensure AIPROXY_TOKEN is set
        if not AIPROXY_TOKEN:
            logger.error("AIPROXY_TOKEN is not set. Please set the environment variable.")
            sys.exit(1)
        
        # Call LLM for narrative generation
        narrative = call_llm_with_analysis(data_analysis, charts)
        
        # Write README with narrative and charts
        write_readme(output_dir, narrative, charts)

        logger.info("Analysis complete!")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
