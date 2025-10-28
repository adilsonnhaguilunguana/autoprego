from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app_old.models.user import User
from models import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/autenticacao')
def autenticacao():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return render_template('auth.html')

@auth_bp.route('/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        flash('Email ou senha incorretos', 'danger')
        return redirect(url_for('auth.autenticacao'))
    
    if not user.is_active:
        flash('Conta desativada. Entre em contato com o administrador.', 'warning')
        return redirect(url_for('auth.autenticacao'))
    
    login_user(user, remember=remember)
    user.update_login_time()
    db.session.commit()
    
    flash('Login realizado com sucesso!', 'success')
    return redirect(url_for('dashboard.dashboard'))

@auth_bp.route('/register', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    
    username = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Validações
    if password != confirm_password:
        flash('As senhas não coincidem', 'danger')
        return redirect(url_for('auth.autenticacao', tab='register'))
    
    if len(password) < 8:
        flash('A senha deve ter pelo menos 8 caracteres', 'danger')
        return redirect(url_for('auth.autenticacao', tab='register'))
    
    if User.query.filter_by(email=email).first():
        flash('Email já cadastrado', 'danger')
        return redirect(url_for('auth.autenticacao', tab='register'))
    
    if User.query.filter_by(username=username).first():
        flash('Nome de usuário já existe', 'danger')
        return redirect(url_for('auth.autenticacao', tab='register'))
    
    # Criar novo usuário
    new_user = User(
        username=username,
        email=email,
        is_admin=False  # Primeiro usuário pode ser admin, outros normais
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    flash('Conta criada com sucesso! Faça login para continuar.', 'success')
    return redirect(url_for('auth.autenticacao'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('auth.autenticacao'))