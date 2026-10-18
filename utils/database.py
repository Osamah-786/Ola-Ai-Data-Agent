
import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()


class DatabaseUtil:
    def __init__(self, db_config):
        self.db_config = db_config
        self.connection = None

        try:
            self.connection = psycopg2.connect(**db_config)
            print("Connected to PostgreSQL successfully.")

        except psycopg2.Error as e:
            print(f"Database connection failed: {e}")

    def schema_details(self, schema_name):
        if self.connection is None:
            return "Error: No database connection. Check credentials and database name."

        context = f"Database Schema: {schema_name}\n"
        cursor = None

        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """, (schema_name,))

            tables = cursor.fetchall()

            if not tables:
                return context + "No tables found in this schema.\n"

            for (table_name,) in tables:
                context += f"\nTable: {table_name}\n"

                cursor.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema_name, table_name))

                for column_name, data_type in cursor.fetchall():
                    context += (
                        f"  Column: {column_name}, "
                        f"Data Type: {data_type}\n"
                    )

                # Safely quote schema and table identifiers.
                query = sql.SQL("SELECT * FROM {}.{} LIMIT 5").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name)
                )
                cursor.execute(query)
                sample_data = cursor.fetchall()

                context += "  Sample Data:\n"
                for row in sample_data:
                    context += f"    {row}\n"

            return context

        except psycopg2.Error as e:
            self.connection.rollback()
            return f"Error fetching schema details: {e}"

        finally:
            if cursor is not None:
                cursor.close()

    def execute_sql(self, query):
        if self.connection is None:
            return "Error: No database connection."

        cursor = None

        try:
            cursor = self.connection.cursor()
            cursor.execute(query)

            if cursor.description is not None:
                result = cursor.fetchall()
            else:
                result = f"{cursor.rowcount} row(s) affected"

            self.connection.commit()
            return str(result)

        except psycopg2.Error as e:
            self.connection.rollback()
            return f"Error executing query: {e}"

        finally:
            if cursor is not None:
                cursor.close()

    def close(self):
        if self.connection is not None and not self.connection.closed:
            self.connection.close()
            print("PostgreSQL connection closed.")


if __name__ == "__main__":
    config = {
        "host": os.getenv("host", "localhost"),
        "port": int(os.getenv("port", "5432")),
        "user": os.getenv("user", "postgres"),
        "password": os.getenv("password"),
        "dbname": os.getenv("database", "ola-agentic-ai"),
    }

    if not config["password"]:
        raise ValueError("Set your PostgreSQL password in the .env file.")

    obj = DatabaseUtil(config)

    try:
        result = obj.schema_details("public")
        with open("test_schema_details.txt", "w", encoding="utf-8") as f:
            f.write(result)

        print(result)
        print("\nSchema details saved to test_schema_details.txt")

    finally:
        obj.close()
