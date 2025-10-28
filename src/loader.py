import pymongo

class MongoLoader:
    """
    Handles the Loading logic for the ETL pipeline into MongoDB.
    """
    
    def __init__(self, connection_string, db_name):
        """
        Initializes the loader by connecting to the MongoDB cluster.
        
        Args:
            connection_string (str): The MongoDB connection string (e.g., from Atlas).
            db_name (str): The name of the database to use (e.g., 'dicom_db').
        """
        try:
            self.client = pymongo.MongoClient(connection_string)
            self.db = self.client[db_name]
            # Test connection
            self.client.server_info()
            print(f"MongoDB connection successful. Connected to database '{db_name}'.")
        except Exception as e:
            print(f"ERROR: Could not connect to MongoDB. Check connection string/network access. Error: {e}")
            raise
            
    def get_or_create_dimension(self, collection_name, doc_values, pk_name):
        """
        Implements the 'get_or_create' logic as requested in the PDF.
        It checks if a document with the given surrogate key exists.
        If not, it inserts one.
        
        This implementation uses the surrogate key (e.g., MD5 hash) as the 
        primary key ('_id') in MongoDB for high performance.

        Args:
            collection_name (str): The name of the dimension collection (e.g., 'dim_patient').
            doc_values (dict): The dictionary of values for the dimension.
            pk_name (str): The name of the surrogate key field in doc_values (e.g., 'patient_id').

        Returns:
            str: The surrogate key (the '_id' of the document).
        """
        
        # 1. Get the collection
        collection = self.db[collection_name]
        
        # 2. Get the surrogate key value (our MD5 hash)
        surrogate_key = doc_values[pk_name]
        
        # 3. Check if a document with this _id already exists
        # We use our hash as MongoDB's primary key `_id`
        existing_doc = collection.find_one({"_id": surrogate_key})
        
        if existing_doc:
            # 4. If it exists, do nothing. Just return the key.
            # print(f"Dimension doc {surrogate_key} already exists in {collection_name}.")
            return surrogate_key
        else:
            # 5. If it does not exist, insert it.
            
            # Create a new doc to insert.
            doc_to_insert = doc_values.copy()
            
            # We must rename our 'patient_id' field to '_id' 
            # to use it as MongoDB's primary key.
            del doc_to_insert[pk_name]
            doc_to_insert['_id'] = surrogate_key
            
            try:
                collection.insert_one(doc_to_insert)
                print(f"[L] Created new dimension record in '{collection_name}' with _id: {surrogate_key}")
                return surrogate_key
            except Exception as e:
                print(f"ERROR inserting into {collection_name}: {e}")
                return None

    def load_fact(self, collection_name, doc_values):
        """
        Loads a fact document directly into the specified collection.
        Facts are not de-duplicated; we just insert them.

        Args:
            collection_name (str): The name of the fact collection (e.g., 'fact_study').
            doc_values (dict): The fact record to insert.
        """
        try:
            collection = self.db[collection_name]
            collection.insert_one(doc_values)
            # print(f"Loaded fact record into {collection_name}.")
        except Exception as e:
            print(f"ERROR inserting into {collection_name}: {e}")

    def create_indexes(self):
        """
        (Optional but Recommended)
        Creates indexes on the foreign key (FK) fields in the fact table
        to speed up queries (joins).
        """
        print("Creating indexes on fact_study collection...")
        fact_collection = self.db['fact_study']
        fact_collection.create_index("patient_id")
        fact_collection.create_index("station_id")
        fact_collection.create_index("protocol_id")
        fact_collection.create_index("image_id")
        fact_collection.create_index("date_id")
        print("Indexes created.")
