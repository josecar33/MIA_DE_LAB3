import os
import pydicom
import numpy as np
import cv2  # OpenCV for image processing
import hashlib
import json
import re
from datetime import datetime

class ETLProcessor:
    """
    Handles the Extraction and Transformation logic for the DICOM ETL pipeline.
    """
    
    def __init__(self, jpeg_output_dir):
        """
        Initializes the processor and ensures the output directory for JPEGs exists.
        
        Args:
            jpeg_output_dir (str): Path to the directory where JPEGs will be saved.
        """
        self.jpeg_output_dir = jpeg_output_dir
        os.makedirs(self.jpeg_output_dir, exist_ok=True)
        print(f"ETLProcessor initialized. JPEG output directory: {self.jpeg_output_dir}")

    # --- 1. EXTRACT ---

    def extract_metadata(self, dicom_file_path):
        """
        Extracts raw metadata from a single DICOM file based on the star schema.
        
        Args:
            dicom_file_path (str): The full path to the .dcm file.
            
        Returns:
            dict: A dictionary containing the raw extracted metadata, or None if extraction fails.
        """
        print(f"\n[E] Extracting from: {dicom_file_path}")
        try:
            # Read DICOM file, stop_before_pixels=True makes it faster as we don't need the image yet
            ds = pydicom.dcmread(dicom_file_path, stop_before_pixels=True)
            
            # Helper function to safely get string values from DICOM tags
            def get_val(tag, default=None):
                val = ds.get(tag, default)
                # Check if the value exists and has a 'value' attribute
                if hasattr(val, 'value'):
                    return str(val.value)
                # If it's a simple value (like default), return it as string
                return str(val) if val is not None else None

            # Extract raw data based on the schema
            raw_data = {
                # Patient Dimension
                'PatientID': get_val((0x0010, 0x0020)),
                'PatientSex': get_val((0x0010, 0x0040)),
                'PatientAge': get_val((0x0010, 0x1010)), # e.g., '061Y'

                # Station Dimension
                'Manufacturer': get_val((0x0008, 0x0070)),
                'ManufacturerModelName': get_val((0x0008, 0x1090)),

                # Protocol Dimension
                'BodyPartExamined': get_val((0x0018, 0x0015)),
                'ContrastBolusAgent': get_val((0x0018, 0x0010)),
                'PatientPosition': get_val((0x0018, 0x5100)),

                # Image Dimension
                'Rows': get_val((0x0028, 0x0010)),
                'Columns': get_val((0x0028, 0x0011)),
                'PixelSpacing': get_val((0x0028, 0x0030)), # This is often an array e.g., ['0.7', '0.7']
                'SliceThickness': get_val((0x0018, 0x0050)),
                'KVP': get_val((0x0018, 0x0060)),

                # Date Dimension
                'StudyDate': get_val((0x0008, 0x0020)), # e.g., '20230101'

                # Study Fact
                'StudyInstanceUID': get_val((0x0020, 0x000D)), # Main key for the study
                'ExposureTime': get_val((0x0018, 0x1150)),
                'XRayTubeCurrent': get_val((0x0018, 0x1151)),
            }
            print(f"[E] Raw data extracted for Study UID {raw_data.get('StudyInstanceUID')}")
            # print(f"[E] Raw data: {raw_data}") # Uncomment for full data dump
            return raw_data
        
        except Exception as e:
            print(f"[E] ERROR: Failed to read {dicom_file_path}. Error: {e}")
            return None

    # --- 2. TRANSFORM ---

    def transform_data(self, raw_data, dicom_file_path):
        """
        Transforms raw extracted data into the structured star schema format
        and processes the image file (DICOM -> JPEG).
        
        Args:
            raw_data (dict): The raw metadata from extract_metadata.
            dicom_file_path (str): The full path to the original .dcm file (for image processing).
            
        Returns:
            dict: A dictionary containing all dimension and fact table data, ready for loading.
        """
        if not raw_data:
            print("[T] Skipping transform, no raw data provided.")
            return None

        print(f"\n[T] Transforming data for Study UID: {raw_data.get('StudyInstanceUID')}")
        
        # --- 1. Transform Dimensions ---

        # Patient Dimension
        patient_age_int = self.format_age(raw_data.get('PatientAge'))
        patient_dim_vals = {
            'patient_id_dicom': raw_data.get('PatientID'),
            'sex': raw_data.get('PatientSex'),
            'age': patient_age_int
        }
        patient_key = self.surrogate_key(patient_dim_vals)
        print(f"[T] Patient Dim transformed: Key={patient_key}, Data={patient_dim_vals}")

        # Station Dimension
        station_dim_vals = {
            'manufacturer': raw_data.get('Manufacturer'),
            'model': raw_data.get('ManufacturerModelName')
        }
        station_key = self.surrogate_key(station_dim_vals)
        print(f"[T] Station Dim transformed: Key={station_key}, Data={station_dim_vals}")

        # Protocol Dimension
        contrast_agent = self.normalize_contrast_agent(raw_data.get('ContrastBolusAgent'))
        protocol_dim_vals = {
            'body_part': raw_data.get('BodyPartExamined'),
            'contrast_agent': contrast_agent,
            'position': raw_data.get('PatientPosition')
        }
        protocol_key = self.surrogate_key(protocol_dim_vals)
        print(f"[T] Protocol Dim transformed: Key={protocol_key}, Data={protocol_dim_vals}")

        # Date Dimension
        study_date = raw_data.get('StudyDate')
        year, month = None, None
        try:
            if study_date:
                dt = datetime.strptime(study_date, '%Y%m%d')
                year, month = dt.year, dt.month
        except Exception as e:
            print(f"[T] Warning: Could not parse date '{study_date}'. Error: {e}")
        
        date_dim_vals = {'year': year, 'month': month}
        date_key = self.surrogate_key(date_dim_vals)
        print(f"[T] Date Dim transformed: Key={date_key}, Data={date_dim_vals}")

        # Image Dimension
        raw_pixel_spacing = raw_data.get('PixelSpacing')
        pixel_spacing_val = None
        if raw_pixel_spacing:
            try:
                # Find the first numeric value in the string (e.g., "['0.7', '0.7']" -> "0.7")
                match = re.search(r"[\d\.]+", raw_pixel_spacing)
                if match:
                    pixel_spacing_val = float(match.group(0))
            except Exception:
                pass # Keep as None
        
        norm_pixel_spacing = self.normalize_pixel_spacing(pixel_spacing_val)
        
        image_dim_vals = {
            'rows': int(raw_data.get('Rows')) if raw_data.get('Rows') else None,
            'cols': int(raw_data.get('Columns')) if raw_data.get('Columns') else None,
            'pixel_spacing_norm': norm_pixel_spacing,
            'slice_thickness': float(raw_data.get('SliceThickness')) if raw_data.get('SliceThickness') else None,
            'kvp': float(raw_data.get('KVP')) if raw_data.get('KVP') else None
        }
        image_key = self.surrogate_key(image_dim_vals)
        print(f"[T] Image Dim transformed: Key={image_key}, Data={image_dim_vals}")

        # --- 2. Transform Image File (DICOM -> JPEG) ---
        jpeg_path = self.dicom_to_jpeg(dicom_file_path, self.jpeg_output_dir)
        print(f"[T] Image file transformed and saved to: {jpeg_path}")

        # --- 3. Assemble Fact Table Data ---
        study_fact = {
   
            # Foreign Keys
            'patient_id': patient_key,
            'station_id': station_key,
            'protocol_id': protocol_key,
            'image_id': image_key,
            'date_id': date_key,

            'exposure_time': float(raw_data.get('ExposureTime')) if raw_data.get('ExposureTime') else None,
            'tube_current': float(raw_data.get('XRayTubeCurrent')) if raw_data.get('XRayTubeCurrent') else None,
            'file_path': jpeg_path
         
        }
        print(f"[T] Study Fact assembled: {study_fact}")

        # Return all transformed data, structured for loading
        return {
            'fact_study': study_fact,
            'dim_patient': {'patient_id': patient_key, **patient_dim_vals},
            'dim_station': {'station_id': station_key, **station_dim_vals},
            'dim_protocol': {'protocol_id': protocol_key, **protocol_dim_vals},
            'dim_image': {'image_id': image_key, **image_dim_vals},
            'dim_date': {'date_id': date_key, **date_dim_vals}
        }

    # --- 3. HELPER FUNCTIONS (as requested by PDF) ---

    @staticmethod
    def surrogate_key(values):
        """
        Creates a unique, repeatable MD5 hash string from a dictionary.
        
        Args:
            values (dict): A dictionary of values for a dimension.
            
        Returns:
            str: A 32-character MD5 hash string.
        """
        # Convert dict to a sorted JSON string to ensure consistency
        values_string = json.dumps(values, sort_keys=True, default=str)
        
        # Create MD5 hash
        md5_hash = hashlib.md5(values_string.encode('utf-8')).hexdigest()
        return md5_hash

    @staticmethod
    def format_age(age_str):
        """
        Transforms a DICOM age string (e.g., '061Y') into an integer.
        Handles missing or malformed data safely.
        
        Args:
            age_str (str): The DICOM age string.
            
        Returns:
            int or None: The age as an integer, or None if not found.
        """
        if not age_str:
            return None
        
        # Use regex to find the first sequence of digits
        match = re.search(r'(\d+)', age_str)
        if match:
            try:
                # Return the found digits as an integer
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def dicom_to_jpeg(input_path, output_dir, size=(256, 256)):
        """
        Reads a DICOM file, normalizes its pixel values, resizes it, 
        and saves it as a grayscale JPEG.
        
        Args:
            input_path (str): Path to the source DICOM file.
            output_dir (str): Directory to save the JPEG.
            size (tuple): The target (width, height) for resizing.
            
        Returns:
            str or None: The full path to the saved JPEG, or None on failure.
        """
        try:
            # Read the full DICOM file (including pixels)
            ds = pydicom.dcmread(input_path)
            
            # Get pixel data
            pixels = ds.pixel_array.astype(float)
            
            # Normalize pixel values to 0-255
            # Add a small epsilon to prevent division by zero if image is all black
            min_val = np.min(pixels)
            max_val = np.max(pixels)
            if (max_val - min_val) > 1e-6:
                pixels_scaled = (pixels - min_val) / (max_val - min_val)
            else:
                pixels_scaled = np.zeros(pixels.shape) # Avoid division by zero
                        
            pixels_8bit = (pixels_scaled * 255.0).astype(np.uint8)
            
            # Resize to specified size using OpenCV
            resized_img = cv2.resize(pixels_8bit, size, interpolation=cv2.INTER_AREA)
            
            # Create output path
            # Use the original filename but change the extension
            filename = os.path.basename(input_path).replace('.dcm', '.jpg')
            output_path = os.path.join(output_dir, filename)
            
            # Save the image as grayscale JPEG
            cv2.imwrite(output_path, resized_img)
            
            return output_path
        
        except Exception as e:
            print(f"ERROR processing image {input_path}: {e}")
            # This error often happens if a specific decompressor is needed
            if 'decompress' in str(e):
                 print("-> HINT: This DICOM file might be compressed. Ensure 'pylibjpeg' is installed (`pip install pylibjpeg`).")
            return None

    @staticmethod
    def normalize_pixel_spacing(raw_value):
        """
        Rounds a numeric pixel spacing value to the nearest predefined bin
        (0.6, 0.65, 0.7, 0.75, 0.8).
        
        Args:
            raw_value (float or str): The raw pixel spacing value.
            
        Returns:
            float or None: The normalized (binned) value, or None.
        """
        if raw_value is None:
            return None
            
        bins = [0.6, 0.65, 0.7, 0.75, 0.8]
        try:
            # Find the bin with the minimum absolute difference
            float_val = float(raw_value)
            normalized_val = min(bins, key=lambda x: abs(x - float_val))
            return normalized_val
        except (ValueError, TypeError):
            # Handle cases where raw_value is not a number
            return None

    @staticmethod
    def normalize_contrast_agent(val):
        """
        Standardizes DICOM contrast agent metadata.
        Replaces missing, empty, or single-character values with 'None'.
        
        Args:
            val (str): The raw contrast agent string.
            
        Returns:
            str: The standardized string.
        """
        if val is None:
            return "None"
        
        # Remove leading/trailing whitespace
        val_str = str(val).strip()
        
        # Replace missing, empty, or single-character values
        if not val_str or len(val_str) <= 1:
            return "None"
        
        # Return the cleaned, non-empty string
        return val_str
