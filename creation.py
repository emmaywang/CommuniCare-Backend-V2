import pyodbc
import routes
#one-time scripts to create tables

# create the Users table
def create_users_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Users')
        BEGIN
            CREATE TABLE Users (
                username NVARCHAR(255) PRIMARY KEY,
                sex NVARCHAR(10) CHECK (sex IN ('Male', 'Female', 'Other')),
                primary_insurance_company NVARCHAR(255),
                primary_insurance_plan NVARCHAR(255),
                policy NVARCHAR(255),
                services NVARCHAR(MAX) CHECK (ISJSON(services) = 1),
                Age INT CHECK (Age >= 0),
                Past_medical_history NVARCHAR(MAX) CHECK (ISJSON(Past_medical_history) = 1),
                Current_health_conditions NVARCHAR(MAX) CHECK (ISJSON(Current_health_conditions) = 1),
                Premium BIT NOT NULL DEFAULT 0
            );
        END
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Users table created (if it didn't already exist).")

# create the Clinics table
def create_clinics_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Clinics')
        BEGIN
            CREATE TABLE Clinics (
                clinic_id INT PRIMARY KEY IDENTITY(1,1),
                clinic_name NVARCHAR(255) NOT NULL,
                address NVARCHAR(255),
                phone_number NVARCHAR(50),
                email NVARCHAR(255)
            );
        END
    """)

    conn.commit()
    cursor.close()
    conn.close()

def create_programs_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Programs')
        BEGIN
            CREATE TABLE Programs (
                id INT PRIMARY KEY IDENTITY(1,1),
                name NVARCHAR(255)
                languages NVARCHAR(MAX),
                website NVARCHAR(255),
                services NVARCHAR(MAX),
                paymentModel NVARCHAR(255),
                clinic NVARCHAR(255),
                location NVARCHAR(255),
                opening_hour NVARCHAR(50),
                closing_hour NVARCHAR(50),
                contact_information NVARCHAR(255),
                service_description NVARCHAR(MAX),
                FOREIGN KEY (clinic) REFERENCES Clinics(clinic_name)
            );
        END
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Programs table created (if it didn't already exist).")

    print("Clinics table created (if it didn't already exist).")
if __name__ == "__main__":
    create_users_table()
    create_clinics_table()
    create_programs_table()
