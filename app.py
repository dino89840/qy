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
    name = db.Column(db.String(200))
    url = db.Column(db.String(500))
    token = db.Column(db.String(50))
    file_id = db.Column(db.String(50))
    status = db.Column(db.String(50), default="Active")
    direct_link = db.Column(db.Text, default="")

def get_full_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        html = response.text
        name = re.search(r"<h1 class=\"app-name\">(.*?)</h1>", html).group(1)
        token = re.search(r"const token = \"(.*?)\";", html).group(1)
        file_id = re.search(r"const fileId = (\d+);", html).group(1)
        return name, token, file_id
    except:
        return "Unknown File", None, None

def refresh_task():
    with app.app_context():
        links = FileLink.query.all()
        for item in links:
            try:
                api_url = f"https://qyun.org/api/share/download?token={item.token}&fileId={item.file_id}"
                requests.get(api_url, timeout=15)
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
    url = request.form.get('url').strip()
    name, token, file_id = get_full_info(url)
    if token and file_id:
        new_link = FileLink(name=name, url=url, token=token, file_id=file_id)
        db.session.add(new_link)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/check/<int:id>')
def check_manual(id):
    link = FileLink.query.get(id)
    try:
        api_url = f"https://qyun.org/api/share/download?token={link.token}&fileId={link.file_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer': link.url
        }
        res = requests.get(api_url, headers=headers, timeout=60, allow_redirects=True)
        if res.status_code == 200:
            link.direct_link = res.url
            link.status = "Alive ✅"
        else:
            link.status = "Error"
    except:
        link.status = "Timeout"
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
