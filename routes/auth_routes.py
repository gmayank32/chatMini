from flask import Blueprint, render_template, request, redirect, url_for, make_response
from models import db, User
from auth import generate_token, hash_password, check_password
from config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration route"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            return "User already exists", 400
        
        password_hash = hash_password(password)
        new_user = User(username=username, password_hash=password_hash)
        
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('auth.login'))
    
    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password(password, user.password_hash):
            return "Invalid credentials", 401
        
        token = generate_token(user.id)
        resp = make_response(redirect(url_for('main.home')))
        resp.set_cookie(Config.JWT_COOKIE_NAME, token, httponly=True, samesite='Lax')
        
        return resp
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    """User logout route"""
    resp = make_response(redirect(url_for('auth.login')))
    resp.delete_cookie(Config.JWT_COOKIE_NAME)
    return resp