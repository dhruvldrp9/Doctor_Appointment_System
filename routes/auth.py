from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models import User, Specialization
from sqlalchemy.exc import IntegrityError
import os

auth_bp = Blueprint('auth', __name__)

ADMIN_REGISTRATION_CODE = os.environ.get('ADMIN_REGISTRATION_CODE', 'admin123')  # Set this in environment variables

@auth_bp.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('patient.dashboard'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('doctor.dashboard'))
            else:
                return redirect(url_for('patient.dashboard'))
        flash('Invalid email or password')
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role')
        admin_code = request.form.get('admin_code')
        specialization_id = request.form.get('specialization_id')

        if not all([email, password, first_name, last_name, role]):
            flash('All fields are required')
            return redirect(url_for('auth.register'))

        # Handle admin registration
        if admin_code:
            if admin_code != ADMIN_REGISTRATION_CODE:
                flash('Invalid admin registration code')
                return redirect(url_for('auth.register'))
            role = 'admin'

        # Validate doctor registration
        if role == 'doctor' and not specialization_id:
            flash('Specialization is required for doctor registration')
            return redirect(url_for('auth.register'))

        try:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                specialization_id=specialization_id if role == 'doctor' else None
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please login.')
            return redirect(url_for('auth.login'))
        except IntegrityError:
            db.session.rollback()
            flash('Email address is already registered. Please use a different email.')
            return redirect(url_for('auth.register'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.')
            return redirect(url_for('auth.register'))

    specializations = Specialization.query.all()
    return render_template('auth/register.html', specializations=specializations)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))