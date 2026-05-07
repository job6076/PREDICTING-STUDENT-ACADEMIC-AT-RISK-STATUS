from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import os, sys, io
from datetime import datetime
import pandas as pd
import numpy as np
from fpdf import FPDF
import scipy.stats as stats

sys.path.insert(0, os.path.dirname(__file__))

from database.database_manager import DatabaseManager
from modules.auth import AuthManager
from modules.ml_engine import RiskPredictor
from modules.data_manager import DataManager
from modules.email_service import EmailService

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global instances
db = DatabaseManager()
auth_mgr = AuthManager(db)
ml_store = {}
data_mgr = DataManager()
email_svc = EmailService(db)

# Email Mapping
STUDENT_EMAIL_MAP = {
    "STU001": "example1@gmail.com", "STU002": "example2@gmail.com",
    "STU003": "example3@gmail.com", "STU004": "example4@gmail.com",
}
for i in range(1, 147):
    sid = f"STU{i + 4:03d}"
    STUDENT_EMAIL_MAP[sid] = f"student{i:03d}@gmail.com"


def get_ml(user_id):
    if user_id not in ml_store:
        ml_store[user_id] = RiskPredictor()
    return ml_store[user_id]


def uid():
    return session.get('user_id', 1)


def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)

    return decorated


def sanitize_text(text):
    if not text:
        return ""
    replacements = {
        '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '*', '\u2026': '...'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode('latin-1', 'replace').decode('latin-1')


# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('app.html', username=session.get('username'), role=session.get('role'))


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')

    user = db.get_user(username)
    if user and user.get('lockout_time'):
        lockout_dt = datetime.fromisoformat(str(user.get('lockout_time')))
        if datetime.now() < lockout_dt:
            return jsonify({'ok': False, 'error': 'Account locked. Try again in 15 minutes.'})

    res = auth_mgr.login(username, password)
    if res:
        session['user_id'] = res['id']
        session['username'] = res['username']
        session['role'] = res['role']
        return jsonify({'ok': True, 'user': res, 'needs_consent': not db.check_consent(res['id'])})
    return jsonify({'ok': False, 'error': 'Invalid username or password'})


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    ok, msg = auth_mgr.register(
        data.get('username', ''),
        data.get('email', ''),
        data.get('password', ''),
        'Researcher'
    )
    return jsonify({'ok': ok, 'message': msg})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/consent', methods=['POST'])
@require_login
def api_consent():
    db.save_consent(uid())
    return jsonify({'ok': True})


# API Endpoints
@app.route('/api/dashboard/stats', methods=['GET'])
@require_login
def api_dashboard_stats():
    user_id = uid()
    data = db.get_predictions(1, user_id)
    total = len(data)
    risk = sum(1 for d in data if d[2] == 'At-Risk')
    hist = db.get_model_history(user_id)

    return jsonify({
        'total': total,
        'at_risk': risk,
        'safe': total - risk,
        'accuracy': f"{hist[0][1] * 100:.1f}%" if hist else 'N/A',
        'meetings': len(db.get_meetings(user_id=user_id)),
        'alerts': len(db.get_notifications(user_id=user_id)),
        'tutoring': len(db.get_tutoring(user_id=user_id)),
        'top10': [list(r) for r in db.get_top_at_risk(1, user_id, 10)]
    })


@app.route('/api/lms/extract', methods=['POST'])
@require_login
def api_lms_extract():
    df = data_mgr.generate_lms_data(150)
    df['StudentEmail'] = df['StudentID'].map(STUDENT_EMAIL_MAP)
    db.seed_lms_logs(df)
    return jsonify({'ok': True, 'count': len(df), 'server': 'lms.university.ac.ke'})


@app.route('/api/lms/data', methods=['GET'])
@require_login
def api_lms_data():
    rows = db.get_lms_logs()
    return jsonify({
        'ok': True,
        'data': [{
            'id': r[0],
            'student_id': r[1],
            'full_name': r[2],
            'course': r[3],
            'login_count': r[4],
            'quiz_score': r[5],
            'last_login': r[13]
        } for r in rows],
        'count': len(rows)
    })


@app.route('/api/train', methods=['POST'])
@require_login
def api_train():
    try:
        user_id = uid()
        rows = db.get_lms_logs()
        if not rows:
            return jsonify({'ok': False, 'error': 'No data'})

        cols = ['StudentID', 'LoginCount', 'QuizScore', 'ForumPosts', 'ContentViews',
                'SessionDuration', 'AssignmentSubmissionRate', 'LateSubmissions',
                'QuizParticipationRate', 'EngagementVariance', 'AtRisk']
        data = []

        for r in rows:
            lc = float(r[4] or 0)
            qs = float(r[5] or 0)
            fp = float(r[6] or 0)
            cv = float(r[7] or 0)
            sd = float(r[9] or 0)
            asr = float(r[10] or 0)
            ls = float(r[11] or 0)
            qpr = float(r[12] or 0)
            ev = float(r[13] or 0)

            s = (lc < 30) * 0.25 + (qs < 50) * 0.25 + (asr < 0.5) * 0.20 + (sd < 15) * 0.10 + \
                (qpr < 0.4) * 0.10 + (ls > 4) * 0.05 + (fp < 3) * 0.05
            data.append((r[1], lc, qs, fp, cv, sd, asr, ls, qpr, ev, 1 if s >= 0.30 else 0))

        df = pd.DataFrame(data, columns=cols)
        ml = get_ml(user_id)
        acc = ml.train_model(df)
        db.save_model_history(acc, user_id)
        return jsonify({'ok': True, 'accuracy': round(acc * 100, 2)})
    except Exception as e:
        print(f"Training Error: {e}")
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/train/csv', methods=['POST'])
@require_login
def api_train_csv():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'ok': False, 'error': 'No file selected'})

    try:
        df = pd.read_csv(file)
        if 'AtRisk' not in df.columns:
            df['AtRisk'] = ((df['LoginCount'] < 30) * 0.25 +
                            (df['QuizScore'] < 50) * 0.25 +
                            (df['AssignmentSubmissionRate'] < 0.5) * 0.20) >= 0.3

        ml = get_ml(uid())
        acc = ml.train_model(df)
        db.save_model_history(acc, uid())
        db.seed_lms_logs(df)
        return jsonify({'ok': True, 'accuracy': round(acc * 100, 2)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/predict', methods=['POST'])
@require_login
def api_predict():
    user_id = uid()
    ml = get_ml(user_id)

    if not ml.is_trained:
        return jsonify({'ok': False, 'error': 'Train model first'})

    rows = db.get_lms_logs()
    if not rows:
        return jsonify({'ok': False, 'error': 'No data'})

    cols = ['StudentID', 'LoginCount', 'QuizScore', 'ForumPosts', 'ContentViews',
            'SessionDuration', 'AssignmentSubmissionRate', 'LateSubmissions',
            'QuizParticipationRate', 'EngagementVariance']

    df = pd.DataFrame([
        (r[1], r[4], r[5], r[6], r[7], r[9], r[10], r[11], r[12], r[13])
        for r in rows
    ], columns=cols)

    results = ml.predict(df)
    db.save_predictions(1, results, user_id)

    formatted_data = []
    for _, row in results.iterrows():
        formatted_data.append({
            'student_id': row['StudentID'],
            'risk_score': row['RiskScore'],
            'status': row['Status'],
            'login_count': row['LoginCount'],
            'quiz_score': row['QuizScore'],
            'forum_posts': row['ForumPosts'],
            'content_views': row['ContentViews'],
            'session_duration': row['SessionDuration'],
            'assignment_submission_rate': row['AssignmentSubmissionRate'],
            'late_submissions': row['LateSubmissions'],
            'quiz_participation_rate': row['QuizParticipationRate'],
            'engagement_variance': row['EngagementVariance']
        })

    return jsonify({
        'ok': True,
        'count': len(formatted_data),
        'data': formatted_data
    })


@app.route('/api/predictions', methods=['GET'])
@require_login
def api_get_predictions():
    rows = db.get_predictions(1, uid(), sort_by_id=True)
    return jsonify({
        'ok': True,
        'data': [{
            'student_id': r[2],
            'risk_score': r[3],
            'status': r[4],
            'login_count': r[5],
            'quiz_score': r[6],
            'forum_posts': r[7],
            'content_views': r[8],
            'session_duration': r[9],
            'assignment_submission_rate': r[10],
            'late_submissions': r[11],
            'quiz_participation_rate': r[12],
            'engagement_variance': r[13]
        } for r in rows]
    })


@app.route('/api/student/<student_id>', methods=['GET'])
@require_login
def api_student_detail(student_id):
    user_id = uid()
    ml = get_ml(user_id)
    d = db.get_student_detail(student_id, user_id)

    if not d:
        return jsonify({'ok': False, 'error': 'Not found'})

    row = {
        'StudentID': d[2],
        'risk_score': d[3],
        'risk_status': d[4],
        'login_count': d[5],
        'quiz_score': d[6],
        'forum_posts': d[7],
        'content_views': d[8],
        'session_duration': d[9],
        'assignment_submission_rate': d[10],
        'late_submissions': d[11],
        'quiz_participation_rate': d[12],
        'engagement_variance': d[13],
        'Status': d[4]
    }

    analysis = ml.analyse_student(row)
    contact = db.get_student_contact(student_id)

    return jsonify({
        'ok': True,
        'student': row,
        'analysis': analysis,
        'contact': {
            'student_email': contact[2] if contact else '',
            'parent_email': contact[3] if contact else '',
            'parent_phone': contact[4] if contact else '',
            'advisor_email': contact[5] if contact else ''
        }
    })


# Report Downloads
@app.route('/api/report/download/excel', methods=['POST'])
@require_login
def api_download_excel():
    data = request.json
    f = data.get('filter', 'All')
    s_id = data.get('student_id')
    rows = db.get_predictions(1, uid())
    df_data = []

    for r in rows:
        include = (f == 'All') or \
                  (f == 'At-Risk' and r[4] == 'At-Risk') or \
                  (f == 'Safe' and r[4] == 'Safe') or \
                  (f == 'Specific' and r[2] == s_id)
        if include:
            df_data.append({
                'StudentID': r[2],
                'RiskScore': r[3],
                'Status': r[4],
                'LoginCount': r[5],
                'QuizScore': r[6],
                'ForumPosts': r[7],
                'ContentViews': r[8],
                'SessionDuration': r[9],
                'SubRate': r[10],
                'LateSubs': r[11],
                'QuizPart': r[12],
                'EngVar': r[13]
            })

    df = pd.DataFrame(df_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Risk Report')
    output.seek(0)
    return send_file(
        output,
        download_name='risk_report.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/api/report/download/csv', methods=['POST'])
@require_login
def api_download_csv():
    data = request.json
    f = data.get('filter', 'All')
    s_id = data.get('student_id')
    rows = db.get_predictions(1, uid())
    df_data = []

    for r in rows:
        include = (f == 'All') or \
                  (f == 'At-Risk' and r[4] == 'At-Risk') or \
                  (f == 'Safe' and r[4] == 'Safe') or \
                  (f == 'Specific' and r[2] == s_id)
        if include:
            df_data.append({
                'StudentID': r[2],
                'RiskScore': r[3],
                'Status': r[4],
                'LoginCount': r[5],
                'QuizScore': r[6]
            })

    df = pd.DataFrame(df_data)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(
        output,
        download_name='risk_data.csv',
        as_attachment=True,
        mimetype='text/csv'
    )


@app.route('/api/report/download/pdf', methods=['GET'])
@require_login
def api_download_pdf():
    user_id = uid()
    f = request.args.get('filter', 'All')
    sid = request.args.get('student_id')
    rows = db.get_predictions(1, user_id)
    filtered_rows = []

    for r in rows:
        include = (f == 'All') or \
                  (f == 'At-Risk' and r[4] == 'At-Risk') or \
                  (f == 'Safe' and r[4] == 'Safe') or \
                  (f == 'Specific' and r[2] == sid)
        if include:
            filtered_rows.append(r)

    if not filtered_rows:
        return jsonify({'ok': False, 'error': 'No data'})

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(200, 10, txt="Academic Risk Report", ln=1, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 6, txt=f"Filter: {f} {f'Student: {sid}' if sid else ''}", ln=1, align='C')
    pdf.ln(5)

    if f == 'Specific' and len(filtered_rows) == 1:
        r = filtered_rows[0]
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Student ID: {r[2]}", ln=1)
        pdf.cell(200, 10, txt=f"Risk Status: {sanitize_text(r[4])}", ln=1)
        pdf.cell(200, 10, txt=f"Risk Score: {float(r[3]) * 100:.1f}%", ln=1)
        pdf.ln(5)
        pdf.cell(200, 10, txt="Metrics:", ln=1)
        pdf.cell(200, 8, txt=f"  - Login Count: {r[5]}", ln=1)
        pdf.cell(200, 8, txt=f"  - Quiz Score: {r[6]}", ln=1)

        ml = get_ml(user_id)
        row_obj = {
            'StudentID': r[2], 'risk_score': r[3], 'Status': r[4],
            'login_count': r[5], 'quiz_score': r[6]
        }
        analysis = ml.analyse_student(row_obj)
        pdf.ln(5)
        pdf.cell(200, 10, txt="Analysis:", ln=1)
        for reason in analysis['reasons']:
            pdf.multi_cell(0, 6, f"  - {sanitize_text(reason)}")
    else:
        pdf.set_font("Arial", size=10, style='B')
        w_id, w_score, w_stat, w_log, w_quiz = 30, 20, 25, 20, 20
        headers = ["ID", "Score", "Status", "Logins", "Quiz"]
        pdf.set_fill_color(30, 41, 59)
        pdf.set_text_color(226, 232, 240)
        for i, h in enumerate(headers):
            pdf.cell([w_id, w_score, w_stat, w_log, w_quiz][i], 8, h, border=1, align='C', fill=True)
        pdf.ln()

        pdf.set_font("Arial", size=9)
        pdf.set_text_color(148, 163, 184)
        for r in filtered_rows[:50]:
            pdf.cell(w_id, 7, str(r[2]), border=1, align='C')
            pdf.cell(w_score, 7, f"{float(r[3]) * 100:.0f}%", border=1, align='C')
            pdf.cell(w_stat, 7, sanitize_text(r[4]), border=1, align='C')
            pdf.cell(w_log, 7, str(r[5]), border=1, align='C')
            pdf.cell(w_quiz, 7, str(r[6]), border=1, align='C')
            pdf.ln()

        if len(filtered_rows) > 50:
            pdf.cell(0, 10, txt=f"... and {len(filtered_rows) - 50} more.", ln=1)

    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)
    return send_file(
        output,
        download_name='risk_report.pdf',
        as_attachment=True,
        mimetype='application/pdf'
    )


# Actions
@app.route('/api/action/send_email', methods=['POST'])
@require_login
def api_action_send_email():
    data = request.json
    user_id = uid()
    gmail, app_pw = db.get_smtp(user_id)

    if not gmail or not app_pw:
        return jsonify({'ok': False, 'error': 'SMTP not configured in Settings'})

    ok, msg = email_svc.send_single_email(
        gmail, app_pw,
        data['recipient'],
        data['subject'],
        data['body']
    )

    if ok:
        db.log_automated_email(
            data.get('type', 'custom'),
            data.get('student_id'),
            data['recipient'],
            data['subject'],
            data['body'],
            'sent',
            user_id
        )
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': msg})


@app.route('/api/action/schedule_meeting', methods=['POST'])
@require_login
def api_action_schedule_meeting():
    data = request.json
    user_id = uid()
    mid = db.save_meeting(
        data['student_id'],
        data.get('advisor_name', 'Advisor'),
        data['date'],
        data['time'],
        data['venue'],
        data['type'],
        data.get('link', ''),
        data.get('notes', ''),
        user_id
    )
    return jsonify({'ok': True, 'id': mid})


@app.route('/api/action/assign_tutor', methods=['POST'])
@require_login
def api_action_assign_tutor():
    data = request.json
    user_id = uid()
    tid = db.save_tutoring(
        data['student_id'],
        data['tutor_name'],
        data['subject'],
        data['schedule'],
        user_id
    )
    return jsonify({'ok': True, 'id': tid})


# Email Center
@app.route('/api/email/smtp', methods=['POST'])
@require_login
def api_save_smtp():
    data = request.json
    db.save_smtp(uid(), data.get('gmail', ''), data.get('app_password', ''))
    return jsonify({'ok': True})


@app.route('/api/email/smtp', methods=['GET'])
@require_login
def api_get_smtp():
    g, p = db.get_smtp(uid())
    return jsonify({'gmail': g, 'app_password': p})


@app.route('/api/email/send_bulk', methods=['POST'])
@require_login
def api_send_bulk():
    data = request.json
    user_id = uid()
    gmail = data.get('gmail', '').strip()
    app_pw = data.get('app_password', '').strip()
    template = data.get('template', 'warning')

    if not gmail or not app_pw:
        return jsonify({'ok': False, 'error': 'Gmail and App Password required'})

    db.save_smtp(user_id, gmail, app_pw)
    students = [s for s in db.get_predictions(1, user_id) if s[4] == 'At-Risk']

    if not students:
        return jsonify({'ok': False, 'error': 'No at-risk students found.'})

    results = email_svc.send_bulk(gmail, app_pw, students, template, user_id, STUDENT_EMAIL_MAP)
    return jsonify(results)


@app.route('/api/analytics/chart_data', methods=['GET'])
@require_login
def api_chart_data():
    user_id = uid()
    preds = db.get_predictions(1, user_id)
    risk = sum(1 for d in preds if d[4] == 'At-Risk')
    safe = len(preds) - risk
    hist = db.get_model_history(user_id)
    top10 = db.get_top_at_risk(1, user_id, 10)

    return jsonify({
        'ok': True,
        'distribution': {'at_risk': risk, 'safe': safe},
        'accuracy_history': [
            {'time': str(h[0])[11:16], 'accuracy': round(h[1] * 100, 1)}
            for h in reversed(hist)
        ],
        'top10': [
            {'id': r[0], 'score': round(float(r[1]) * 100, 1)}
            for r in top10
        ],
    })


@app.route('/api/model/history', methods=['GET'])
@require_login
def api_model_history():
    rows = db.get_model_history(uid())
    data = [{'timestamp': r[0], 'accuracy': round(r[1] * 100, 2)} for r in rows]
    return jsonify({
        'ok': True,
        'data': data,
        'trained': get_ml(uid()).is_trained
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)