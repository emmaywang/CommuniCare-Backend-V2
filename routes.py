#run pip install pyodbc

from flask import Flask, jsonify, request
import pyodbc

app = Flask(__name__)

# Azure SQL Database connection details
SERVER = 'pending'
DATABASE = 'pending'
USERNAME = 'pending'
PASSWORD = 'pending'
DRIVER = '{ODBC Driver 17 for SQL Server}'


def get_db_connection():
    conn = pyodbc.connect(
        f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}'
    )
    return conn

# example endpoint to fetch all programs
@app.route('/programs', methods=['GET'])
def get_programs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, services, website FROM Programs")
    customers = [
        {"name": row.name, "services": row.services, "website": row.website}
        for row in cursor.fetchall()
    ]
    cursor.close()
    conn.close()
    return jsonify(customers)

if __name__ == '__main__':
    app.run(debug=True)
