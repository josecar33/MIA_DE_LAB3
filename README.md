# DICOM Medical Images ETL Pipeline

This project implements an ETL (Extract, Transform, Load) pipeline for DICOM medical images, converting them to JPEG format and storing metadata in MongoDB using a star schema design.

## Prerequisites

- Python 3.8+
- MongoDB installed and running locally
- Virtual environment (recommended)

## Installation



1. Activate the virtual environment:

```bash
# Windows
.\venv\Scripts\activate

# Linux/MacOS
source venv/bin/activate
```

Project Structure

Lab3/
│
├── data/
│   ├── dicom_dir/        # Place your .dcm files here
│   ├── jpeg_output/      # Generated JPEG images
│   └── processed_csv/    # Generated CSV files
│
├── src/
│   ├── main.py          # Main ETL pipeline script
│   ├── et.py            # Extract & Transform logic
│   ├── analizer.py      # Analizer output
│   └── loader.py        # MongoDB loader
│
├── requirements.txt
└── README.md

2. Configuration
Ensure MongoDB is running locally on default port (27017)
Place your DICOM (.dcm) files in the dicom_dir folder
Key configuration variables in main.py:

```bash
MONGO_CONNECTION_STRING = "mongodb://localhost:27017/"
DB_NAME = "images"
```

3. Running the Pipeline
Ensure your virtual environment is activated
Run the main script:

```bash
python src/main.py
```

The pipeline will:

    Process all DICOM files in dicom_dir
    Convert images to JPEG format in jpeg_output
    Generate CSV files in processed_csv
    Load data into MongoDB collections:
        dim_patient
        dim_station
        dim_protocol
        dim_image
        dim_date
        
        
Then run 

```bash
python src/analizer.py
```

this will made a analisys of teh output, remenber must to be run after the main.py