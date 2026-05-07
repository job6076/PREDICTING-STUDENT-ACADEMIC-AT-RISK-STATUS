## Project Title
Predicting Student Academic At-Risk Status Using Machine Learning on LMS Log Data

## Project Description
The Student Academic Risk Prediction System (SARPS) is a machine learning-based desktop application designed to identify students who are academically at risk using Learning Management System (LMS) log data.

The system analyzes behavioral features such as:
- Login frequency
- Session duration
- Resource access count
- Assessment scores
- Forum participation

Using machine learning algorithms such as:
- Logistic Regression
- Decision Tree
- Random Forest

The system predicts whether a student is:
- At-Risk
- Safe

This allows universities and instructors to provide early academic interventions and improve student retention rates.

---

# Objectives

## General Objective
To develop a machine learning-based system that predicts student academic at-risk status using LMS log data.

## Specific Objectives
- Extract LMS behavioral features from student interaction logs
- Train machine learning prediction models
- Evaluate model performance using classification metrics
- Develop a desktop GUI application for predictions and analytics

---

# Features

- User Authentication System
- LMS Data Upload (CSV)
- Machine Learning Model Training
- Student Risk Prediction
- Risk Distribution Analytics
- Top At-Risk Students Visualization
- PDF/Excel/CSV Report Export
- Notification Module for Advisors/Parents
- Dashboard with Real-Time Statistics

---

# Technologies Used

## Programming Language
- Python 3.8+

## Machine Learning
- Scikit-learn

## Database
- SQLite

## GUI Framework
- Tkinter

## Data Processing Libraries
- Pandas
- NumPy

## Visualization
- Matplotlib

---

# Machine Learning Models

The system compares multiple machine learning algorithms:
- Logistic Regression
- Decision Tree
- Random Forest

Random Forest achieved the best performance with approximately 85% prediction accuracy.

---

# System Modules

## 1. Authentication Module
Handles secure user login and access control.

## 2. Data Upload Module
Allows upload of LMS student data in CSV format.

## 3. Prediction Engine
Processes student behavioral data and predicts academic risk status.

## 4. Analytics Dashboard
Displays:
- Risk distribution
- Model accuracy
- Top at-risk students
- Prediction trends

## 5. Report Export Module
Exports reports in:
- PDF
- Excel
- CSV

---

# Required CSV Structure

The uploaded CSV file must contain:

| Column Name | Description |
|---|---|
| Student_ID | Unique student identifier |
| Login_Count | Number of LMS logins |
| Avg_Session_Duration | Average session time |
| Resource_Access_Count | Number of resources accessed |
| Assessment_Score | Student assessment average |


# How To Run The System

## Step 1
Install Python 3.8+

## Step 2
Install required packages:

```bash
pip install pandas numpy scikit-learn matplotlib
````

## Step 3

Run the application:

```bash
python main.py
```

# Expected Output

The system:

* predicts student academic risk status
* visualizes student risk distribution
* generates analytical reports
* assists institutions in proactive intervention

---

# Authors

Group 4 – Meru University of Science and Technology

| Registration Number | Name |
|---|---|
| CT203/113832/23 | KIPCHUMBA KIBET JOB |
| CT203/113815/23 | JOHN LOBUIN OME |
| CT203/113824/23 | KENNEDY ODUOR |
| CT203/113835/23 | EUNICE NJERI |
| CT203/100833/19 | MICHAEL MAUNDU |
| CT203/109445/22 | JACKSON JUMA |
| CT203/113788/23 | GIDEON MUHORO |

# Supervisor

Dr. Mwenda Gichuru

---

# Academic Year

2025/2026

---

# License

This project is for academic and research purposes only.

```

After saving:

1. Put this `README.md` in the main project folder
2. Upload everything to GitHub
3. GitHub will automatically display the README beautifully on the repository homepage.
```
