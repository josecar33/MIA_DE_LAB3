import pydicom
import os
import glob

# --- Configuración ---
# Cambia esto si tu carpeta de DICOMs tiene otro nombre
DICOM_DIR = 'data/dicom_dir' 
# Cambia esto al nombre exacto de UNO de los archivos .dcm que quieres inspeccionar
# Es mejor elegir uno de los primeros que dieron error.
EXAMPLE_DICOM_FILE = 'ID_0000_AGE_0060_CONTRAST_1_CT.dcm' 

def inspect_single_dicom(filepath):
    """
    Lee un archivo DICOM e imprime todos sus metadatos.
    """
    if not os.path.exists(filepath):
        print(f"Error: El archivo no existe en la ruta: {filepath}")
        return

    print(f"\n--- Inspeccionando Metadatos del Archivo: {os.path.basename(filepath)} ---")

    try:
        # Lee el archivo DICOM
        dcm = pydicom.dcmread(filepath, force=True)

        # Imprime toda la información del encabezado (metadatos)
        print("\nMetadatos Encontrados:")
        print("-" * 30)
        print(dcm) # pydicom formatea la salida de forma legible
        print("-" * 30)

        # Opcional: Intenta acceder a algunas etiquetas clave que usamos en el ETL
        print("\nAccediendo a etiquetas específicas:")
        patient_id = dcm.get("PatientID", "¡¡¡ PatientID NO ENCONTRADO !!!")
        study_uid = dcm.get("StudyInstanceUID", "¡¡¡ StudyInstanceUID NO ENCONTRADO !!!")
        series_uid = dcm.get("SeriesInstanceUID", "¡¡¡ SeriesInstanceUID NO ENCONTRADO !!!")
        manufacturer = dcm.get("Manufacturer", "¡¡¡ Manufacturer NO ENCONTRADO !!!")
        model = dcm.get("ManufacturerModelName", "¡¡¡ Model NO ENCONTRADO !!!")
        study_date = dcm.get("StudyDate", "¡¡¡ StudyDate NO ENCONTRADO !!!")

        print(f"  PatientID:             {patient_id}")
        print(f"  StudyInstanceUID:      {study_uid}")
        print(f"  SeriesInstanceUID:     {series_uid}")
        print(f"  Manufacturer:          {manufacturer}")
        print(f"  ManufacturerModelName: {model}")
        print(f"  StudyDate:             {study_date}")

    except Exception as e:
        print(f"Error al leer o procesar el archivo DICOM: {e}")

# --- Punto de Entrada ---
if __name__ == "__main__":
    file_to_inspect = os.path.join(DICOM_DIR, EXAMPLE_DICOM_FILE)
    inspect_single_dicom(file_to_inspect)