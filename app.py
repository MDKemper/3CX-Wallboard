from flask import Flask, render_template, request, redirect, url_for, jsonify
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)

DATA_FILE = 'call_log.csv'
ARCHIVE_DIR = 'archives'
LAST_ARCHIVE_FILE = 'last_archive.txt'

def daily_archive():
    today = datetime.now().strftime('%Y-%m-%d')
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    if os.path.exists(LAST_ARCHIVE_FILE):
        with open(LAST_ARCHIVE_FILE, 'r') as f:
            last_date = f.read().strip()
    else:
        last_date = ''
    if last_date != today and os.path.exists(DATA_FILE):
        archive_name = os.path.join(ARCHIVE_DIR, f'call_log_{today}.csv')
        os.rename(DATA_FILE, archive_name)
        pd.DataFrame(columns=['CallID', 'Time', 'Duration', 'Direction', 'Status']).to_csv(DATA_FILE, index=False)
        with open(LAST_ARCHIVE_FILE, 'w') as f:
            f.write(today)

daily_archive()

def load_data():
    return pd.read_csv(DATA_FILE)

@app.route('/')
def home():
    return redirect(url_for('wallboard'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            df_new = pd.read_csv(file)
            df_existing = load_data()
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_csv(DATA_FILE, index=False)
            return redirect(url_for('wallboard'))
    return '''
        <h2>Upload 3CX CDR CSV File</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file">
            <input type="submit" value="Upload">
        </form>
    '''

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data:
        df_new = pd.DataFrame([data])
        df_existing = load_data()
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.to_csv(DATA_FILE, index=False)
        return {"status": "success", "message": "Call record added."}, 200
    else:
        return {"status": "error", "message": "No JSON payload received."}, 400

@app.route('/wallboard')
def wallboard():
    df = load_data()
    total_calls = len(df)
    answered_calls = len(df[df['Status'].str.contains('Completed|Answered', case=False, na=False)])
    missed_calls = len(df[df['Status'].str.contains('No Answer|Missed', case=False, na=False)])
    avg_duration = round(df['Duration'].mean(), 1) if not df['Duration'].empty else 0

    pie_labels = ['Answered', 'Missed']
    pie_values = [answered_calls, missed_calls]

    if not df['Time'].empty:
        df['Hour'] = pd.to_datetime(df['Time'], errors='coerce').dt.hour
        hourly_counts = df['Hour'].value_counts().sort_index()
        bar_labels = [str(int(hr)) + ':00' for hr in hourly_counts.index]
        bar_values = hourly_counts.values.tolist()
    else:
        bar_labels = []
        bar_values = []

    return render_template('wallboard.html',
                           total_calls=total_calls,
                           answered_calls=answered_calls,
                           missed_calls=missed_calls,
                           avg_duration=avg_duration,
                           pie_labels=pie_labels,
                           pie_values=pie_values,
                           bar_labels=bar_labels,
                           bar_values=bar_values)

@app.route('/trends')
def trends():
    df = load_data()
    if not df.empty:
        df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
        df = df.dropna(subset=['Time'])
        df['Week'] = df['Time'].dt.strftime('%Y-%U')
        weekly_counts = df.groupby('Week').size()
        weekly_avg_duration = df.groupby('Week')['Duration'].mean().round(1)
        weekly_answered = df[df['Status'].str.contains('Completed|Answered', case=False, na=False)].groupby('Week').size()
        weekly_missed = df[df['Status'].str.contains('No Answer|Missed', case=False, na=False)].groupby('Week').size()

        weeks = weekly_counts.index.tolist()
        counts = weekly_counts.values.tolist()
        avg_durations = weekly_avg_duration.reindex(weeks, fill_value=0).values.tolist()
        answered = weekly_answered.reindex(weeks, fill_value=0).values.tolist()
        missed = weekly_missed.reindex(weeks, fill_value=0).values.tolist()
    else:
        weeks = []
        counts = []
        avg_durations = []
        answered = []
        missed = []

    return render_template('trends.html',
                           weeks=weeks,
                           counts=counts,
                           avg_durations=avg_durations,
                           answered=answered,
                           missed=missed)

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

