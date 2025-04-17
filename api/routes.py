# run pip install pyodbc
# run pip install authlib

from flask import Flask, jsonify, request
import requests
from authlib.integrations.flask_client import OAuth
from firebase_admin import auth
from firebase_conn import firebase_app
import pyodbc
import json
from math import radians, sin, cos, sqrt, atan2
from dotenv import load_dotenv
import os

# Change these values to the ones used to create the App Service.

app = Flask(__name__)


@app.route("/")
def home():
    return "Hello from CommuniCare!"


# Azure SQL Database connection details
# SERVER = "pending"
# DATABASE = "pending"
# USERNAME = "pending"
# PASSWORD = "pending"
# DRIVER = "{ODBC Driver 17 for SQL Server}"

load_dotenv()
conn_str = os.getenv("DATABASE_CONNECTION")


@app.route("/health-check")
def health_check():
    try:
        # Test DB connection with actual credentials
        with pyodbc.connect(conn_str) as conn:
            # Simple query verification
            conn.execute("SELECT 1;").fetchval()
        return "OK", 200
    except pyodbc.Error as e:
        app.logger.error(f"Database connection failed: {str(e)}")
        return f"Database Error: {str(e)}", 500
    except Exception as e:
        app.logger.error(f"Health check error: {str(e)}")
        return f"Application Error: {str(e)}", 500


def get_db_connection():

    # conn = pyodbc.connect(
    #     f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}'
    # )
    conn = pyodbc.connect(conn_str)
    return conn


def failure_response(message, code=404):
    return json.dumps({"success": False, "error": message}), code


# ---------AUTH------------
def authenticate_request():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    try:
        token = auth_header.split(" ")[1]  # Expecting "Bearer <token>"
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        return None


# @app.route("/api/protected", methods=["GET"])
def protected_route():
    user = authenticate_request()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify({"user": user}), 200


# @app.route("/api/username-check", methods=["GET"])
def username_check(username):
    cursor = get_db_connection()
    response = protected_route()
    status_code = response[1]
    if status_code != 200:
        return response  # that is, jsonify({"error": "Unauthorized"}), 401
    user = response["user"]
    user_id = user["uid"]
    cursor.execute("SELECT username FROM Users WHERE firebase_uid = ?;", (user_id,))
    found_username = (
        cursor.fetchone()
    )  # the username matching the firebase uid given in the token
    if found_username != username:
        return jsonify({"error": "Invalid permissions"}), 401

    return response  # that is, jsonify({"user":user})


@app.route("/api/verify-user", methods=["POST"])
def verify_firebase_token():
    try:
        data = request.get_json()
        token = data.get("token")

        # Verify Firebase ID token
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token["uid"]
        email = decoded_token.get("email")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists in Azure SQL database
        cursor.execute("SELECT * FROM Users WHERE firebase_uid = ?;", user_id)
        user = cursor.fetchone()

        if not user:
            # User is new – return response asking for additional info
            return jsonify({"new_user": True, "message": "Complete your profile"}), 200

        conn.close()
        return jsonify({"success": True, "userId": user_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 401


# ------------END AUTH------------------------------


# example endpoint to fetch all programs
@app.route("/programs", methods=["GET"])
def get_programs():
    try:
        # Original connection
        conn = pyodbc.connect(conn_str)  # Hardcoded or from variable
        cursor = conn.cursor()
        cursor.execute("SELECT name, services, website FROM Programs;")
        columns = [column[0] for column in cursor.description]

        # Convert rows to dictionaries properly
        programs = []
        for row in cursor.fetchall():
            programs.append(dict(zip(columns, row)))
        return jsonify(programs)
    except Exception as e:
        print("FULL ERROR TRACEBACK:", repr(e))
        return {"error": str(e), "type": type(e).__name__}, 500
    finally:
        cursor.close()
        conn.close()


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance


def user_check(cursor, username):
    cursor.execute("SELECT * FROM Users WHERE username = ?;", (username,))
    check = cursor.fetchall()
    if len(check) == 0:
        return False
    return True


@app.route("/api/programs/search", methods=["GET"])
def search_programs():
    args = request.args
    user_latitude = float(args.get("userLatitude"))
    user_longitude = float(args.get("userLongitude"))
    radius = float(args.get("radius"))
    languages = args.getlist("languages")
    primary_insurance_company = request.args.get("primary_insurance_company", None)
    primary_insurance_plan = request.args.get("primary_insurance_plan", None)
    services = request.args.getlist("services", None)
    username = args.get("username")
    account = args.get("Account")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Fetch user details if username is provided
            user_details = {}
            if account:
                username_check(username)

                cursor.execute("SELECT * FROM Users WHERE username = ?;", (username,))
                user_details = cursor.fetchone()
                if user_details:
                    if not primary_insurance_company:
                        primary_insurance_company = (
                            user_details.primary_insurance_company
                        )
                    if not primary_insurance_plan:
                        primary_insurance_plan = user_details.primary_insurance_plan
                    if not services:
                        services = json.loads(user_details.services)

            # Base query
            sql = """
            select * FROM Programs WHERE
            """
            params = []
            # Filter by languages
            sql += "EXISTS (select value FROM OPENJSON(languages) WHERE value IN ({0}))".format(
                ",".join(["?"] * len(languages))
            )
            params.extend(languages)

            # Filter by insurance if provided
            if primary_insurance_company and primary_insurance_plan:
                sql += " AND paymentModel LIKE ?"
                params.append(f"%{primary_insurance_company}%{primary_insurance_plan}%")
            else:
                return failure_response("No insurance provided and no user found", 400)

            # Filter by services if provided
            if services:
                sql += (
                    " AND EXISTS (select value FROM OPENJSON(services) WHERE value IN (%s))"
                    % ",".join(["?"] * len(services))
                )
                params.extend(services)
            else:
                return failure_response("No services provided and no user found", 400)

            cursor.execute(sql, params)
            programs = cursor.fetchall()
            if not programs:
                return jsonify({"message": "No programs that fit criteria."}), 200
            # Filter programs by distance
            filtered_programs = []
            google_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            program_lats_lons = ""
            program_lats_lons = "|".join([i.location.strip("()") for i in programs])
            google_params = {
                "destinations": program_lats_lons,
                "origins": user_latitude + "," + user_longitude,
                "key": "YOUR_API_KEY",
            }
            response = requests.get(google_url, params=google_params)
            if response.status_code != 200:
                return (
                    jsonify(
                        {
                            "error": "Failed to fetch response from Google distance calculator"
                        }
                    ),
                    response.status_code,
                )
            google_data = response.json()
            if "rows" not in google_data or not google_data["rows"]:
                return (
                    jsonify({"error": "Invalid response from Google distance API"}),
                    500,
                )
            lst = google_data["rows"][0]["elements"]
            for i in range(len(lst)):
                if lst[i]["distance"]["value"] <= radius:  # radius is in meters (?)
                    filtered_programs.append(programs[i])

            final_programs = []
            for program in filtered_programs:
                final_programs.append(
                    {
                        "id": program.id,
                        "name": program.name,
                        "services": program.services,
                        "website": program.website,
                        "paymentModel": program.paymentModel,
                        "clinic": program.clinic,
                        "location": program.location,
                        "Opening_hour": program.Opening_hour,
                        "Closing_hour": program.Closing_hour,
                        "Contact_information": program.Contact_information,
                        "service_description": program.service_description,
                    }
                )

            return jsonify(final_programs), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/<string:username>", methods=["GET"])
def get_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        username_check(username)
        cursor.execute("SELECT * FROM Users WHERE username = ?;", (username,))
        user = cursor.fetchone()
        if user:
            data = {
                "username": user.username,
                "sex": user.sex,
                "primary_insurance_company": user.primary_insurance_company,
                "primary_insurance_plan": user.primary_insurance_plan,
                "policy": user.policy,
                "services": json.loads(user.services),
                "age": user.Age,
                "past_medical_history": json.loads(user.Past_medical_history),
                "current_health_conditions": json.loads(user.Current_health_conditions),
                "premium": user.Premium,
            }
            return jsonify(data), 200
    except:
        return failure_response("User not found", 404)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/<string:username>", methods=["POST"])
def create_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        cursor.execute("SELECT * FROM Users WHERE username = ?;", (username,))
        check = cursor.fetchall()
        if len(check) > 0:
            return failure_response("User already exists", 400)
        cursor.execute(
            """
            INSERT INTO Users (username, sex, primary_insurance_company, primary_insurance_plan, policy, services, Age, Past_medical_history, Current_health_conditions, Premium)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                username,
                data.get("sex"),
                data.get("primary_insurance_company"),
                data.get("primary_insurance_plan"),
                data.get("policy"),
                json.dumps(data.get("services", [])),
                data.get("age"),
                json.dumps(data.get("past_medical_history", [])),
                json.dumps(data.get("current_health_conditions", [])),
                data.get("premium", 0),
            ),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User created", "body": data}), 201
    except:
        return failure_response("An error occurred", 500)


@app.route("/api/users/<string:username>", methods=["DELETE"])
def delete_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute("DELETE FROM Users WHERE username = ?;", (username,))
        conn.commit()
        return jsonify({"success": True, "message": "User deleted"}), 200
    except:
        return failure_response("An error occurred", 500)


@app.route("/api/users/insurance_plan/<string:username>", methods=["PUT"])
def update_user_insurance_plan(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET primary_insurance_plan = ?
            WHERE username = ?;
            """,
            (data.get("primary_insurance_plan"), username),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User insurance plan updated"}), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/insurance_company/<string:username>", methods=["PUT"])
def update_user_insurance_company(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET primary_insurance_company = ?
            WHERE username = ?;
            """,
            (data.get("primary_insurance_company"), username),
        )
        conn.commit()
        return (
            jsonify({"success": True, "message": "User insurance company updated"}),
            200,
        )
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/sex/<string:username>", methods=["PUT"])
def update_user_sex(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET sex = ?
            WHERE username = ?;
            """,
            (data.get("sex"), username),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User sex updated"}), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/services/<string:username>", methods=["PUT"])
def update_user_services(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute("SELECT services FROM Users WHERE username = ?;", (username,))
        services = cursor.fetchone()
        if services:
            services = json.loads(services.services)
            services.extend(data.get("addServices"))
            for service in data.get("removeServices"):
                if service in services:
                    services.remove(service)
        cursor.execute(
            """
            UPDATE Users
            SET services = ?
            WHERE username = ?;
            """,
            (json.dumps(services), username),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User services updated"}), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/age/<string:username>", methods=["PUT"])
def update_user_age(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET Age = ?
            WHERE username = ?;
            """,
            (data.get("age"), username),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User age updated"}), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/policy/<string:username>", methods=["PUT"])
def update_user_policy(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET policy = ?
            WHERE username = ?;
            """,
            (data.get("policy"), username),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User policy updated"}), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/past_medical_history/<string:username>", methods=["PUT"])
def update_user_past_medical_history(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET Past_medical_history = ?
            WHERE username = ?;
            """,
            (json.dumps(data.get("Past_medical_history")), username),
        )
        conn.commit()
        return (
            jsonify({"success": True, "message": "User Past_medical_history updated"}),
            200,
        )
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/current_health_conditions/<string:username>", methods=["PUT"])
def update_user_Current_health_conditions(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET Current_health_conditions = ?
            WHERE username = ?;
            """,
            (json.dumps(data.get("Current_health_conditions")), username),
        )
        conn.commit()
        return (
            jsonify(
                {"success": True, "message": "User Current_health_conditions updated"}
            ),
            200,
        )
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/premium/<string:username>", methods=["PUT"])
def update_user_premium(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
        username_check(username)
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute(
            """
            UPDATE Users
            SET Premium = ?
            WHERE username = ?;
            """,
            (data.get("premium"), username),
        )
        conn.commit()
        return jsonify({"success": True, "message": "User premium updated"}), 200
    except pyodbc.DataError:
        return failure_response("Invalid premium value", 400)
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


# ------BOOKMARKS---------


@app.route("/api/bookmark-lists", methods=["POST"])
def create_bookmark_list():
    data = request.get_json()
    username = data.get("username")
    list_name = data.get("list_name")

    if not username or not list_name:
        return jsonify({"error": "Missing username or list_name"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    username_check(username)
    try:
        cursor.execute(
            """
            INSERT INTO BookmarkLists (username, list_name)
            VALUES (?, ?);
        """,
            (username, list_name),
        )  # database automatically adds list_id and created_at
        conn.commit()
        return jsonify({"message": "Bookmark list created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/api/bookmark-lists/<int:list_id>/bookmarks", methods=["POST"])
def add_bookmark(list_id):
    data = request.get_json()
    resource_type = data.get("resource_type")
    resource_id = data.get("resource_id")
    note = data.get("note", "")
    protected_route()
    if not resource_type or not resource_id:
        return jsonify({"error": "Missing resource_type or resource_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO Bookmarks (list_id, resource_type, resource_id, note)
            VALUES (?, ?, ?, ?);
        """,
            (list_id, resource_type, resource_id, note),
        )  # database automatically adds list_id and created_at
        # list_id must already exist (so entry in BookmarkLists must be created first)
        conn.commit()
        return jsonify({"message": "Bookmark added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/<username>/bookmark-lists", methods=["GET"])
def get_user_bookmark_lists(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    username_check(username)
    try:
        # Get all lists for the user
        cursor.execute(
            """
            SELECT list_id, list_name, created_at
            FROM BookmarkLists
            WHERE username = ?;
        """,
            (username,),
        )
        lists = cursor.fetchall()
        bookmark_lists = []
        for l in lists:
            list_dict = {
                "list_id": l.list_id,
                "list_name": l.list_name,
                "created_at": l.created_at,
                "bookmarks": [],
            }
            # Get bookmarks for each list
            cursor.execute(
                """
                SELECT bookmark_id, resource_type, resource_id, note, created_at
                FROM Bookmarks
                WHERE list_id = ?;
            """,
                (l.list_id,),
            )
            bookmarks = cursor.fetchall()
            list_dict["bookmarks"] = [
                {
                    "bookmark_id": b.bookmark_id,
                    "resource_type": b.resource_type,
                    "resource_id": b.resource_id,
                    "note": b.note,
                    "created_at": b.created_at,
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


@app.route(
    "/api/bookmark-lists/<int:list_id>/bookmarks/<int:bookmark_id>", methods=["DELETE"]
)
def delete_bookmark(list_id, bookmark_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM Bookmarks
            WHERE bookmark_id = ? AND list_id = ?;
        """,
            (bookmark_id, list_id),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Bookmark not found"}), 404
        conn.commit()
        return jsonify({"message": "Bookmark deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# --------REMINDERS--------------

# # Get all reminders of user by username.
# # When authorization is integrated maybe we require User as parameter instead.
# @app.route('/reminder/<username>', methods=['GET'])
# def get_reminders_by_user(user_id: int):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM Users WHERE user_id = " + user_id)
#     if not cursor.fetchall():
#         return jsonify({'message': 'User not found'}), 404
#     cursor.execute("SELECT clinic, program, time, subject FROM Appointments WHERE user_id = ?", (user_id,))
#     reminders = [
#         {"clinic_id": row[0], "program": row[1], "time": row[2], "subject": row[3]}
#         for row in cursor.fetchall()
#     ]
#     cursor.close()
#     conn.close()
#     return jsonify(reminders), 200

# # helper for getting one reminder by clinic, user and program.
# @app.route('/reminder/<user_id>/<clinic_id>', methods=['GET'])
# def get_reminder_by_clinic_user(user_id: int, clinic_id: int):
#     conn = get_db_connection()
#     cursor = conn.cursor()

#     cursor.execute("SELECT 1 FROM Users WHERE user_id = ?", (user_id,))
#     if not cursor.fetchone():
#         return jsonify({'message': 'User not found'}), 404
#     reminder = get_reminder_helper(cursor, user_id, clinic_id)
#     if not reminder:
#         return jsonify({'message': 'Appointment not found.'}), 404
#     return jsonify(reminder), 201

# def get_reminder_helper(cursor, user_id: int, clinic_id: int):
#     cursor.execute(
#         "SELECT clinic_id, program, time, subject FROM Appointments "
#         "WHERE user_id = ? AND clinic_id = ?",
#         (user_id, clinic_id)
#     )
#     row = cursor.fetchone()
#     if not row:
#         return None
#     reminder = {
#         "clinic_id": row.clinic_id, "program": row.program, "time": row.time, "subject": row.subject
#     }
#     return reminder

# @app.route('/reminder/<user_id>/<clinic_id>', methods=['PUT'])
# def update_reminder_by_clinic(user_id: int, clinic_id: int):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
#     if not cursor.fetchall():
#         return jsonify({'message': 'User not found'}), 404
#     newInfo = request.get_json()
#     if 'program' not in newInfo or 'time' not in newInfo or 'subject' not in newInfo:
#         return jsonify({"message": "incomplete information in request"}), 400
#     cursor.execute("UPDATE Appointments SET program = ?, time = ?, subject = ? " +
#                    "WHERE user_id = ? AND clinic_id = ?",
#                    (newInfo['program'], newInfo['time'], newInfo['subject'], user_id, clinic_id))
#     conn.commit()

#     reminder = get_reminder_helper(cursor, user_id, clinic_id)
#     if not reminder:
#         return jsonify({'message': 'Appointment failed to update'}), 500
#     return jsonify(reminder), 201

# @app.route('/reminder/<user_id>', methods=['POST'])
# def create_reminder_by_user(user_id: int):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
#     if not cursor.fetchall():
#         return jsonify({'message': 'User not found'}), 404
#     newInfo = request.get_json()
#     if not all(key in newInfo for key in ['clinic_name', 'program', 'time', 'subject']):
#         return jsonify({"message": "incomplete information in request"}), 400
#     cursor.execute("SELECT clinic_id FROM Clinics WHERE clinic_name = ?", (newInfo['clinic_name'],))
#     clinicId = cursor.fetchone()
#     if not clinicId:
#         return jsonify({'message': 'Clinic of create reminder request not found'}), 404
#     cursor.execute("INSERT INTO Appointments (user_id, clinic_id, program, time, subject) VALUES (?,?,?,?,?)",
#                    (user_id, clinicId, newInfo['program'], newInfo['time'], newInfo['subject']))
#     conn.commit()

#     reminder = get_reminder_helper(cursor, user_id, clinicId)
#     if not reminder:
#         return jsonify({'message': 'Appointment failed to update'}), 500
#     return jsonify(reminder), 201

# @app.route('/reminder/<user_id>', methods=['DELETE'])
# def delete_reminder_by_user_clinic(user_id: int, clinic_id: int):
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
#     if not cursor.fetchall():
#         return jsonify({'message': 'User not found'}), 404
#     reminder = get_reminder_helper(cursor, user_id, clinic_id)
#     if not reminder:
#         return jsonify({'message': 'Appointment not found.'}), 404
#     cursor.execute("DELETE FROM Appointments WHERE user_id = ? AND clinic_id = ?",
#         (user_id, clinic_id))
#     reminder = get_reminder_helper(cursor, user_id, clinic_id)
#     if not reminder:
#         return jsonify({'message': 'Appointment deleted.'}), 201
#     else:
#         return jsonify({'message': 'Appointment failed to delete.'}), 500


# if __name__ == '__main__':
#     app.run(debug=True)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

# handler = app
