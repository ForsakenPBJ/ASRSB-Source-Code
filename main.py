import os
from flask import Flask, request, redirect, url_for, render_template, session
import sqlite3
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

UPLOAD_FOLDER = 'defects/'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the defects directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    warning = []  # To store any error messages

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            conn = sqlite3.connect("band_data.db")
            cursor = conn.cursor()

            # Query to get the user's username and hashed password from the database
            cursor.execute("SELECT name, password FROM UserData WHERE email = ?", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user[1], password):  # Compare hashed password with input
                session['name'] = user[0]  # Set session variable to indicate the user is logged in
                return redirect(url_for('main_page'))  # Redirect to the dashboard (/main)

            else:
                warning.append("Invalid email or password. Please try again.")

        except Exception as e:
            warning.append(f"An error occurred: {e}")
        
        finally:
            conn.close()

    return render_template('login_page.html', warning=warning)


@app.route("/registration", methods=["GET", "POST"])
def reg_page():
    warning = []
    
    if request.method == "POST":
        new_name = str(request.form["new_name"])
        email = str(request.form["email"])
        new_pw = str(request.form["new_password"])
        conf_pw = str(request.form["conf_password"])

        # Email domain validation
        email_domain = email.split("@")[1] if "@" in email else ""
        if email_domain != "students.edu.sg":
            warning.append("Invalid email address, use your ICON email!")

        # Password match validation
        if new_pw != conf_pw:
            warning.append("Passwords don't match, try again.")

        # Password length validation
        if len(new_pw) < 8 or len(new_pw) > 20:
            warning.append("Password length must be between 8 and 20 characters.")

        # Additional password security checks
        if not any(char.isupper() for char in new_pw):
            warning.append("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in new_pw):
            warning.append("Password must contain at least one lowercase letter.")
        if not any(char.isdigit() for char in new_pw):
            warning.append("Password must contain at least one digit.")
        if not any(char in "!@#$%^&*()_+-=[]{};':,.<>?/`~" for char in new_pw):
            warning.append("Password must contain at least one special character.")

        # Proceed with database operations only if no warnings
        if not warning:
            try:
                conn = sqlite3.connect("band_data.db")
                cursor = conn.cursor()

                # Fetching emails from the database
                cursor.execute("SELECT email FROM UserData")
                emails = [row[0] for row in cursor.fetchall()]  # Flatten list of tuples

                # Check if email already exists
                if email in emails:
                    warning.append("Email already exists in the database.")
                else:
                    # Hash the password before storing it
                    hashed_pw = generate_password_hash(new_pw)

                    # Insert new user data into the database
                    cursor.execute("""
                        INSERT INTO UserData (name, email, password)
                        VALUES (?, ?, ?)""", (new_name, email, hashed_pw))

                    # Commit the transaction
                    conn.commit()

                    # Redirect to main
                    return redirect(url_for('main_page'))

            except Exception as e:
                warning.append(f"An error occurred: {e}")

            finally:
                conn.close()

    return render_template("registration.html", warning=warning)

@app.route("/main", methods=['GET', 'POST'])
def main_page():
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    user_name = session['name']

    if request.method == 'POST':
        action = request.form.get('action')

        # Handle different actions
        if action == 'loan_form':
            return redirect(url_for('loan_form'))
        elif action == 'ret_instr':
            return redirect(url_for('ret_instr'))
        elif action == 'rep_defct':
            return redirect(url_for('rep_defct'))
        elif action == 'abs_appl':
            return redirect(url_for('abs_appl'))
        elif action == 'atd_check':
            return redirect(url_for('atd_check'))
        elif action == 'sched':
            return redirect(url_for('sched'))
        elif action == 'logout':
            # Clear the session to log out the user
            session.clear()
            return redirect(url_for('login_page'))

    # Render the dashboard page
    return render_template('index.html', user_name=user_name)  # Use your dashboard template here


@app.route("/instrument/loan_form", methods=["GET", "POST"])
def loan_form():
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    user_name = session['name']
    avail_instr = []
    success = False
    current_date = datetime.now().date()
    
    if request.method == "POST":
        instrument = request.form.get('instrument')
        serial_num = request.form.get('serial_num')

        if instrument:
            try:
                conn = sqlite3.connect("band_data.db")
                cursor = conn.cursor()

                cursor.execute(
                    """SELECT ModelType.assetid
                    FROM ModelType
                    INNER JOIN InstrumentType
                    ON ModelType.specInst = InstrumentType.specInst
                    WHERE ModelType.loaned = 'no'
                    AND InstrumentType.Instr = ?""", (instrument,)
                )

                avail_instr = [row[0] for row in cursor.fetchall()]

            except Exception as e:
                print(f"An error occurred: {e}")
                
            finally:
                conn.close()

        elif serial_num:
            # File closes after with block
            with open("loan_requests.txt", "a") as file:
                file.write(f"{user_name} requested {serial_num} on {current_date}")
            success = True


    return render_template("loan_form.html", avail_instr=avail_instr, success=success)


@app.route("/instrument/return_instrument", methods=["GET", "POST"])
def ret_instr():
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    loaned_instr = []
    success = False
    user_name = session['name']
    current_date = datetime.now().date()

    try:
        conn = sqlite3.connect("band_data.db")
        cursor = conn.cursor()

        # Query to get the user's username and hashed password from the database
        cursor.execute(
            """SELECT LoaningData.assetid, ModelType.model
            FROM LoaningData
            INNER JOIN ModelType
            ON LoaningData.assetid = ModelType.assetid
            WHERE LoaningData.returnDate IS NULL""")
        
        loaned_instr = cursor.fetchone()
        
    finally:
        conn.close()

    if request.method == 'POST':
        # Handle form submission
        action = request.form.get('action')
        if action == 'conf_save':
            # Log the return request with the current date
            with open("return_requests.txt", "a") as file:
                file.write(f"{user_name} requested return for {loaned_instr[0]}, {loaned_instr[1]} on {current_date}\n")
            success = True
        
    return render_template("ret_instr.html", loaned_instr=loaned_instr, success=success)

@app.route("/instrument/report_defect", methods=["GET", "POST"])
def rep_defct():
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    serial_nums = []
    message = ""
    
    try:
        conn = sqlite3.connect("band_data.db")
        cursor = conn.cursor()

        cursor.execute(
            """SELECT assetid
            FROM ModelType
            ORDER BY assetid ASC"""
            )
        serial_nums = [row[0] for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        conn.close()

    if request.method == "POST":
        serial_num = request.form.get("serial_num")
        defect_description = request.form.get("defect_description")
        file = request.files.get("fileUpload")

        if file and allowed_file(file.filename):
            filename = file.filename
            # Save the file to the defects directory
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            message = "File successfully uploaded and report sent!"

            # File closes after with block
            with open("defect_reports.txt", "a") as file:
                file.write(f"{serial_num}: {defect_description}")

        else:
            message = "Invalid file type or no file selected. Please upload a .jpg or .png file."

    
    return render_template("rep_defct.html", serial_nums=serial_nums, message=message)

@app.route("/attendance/absentee_form", methods=["GET", "POST"])
def abs_appl():    
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    user_name = session['name']
    success = False

    if request.method == "POST":
        absence_date = request.form.get("absence_date")
        reason = request.form.get("reason")

        # File closes after with block
        with open("absentee_requests.txt", "a") as file:
            file.write(f"{user_name} requests absence on {absence_date} due to {reason}")
        success = True
    
    return render_template("abs_appl.html", success=success)

@app.route("/attendance/attendance_check")
def atd_check():    
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    name = session['name']

    user_attendance = []
    try:
        conn = sqlite3.connect("band_data.db")
        cursor = conn.cursor()

        cursor.execute(
            """SELECT Event.eventName, Event.eventDate, Attendance.status, Attendance.remarks
            FROM Attendance
            INNER JOIN UserData
            ON Attendance.userid = UserData.userid
            INNER JOIN Event
            ON Attendance.eventid = Event.eventid
            WHERE UserData.name = ?
            ORDER BY Event.eventDate DESC
            LIMIT 12""", (name,)
            )
        user_attendance = cursor.fetchall()
        
    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        conn.close()
    
    return render_template("atd_check.html", user_attendance=user_attendance)

@app.route("/attendance/schedule")
def sched():
    # Check if the user is logged in
    if 'name' not in session:
        return redirect(url_for('login_page'))  # Redirect to login if not logged in

    events = []
    try:
        conn = sqlite3.connect("band_data.db")
        cursor = conn.cursor()

        cursor.execute(
            """SELECT eventName, eventDate
            FROM Event
            WHERE eventid NOT IN (SELECT eventid FROM Attendance)
            ORDER BY eventDate ASC"""
            )
        events = cursor.fetchall()
        
    except Exception as e:
        return f"An error occurred: {e}"
    
    finally:
        conn.close()

    return render_template("sched.html", events=events)
    
    
@app.route("/")
@app.route("/instrument")
@app.route("/attendance")
def main():
    return redirect("/main")

@app.route('/logout')
def logout():
    session.pop('name', None)
    return redirect(url_for('login_page'))



if __name__ == "__main__":
    app.run(debug=True, port=42069)
