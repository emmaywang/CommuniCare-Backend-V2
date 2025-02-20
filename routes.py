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

# reminders

# Get all reminders of user by username. 
# When authorization is integrated maybe we require User as parameter instead.
@app.route('/reminder/<username>', methods=['GET'])
def get_reminders_by_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE user_id = " + user_id)
    if not cursor.fetchall():
        return jsonify({'message': 'User not found'}), 404
    cursor.execute("SELECT clinic, program, time, subject FROM Appointments WHERE user_id = ?", (user_id,))
    reminders = [
        {"clinic_id": row[0], "program": row[1], "time": row[2], "subject": row[3]}
        for row in cursor.fetchall()
    ]
    cursor.close()
    conn.close()
    return jsonify(reminders), 200

# helper for getting one reminder by clinic, user and program.
@app.route('/reminder/<user_id>/<clinic_id>', methods=['GET'])
def get_reminder_by_clinic_user(user_id: int, clinic_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM Users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        return jsonify({'message': 'User not found'}), 404
    reminder = get_reminder_helper(cursor, user_id, clinic_id)
    if not reminder:
        return jsonify({'message': 'Appointment not found.'}), 404
    return jsonify(reminder), 201
    
def get_reminder_helper(cursor, user_id: int, clinic_id: int):
    cursor.execute(
        "SELECT clinic_id, program, time, subject FROM Appointments "
        "WHERE user_id = ? AND clinic_id = ?", 
        (user_id, clinic_id)
    )
    row = cursor.fetchone()
    if not row:
        return None
    reminder = {
        "clinic_id": row.clinic_id, "program": row.program, "time": row.time, "subject": row.subject
    }
    return reminder

@app.route('/reminder/<user_id>/<clinic_id>', methods=['PUT'])
def update_reminder_by_clinic(user_id: int, clinic_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
    if not cursor.fetchall():
        return jsonify({'message': 'User not found'}), 404
    newInfo = request.get_json()
    if 'program' not in newInfo or 'time' not in newInfo or 'subject' not in newInfo:
        return jsonify({"message": "incomplete information in request"}), 400
    cursor.execute("UPDATE Appointments SET program = ?, time = ?, subject = ? " +
                   "WHERE user_id = ? AND clinic_id = ?",
                   (newInfo['program'], newInfo['time'], newInfo['subject'], user_id, clinic_id))
    conn.commit()
    
    reminder = get_reminder_helper(cursor, user_id, clinic_id)
    if not reminder:
        return jsonify({'message': 'Appointment failed to update'}), 500
    return jsonify(reminder), 201

@app.route('/reminder/<user_id>', methods=['POST'])
def create_reminder_by_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
    if not cursor.fetchall():
        return jsonify({'message': 'User not found'}), 404
    newInfo = request.get_json()
    if not all(key in newInfo for key in ['clinic_name', 'program', 'time', 'subject']):
        return jsonify({"message": "incomplete information in request"}), 400
    cursor.execute("SELECT clinic_id FROM Clinics WHERE clinic_name = ?", (newInfo['clinic_name'],))
    clinicId = cursor.fetchone()
    if not clinicId:
        return jsonify({'message': 'Clinic of create reminder request not found'}), 404
    cursor.execute("INSERT INTO Appointments (user_id, clinic_id, program, time, subject) VALUES (?,?,?,?,?)",
                   (user_id, clinicId, newInfo['program'], newInfo['time'], newInfo['subject']))
    conn.commit()
    
    reminder = get_reminder_helper(cursor, user_id, clinicId)
    if not reminder:
        return jsonify({'message': 'Appointment failed to update'}), 500
    return jsonify(reminder), 201

@app.route('/reminder/<user_id>', methods=['DELETE'])
def delete_reminder_by_user_clinic(user_id: int, clinic_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
    if not cursor.fetchall():
        return jsonify({'message': 'User not found'}), 404
    reminder = get_reminder_helper(cursor, user_id, clinic_id)
    if not reminder:
        return jsonify({'message': 'Appointment not found.'}), 404
    cursor.execute("DELETE FROM Appointments WHERE user_id = ? AND clinic_id = ?", 
        (user_id, clinic_id))
    reminder = get_reminder_helper(cursor, user_id, clinic_id)
    if not reminder:
        return jsonify({'message': 'Appointment deleted.'}), 201
    else:
        return jsonify({'message': 'Appointment failed to delete.'}), 500

if __name__ == '__main__':
    app.run(debug=True)
