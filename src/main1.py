import os
import json
import pandas as pd
from et1 import ETLProcessor # Using the 'et1.py' filename you provided

# --- Configuration ---
# Get the directory where this script is located (e.g., .../Lab3/src)
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory (the project root, e.g., .../Lab3)
BASE_DIR = os.path.dirname(CURRENT_SCRIPT_DIR) 

# Build paths from the project root
DATA_DIR = os.path.join(BASE_DIR, 'data', 'dicom_dir')
JPEG_OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'jpeg_output')
CSV_OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed_csv') # New folder for CSVs

def main():
    """
    Main function to run the ETL process.
    """
    print("--- Starting ETL Process (Extract & Transform) ---")
    
    # 1. Initialize the ETL Processor
    # Ensure output directories exist
    os.makedirs(JPEG_OUTPUT_DIR, exist_ok=True)
    os.makedirs(CSV_OUTPUT_DIR, exist_ok=True)
    
    processor = ETLProcessor(jpeg_output_dir=JPEG_OUTPUT_DIR)
    
    # Lists to hold all our transformed data, separated by table
    all_facts = []
    all_dim_patients = []
    all_dim_stations = []
    all_dim_protocols = []
    all_dim_images = []
    all_dim_dates = []
    
    # --- Configuration for Demo ---
    max_files_to_process = 100  # Set to a high number to process all, or 3 for a quick test
    files_processed = 0
    
    # 2. Iterate over DICOM files in the input directory
    print(f"Scanning for DICOM files in: {DATA_DIR}")
    try:
        dicom_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.dcm')]
        total_files = len(dicom_files)
        print(f"Found {total_files} DICOM files.")

        for filename in dicom_files:
            if files_processed >= max_files_to_process:
                print(f"\nReached max file limit ({max_files_to_process}) for this demo.")
                break
            
            print(f"\n--- Processing file {files_processed + 1}/{total_files}: {filename} ---")
            file_path = os.path.join(DATA_DIR, filename)
            
            try:
                # 3. Step E: Extract
                raw_data = processor.extract_metadata(file_path)
                
                if raw_data:
                    # 4. Step T: Transform
                    transformed_data = processor.transform_data(raw_data, file_path)
                    
                    if transformed_data:
                        # Append data to the correct list
                        all_facts.append(transformed_data['fact_study'])
                        all_dim_patients.append(transformed_data['dim_patient'])
                        all_dim_stations.append(transformed_data['dim_station'])
                        all_dim_protocols.append(transformed_data['dim_protocol'])
                        all_dim_images.append(transformed_data['dim_image'])
                        all_dim_dates.append(transformed_data['dim_date'])

                        print(f"--- Successfully Transformed {filename} ---")
                        # print(json.dumps(transformed_data, indent=2)) # Uncomment to see full JSON
                
                files_processed += 1
                    
            except Exception as e:
                print(f"!!! CRITICAL ERROR processing {filename}: {e} !!!")
                
    except FileNotFoundError:
        print(f"!!! ERROR: Input directory not found: {DATA_DIR}")
        print("Please ensure the 'data/dicom_dir' directory exists and contains .dcm files.")
        return
    except Exception as e:
        print(f"!!! An unexpected error occurred: {e}")
        return

    print("\n--- ETL Process (Extract & Transform) Complete ---")
    print(f"Total files processed: {files_processed}")
    
    # --- 5. Save to CSV ---
    print("\n--- Saving DataFrames to CSV ---")
    
    if not all_facts:
        print("No data was processed, skipping CSV save.")
        return

    # Create a dictionary of DataFrames
    # We drop duplicates from DIMENSION tables to keep them clean
    dataframes_to_save = {
        "fact_study": pd.DataFrame(all_facts),
        "dim_patient": pd.DataFrame(all_dim_patients).drop_duplicates(subset=['_id']),
        "dim_station": pd.DataFrame(all_dim_stations).drop_duplicates(subset=['_id']),
        "dim_protocol": pd.DataFrame(all_dim_protocols).drop_duplicates(subset=['_id']),
        "dim_image": pd.DataFrame(all_dim_images).drop_duplicates(subset=['_id']),
        "dim_date": pd.DataFrame(all_dim_dates).drop_duplicates(subset=['_id'])
    }
    
    # Save each DataFrame to CSV
    for name, df in dataframes_to_save.items():
        if not df.empty:
            csv_path = os.path.join(CSV_OUTPUT_DIR, f"{name}.csv")
            # Save CSV using UTF-8 encoding and setting the key as index
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Saved {name}.csv with {len(df)} records.")
        else:
            print(f"DataFrame {name} is empty, not saving CSV.")

    print("\n--- Verification: Displaying head of processed DataFrames ---")
    for name, df in dataframes_to_save.items():
          print(f"\n** {name} **")
          print(df.head())

if __name__ == "__main__":
    main()
