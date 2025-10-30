import pymongo
from pymongo.operations import ReplaceOne

class MongoLoader:
    """
    Handles the Loading logic for the ETL pipeline into MongoDB.
    """
    
    def __init__(self, connection_string, db_name):
        """
        Initializes the loader by connecting to the MongoDB cluster.
        """
        try:
            self.client = pymongo.MongoClient(connection_string)
            self.db = self.client[db_name]
            self.client.server_info() # Test connection
            print(f"MongoDB connection successful. Connected to database '{db_name}'.")
        except Exception as e:
            print(f"ERROR: Could not connect to MongoDB. Check connection string/network access. Error: {e}")
            raise
            
    # --- MODIFIED FUNCTION FOR BATCH LOADING DIMENSIONS ---
    def bulk_upsert_dimension(self, collection_name, data_list, pk_name):
        """
        Performs a bulk "upsert" (update or insert) for dimension data.
        This version keeps the original pk_name (e.g., 'patient_id')
        and relies on a unique index on that field.
        """
        if not data_list:
            print(f"No data to load for {collection_name}.")
            return

        collection = self.db[collection_name]
        operations = []

        for doc in data_list:
            # Get the surrogate key value (e.g., the hash)
            pk_value = doc[pk_name] 
            
            # --- CAMBIO CLAVE AQUÍ ---
            # Ya no renombramos el campo a '_id'.
            # Le decimos a ReplaceOne que busque un documento donde 'patient_id' == pk_value
            # Si lo encuentra, lo reemplaza.
            # Si no (upsert=True), inserta este nuevo documento.
            # MongoDB creará su propio campo '_id' automáticamente.
            op = ReplaceOne(
                { pk_name: pk_value }, # El FILTRO para encontrar el documento
                doc,                   # El documento de REEMPLAZO (con 'patient_id' intacto)
                upsert=True
            )
            operations.append(op)

        try:
            print(f"[L] Loading {len(operations)} records into '{collection_name}' (bulk upsert on '{pk_name}')...")
            result = collection.bulk_write(operations)
            print(f"[L] Bulk load complete for '{collection_name}': {result.upserted_count} inserted, {result.modified_count} updated.")
        except Exception as e:
            print(f"ERROR: Bulk upsert failed for {collection_name}. Error: {e}")
            
    # --- NO CHANGES TO THIS FUNCTION ---
    def bulk_insert_facts(self, collection_name, data_list):
        """
        Performs a simple bulk insert for fact data.
        Facts are just inserted, not updated.
        """
        if not data_list:
            print(f"No fact data to load for {collection_name}.")
            return
            
        collection = self.db[collection_name]
        try:
            print(f"[L] Loading {len(data_list)} records into '{collection_name}' (bulk insert)...")
            collection.insert_many(data_list)
            print(f"[L] Bulk insert complete for '{collection_name}'.")
        except Exception as e:
            print(f"ERROR: Bulk insert failed for {collection_name}. Error: {e}")

    # --- (Las funciones originales de abajo ya no se usan en el main.py) ---
    
    def get_or_create_dimension(self, collection_name, doc_values, pk_name):
        """ Implements the 'get_or_create' logic (one doc at a time). """
        collection = self.db[collection_name]
        surrogate_key = doc_values[pk_name]
        # This implementation is not batch-optimal
        existing_doc = collection.find_one({pk_name: surrogate_key})
        
        if existing_doc:
            return surrogate_key
        else:
            try:
                collection.insert_one(doc_values)
                print(f"[L] Created new dimension record in '{collection_name}' with key: {surrogate_key}")
                return surrogate_key
            except Exception as e:
                print(f"ERROR inserting into {collection_name}: {e}")
                return None

    def load_fact(self, collection_name, doc_values):
        """ Loads a single fact document. """
        try:
            collection = self.db[collection_name]
            collection.insert_one(doc_values)
        except Exception as e:
            print(f"ERROR inserting into {collection_name}: {e}")

    # --- MODIFIED FUNCTION FOR INDEXES ---
    def create_indexes(self):
        """ 
        Creates indexes on the fact table FKs 
        and UNIQUE indexes on the dimension table surrogate keys.
        """
        print("Creating indexes on fact_study collection...")
        fact_collection = self.db['fact_study']
        fact_collection.create_index("patient_id")
        fact_collection.create_index("station_id")
        fact_collection.create_index("protocol_id")
        fact_collection.create_index("image_id")
        fact_collection.create_index("date_id")
        
        # --- CAMBIO CLAVE AQUÍ ---
        # Añadimos índices ÚNICOS a nuestras claves (patient_id, etc.)
        # para asegurar que no haya duplicados y que las búsquedas (upserts) sean rápidas.
        print("Creating UNIQUE indexes on dimension collections...")
        self.db['dim_patient'].create_index("patient_id", unique=True)
        self.db['dim_station'].create_index("station_id", unique=True)
        self.db['dim_protocol'].create_index("protocol_id", unique=True)
        self.db['dim_image'].create_index("image_id", unique=True)
        self.db['dim_date'].create_index("date_id", unique=True)

        print("Indexes created.")