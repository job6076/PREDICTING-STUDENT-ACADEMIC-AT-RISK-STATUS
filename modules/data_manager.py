import pandas as pd
import random
from datetime import datetime, timedelta

class DataManager:
    def generate_lms_data(self, count=100):
        data = []
        courses = ["CS101", "MA202", "PH301", "EN102", "ST401"]
        names = ["John", "Mary", "James", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]

        for i in range(count):
            sid = f"STU{i + 1:03d}"
            login = random.randint(0, 100)
            quiz = random.randint(0, 100)
            forum = random.randint(0, 20)

            data.append({
                "StudentID": sid,
                "StudentName": f"{random.choice(names)} {random.choice(names)}",
                "Course": random.choice(courses),
                "LoginCount": login,
                "QuizScore": quiz,
                "ForumPosts": forum,
                "ContentViews": random.randint(0, 50),
                "IPAddress": f"192.168.1.{random.randint(1, 255)}",
                "SessionDuration": random.uniform(5, 120),
                "AssignmentSubmissionRate": random.uniform(0, 1),
                "LateSubmissions": random.randint(0, 5),
                "QuizParticipationRate": random.uniform(0, 1),
                "EngagementVariance": random.uniform(0, 1),
                "LastLogin": (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d %H:%M")
            })
        return pd.DataFrame(data)