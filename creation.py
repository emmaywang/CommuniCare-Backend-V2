import pyodbc
import routes

# one-time scripts to create tables


# create the Users table
def create_users_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
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
                Premium BIT NOT NULL DEFAULT 0,
                firebase_uid VARCHAR(36) UNIQUE NULL
            );
        END
    """
    )

    conn.commit()
    cursor.close()
    conn.close()
    print("Users table created (if it didn't already exist).")


# create the Clinics table
def create_clinics_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
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
    """
    )

    conn.commit()
    cursor.close()
    conn.close()


def create_programs_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Programs')
        BEGIN
            CREATE TABLE Programs (
                id INT PRIMARY KEY IDENTITY(1,1),
                name NVARCHAR(255),
                languages NVARCHAR(MAX),
                website NVARCHAR(255),
                services NVARCHAR(MAX),
                paymentModel NVARCHAR(255),
                clinic INT,
                location NVARCHAR(255),
                opening_hour NVARCHAR(50),
                closing_hour NVARCHAR(50),
                contact_information NVARCHAR(255),
                service_description NVARCHAR(MAX),
                FOREIGN KEY (clinic) REFERENCES Clinics(clinic_id)
            );
        END
    """
    )

    conn.commit()
    cursor.close()
    conn.close()
    print("Programs table created (if it didn't already exist).")

    print("Clinics table created (if it didn't already exist).")


def create_bookmarklists_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'BookmarkLists')
        BEGIN
            CREATE TABLE BookmarkLists (
                list_id INT PRIMARY KEY IDENTITY(1,1),
                username NVARCHAR(255) NOT NULL,
                list_name NVARCHAR(255) NOT NULL,
                created_at DATETIME DEFAULT GETDATE(),
                FOREIGN KEY (username) REFERENCES Users(username)
            );
        END   
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("BookmarkLists table created (if it didn't already exist).")

def create_bookmarks_table():
    conn = routes.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Bookmarks')
        BEGIN
            CREATE TABLE Bookmarks (
                bookmark_id INT PRIMARY KEY IDENTITY(1,1),
                list_id INT NOT NULL,
                resource_type NVARCHAR(50) NOT NULL,  -- e.g., 'Program', 'Clinic'
                resource_id INT NOT NULL,            -- ID of the resource in its table
                note NVARCHAR(MAX),                  -- optional note from the user
                created_at DATETIME DEFAULT GETDATE(),
                FOREIGN KEY (list_id) REFERENCES BookmarkLists(list_id)
            );
        END
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("Bookmarks table created (if it didn't already exist).")    


if __name__ == "__main__":
    create_users_table()
    create_clinics_table()
    create_programs_table()
