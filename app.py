import requests
import re
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

class FileLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    url = db.Column(db.String(500))
    token = db.Column(db.String(50))
    file_id = db.Column(db.String(50))
    status = db.Column(db.String(50), default="Unknown") # ဖိုင် အခြေအနေ သိမ်းရန်

def get_file_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text
        token = re.search(r"const token = \"(.*?)\";", html).group(1)
        file_id = re.search(r"const fileId = (\d+);", html).group(1)
        return token, file_id
    except:
        return None, None

def refresh_task():
    with app.app_context():
        links = FileLink.query.all()
        for item in links:
            try:
                api_url = f"https://qyun.org/api/share/download?token={item.token}&fileId={item.file_id}"
                res = requests.get(api_url, timeout=10)
                if res.status_code == 200:
                    item.status = "Active (Refreshed)"
                else:
                    item.status = "Error"
                db.session.commit()
            except:
                pass

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_task, trigger="interval", days=7)
scheduler.start()

@app.route('/')
def home():
    links = FileLink.query.all()
    return render_template('index.html', links=links)

@app.route('/add', methods=['POST'])
def add():
    name = request.form.get('name')
    url = request.form.get('url')
    token, file_id = get_file_info(url)
    if token and file_id:
        new_link = FileLink(name=name, url=url, token=token, file_id=file_id, status="Active")
        db.session.add(new_link)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/check/<int:id>')
def check_manual(id):
    link = FileLink.query.get(id)
    try:
        res = requests.get(link.url, timeout=10)
        if "文件不存在" in res.text or res.status_code == 404:
            link.status = "Dead (Deleted)"
        else:
            link.status = "Alive"
    except:
        link.status = "Server Error"
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete/<int:id>')
def delete(id):
    link = FileLink.query.get(id)
    db.session.delete(link)
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
