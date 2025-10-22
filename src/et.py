# ...existing code...
import os
import pandas as pd
import matplotlib.pyplot as plt
import pydicom
import glob
import hashlib

DATA_PATH = 'data/dicom_dir'

# Check if the directory exists
if not os.path.exists(DATA_PATH):
    print(f"Error: The directory {DATA_PATH} does not exist.")
    exit()

DICOM_FILES_PATH = os.path.join(DATA_PATH, '*.dcm')
dicom_data = pd.DataFrame([{'path': filepath} for filepath in glob.glob(DICOM_FILES_PATH)])  # Use glob.glob
dicom_data['file'] = dicom_data['path'].map(os.path.basename)

# Show all DICOM metadata of one file
dicom_file_path = list(dicom_data[:1].T.to_dict().values())[0]['path']
dicom_file_metadata = pydicom.dcmread(dicom_file_path)
print(dicom_file_metadata)

# ========== New DICOM IMAGE ETL class ==========
class DicomImageETL:
    """
    Extract IMAGE dimension from DICOM files in a folder.
    Produces a pandas.DataFrame with columns:
      - image_id
      - path
      - file
      - rows
      - columns
      - pixel_spacing_x
      - pixel_spacing_y
      - slice_thickness
      - photometric_interp
      - sop_instance_uid (if present)
    """
    def __init__(self, data_path=DATA_PATH):
        self.data_path = data_path
        self.files = []
        self.df_images = pd.DataFrame()

    def discover_files(self):
        pattern = os.path.join(self.data_path, '*.dcm')
        self.files = sorted(glob.glob(pattern))
        return self.files

    def _generate_image_id(self, ds, filepath):
        # Prefer SOPInstanceUID; fallback to MD5 of file bytes
        sop = getattr(ds, 'SOPInstanceUID', None)
        if sop:
            return str(sop)
        # fallback: md5 of file bytes
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def extract_metadata(self, stop_before_pixels=True):
        """
        Read each DICOM header and extract requested tags.
        stop_before_pixels=True speeds up read when pixel data not needed.
        """
        rows = []
        if not self.files:
            self.discover_files()
        for fp in self.files:
            try:
                ds = pydicom.dcmread(fp, stop_before_pixels=stop_before_pixels)
            except Exception as e:
                print(f"Warning: cannot read {fp}: {e}")
                continue

            # safe getters with defaults
            r = getattr(ds, 'Rows', None)
            c = getattr(ds, 'Columns', None)
            pixel_spacing = getattr(ds, 'PixelSpacing', None)  # often [row_spacing, col_spacing]
            ps_x = None
            ps_y = None
            if pixel_spacing:
                try:
                    # PixelSpacing may come as list-like of strings/numbers
                    ps_y = float(pixel_spacing[0])  # usually row spacing (y)
                    ps_x = float(pixel_spacing[1])  # usually column spacing (x)
                except Exception:
                    # try convert individually or skip
                    try:
                        ps_x = float(pixel_spacing[0])
                        ps_y = float(pixel_spacing[1])
                    except Exception:
                        ps_x = ps_y = None

            slice_thickness = None
            try:
                st = getattr(ds, 'SliceThickness', None)
                if st is not None:
                    slice_thickness = float(st)
            except Exception:
                slice_thickness = None

            photometric = getattr(ds, 'PhotometricInterpretation', None)
            sop_uid = getattr(ds, 'SOPInstanceUID', None)
            image_id = self._generate_image_id(ds, fp)

            rows.append({
                'image_id': image_id,
                'path': fp,
                'file': os.path.basename(fp),
                'rows': int(r) if r is not None else None,
                'columns': int(c) if c is not None else None,
                'pixel_spacing_x': ps_x,
                'pixel_spacing_y': ps_y,
                'slice_thickness': slice_thickness,
                'photometric_interp': photometric,
                'sop_instance_uid': sop_uid
            })

        self.df_images = pd.DataFrame(rows)
        return self.df_images

    def save_csv(self, out_path):
        if self.df_images.empty:
            raise RuntimeError("No image metadata to save. Run extract_metadata() first.")
        self.df_images.to_csv(out_path, index=False)
        return out_path

# Example quick-run (only when invoked directly)
if __name__ == '__main__':
    etl = DicomImageETL(DATA_PATH)
    etl.discover_files()
    df = etl.extract_metadata()
    print(df.head())
    # opcional: guardar
    etl.save_csv(os.path.join(DATA_PATH, 'image_dimension.csv'))

