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

@app.route('/bookmark-lists', methods=['POST'])
def create_bookmark_list():
    data = request.get_json()
    username = data.get('username')
    list_name = data.get('list_name')
    
    if not username or not list_name:
        return jsonify({"error": "Missing username or list_name"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO BookmarkLists (username, list_name)
            VALUES (?, ?)
        """, (username, list_name))
        conn.commit()
        return jsonify({"message": "Bookmark list created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/bookmark-lists/<int:list_id>/bookmarks', methods=['POST'])
def add_bookmark(list_id):
    data = request.get_json()
    resource_type = data.get('resource_type')
    resource_id = data.get('resource_id')
    note = data.get('note', '')
    
    if not resource_type or not resource_id:
        return jsonify({"error": "Missing resource_type or resource_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Bookmarks (list_id, resource_type, resource_id, note)
            VALUES (?, ?, ?, ?)
        """, (list_id, resource_type, resource_id, note))
        conn.commit()
        return jsonify({"message": "Bookmark added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/users/<username>/bookmark-lists', methods=['GET'])
def get_user_bookmark_lists(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get all lists for the user
        cursor.execute("""
            SELECT list_id, list_name, created_at
            FROM BookmarkLists
            WHERE username = ?
        """, (username,))
        lists = cursor.fetchall()
        bookmark_lists = []
        for l in lists:
            list_dict = {
                "list_id": l.list_id,
                "list_name": l.list_name,
                "created_at": l.created_at,
                "bookmarks": []
            }
            # Get bookmarks for each list
            cursor.execute("""
                SELECT bookmark_id, resource_type, resource_id, note, created_at
                FROM Bookmarks
                WHERE list_id = ?
            """, (l.list_id,))
            bookmarks = cursor.fetchall()
            list_dict["bookmarks"] = [
                {
                    "bookmark_id": b.bookmark_id,
                    "resource_type": b.resource_type,
                    "resource_id": b.resource_id,
                    "note": b.note,
                    "created_at": b.created_at
                }
                for b in bookmarks
            ]
            bookmark_lists.append(list_dict)
        return jsonify(bookmark_lists), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/bookmark-lists/<int:list_id>/bookmarks/<int:bookmark_id>', methods=['DELETE'])
def delete_bookmark(list_id, bookmark_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM Bookmarks
            WHERE bookmark_id = ? AND list_id = ?
        """, (bookmark_id, list_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Bookmark not found"}), 404
        conn.commit()
        return jsonify({"message": "Bookmark deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run(debug=True)
