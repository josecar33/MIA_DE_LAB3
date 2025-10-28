import pymongo

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
            
    # --- NEW FUNCTION FOR BATCH LOADING DIMENSIONS ---
    def bulk_upsert_dimension(self, collection_name, data_list, pk_name):
        """
        Performs a bulk "upsert" (update or insert) for dimension data.
        This is the batch-equivalent of 'get_or_create'.

        Args:
            collection_name (str): The name of the dimension collection.
            data_list (list[dict]): A list of dimension documents (from DataFrame.to_dict('records')).
            pk_name (str): The name of the surrogate key field (e.g., 'patient_id').
        """
        if not data_list:
            print(f"No data to load for {collection_name}.")
            return

        collection = self.db[collection_name]
        operations = []

        for doc in data_list:
            # Copy doc to avoid modifying original
            doc_to_insert = doc.copy()
            # Get the surrogate key value
            pk_value = doc_to_insert.pop(pk_name)
            # Set it as MongoDB's primary key
            doc_to_insert['_id'] = pk_value
            
            # Create an "upsert" operation:
            # - filter: {'_id': pk_value} (find a doc with this ID)
            # - replacement: doc_to_insert (this is the new data)
            # - upsert=True (if it doesn't exist, insert it)
            op = pymongo.ReplaceOne({'_id': pk_value}, doc_to_insert, upsert=True)
            operations.append(op)

        try:
            print(f"[L] Loading {len(operations)} records into '{collection_name}' (bulk upsert)...")
            result = collection.bulk_write(operations)
            print(f"[L] Bulk load complete for '{collection_name}': {result.upserted_count} inserted, {result.modified_count} updated.")
        except Exception as e:
            print(f"ERROR: Bulk upsert failed for {collection_name}. Error: {e}")
            
    # --- NEW FUNCTION FOR BATCH LOADING FACTS ---
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

    # --- Original functions (no longer used in batch mode, but good to keep) ---
    
    def get_or_create_dimension(self, collection_name, doc_values, pk_name):
        """ Implements the 'get_or_create' logic (one doc at a time). """
        collection = self.db[collection_name]
        surrogate_key = doc_values[pk_name]
        existing_doc = collection.find_one({"_id": surrogate_key})
        
        if existing_doc:
            return surrogate_key
        else:
            doc_to_insert = doc_values.copy()
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
        """ Loads a single fact document. """
        try:
            collection = self.db[collection_name]
            collection.insert_one(doc_values)
        except Exception as e:
            print(f"ERROR inserting into {collection_name}: {e}")

    def create_indexes(self):
        """ Creates indexes on the fact table FKs for faster queries. """
        print("Creating indexes on fact_study collection...")
        fact_collection = self.db['fact_study']
        fact_collection.create_index("patient_id")
        fact_collection.create_index("station_id")
        fact_collection.create_index("protocol_id")
        fact_collection.create_index("image_id")
        fact_collection.create_index("date_id")
        print("Indexes created.")