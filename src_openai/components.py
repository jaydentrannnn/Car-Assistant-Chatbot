from typing import List
from haystack import component
import sqlite3
import pandas as pd



@component
class SQLQuery:
    def __init__(self, db_path: str):
        """
        Initializes the SQLQuery component with the path to the database.
        The connection is established in the run method.
        """
        self.db_path = db_path
        self.disallowed_keywords = {'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER'}

    @component.output_types(results=List[str], queries=List[str])
    def run(self, queries: List[str]) -> dict[str, any]:
        """
        Executes a list of SQL query strings.
        A new database connection is created for each run to ensure data freshness.
        """
        print("Running SQL Query...")
        results = []
        executed_queries = []
        queries = [queries[0].text.removeprefix('GENERATE_SQL').lstrip(':').strip()]


        # Establish the connection inside the run method
        try:
            with sqlite3.connect(self.db_path) as connection:
                for query_block in queries:

                    cleaned_block = query_block.replace("```sql", "").replace("```", "").strip()
                    individual_queries = [q.strip() for q in cleaned_block.split(';') if q.strip()]

                    for query in individual_queries:
                        if any(keyword in query.upper().split() for keyword in self.disallowed_keywords):
                            print(f"Skipping disallowed query: {query}")
                            continue

                        executed_queries.append(query)
                        try:
                            result_df = pd.read_sql_query(query, connection)
                            if not result_df.empty:
                                results.append(result_df.to_markdown(index=False))
                        except Exception as e:
                            print(f"Error executing query: '{query}'\nError: {e}")
                            results.append("")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            # If the connection fails, return empty results.
            return {"results": ['no_matching_result_found'], "queries": executed_queries}


        if len(results) == 0:
            results = ["No_matching_result_found"]

        return {"results": results, "queries": executed_queries}
