# run pip install pyodbc

from flask import Flask, jsonify, request
import pyodbc
import json
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

# Azure SQL Database connection details
SERVER = "pending"
DATABASE = "pending"
USERNAME = "pending"
PASSWORD = "pending"
DRIVER = "{ODBC Driver 17 for SQL Server}"


def get_db_connection():
    conn = pyodbc.connect(
        f"DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}"
    )
    return conn


def failure_response(message, code=404):
    return json.dumps({"success": False, "error": message}), code


# example endpoint to fetch all programs
@app.route("/programs", methods=["GET"])
def get_programs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, services, website FROM Programs;")
    customers = [
        {"name": row.name, "services": row.services, "website": row.website}
        for row in cursor.fetchall()
    ]
    cursor.close()
    conn.close()
    return jsonify(customers)


@app.route("/api/programs", methods=["GET"])
def get_programs_id():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        id = request.args.get("id")
        cursor.execute("SELECT name, services, website FROM Programs WHERE id = ?;", id)
        data = cursor.fetchone()
        customers = {
            "name": data.name,
            "services": data.services,
            "website": data.website,
        }
        return jsonify(customers)
    except:
        return failure_response("An error occurred", 500)
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

            # Filter programs by distance
            filtered_programs = []
            for program in programs:
                program_lat, program_lon = map(
                    float, program.location.strip("()").split(",")
                )
                if (
                    calculate_distance(
                        user_latitude, user_longitude, program_lat, program_lon
                    )
                    <= radius
                ):
                    filtered_programs.append(program)
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
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/<string:username>", methods=["GET"])
def get_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
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
        return failure_response("User not found", 404)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/<string:username>", methods=["DELETE"])
def delete_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not user_check(cursor, username):
            return failure_response("User does not exists", 404)
        cursor.execute("DELETE FROM Users WHERE username = ?;", (username,))
        conn.commit()
        return jsonify({"success": True, "message": "User deleted"}), 200
    except:
        return failure_response("An error occurred", 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/users/insurance_plan/<string:username>", methods=["PUT"])
def update_user_insurance_plan(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
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


app.route("/api/users/current_health_conditions/<string:username>", methods=["PUT"])


def update_user_Current_health_conditions(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        data = request.get_json()
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


if __name__ == "__main__":
    app.run(debug=True)
