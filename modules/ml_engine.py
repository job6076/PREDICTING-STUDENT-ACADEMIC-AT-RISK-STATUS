import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import numpy as np


class RiskPredictor:
    def __init__(self):
        self.model = None
        self.is_trained = False

    def train_model(self, df: pd.DataFrame):
        # Features used for prediction
        features = ['LoginCount', 'QuizScore', 'ForumPosts', 'ContentViews',
                    'SessionDuration', 'AssignmentSubmissionRate', 'LateSubmissions',
                    'QuizParticipationRate', 'EngagementVariance']

        X = df[features]
        y = df['AtRisk']

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Initialize and train model
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)

        # Calculate accuracy
        preds = self.model.predict(X_test)
        acc = accuracy_score(y_test, preds)

        self.is_trained = True
        return acc

    def predict(self, df: pd.DataFrame):
        if not self.is_trained:
            raise Exception("Model not trained")

        features = ['LoginCount', 'QuizScore', 'ForumPosts', 'ContentViews',
                    'SessionDuration', 'AssignmentSubmissionRate', 'LateSubmissions',
                    'QuizParticipationRate', 'EngagementVariance']

        X = df[features]
        probs = self.model.predict_proba(X)

        results = df.copy()
        results['RiskScore'] = probs[:, 1]  # Probability of class 1 (At-Risk)
        results['Status'] = results['RiskScore'].apply(lambda x: 'At-Risk' if x >= 0.30 else 'Safe')
        return results

    def analyse_student(self, row):
        reasons = []
        if row.get('login_count', 0) < 30:
            reasons.append("Low login count indicates disengagement.")
        if row.get('quiz_score', 0) < 50:
            reasons.append("Quiz scores are below average.")
        if row.get('assignment_submission_rate', 0) < 0.5:
            reasons.append("Assignment submission rate is critical.")

        metrics = {
            "Logins": row.get('login_count', 0),
            "Quiz": f"{row.get('quiz_score', 0)}%",
            "Sub Rate": f"{row.get('assignment_submission_rate', 0) * 100:.0f}%"
        }
        return {'reasons': reasons, 'metrics': metrics}