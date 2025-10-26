# ...existing code...
import os
import pandas as pd
import matplotlib.pyplot as plt
import pydicom
import glob
import hashlib

import json
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image
try:
    import pymongo
    from pymongo.errors import DuplicateKeyError
except Exception:
    pymongo = None


DATA_PATH = 'data/dicom_dir'

# Check if the directory exists
if not os.path.exists(DATA_PATH):
    print(f"Error: The directory {DATA_PATH} does not exist.")
    exit()

DICOM_FILES_PATH = os.path.join(DATA_PATH, '*.dcm')
dicom_data = pd.DataFrame([{'path': filepath} for filepath in glob.glob(DICOM_FILES_PATH)])  # Use glob.glob
dicom_data['file'] = dicom_data['path'].map(os.path.basename)

# Show all DICOM metadata of one file
#dicom_file_path = list(dicom_data[:1].T.to_dict().values())[0]['path']
#dicom_file_metadata = pydicom.dcmread(dicom_file_path)
#print(dicom_file_metadata)


def surrogate_key(values: Dict[str, Any]) -> str:
    """
    Genera una clave surrogate determinista (MD5) a partir de un dict.
    - Ordena las claves (sort_keys=True) para garantizar determinismo.
    - Usa default=str para serializar tipos no JSON-serializables.
    """
    # Normalizar: conservar claves incluso si None (para consistencia)
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()

class InMemoryCollection:
    """Colección simple en memoria para pruebas (find_one / insert_one)."""
    def __init__(self):
        self._store = {}

    def find_one(self, query: Dict[str, Any]):
        if not query:
            return None
        k, v = next(iter(query.items()))
        return self._store.get(v)

    def insert_one(self, doc: Dict[str, Any]):
        # suponer que la clave primaria ya está en doc con nombre pk
        pk_candidates = [k for k in doc.keys() if k.endswith("_key")]
        if not pk_candidates:
            pk = str(len(self._store) + 1)
        else:
            pk = doc[pk_candidates[0]]
        if pk in self._store:
            raise DuplicateKeyError("duplicate key") if pymongo else Exception("duplicate")
        self._store[pk] = doc
        return {"inserted_id": pk}
    
def get_or_create(collection: Optional[Any], values: Dict[str, Any], pk_name: str) -> str:
    """
    Busca en la colección por pk_name; si no existe, inserta doc con pk_name = surrogate_key(values).
    - collection puede ser una pymongo.collection.Collection o InMemoryCollection (o None -> in-memory).
    - Retorna la surrogate key (siempre).
    """
    key = surrogate_key(values)
    coll = collection or InMemoryCollection()

    # Búsqueda por la pk
    existing = None
    try:
        existing = coll.find_one({pk_name: key})
    except Exception:
        # colección no soporta find_one -> ignorar y proceder a insertar
        existing = None

    if existing:
        return key

    # preparar documento para insertar
    doc = values.copy()
    doc[pk_name] = key

    # intentar inserción (si ocurre duplicate, devolvemos key)
    try:
        coll.insert_one(doc)
    except Exception as e:
        # si la excepción es por duplicado, devolver key; si no, levantar
        if (pymongo and isinstance(e, DuplicateKeyError)) or "duplicate" in str(e).lower():
            return key
        raise
    return key
def format_age(age_str: Optional[str]) -> Optional[float]:
    """
    Convierte un age string DICOM como '061Y', '018M', '002W', '010D' en años (float).
    - Y => años enteros
    - M => meses / 12
    - W => semanas / 52
    - D => días / 365
    Devuelve None si la entrada es inválida o faltante.
    """
    if not age_str or not isinstance(age_str, str):
        return None
    s = age_str.strip().upper()
    if len(s) < 2:
        return None
    unit = s[-1]
    try:
        val = int(s[:-1])
    except Exception:
        return None
    if unit == "Y":
        return float(val)
    if unit == "M":
        return round(val / 12.0, 4)
    if unit == "W":
        return round(val / 52.0, 4)
    if unit == "D":
        return round(val / 365.0, 4)
    return None

def dicom_to_jpeg(input_path: str, output_dir: str, size: Optional[tuple] = None) -> str:
    """
    Convierte un DICOM a JPEG normalizando la intensidad y redimensionando opcionalmente.
    - input_path: ruta al .dcm
    - output_dir: carpeta de salida (se crea si no existe)
    - size: tupla (width, height) o None para conservar tamaño
    Retorna la ruta del archivo JPEG generado.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    ds = pydicom.dcmread(input_path)
    arr = ds.pixel_array.astype(np.float32)

    # Normalizar a 0-255
    amin, amax = np.min(arr), np.max(arr)
    if amax > amin:
        norm = (arr - amin) / (amax - amin)
    else:
        norm = np.zeros_like(arr)
    img8 = (norm * 255.0).astype(np.uint8)

    # Pillow Image
    if img8.ndim == 2:
        pil = Image.fromarray(img8, mode="L")
    elif img8.shape[2] == 3:
        pil = Image.fromarray(img8, mode="RGB")
    else:
        # fallback a escala de grises usando la primera banda
        pil = Image.fromarray(img8[..., 0], mode="L")

    if size:
        pil = pil.resize(size, resample=Image.LANCZOS)

    base = os.path.splitext(os.path.basename(input_path))[0] + ".jpg"
    out_path = os.path.join(output_dir, base)
    pil.save(out_path, format="JPEG", quality=90)
    return out_path

class DicomImageETL:
    """
    Extrae la dimensión IMAGE desde archivos DICOM en una carpeta.
    La DataFrame resultante incluye:
      - image_id: SOPInstanceUID o MD5 del archivo
      - path, file
      - rows (0028,0010)
      - columns (0028,0011)
      - pixel_spacing_x, pixel_spacing_y (0028,0030)
      - slice_thickness (0018,0050)
      - photometric_interp (0028,0004)
      - sop_instance_uid
      - surrogate_key: clave determinista para la dimensión IMAGE
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
        sop = getattr(ds, 'SOPInstanceUID', None)
        if sop:
            return str(sop)
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    def extract_metadata(self, stop_before_pixels=True, persist_collection: Optional[Any] = None, pk_name: str = "image_key"):
        """
        Extrae metadatos de cada DICOM y genera surrogate_key por fila.
        - stop_before_pixels: si True evita leer PixelData (más rápido).
        - persist_collection: si se pasa una colección (MongoDB o InMemoryCollection), se hará get_or_create por cada fila.
        - pk_name: nombre de la columna PK/clave surrogate en la colección.
        Retorna el DataFrame con las filas extraídas.
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

            r = getattr(ds, 'Rows', None)
            c = getattr(ds, 'Columns', None)
            pixel_spacing = getattr(ds, 'PixelSpacing', None)
            ps_x = ps_y = None
            if pixel_spacing:
                try:
                    ps_y = float(pixel_spacing[0])
                    ps_x = float(pixel_spacing[1])
                except Exception:
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

            row = {
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
            }

            # Definir los campos que determinan unicidad en la dimensión IMAGE
            surrogate_input = {
                'rows': row['rows'],
                'columns': row['columns'],
                'pixel_spacing_x': row['pixel_spacing_x'],
                'pixel_spacing_y': row['pixel_spacing_y'],
                'slice_thickness': row['slice_thickness'],
                'photometric_interp': row['photometric_interp']
            }
            row['surrogate_key'] = surrogate_key(surrogate_input)

            # Persistir en colección si se suministra (get_or_create)
            if persist_collection is not None:
                try:
                    get_or_create(persist_collection, surrogate_input, pk_name)
                except Exception as e:
                    print(f"Warning: persist failed for {fp}: {e}")

            rows.append(row)

        self.df_images = pd.DataFrame(rows)
        return self.df_images

    def save_csv(self, out_path):
        if self.df_images.empty:
            raise RuntimeError("No image metadata to save. Run extract_metadata() first.")
        self.df_images.to_csv(out_path, index=False)
      
if __name__ == '__main__':
    etl = DicomImageETL(DATA_PATH)
    etl.discover_files()
    df = etl.extract_metadata()
    print(df.head())
    # opcional: guardar
    etl.save_csv(os.path.join(DATA_PATH, 'image_dimension_test_1.csv'))

