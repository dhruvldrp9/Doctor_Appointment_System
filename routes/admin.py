from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models import User, Appointment, Specialization
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You need admin privileges to access this page.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_doctors = User.query.filter_by(role='doctor').count()
    total_patients = User.query.filter_by(role='patient').count()
    total_appointments = Appointment.query.count()
    recent_appointments = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_doctors=total_doctors,
                         total_patients=total_patients,
                         total_appointments=total_appointments,
                         recent_appointments=recent_appointments)

@admin_bp.route('/doctors')
@login_required
@admin_required
def manage_doctors():
    doctors = User.query.filter_by(role='doctor').all()
    specializations = Specialization.query.all()
    return render_template('admin/doctors.html',
                         doctors=doctors,
                         specializations=specializations)

@admin_bp.route('/add_doctor', methods=['POST'])
@login_required
@admin_required
def add_doctor():
    email = request.form.get('email')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    specialization_id = request.form.get('specialization_id')
    
    if User.query.filter_by(email=email).first():
        flash('Email already registered')
        return redirect(url_for('admin.manage_doctors'))
    
    doctor = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role='doctor',
        specialization_id=specialization_id
    )
    doctor.set_password(password)
    
    db.session.add(doctor)
    db.session.commit()
    
    flash('Doctor added successfully')
    return redirect(url_for('admin.manage_doctors'))

@admin_bp.route('/appointments')
@login_required
@admin_required
def view_appointments():
    appointments = Appointment.query.all()
    return render_template('admin/appointments.html', appointments=appointments)
