import pydicom
import pandas as pd
import hashlib
import json
import os
import glob
from datetime import datetime

class DicomETLProcessor:
    """
    Handles the Extraction and Transformation of DICOM metadata
    into Pandas DataFrames for dimensions and a fact table,
    managing dimensions in memory using surrogate keys.
    """
    def __init__(self, dicom_dir_path):
        """
        Initializes the processor.
        Args:
            dicom_dir_path (str): Path to the directory containing DICOM files.
        """
        self.dicom_dir_path = dicom_dir_path
        # In-memory storage for unique dimension records (key: SK, value: attributes dict)
        self.dimensions = {
            "patient": {},
            "image": {},
            "station": {},
            "protocol": {},
            "date": {}
        }
        print("DicomETLProcessor initialized.")

    # --- 1. Required Helper Functions (from Guide) ---

    def surrogate_key(self, values):
        """Generates a unique MD5 hash surrogate key from a dictionary."""
        # Convert dict to a sorted JSON string for consistent hashing
        try:
            # Use default=str for complex DICOM types that might not be directly serializable
            ordered_json = json.dumps(values, sort_keys=True, default=str)
        except TypeError as e:
            print(f"Warning: Could not serialize values for hashing: {values}. Error: {e}")
            # Fallback: create hash from a simple representation
            simple_repr = repr(sorted(values.items()))
            ordered_json = json.dumps(simple_repr)

        hash_object = hashlib.md5(ordered_json.encode())
        return hash_object.hexdigest()

    def format_age(self, age_str):
        """Transforms DICOM age string ('061Y') into an integer (61). Handles errors safely."""
        if not age_str or not isinstance(age_str, str) or 'Y' not in age_str:
            return None
        try:
            return int(age_str.split('Y')[0])
        except (ValueError, IndexError):
            return None

    def normalize_pixel_spacing(self, raw_value):
        """Normalizes pixel spacing to the nearest predefined bin."""
        if pd.isna(raw_value): return None
        try: value = float(raw_value)
        except (ValueError, TypeError): return None
        bins = [0.6, 0.65, 0.7, 0.75, 0.8]
        closest_bin = min(bins, key=lambda x: abs(x - value))
        return closest_bin

    def normalize_contrast_agent(self, val):
        """Standardizes the contrast agent field."""
        default = "No contrast agent"
        if pd.isna(val) or val == '' or (isinstance(val, str) and len(val.strip()) <= 1):
            return default
        return str(val).strip() if isinstance(val, str) else default

    # --- 2. Generic Dimension Processing Method ---

    # et.py - Reemplaza este método completo

    # et.py - Modifica esta función

    def _get_or_create_dimension_sk(self, dcm_dataset, dim_key, defining_attributes, all_attributes_map, transformations=None):
        """
        Extracts dimension attributes, generates SK, stores unique records in memory, and returns SK.
        Handles different DICOM value types more robustly.
        Can now handle defining_attributes provided directly (for Date dimension).
        """
        defining_values = {}
        valid_key = True

        # --- Extract DEFINING attributes ---
        for out_col, source in defining_attributes.items():
            value = None
            # --- NUEVA LÓGICA: Si source no es string, es un valor directo (para Date) ---
            if not isinstance(source, str):
                value = source # Usar el valor directamente (ej: year=2023)
            # --- FIN NUEVA LÓGICA ---
            else: # Si es string, es un DICOM Tag Keyword
                tag_keyword = source
                data_element = dcm_dataset.get(tag_keyword, None)
                if data_element is not None and hasattr(data_element, 'value'):
                    raw_val = data_element.value
                    if isinstance(raw_val, pydicom.valuerep.PersonName): value = str(raw_val)
                    elif isinstance(raw_val, list): value = tuple(str(v) for v in raw_val)
                    else: value = raw_val # Asume que es un tipo simple o serializable
                else:
                    valid_key = False # Si falta un tag definitorio, clave inválida

            defining_values[out_col] = value
            if value is None: # Si después de extraer/asignar, el valor es None
                valid_key = False

        if not valid_key:
            # print(f"Warning: Missing defining attributes for dimension '{dim_key}'. Cannot generate key.")
            return None

        sk = self.surrogate_key(defining_values)

        if sk not in self.dimensions[dim_key]:
            record_attributes = {}
             # --- NUEVA LÓGICA: Extraer TODOS los atributos ---
            for out_col, source in all_attributes_map.items():
                 value = None
                 if not isinstance(source, str): # Valor directo (para Date)
                     value = source
                 else: # DICOM Tag Keyword
                     tag_keyword = source
                     data_element = dcm_dataset.get(tag_keyword, None)
                     # (Aquí va la lógica de extracción robusta que ya teníamos)
                     if data_element is not None:
                         if hasattr(data_element, 'value'):
                             raw_val = data_element.value
                             if isinstance(raw_val, pydicom.valuerep.PersonName): value = str(raw_val)
                             elif isinstance(raw_val, list): value = tuple(str(v) for v in raw_val)
                             elif isinstance(raw_val, (int, float, str, bytes)): value = raw_val
                             elif isinstance(raw_val, pydicom.Sequence): value = "[Sequence Data]"
                             else:
                                 try: value = str(raw_val)
                                 except: value = "[Unrepresentable Value]"
                         elif isinstance(data_element, (int, float, str)): value = data_element
                         else:
                             try: value = str(data_element)
                             except: value = "[Unknown DICOM Element Type]"

                 record_attributes[out_col] = value
                 # --- FIN NUEVA LÓGICA EXTRACCIÓN ---

                 # Aplicar transformaciones
                 if transformations and out_col in transformations:
                     try:
                         record_attributes[out_col] = transformations[out_col](record_attributes[out_col])
                     except Exception as e:
                         # print(f"Warning: Transformation failed...")
                         record_attributes[out_col] = None

            # Asegurarse de que los valores definitorios estén en el registro final
            record_attributes.update(defining_values)
            self.dimensions[dim_key][sk] = record_attributes

        return sk
        """
        Extracts dimension attributes, generates SK, stores unique records in memory, and returns SK.
        Handles different DICOM value types more robustly.
        """
        defining_values = {}
        valid_key = True

        # --- Extract DEFINING attributes first for the key ---
        for out_col, tag_keyword in defining_attributes.items():
            data_element = dcm_dataset.get(tag_keyword, None) # Get the DataElement object
            
            if data_element is not None and hasattr(data_element, 'value'):
                # Convert common DICOM types to basic Python types for the key
                value = data_element.value
                if isinstance(value, pydicom.valuerep.PersonName):
                    defining_values[out_col] = str(value) # Use string representation for names
                elif isinstance(value, list): # Handle MultiValue
                     defining_values[out_col] = tuple(str(v) for v in value) # Use tuple of strings
                else:
                    defining_values[out_col] = value # Use the value directly if simple type
            else:
                defining_values[out_col] = None
                valid_key = False

        if not valid_key:
            # print(f"Warning: Missing defining attributes for dimension '{dim_key}'.")
            return None

        sk = self.surrogate_key(defining_values)

        if sk not in self.dimensions[dim_key]:
            # --- If new, extract ALL attributes for the dimension record ---
            record_attributes = {}
            for out_col, tag_keyword in all_attributes_map.items():
                data_element = dcm_dataset.get(tag_keyword, None)
                value = None # Default to None

                if data_element is not None:
                     # Check if it's a DataElement with a value property
                    if hasattr(data_element, 'value'):
                        raw_val = data_element.value
                        # Handle specific types for storage
                        if isinstance(raw_val, pydicom.valuerep.PersonName):
                            value = str(raw_val)
                        elif isinstance(raw_val, list): # MultiValue
                             value = tuple(str(v) for v in raw_val) # Store as tuple
                        elif isinstance(raw_val, (int, float, str, bytes)):
                             value = raw_val # Keep basic types as they are
                        elif isinstance(raw_val, pydicom.Sequence):
                             # Decide how to handle sequences (e.g., skip, take first item, serialize to JSON)
                             value = "[Sequence Data]" # Placeholder - adjust as needed
                        else:
                             # Fallback for other complex types - convert to string
                             try:
                                value = str(raw_val)
                             except:
                                value = "[Unrepresentable Value]"
                    # Handle cases where .get() might return a simple type directly (less common but possible)
                    elif isinstance(data_element, (int, float, str)):
                         value = data_element
                    else:
                         # Fallback if it's not a standard DataElement structure we expect
                         try:
                            value = str(data_element)
                         except:
                             value = "[Unknown DICOM Element Type]"

                record_attributes[out_col] = value

                # Apply transformations AFTER basic extraction
                if transformations and out_col in transformations:
                    try:
                        # Pass the extracted value to the transformation function
                        record_attributes[out_col] = transformations[out_col](record_attributes[out_col])
                    except Exception as e:
                        # print(f"Warning: Transformation failed for {out_col} with value {record_attributes[out_col]}. Error: {e}")
                        record_attributes[out_col] = None

            # Add the defining values used for the key into the record if they weren't already included
            record_attributes.update(defining_values)
            self.dimensions[dim_key][sk] = record_attributes

        return sk
    # --- 3. Main Processing Loop ---

    # et.py - Reemplaza esta función completa

# et.py - Replace the entire process_dicom_files function with this one

    def process_dicom_files(self):
        """
        Iterates through DICOM files, processes dimensions using helper method,
        collects fact data, and returns final DataFrames.
        """
        print(f"Searching for DICOM files in: {self.dicom_dir_path}")
        dicom_files = glob.glob(os.path.join(self.dicom_dir_path, '*.dcm'))
        print(f"Found {len(dicom_files)} DICOM files.")
        if not dicom_files:
            print("No DICOM files found. Exiting.")
            return None # Return None if no files

        fact_study_list = []

        for filepath in dicom_files:
            filename = os.path.basename(filepath) # Define filename here
            try:
                # print(f"Processing: {filename}") # Uncomment for detailed file processing log
                dcm = pydicom.dcmread(filepath, force=True)

                # --- Process Dimensions for this file using correct Keywords ---

                # Patient Dimension (Keyword: PatientID)
                patient_sk = self._get_or_create_dimension_sk(
                    dcm, 'patient',
                    defining_attributes={'patient_dicom_id': 'PatientID'},
                    all_attributes_map={'patient_dicom_id': 'PatientID', 'sex': 'PatientSex', 'age': 'PatientAge'},
                    transformations={'age': self.format_age}
                )

                # Image Dimension (Keyword: SOPInstanceUID)
                image_sk = self._get_or_create_dimension_sk(
                    dcm, 'image',
                    defining_attributes={'sop_instance_uid': 'SOPInstanceUID'},
                    all_attributes_map={
                        'sop_instance_uid': 'SOPInstanceUID', 'rows': 'Rows', 'columns': 'Columns',
                        'pixel_spacing': 'PixelSpacing', # Raw value stored here
                        'slice_thickness': 'SliceThickness', 'photometric_interp': 'PhotometricInterpretation'
                    }
                )

                # Station Dimension (Keywords: Manufacturer, ManufacturerModelName)
                station_sk = self._get_or_create_dimension_sk(
                    dcm, 'station',
                    defining_attributes={'manufacturer': 'Manufacturer', 'model': 'ManufacturerModelName'},
                    all_attributes_map={'manufacturer': 'Manufacturer', 'model': 'ManufacturerModelName'}
                )

                # Protocol Dimension (Keyword: BodyPartExamined as primary identifier)
                protocol_sk = self._get_or_create_dimension_sk(
                    dcm, 'protocol',
                    defining_attributes={'bodypart_part': 'BodyPartExamined'}, # Using only BodyPartExamined
                    all_attributes_map={
                        'bodypart_part': 'BodyPartExamined',
                        'protocol_name': 'ProtocolName', # Attempt to capture if exists
                        'study_description_fallback': 'StudyDescription', # Capture description
                        'contrast_agent': 'ContrastBolusAgent',
                        'patient_position': 'PatientPosition'
                    },
                    transformations={'contrast_agent': self.normalize_contrast_agent}
                )

                # Date Dimension (Based on calculated Year/Month from StudyDate)
                study_date_str = dcm.get('StudyDate', None)
                date_sk = None # Initialize
                year, month = None, None
                if study_date_str and len(str(study_date_str)) == 8:
                    try:
                        dt = datetime.strptime(str(study_date_str), '%Y%m%d')
                        year = dt.year
                        month = dt.month
                        date_key_dict = {'year': year, 'month': month}
                        # Pass None for dcm_dataset as attributes are directly provided
                        date_sk = self._get_or_create_dimension_sk(
                            None, 'date', # Pass None here
                            defining_attributes=date_key_dict,
                            all_attributes_map=date_key_dict
                        )
                    except ValueError:
                         date_sk = None # Handle invalid date format silently now
                # else: date_sk remains None if StudyDate is missing/invalid

                # --- Print generated SKs for debugging ---
                # print(f"  File: {filename}")
                # print(f"    Patient SK: {patient_sk}")
                # print(f"    Image SK:   {image_sk}")
                # print(f"    Station SK: {station_sk}")
                # print(f"    Protocol SK:{protocol_sk}")
                # print(f"    Date SK:    {date_sk}")

                # --- Assemble Fact Record ---
                # Define which dimension SKs are absolutely essential for a fact record
                essential_sks = [station_sk, patient_sk, image_sk, date_sk] # Example: Protocol SK is optional
                if not all(essential_sks):
                    # print(f"  --> Skipping file {filename} due to missing essential dimension keys.")
                    continue # Skip this file

                # --- Extract Facts ---
                exposure_time = dcm.get('ExposureTime', None)
                tube_current = dcm.get('XRayTubeCurrent', None)

                # Extract and normalize pixel spacing values for the fact table
                pixel_spacing_raw = dcm.get("PixelSpacing", [None, None])
                pixel_spacing_x_norm = self.normalize_pixel_spacing(pixel_spacing_raw[0] if isinstance(pixel_spacing_raw, list) and len(pixel_spacing_raw)>0 else None)
                pixel_spacing_y_norm = self.normalize_pixel_spacing(pixel_spacing_raw[1] if isinstance(pixel_spacing_raw, list) and len(pixel_spacing_raw)>1 else None)

                fact_record = {
                    'station_id': station_sk,
                    'patient_id': patient_sk,
                    'image_id': image_sk,
                    'protocol_id': protocol_sk, # Can be None if protocol_sk was None
                    'study_date_id': date_sk,   # Renamed for clarity
                    'exposure_time': float(exposure_time) if exposure_time is not None else None,
                    'tube_current': float(tube_current) if tube_current is not None else None,
                    'file_path': filepath, # Store the relative path
                    # Store normalized pixel spacing as facts
                    'pixel_spacing_x_norm': pixel_spacing_x_norm,
                    'pixel_spacing_y_norm': pixel_spacing_y_norm
                }
                fact_study_list.append(fact_record)

            except Exception as e:
                print(f"ERROR processing file {filepath}: {e}")

        # --- Convert In-Memory Dimensions and Facts to DataFrames ---
        print("\nCreating final DataFrames from collected dimension data...")

        dim_dfs = {}
        for dim_name, dim_data in self.dimensions.items():
            if dim_data:
                df = pd.DataFrame.from_dict(dim_data, orient='index')
                # Use the dimension name + '_id' convention for the SK column
                sk_col_name = f'{dim_name}_id'
                df.index.name = sk_col_name
                df.reset_index(inplace=True)
                dim_dfs[f'dim_{dim_name}'] = df
                print(f"Created DataFrame for dimension: dim_{dim_name}")
            else:
                print(f"Warning: No data collected for dimension: {dim_name}")
                dim_dfs[f'dim_{dim_name}'] = pd.DataFrame() # Create empty DF

        if fact_study_list:
            fact_study_df = pd.DataFrame(fact_study_list)
            # Add a unique primary key for the fact table itself (optional but good practice)
            fact_study_df.insert(0, 'study_fact_id', range(1, len(fact_study_df) + 1))
            print("Created DataFrame for fact table: fact_study")
        else:
            print("Warning: No data collected for fact table.")
            fact_study_df = pd.DataFrame()

        dim_dfs['fact_study'] = fact_study_df

        print("ETL (Extract-Transform) phase finished.")
        return dim_dfs