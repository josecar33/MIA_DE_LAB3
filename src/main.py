# main.py
from et import DicomETLProcessor # Asegúrate que el nombre de la clase sea correcto
import os

def run_et_pipeline():
    print("--- DICOM ET (Extract-Transform) Pipeline Started ---")
    
    DATA_PATH = 'data/dicom_dir' # Ajusta esta ruta si es necesario
    PROCESSED_DATA_PATH = 'data/processed' # Carpeta para guardar CSVs (opcional)

    if not os.path.exists(PROCESSED_DATA_PATH):
        os.makedirs(PROCESSED_DATA_PATH)
        
    try:
        # 1. Inicializa el procesador
        processor = DicomETLProcessor(dicom_dir_path=DATA_PATH)
        
        # 2. Ejecuta el procesamiento principal
        processed_data = processor.process_dicom_files()
        
        if processed_data:
            # 3. (Opcional) Guarda los DataFrames resultantes como CSV
            for name, df in processed_data.items():
                if not df.empty:
                    csv_path = os.path.join(PROCESSED_DATA_PATH, f"{name}.csv")
                    df.to_csv(csv_path, index=False)
                    print(f"Saved {name}.csv with {len(df)} records.")
                else:
                    print(f"DataFrame {name} is empty, not saving CSV.")

            # Puedes imprimir los .head() para verificar
            print("\n--- Verification: Displaying head of processed DataFrames ---")
            for name, df in processed_data.items():
                 print(f"\n** {name} **")
                 print(df.head())
        else:
             print("Processing did not yield any data.")
            
    except Exception as e:
        print(f"An error occurred during the ET process: {e}")
        
    print("\n--- DICOM ET Pipeline Finished ---")

if __name__ == "__main__":
    run_et_pipeline()