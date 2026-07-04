import sqlite3
import os
import sys
from datetime import datetime, timezone

def main():
    # Determine the database path
    db_path = os.getenv("DB_PATH", "backend/data/monitor.db")
    
    # Check if the database path exists relative to where the script is run
    if not os.path.exists(db_path):
        # Fallback to local data folder if running from backend folder
        if os.path.exists("data/monitor.db"):
            db_path = "data/monitor.db"
        else:
            print(f"Error: Database file not found at '{db_path}'.")
            print("Please run this script from the project root directory or set the DB_PATH environment variable.")
            sys.exit(1)
            
    print(f"Connecting to SQLite database at: {os.path.abspath(db_path)}")
    print("Datetimes ending with '_at' are automatically converted to your local timezone.\n")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("The database is empty (no tables found).")
            return
            
        print(f"Found tables: {', '.join(tables)}")
        
        # Query and display each table
        for table in tables:
            print(f"\n==================================================")
            print(f" TABLE: {table}")
            print(f"==================================================")
            
            # Get table schema/column names
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Get all rows
            cursor.execute(f"SELECT * FROM {table};")
            rows = cursor.fetchall()
            
            if not rows:
                print(" (No rows found in this table)")
                continue
            
            # Pre-format rows to handle timezone conversions
            formatted_rows = []
            for row in rows:
                formatted_row = []
                for i, val in enumerate(row):
                    val_str = str(val) if val is not None else "None"
                    if columns[i].endswith("_at") and val:
                        try:
                            # SQLite stores datetime as 'YYYY-MM-DD HH:MM:SS.ffffff' in UTC
                            dt = datetime.fromisoformat(val_str)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            # Convert to local system timezone
                            local_dt = dt.astimezone()
                            val_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
                        except Exception:
                            pass
                    formatted_row.append(val_str)
                formatted_rows.append(formatted_row)
                
            # Calculate column widths for nice tabular formatting
            col_widths = [len(col) for col in columns]
            for f_row in formatted_rows:
                for i, val in enumerate(f_row):
                    col_widths[i] = max(col_widths[i], len(val))
            
            # Print header
            header_str = " | ".join(f"{col.upper().ljust(col_widths[i])}" for i, col in enumerate(columns))
            print(header_str)
            print("-" * len(header_str))
            
            # Print rows
            for f_row in formatted_rows:
                row_str = " | ".join(f"{val.ljust(col_widths[i])}" for i, val in enumerate(f_row))
                print(row_str)
                
            print(f"Total rows: {len(rows)}")
            
        conn.close()
    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    main()
