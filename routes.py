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

conn_str="Driver={ODBC Driver 18 for SQL Server};Server=tcp:communicare-connect.database.windows.net,1433;Database=HealthConnectDB;Uid=CloudSA2d1c726f;Pwd={communicare_123};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
def get_db_connection():
    # conn = pyodbc.connect(
    #     f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}'
    # )
    conn=pyodbc.connect(conn_str)
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
