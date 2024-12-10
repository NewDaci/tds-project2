# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "matplotlib",
#   "seaborn",
#   "requests",
#   "chardet",
#   "python-dotenv",
# ]
# ///

import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import requests
import chardet



# Load environment variables
load_dotenv()
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN")

if not AIPROXY_TOKEN:
    print("Error: AIPROXY_TOKEN environment variable not set.")
    sys.exit(1)

AIPROXY_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        result = chardet.detect(file.read(10000))  # Detect encoding from a sample
        return result['encoding']

# Function to safely read CSV with detected encoding and handle errors
def read_csv_safe(file_path):
    try:
        # Detect the file encoding first
        encoding = detect_encoding(file_path)
        print(f"Detected encoding: {encoding}")

        # Attempt to read the CSV with the detected encoding
        df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
        
    except Exception as e:
        # Handle general exceptions (including file read issues)
        print(f"Error loading dataset: {e}")
        return None
    
    # Clean column names (strip whitespaces, handle potential issues)
    df.columns = df.columns.str.strip()

    # Automatically detect and convert date columns (if any)
    for col in df.columns:
        if df[col].dtype == 'object':  # For string/object type columns
            # Try to convert columns to datetime
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except Exception:
                pass  # Ignore any errors that occur during conversion

    # Handle any float or number columns that might have incorrect format (e.g., commas)
    for col in df.columns:
        if df[col].dtype == 'object':  # String columns
            # Try to convert to numbers, replacing commas or other symbols if needed
            df[col] = df[col].replace({',': '', '$': '', '€': '', '£': ''}, regex=True)  # Remove common currency symbols
            df[col] = pd.to_numeric(df[col], errors='ignore')  # Convert to numeric, leaving errors unchanged

    # Return the cleaned dataframe
    return df



def load_data(file_path):
    """Load the CSV dataset into a Pandas DataFrame."""
    try:

        data = read_csv_safe(file_path)
        # data = pd.read_csv(file_path, encoding=encoding)
        print(f"Dataset loaded with {data.shape[0]} rows and {data.shape[1]} columns.")
        return data
    except Exception as e:
        print(f"Error loading dataset: {e}")
        sys.exit(1)


def generate_summary_statistics(df):
    """Generate summary statistics of the dataset."""
    summary = df.describe(include="all").to_dict()
    missing_values = df.isnull().sum().to_dict()
    return summary, missing_values

def visualize_data(df, output_prefix):
    """Create and save visualizations."""
    charts = []
    # Correlation heatmap
    if df.select_dtypes(include="number").shape[1] > 1:
        plt.figure(figsize=(10, 8))
        corr_matrix = df.corr()
        sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f")
        heatmap_path = f"{output_prefix}_correlation_heatmap.png"
        plt.title("Correlation Heatmap")
        plt.savefig(heatmap_path)
        charts.append(heatmap_path)
        plt.close()
    
    # Countplot for categorical variables
    for col in df.select_dtypes(include="object").columns[:2]:  # Limit to 2 columns for simplicity
        plt.figure(figsize=(10, 6))
        sns.countplot(y=col, data=df, order=df[col].value_counts().index)
        countplot_path = f"{output_prefix}_{col}_countplot.png"
        plt.title(f"Count Plot for {col}")
        plt.savefig(countplot_path)
        charts.append(countplot_path)
        plt.close()

    return charts

def generate_readme(df, summary, missing_values, charts, output_file):
    """Generate README.md based on the analysis and visualizations."""
    description_prompt = (
        f"The dataset has {df.shape[0]} rows and {df.shape[1]} columns. "
        f"The columns are: {', '.join(df.columns)}.\n"
        f"Missing values: {missing_values}\n"
        "Provide a narrative summary and key insights based on this data."
    )

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": description_prompt}]
        }
        response = requests.post(AIPROXY_URL, headers=headers, json=data)
        response.raise_for_status()  # Raise an error if the request fails
        narrative = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error generating narrative: {e}")
        narrative = "Could not generate narrative."

    # Create README
    with open(output_file, "w") as f:
        f.write("# Automated Analysis\n\n")
        f.write(f"### Summary\n\n{narrative}\n\n")
        for chart in charts:
            f.write(f"![Chart]({chart})\n\n")

def main():
    if len(sys.argv) != 2:
        print("Usage: uv run autolysis.py <dataset.csv>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        sys.exit(1)
    
    # Create a directory named after the file (without extension)
    output_dir = os.path.splitext(file_path)[0]
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    print("Starting analysis...")
    df = load_data(file_path)

    print("Generating summary statistics...")
    summary, missing_values = generate_summary_statistics(df)

    print("Creating visualizations...")
    charts = visualize_data(df, os.path.join(output_dir, os.path.basename(output_dir)))

    print("Generating README.md...")
    output_file = os.path.join(output_dir, "README.md")
    generate_readme(df, summary, missing_values, charts, output_file)

    print("Analysis complete. Results saved to README.md and chart files.")

if __name__ == "__main__":
    main()
