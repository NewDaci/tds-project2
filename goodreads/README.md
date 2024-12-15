# Automated Data Analysis Report

## Analysis Narrative

## Comprehensive Analysis of the Dataset

### Overview

The dataset contains information on 10,000 books with 23 attributes. Key attributes include book identifiers, ratings, publication information, and author details. This comprehensive analysis will explore the structure, missing values, outliers, and statistical characteristics of the dataset, along with visualizations for clarity.

### 1. Dataset Structure

#### Basic Summary:
- **Total Rows:** 10,000
- **Total Columns:** 23

#### Column Types:
- **Integer:** `book_id`, `goodreads_book_id`, `best_book_id`, `work_id`, `books_count`, `ratings_count`, `work_ratings_count`, `work_text_reviews_count`, and various rating counts (`ratings_1`, `ratings_2`, etc.).
- **Float:** `isbn13`, `original_publication_year`, `average_rating`.
- **Object:** `isbn`, `authors`, `original_title`, `title`, `language_code`, `image_url`, `small_image_url`.

### 2. Missing Values Analysis

- **Key Missing Values:**
  - `isbn`: 700 (7.0%)
  - `isbn13`: 585 (5.85%)
  - `original_publication_year`: 21 (0.21%)
  - `original_title`: 585 (5.85%)
  - `language_code`: 1084 (10.84%)

#### Recommendations:
- Consider imputing missing values where applicable, particularly for fields critical for analysis, such as `original_publication_year` and `language_code`.
- Review the impact of missing `isbn` and `isbn13` values on book identification and classification.

### 3. Unique Values Analysis

The dataset offers a good degree of diversity with regard to unique values:
- **Unique Authors:** 4664
- **Unique Languages:** 25
- **Unique Titles:** 9964

This indicates a diverse collection of books to analyze, enhancing the potential for insights around author popularity, genre diversity, and language distribution.

### 4. Outliers Detection

Outliers have been detected for various attributes, notably:
- `goodreads_book_id`: 345 outliers
- `average_rating`: 158 outliers
- `ratings_count`: 1163 outliers

#### Recommendations:
- Review these outliers to determine if they are data-entry errors, legitimate extremes, or require capping to ensure robustness in analysis.
- Visualizations such as box plots could be used to identify outlier patterns visually.

### 5. Statistical Tests

Most columns exhibit non-normal distributions as demonstrated by normality tests with p-values far below common significance levels (α = 0.05). Some key findings include:
- **p-value for `average_rating`:** \(3.20 × 10^{-30}\)
- **Ratings Counts:** All show non-normality.

### 6. Visualizations

Visualizations can assist in understanding distributions, relationships, and overall dataset composition. Below are suggested visualizations:

#### a. Missing Values Heatmap
A heatmap showing missing values helps easily identify affected columns.

```python
import seaborn as sns
import matplotlib.pyplot as plt

# Assuming 'missing_values' is a DataFrame created from the relevant data
missing_percentages = [0.0, 7.0, 5.85, 0.0, 0.21, 5.85, 10.84]  # Add other missing percentages here
columns = ['book_id', 'isbn', 'isbn13', 'original_publication_year', 'original_title', 'language_code']
sns.heatmap(pd.DataFrame(missing_percentages, columns=columns).T, cmap='Blues', annot=True)

plt.title('Missing Values Heatmap')
plt.ylabel('Columns')
plt.xlabel('Missing Percentage')
plt.show()
```

#### b. Distribution of Ratings
A histogram or kernel density plot of the `average_rating` can reveal its distribution.

```python
plt.figure(figsize=(10, 5))
sns.histplot(data=df, x='average_rating', bins=30, kde=True)
plt.title('Distribution of Average Ratings')
plt.xlabel('Average Rating')
plt.ylabel('Frequency')
plt.show()
```

#### c. Outlier Boxplots
Box plots for `ratings_count` to visualize the distributions and outliers.

```python
plt.figure(figsize=(8, 5))
sns.boxplot(data=df, y='ratings_count')
plt.title('Boxplot of Ratings Count')
plt.ylabel('Ratings Count')
plt.show()
```

### 7. Conclusion and Recommendations

1. **Data Quality**: Focus on handling missing values and outlier detection before conducting further analysis.
2. **Exploratory Data Analysis (EDA)**: Conduct EDA to understand underlying trends and patterns—this can be targeted towards author popularity, language distribution, or average ratings

## Visualizations

### correlation_heatmap_compressed.png
![correlation_heatmap_compressed.png](correlation_heatmap_compressed.png)

### numeric_boxplot_compressed.png
![numeric_boxplot_compressed.png](numeric_boxplot_compressed.png)

### isbn_distribution_compressed.png
![isbn_distribution_compressed.png](isbn_distribution_compressed.png)

