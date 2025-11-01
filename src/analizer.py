import os
import pandas as pd


CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_SCRIPT_DIR) 
CSV_DIR = os.path.join(BASE_DIR, 'data', 'processed_csv')

def load_dataframes(csv_dir):
    """
    Loads all processed CSVs into a dictionary of DataFrames.
    """
    print(f"Loading intermediate data from: {csv_dir}")
    try:
        dataframes = {
            "fact_study": pd.read_csv(os.path.join(csv_dir, "fact_study.csv")),
            "dim_patient": pd.read_csv(os.path.join(csv_dir, "dim_patient.csv")),
            "dim_station": pd.read_csv(os.path.join(csv_dir, "dim_station.csv")),
            "dim_protocol": pd.read_csv(os.path.join(csv_dir, "dim_protocol.csv")),
            "dim_image": pd.read_csv(os.path.join(csv_dir, "dim_image.csv")),
            "dim_date": pd.read_csv(os.path.join(csv_dir, "dim_date.csv"))
        }
        print("All CSV files loaded successfully.")
        return dataframes
    except FileNotFoundError as e:
        print(f"!!! ERROR: File not found. {e}")
        print("Please ensure you have run 'main.py' first to generate the CSV files in 'data/processed_csv'")
        return None

def analyze_cardinality(dataframes):
    """
    Analyzes and prints the fact-to-dimension cardinality.
    This justifies the use of a Star Schema.
    """
    print("\n--- 1. Cardinality Analysis (Justification for Star Schema) ---")
    total_facts = len(dataframes['fact_study'])
    print(f"  Total Studies (Facts): {total_facts}")
    print("  --- Unique Dimensions ---")
    
    for name, df in dataframes.items():
        if name != "fact_study":
            unique_count = len(df)
            ratio = total_facts / unique_count if unique_count > 0 else 0
            print(f"  {name}: {unique_count} records (Avg. {ratio:.2f} facts per dimension record)")
            
    print("\n  -> Justification: The low count of unique dimensions (e.g., protocol, station)")
    print("     compared to facts proves that the star schema efficiently reduces data redundancy.")

def analyze_patient_age(dataframes):
    """
    Analyzes and prints the distribution of patient ages.
    This justifies the 'format_age' transformation.
    """
    print("\n--- 2. Patient Age Distribution (Justification for 'format_age') ---")
    age_stats = dataframes['dim_patient']['age'].describe()
    print(age_stats)
    print("\n  -> Justification: Raw data (e.g., '061Y') was unusable. The transformed data allows")
    print(f"     for immediate statistical analysis (e.g., Mean Age: {age_stats['mean']:.1f}, Range: {age_stats['min']:.0f}-{age_stats['max']:.0f}).")

def analyze_contrast_agent(dataframes):
    """
    Analyzes and prints the counts of contrast agent usage.
    This justifies the 'normalize_contrast_agent' transformation.
    """
    print("\n--- 3. Contrast Agent Usage (Justification for 'normalize_contrast_agent') ---")
    contrast_counts = dataframes['dim_protocol']['contrast_agent'].value_counts()
    print(contrast_counts)
    print("\n  -> Justification: Raw data had missing/empty values. They are now standardized to 'None',")
    print("     allowing for clear separation between studies with and without contrast.")

def analyze_pixel_spacing(dataframes):
    """
    Analyzes and prints the binned pixel spacing values.
    This justifies the 'normalize_pixel_spacing' transformation.
    """
    print("\n--- 4. Binned Pixel Spacing (Justification for 'normalize_pixel_spacing') ---")
    pixel_spacing_counts = dataframes['dim_image']['pixel_spacing_norm'].value_counts().sort_index()
    print(pixel_spacing_counts)
    print("\n  -> Justification: Raw pixel spacing values were highly varied (e.g., 0.68, 0.71). Binning")
    print("     them into standardized groups simplifies future queries and analysis.")

def analyze_core_metrics(dataframes):
    """
    (NEW ANALYSIS)
    Provides a statistical summary of the core fact metrics (dose).
    """
    print("\n--- 5. Core Fact Metrics Analysis (Study Dose) ---")
    
    print("\n  --- Exposure Time (ms) ---")
    exposure_stats = dataframes['fact_study']['exposure_time'].describe()
    print(exposure_stats)
    
    print("\n  --- X-Ray Tube Current (mA) ---")
    current_stats = dataframes['fact_study']['tube_current'].describe()
    print(current_stats)
    
    print("\n  -> Justification: This analysis provides a baseline understanding of the radiation dose")
    print("     in the dataset. We can see the mean tube current is")
    print(f"     {current_stats['mean']:.1f} mA, with a wide range from {current_stats['min']:.0f} to {current_stats['max']:.0f}.")

def main():
    """
    Main function to run all analyses.
    """
    print("--- Starting Intermediate Data Analysis Script ---")
    
    dataframes = load_dataframes(CSV_DIR)
    
    if dataframes:
        analyze_cardinality(dataframes)
        analyze_patient_age(dataframes)
        analyze_contrast_agent(dataframes)
        analyze_pixel_spacing(dataframes)
        analyze_core_metrics(dataframes)
        print("\n--- Analysis Complete ---")

if __name__ == "__main__":
    main()