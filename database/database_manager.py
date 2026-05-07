import sqlite3
from datetime import datetime, timedelta


class DatabaseManager:
    def __init__(self, db_path='risk_system.db'):
        self.db_path = db_path
        self.init_db()

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_conn()
        c = conn.cursor()

        # --- SCHEMA MIGRATION ---
        # Check if 'users' table has the new security columns. If not, rebuild.
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if c.fetchone():
            c.execute("PRAGMA table_info(users)")
            cols = [info[1] for info in c.fetchall()]
            if 'failed_login_attempts' not in cols or 'lockout_time' not in cols:
                print("Database schema outdated. Rebuilding 'users' table...")
                c.execute("DROP TABLE users")

        # --- CREATE TABLES ---
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT UNIQUE, 
            email TEXT UNIQUE,
            password TEXT, 
            role TEXT, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            failed_login_attempts INTEGER DEFAULT 0,
            lockout_time TIMESTAMP
        )''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS consent (user_id INTEGER PRIMARY KEY, accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        # LMS Data (15 Columns)
        c.execute('''CREATE TABLE IF NOT EXISTS lms_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, StudentID TEXT, StudentName TEXT, Course TEXT, 
            LoginCount REAL, QuizScore REAL, ForumPosts REAL, ContentViews REAL, IPAddress TEXT, 
            SessionDuration REAL, AssignmentSubmissionRate REAL, LateSubmissions INTEGER, 
            QuizParticipationRate REAL, EngagementVariance REAL, LastLogin TIMESTAMP, StudentEmail TEXT
        )''')

        # Predictions
        c.execute('''CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER, StudentID TEXT, RiskScore REAL, 
            Status TEXT, LoginCount REAL, QuizScore REAL, ForumPosts REAL, ContentViews REAL, 
            SessionDuration REAL, AssignmentSubmissionRate REAL, LateSubmissions REAL, 
            QuizParticipationRate REAL, EngagementVariance REAL, user_id INTEGER, 
            predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Actions
        c.execute(
            '''CREATE TABLE IF NOT EXISTS student_contacts (StudentID TEXT PRIMARY KEY, StudentName TEXT, StudentEmail TEXT, ParentEmail TEXT, ParentPhone TEXT, AdvisorEmail TEXT)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS meetings (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, advisor_name TEXT, date TEXT, time TEXT, venue TEXT, type TEXT, link TEXT, notes TEXT, user_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS tutoring (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, tutor_name TEXT, subject TEXT, schedule TEXT, user_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        # System
        c.execute(
            '''CREATE TABLE IF NOT EXISTS smtp_settings (user_id INTEGER PRIMARY KEY, gmail TEXT, app_password TEXT)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS automated_emails (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, student_id TEXT, recipient TEXT, subject TEXT, body TEXT, status TEXT, user_id INTEGER, sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS model_history (id INTEGER PRIMARY KEY AUTOINCREMENT, accuracy REAL, user_id INTEGER, trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS week_analysis (id INTEGER PRIMARY KEY AUTOINCREMENT, week_number INTEGER, total_students INTEGER, at_risk_count INTEGER, safe_count INTEGER, estimated_accuracy REAL, user_id INTEGER, analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.commit()
        conn.close()

    # Auth
    def add_user(self, username, email, password, role):
        try:
            conn = self.get_conn()
            conn.execute("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                         (username, email, password, role))
            conn.commit()
            return True, "User created"
        except sqlite3.IntegrityError as e:
            if "username" in str(e): return False, "Username already exists"
            if "email" in str(e): return False, "Email already registered"
            return False, "Registration failed"
        finally:
            conn.close()

    def get_user(self, username):
        conn = self.get_conn()
        r = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()
        conn.close()
        return dict(r) if r else None

    def update_login_attempt(self, user_id, success):
        conn = self.get_conn()
        if success:
            conn.execute("UPDATE users SET failed_login_attempts = 0, lockout_time = NULL WHERE id = ?", (user_id,))
        else:
            conn.execute("UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = ?", (user_id,))
            user = conn.execute("SELECT failed_login_attempts FROM users WHERE id = ?", (user_id,)).fetchone()
            if user and user['failed_login_attempts'] >= 5:
                lockout_time = datetime.now() + timedelta(minutes=15)
                conn.execute("UPDATE users SET lockout_time = ? WHERE id = ?", (lockout_time, user_id))
        conn.commit()
        conn.close()

    def check_consent(self, user_id):
        conn = self.get_conn()
        r = conn.execute("SELECT * FROM consent WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        return r is not None

    def save_consent(self, user_id):
        conn = self.get_conn()
        conn.execute("INSERT OR REPLACE INTO consent (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()

    # LMS - FIXED 15 PLACEHOLDERS
    def seed_lms_logs(self, df):
        conn = self.get_conn()
        conn.execute("DELETE FROM lms_logs")
        for _, r in df.iterrows():
            # Columns: 15. Placeholders: Must be 15.
            conn.execute(
                """INSERT INTO lms_logs (StudentID, StudentName, Course, LoginCount, QuizScore, ForumPosts, ContentViews, IPAddress, SessionDuration, AssignmentSubmissionRate, LateSubmissions, QuizParticipationRate, EngagementVariance, LastLogin, StudentEmail) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r.get('StudentID'), r.get('StudentName'), r.get('Course'), r.get('LoginCount'), r.get('QuizScore'),
                 r.get('ForumPosts'), r.get('ContentViews'), r.get('IPAddress'), r.get('SessionDuration'),
                 r.get('AssignmentSubmissionRate'), r.get('LateSubmissions'), r.get('QuizParticipationRate'),
                 r.get('EngagementVariance'), r.get('LastLogin'), r.get('StudentEmail')))
        conn.commit()
        conn.close()

    def get_lms_logs(self):
        conn = self.get_conn()
        rows = conn.execute("SELECT * FROM lms_logs").fetchall()
        conn.close()
        return [tuple(r) for r in rows]

    # Predictions
    def save_predictions(self, batch_id, df, user_id):
        conn = self.get_conn()
        conn.execute("DELETE FROM predictions WHERE user_id = ?", (user_id,))
        for _, r in df.iterrows():
            conn.execute(
                """INSERT INTO predictions (batch_id, StudentID, RiskScore, Status, LoginCount, QuizScore, ForumPosts, ContentViews, SessionDuration, AssignmentSubmissionRate, LateSubmissions, QuizParticipationRate, EngagementVariance, user_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                batch_id, r['StudentID'], r['RiskScore'], r['Status'], r['LoginCount'], r['QuizScore'], r['ForumPosts'],
                r['ContentViews'], r['SessionDuration'], r['AssignmentSubmissionRate'], r['LateSubmissions'],
                r['QuizParticipationRate'], r['EngagementVariance'], user_id))
        conn.commit()
        conn.close()

    def get_predictions(self, batch_id, user_id, sort_by_id=False):
        conn = self.get_conn()
        order = "ORDER BY StudentID ASC" if sort_by_id else "ORDER BY RiskScore DESC"
        rows = conn.execute(f"SELECT * FROM predictions WHERE user_id = ? {order}", (user_id,)).fetchall()
        conn.close()
        return [tuple(r) for r in rows]

    def get_student_detail(self, student_id, user_id):
        conn = self.get_conn()
        r = conn.execute("SELECT * FROM predictions WHERE StudentID = ? AND user_id = ?",
                         (student_id, user_id)).fetchone()
        conn.close()
        return tuple(r) if r else None

    def get_top_at_risk(self, batch_id, user_id, limit):
        conn = self.get_conn()
        rows = conn.execute("SELECT * FROM predictions WHERE user_id = ? ORDER BY RiskScore DESC LIMIT ?",
                            (user_id, limit)).fetchall()
        conn.close()
        return [tuple(r) for r in rows]

    # Contacts
    def get_student_contact(self, student_id):
        conn = self.get_conn()
        r = conn.execute("SELECT * FROM student_contacts WHERE StudentID = ?", (student_id,)).fetchone()
        conn.close()
        return tuple(r) if r else None

    # Actions
    def save_meeting(self, sid, name, date, time, venue, type, link, notes, user_id):
        conn = self.get_conn()
        cur = conn.execute(
            "INSERT INTO meetings (student_id, advisor_name, date, time, venue, type, link, notes, user_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, name, date, time, venue, type, link, notes, user_id))
        conn.commit();
        conn.close()
        return cur.lastrowid

    def get_meetings(self, user_id):
        conn = self.get_conn();
        rows = conn.execute("SELECT * FROM meetings WHERE user_id = ?", (user_id,)).fetchall();
        conn.close();
        return [tuple(r) for r in rows]

    def save_tutoring(self, sid, name, subject, schedule, user_id):
        conn = self.get_conn();
        cur = conn.execute(
            "INSERT INTO tutoring (student_id, tutor_name, subject, schedule, user_id) VALUES (?,?,?,?,?)",
            (sid, name, subject, schedule, user_id));
        conn.commit();
        conn.close();
        return cur.lastrowid

    def get_tutoring(self, user_id):
        conn = self.get_conn();
        rows = conn.execute("SELECT * FROM tutoring WHERE user_id = ?", (user_id,)).fetchall();
        conn.close();
        return [tuple(r) for r in rows]

    # System
    def save_smtp(self, user_id, gmail, app_password):
        conn = self.get_conn();
        conn.execute("INSERT OR REPLACE INTO smtp_settings (user_id, gmail, app_password) VALUES (?,?,?)",
                     (user_id, gmail, app_password));
        conn.commit();
        conn.close()

    def get_smtp(self, user_id):
        conn = self.get_conn();
        r = conn.execute("SELECT gmail, app_password FROM smtp_settings WHERE user_id = ?", (user_id,)).fetchone();
        conn.close();
        return (r['gmail'], r['app_password']) if r else (None, None)

    def log_automated_email(self, type, sid, recipient, subject, body, status, user_id):
        conn = self.get_conn();
        conn.execute(
            "INSERT INTO automated_emails (type, student_id, recipient, subject, body, status, user_id) VALUES (?,?,?,?,?,?,?)",
            (type, sid, recipient, subject, body, status, user_id));
        conn.commit();
        conn.close()

    def get_automated_emails(self, user_id):
        conn = self.get_conn();
        rows = conn.execute("SELECT * FROM automated_emails WHERE user_id = ? ORDER BY sent_at DESC",
                            (user_id,)).fetchall();
        conn.close();
        return [tuple(r) for r in rows]

    def get_notifications(self, user_id):
        conn = self.get_conn();
        count = conn.execute("SELECT COUNT(*) FROM automated_emails WHERE user_id = ?", (user_id,)).fetchone()[0];
        conn.close();
        return [count]

    def save_model_history(self, acc, user_id):
        conn = self.get_conn();
        conn.execute("INSERT INTO model_history (accuracy, user_id) VALUES (?,?)", (acc, user_id));
        conn.commit();
        conn.close()

    def get_model_history(self, user_id):
        conn = self.get_conn();
        rows = conn.execute(
            "SELECT trained_at, accuracy FROM model_history WHERE user_id = ? ORDER BY trained_at DESC LIMIT 10",
            (user_id,)).fetchall();
        conn.close();
        return [tuple(r) for r in rows]

    def save_week_analysis(self, week, total, at_risk, safe, acc, user_id):
        conn = self.get_conn();
        conn.execute(
            "INSERT INTO week_analysis (week_number, total_students, at_risk_count, safe_count, estimated_accuracy, user_id) VALUES (?,?,?,?,?,?)",
            (week, total, at_risk, safe, acc, user_id));
        conn.commit();
        conn.close()

    def get_week_analysis(self, user_id):
        conn = self.get_conn();
        rows = conn.execute(
            "SELECT week_number, total_students, at_risk_count, safe_count, estimated_accuracy, analysis_date FROM week_analysis WHERE user_id = ? ORDER BY week_number ASC",
            (user_id,)).fetchall();
        conn.close();
        return [tuple(r) for r in rows]