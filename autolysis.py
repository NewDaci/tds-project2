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
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN") or os.environ.get("AI_PROXY")

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

def resize_and_compress_image(input_path: str, output_path: str, size: tuple = (512, 512)):
    """
    Resize and compress image to smaller size with reduced quality.
    
    Args:
        input_path (str): Path to input image
        output_path (str): Path to save compressed image
        size (tuple): Desired image size (width, height)
    """
    try:
        with Image.open(input_path) as img:
            # Resize image while maintaining aspect ratio
            img.thumbnail(size, Image.LANCZOS)
            
            # Convert to RGBA mode if needed (PNG supports alpha channel)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Save as PNG (PNG is lossless, so quality parameter is not used)
            img.save(output_path, 'PNG', optimize=True)
        
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
        compressed_corr_path = os.path.join(output_dir, "correlation_heatmap_compressed.png")
        resize_and_compress_image(corr_path, compressed_corr_path)
        charts.append(compressed_corr_path)
        
        # Delete original image after compression
        os.remove(corr_path)
    
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
        compressed_box_path = os.path.join(output_dir, "numeric_boxplot_compressed.png")
        resize_and_compress_image(box_path, compressed_box_path)
        charts.append(compressed_box_path)
        
        # Delete original image after compression
        os.remove(box_path)
    
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
        compressed_cat_path = os.path.join(output_dir, f"{col}_distribution_compressed.png")
        resize_and_compress_image(cat_path, compressed_cat_path)
        charts.append(compressed_cat_path)
        
        # Delete original image after compression
        os.remove(cat_path)
    
    return charts

def analyze_images_with_vision(charts: List[str], api_token: str) -> List[Dict[str, Any]]:
    """
    Analyze images using vision capabilities via AI Proxy.
    
    Args:
        charts (List[str]): Paths to image files to analyze
        api_token (str): API token for authentication
    
    Returns:
        List of analysis results for each image
    """
    def encode_image(image_path: str) -> str:
        """
        Encode an image to base64.
        
        Args:
            image_path (str): Path to the image file
        
        Returns:
            Base64 encoded string of the image
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    # List to store analysis results
    image_analyses = []
    
    # Vision analysis prompts for different visualization types
    analysis_prompts = {
        "correlation_heatmap.png": """
        You are an expert data scientist analyzing a correlation heatmap. 
        Carefully examine the visualization and provide:
        1. Key relationships between variables
        2. Strength of correlations (strong positive/negative)
        3. Any surprising or unexpected correlations
        4. Potential insights for further investigation
        
        Provide a concise, technical analysis highlighting the most important patterns.
        """,
        
        "numeric_boxplot.png": """
        You are a statistical expert analyzing a boxplot of numeric features. 
        Carefully examine the visualization and provide:
        1. Distribution characteristics of each feature
        2. Identification of outliers
        3. Comparative analysis of feature ranges
        4. Potential data quality or collection issues
        
        Provide a detailed, technical breakdown of the numeric feature distributions.
        """,
        
        "distribution.png": """
        You are an expert in categorical data analysis. 
        Carefully examine the categorical feature distribution visualization and provide:
        1. Most frequent categories
        2. Distribution characteristics
        3. Any unexpected or interesting patterns
        4. Potential implications of the distribution
        
        Provide a concise, insightful analysis of the categorical feature.
        """
    }
    
    # API endpoint
    endpoint = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    
    for chart_path in charts:
        try:
            # Determine appropriate prompt based on filename
            prompt = next(
                (prompt for key, prompt in analysis_prompts.items() if key in chart_path), 
                analysis_prompts["correlation_heatmap.png"]  # Default prompt
            )
            
            # Prepare API payload
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url", 
                                "image_url": {
                                    "url": f"data:image/png;base64,{encode_image(chart_path)}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 300
            }
            
            # Make API request
            response = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_token}"
                },
                json=payload
            )
            
            # Process response
            if response.status_code == 200:
                result = response.json()
                analysis = result['choices'][0]['message']['content']
                
                image_analyses.append({
                    "image_path": chart_path,
                    "analysis": analysis
                })
            else:
                logger.error(f"Vision API error for {chart_path}: {response.text}")
        
        except Exception as e:
            logger.error(f"Error analyzing {chart_path}: {e}")
    
    return image_analyses

def generate_dynamic_prompt(user_input: str, analysis_type: str, data_summary: dict) -> str:
    """
    Generates a dynamic prompt for the LLM based on user input and analysis type.
    
    Args:
    user_input (str): The custom user input to drive the analysis.
    analysis_type (str): Type of analysis (e.g., "outlier detection", "correlation analysis").
    data_summary (dict): A summary of the data to be analyzed.

    Returns:
    str: The dynamic LLM prompt.
    """
    prompt = f"User requested {analysis_type} on the dataset. Data summary: {data_summary}. Based on user input: {user_input}, please generate the necessary analysis and visualization."
    return prompt

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
        prompt = generate_dynamic_prompt(
            user_input="Provide insights and recommendations for this dataset.",
            analysis_type="Comprehensive Analysis",
            data_summary=serializable_analysis
        )
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000
        }
        
        response = requests.post(
            "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions", 
            headers=headers, json=data
        )
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    except requests.RequestException as e:
        logger.error(f"LLM API request failed: {e}")
        raise

def write_readme(output_dir: str, narrative: str, charts: List[str], vision_analyses: List[Dict[str, Any]]) -> None:
    """
    Write comprehensive README.md with narrative, image references, and vision-based analyses.
    
    Args:
        output_dir (str): Directory to write README
        narrative (str): Overall data analysis narrative
        charts (List[str]): List of chart file paths
        vision_analyses (List[Dict[str, Any]]): List of vision-based image analyses
    """
    readme_path = os.path.join(output_dir, "README.md")
    
    with open(readme_path, "w") as f:
        f.write("# Automated Data Analysis Report\n\n")
        
        # Write overall narrative
        f.write("## Analysis Narrative\n\n")
        f.write(narrative + "\n\n")
        
        # Write visualizations section
        f.write("## Visualizations\n\n")
        
        # Create a mapping of chart filenames to their vision analyses
        vision_analysis_map = {
            os.path.basename(analysis['image_path']): analysis['analysis'] 
            for analysis in vision_analyses
        }
        
        for chart in charts:
            chart_name = os.path.basename(chart)
            encoded_chart_name = urllib.parse.quote(chart_name)
            
            # Write chart image
            f.write(f"### {chart_name}\n")
            f.write(f"![{chart_name}]({encoded_chart_name})\n\n")
            
            # Write corresponding vision analysis if available
            if chart_name in vision_analysis_map:
                f.write("#### Vision-Based Image Analysis\n\n")
                f.write(f"{vision_analysis_map[chart_name]}\n\n")

    logger.info(f"README.md generated at {readme_path}")

def main():
    if len(sys.argv) != 2:
        print("Usage: uv run autolysis.py <dataset.csv>")
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
        
         # Call vision analysis after generating charts
        vision_analyses = analyze_images_with_vision(charts, AIPROXY_TOKEN)
        
        # Call LLM for narrative generation
        narrative = call_llm_with_analysis(data_analysis, charts)
        
        # Write README with narrative, charts, and vision analyses
        write_readme(output_dir, narrative, charts, vision_analyses)
        logger.info("Analysis complete!")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()