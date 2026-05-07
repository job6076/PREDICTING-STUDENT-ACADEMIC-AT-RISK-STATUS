import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class EmailService:
    def __init__(self, db):
        self.db = db

    def build_email(self, template, student_id, student_data):
        risk = float(student_data[1]) * 100 if student_data[1] else 0
        lc = int(student_data[3]) if len(student_data) > 3 and student_data[3] is not None else 'N/A'
        qs = f"{float(student_data[4]):.1f}%" if len(student_data) > 4 and student_data[4] is not None else 'N/A'
        asr = f"{float(student_data[8]) * 100:.0f}%" if len(student_data) > 8 and student_data[8] is not None else 'N/A'
        date_str = datetime.now().strftime('%B %d, %Y')

        if template == 'advisor':
            subject = f"URGENT: At-Risk Student Alert - {student_id}"
            body = (
                f"Dear Advisor,\n\n"
                f"Student {student_id} has been flagged as AT-RISK (Risk Score: {risk:.1f}%).\n\n"
                f"Behaviour Summary:\n"
                f"  - Login Count: {lc}\n  - Quiz Score: {qs}\n  - Sub Rate: {asr}\n\n"
                f"Please arrange an intervention meeting.\n\nRegards,\nAcademic Analytics System\n{date_str}"
            )
        else:
            subject = f"Academic Alert - {student_id}"
            body = f"Dear Student {student_id},\n\nYou have been identified as at-risk.\n\nRegards,\nSystem"
        return subject, body

    def send_single_email(self, gmail, app_password, to_email, subject, body):
        if not to_email: return False, "No email provided"
        try:
            msg = MIMEMultipart()
            msg['From'] = gmail
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            # Using SMTP_SSL for port 465 (standard for Gmail)
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as server:
                server.login(gmail, app_password)
                server.sendmail(gmail, to_email, msg.as_string())
            return True, "Sent"
        except Exception as e:
            return False, str(e)

    def send_bulk(self, gmail, app_password, students, template, user_id, email_map):
        sent, failed, errors = 0, 0, []
        for s in students:
            sid = s[0]
            to_email = email_map.get(sid)
            if not to_email:
                failed += 1
                continue
            subject, body = self.build_email(template, sid, s)
            ok, msg = self.send_single_email(gmail, app_password, to_email, subject, body)
            if ok:
                sent += 1
            else:
                failed += 1; errors.append(msg)
        return {'ok': True, 'sent': sent, 'failed': failed, 'errors': list(set(errors))[:3]}