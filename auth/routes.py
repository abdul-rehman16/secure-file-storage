from flask import Flask, render_template, redirect, url_for, request, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import User
import os

app = Flask(__name__)
app.secret_key= os.getenv('FLASK_SECRET_KEY')

login_manager=LoginManager()
login_manager.init_app(app)
login_manager.login_view='login'

@login_manager.user_loader
def load_user(user_id):
    return user.query.get(int(user_id))

@app.route('/')
def home():
    return redirect('/login')