import requests
import re
import time
import random
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class FileLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), default="Pending...")
    url = db.Column(db.String(500), unique=True)
    status = db.Column(db.String(50), default="waiting")
    last_check = db.Column(db.String(100))
    error = db.Column(db.Text)

def process_qyshare(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        html = res.text
        
        name_match = re.search(r'<h1 class="app-name">(.*?)</h1>', html)
        name = name_match.group(1) if name_match else "Unknown File"
        
        token = re.search(r'const token = "(.*?)";', html).group(1)
        file_id = re.search(r'const fileId = (\d+);', html).group(1)
        
        # API ကို လှမ်းခေါ်ပြီး သက်တမ်းတိုးမယ်
        api_url = f"{url.split('/s/')[0]}/api/share/download?token={token}&fileId={file_id}"
        api_res = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0", "Referer": url}, timeout=20)
        
        if api_res.status_code == 200:
            return True, name, None
        return False, name, f"API Error: {api_res.status_code}"
    except Exception as e:
        return False, "Error", str(e)

def maintenance_job():
    with app.app_context():
        all_links = FileLink.query.all()
        random.shuffle(all_links) # Deno ထဲကအတိုင်း Shuffle လုပ်မယ်
        
        for link in all_links:
            success, name, err = process_qyshare(link.url)
            link.name = name
            link.last_check = time.strftime('%Y-%m-%d %H:%M:%S')
            if success:
                link.status = "active ✅"
                link.error = None
            else:
                link.status = "failed ❌"
                link.error = err
            db.session.commit()
            time.sleep(5) # ၅ စက္ကန့်ခြားမှ တစ်ဖိုင်သွားမယ် (Anti-ban)

scheduler = BackgroundScheduler()
# ၂ ရက်တစ်ခါ Run မယ် (Deno logic အတိုင်း)
scheduler.add_job(func=maintenance_job, trigger="interval", days=2)
scheduler.start()

@app.route('/')
def home():
    links = FileLink.query.order_by(FileLink.id.desc()).all()
    return render_template('index.html', links=links)

@app.route('/api/add', methods=['POST'])
def add():
    urls = request.form.get('url').split('\n')
    for url in urls:
        url = url.strip()
        if url and not FileLink.query.filter_by(url=url).first():
            new_link = FileLink(url=url)
            db.session.add(new_link)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/api/delete/<int:id>')
def delete(id):
    link = FileLink.query.get(id)
    if link:
        db.session.delete(link)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/api/trigger')
def trigger():
    maintenance_job()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
