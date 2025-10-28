import os
import json
import pandas as pd
from et1 import ETLProcessor 
from loader import MongoLoader 


CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_SCRIPT_DIR) 

# Build paths from the project root
DATA_DIR = os.path.join(BASE_DIR, 'data', 'dicom_dir')
JPEG_OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'jpeg_output')
CSV_OUTPUT_DIR = os.path.join(BASE_DIR, 'data', 'processed_csv') 

MONGO_CONNECTION_STRING = "mongodb://localhost:27017/"
DB_NAME = "images"


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

    try:
        print(f"Connecting to LOCAL MongoDB at {MONGO_CONNECTION_STRING}...")
        loader = MongoLoader(connection_string=MONGO_CONNECTION_STRING, db_name=DB_NAME)
    except Exception as e:
        print(f"Failed to initialize MongoDB loader. Halting process. Error: {e}")
        print("HINT: Is your local MongoDB service running?")
        return
    
    all_facts = []
    all_dim_patients = []
    all_dim_stations = []
    all_dim_protocols = []
    all_dim_images = []
    all_dim_dates = []

    #try:
        # Check if the user has updated the connection string
        #if "<username>" in MONGO_CONNECTION_STRING:
        #    print("="*50)
        #    print("!!! ERROR: Please update MONGO_CONNECTION_STRING in main.py !!!")
        #    print("Get your connection string from MongoDB Atlas (see Step 1 in guide).")
        #    print("="*50)
        #    return
            
        #loader = MongoLoader(connection_string=MONGO_CONNECTION_STRING, db_name=DB_NAME)
    #except Exception as e:
        #print(f"Failed to initialize MongoDB loader. Halting process. Error: {e}")
        #return
    
    max_files_to_process = 110  # Set to a high number to process all, or 3 for a quick test
    files_processed = 0
    
    
    print(f"Scanning for DICOM files in: {DATA_DIR}")
    try:
        dicom_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.dcm')]
        total_files = len(dicom_files)
        print(f"Found {total_files} DICOM files.")

        for filename in dicom_files:
            if files_processed >= max_files_to_process:
                print(f"\nReached max file limit ({max_files_to_process}) for this demo.")
                break
            
            #print(f"\n--- Processing file {files_processed + 1}/{total_files}: {filename} ---")
            file_path = os.path.join(DATA_DIR, filename)
            
            try:
                raw_data = processor.extract_metadata(file_path)
                
                if raw_data:
                    transformed_data = processor.transform_data(raw_data, file_path)
                    
                    if transformed_data:
                        # Append data to the correct list
                        all_facts.append(transformed_data['fact_study'])
                        all_dim_patients.append(transformed_data['dim_patient'])
                        all_dim_stations.append(transformed_data['dim_station'])
                        all_dim_protocols.append(transformed_data['dim_protocol'])
                        all_dim_images.append(transformed_data['dim_image'])
                        all_dim_dates.append(transformed_data['dim_date'])

                        #print(f"--- Successfully Transformed {filename} ---")
                        #print(json.dumps(transformed_data, indent=2)) # Uncomment to see full JSON
                
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
        "dim_patient": pd.DataFrame(all_dim_patients).drop_duplicates(subset=['patient_id']),
        "dim_station": pd.DataFrame(all_dim_stations).drop_duplicates(subset=['station_id']),
        "dim_protocol": pd.DataFrame(all_dim_protocols).drop_duplicates(subset=['protocol_id']),
        "dim_image": pd.DataFrame(all_dim_images).drop_duplicates(subset=['image_id']),
        "dim_date": pd.DataFrame(all_dim_dates).drop_duplicates(subset=['date_id'])
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

    print("\n--- Loading Data to MongoDB (Bulk Operation) ---")
    try:
        # Convert DataFrames to lists of dictionaries
        dim_patients_data = dataframes_to_save['dim_patient'].to_dict('records')
        dim_stations_data = dataframes_to_save['dim_station'].to_dict('records')
        dim_protocols_data = dataframes_to_save['dim_protocol'].to_dict('records')
        dim_images_data = dataframes_to_save['dim_image'].to_dict('records')
        dim_dates_data = dataframes_to_save['dim_date'].to_dict('records')
        facts_data = dataframes_to_save['fact_study'].to_dict('records')
        
        # Load Dimensions (Bulk Upsert)
        loader.bulk_upsert_dimension('dim_patient', dim_patients_data, 'patient_id')
        loader.bulk_upsert_dimension('dim_station', dim_stations_data, 'station_id')
        loader.bulk_upsert_dimension('dim_protocol', dim_protocols_data, 'protocol_id')
        loader.bulk_upsert_dimension('dim_image', dim_images_data, 'image_id')
        loader.bulk_upsert_dimension('dim_date', dim_dates_data, 'date_id')
        
        # Load Facts (Bulk Insert)
        loader.bulk_insert_facts('fact_study', facts_data)
        
        # 7. Create Indexes
        loader.create_indexes()

    except Exception as e:
        print(f"!!! ERROR during MongoDB load: {e}")

    print("\n--- Full ETL Process Finished ---")
    print("Check MongoDB Compass (connect to localhost) to see your 'dicom_db' database.")

if __name__ == "__main__":
    main()
