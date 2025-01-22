from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Appointment, DoctorSchedule
from datetime import datetime, timedelta
from functools import wraps

doctor_bp = Blueprint('doctor', __name__)

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'doctor':
            flash('You need doctor privileges to access this page.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@doctor_bp.route('/dashboard')
@login_required
@doctor_required
def dashboard():
    # Get today's and upcoming appointments
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    today_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.datetime >= today,
        Appointment.datetime < tomorrow
    ).order_by(Appointment.datetime).all()

    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.datetime >= tomorrow,
        Appointment.status != 'cancelled'
    ).order_by(Appointment.datetime).limit(5).all()

    pending_appointments = Appointment.query.filter_by(
        doctor_id=current_user.id,
        status='pending'
    ).all()

    return render_template('doctor/dashboard.html',
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         pending_appointments=pending_appointments)

@doctor_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
@doctor_required
def manage_schedule():
    if request.method == 'POST':
        day = int(request.form.get('day'))
        start_time = datetime.strptime(request.form.get('start_time'), '%H:%M').time()
        end_time = datetime.strptime(request.form.get('end_time'), '%H:%M').time()
        slot_duration = int(request.form.get('slot_duration', 30))

        # Create new schedule
        new_schedule = DoctorSchedule(
            doctor_id=current_user.id,
            day_of_week=day,
            start_time=start_time,
            end_time=end_time,
            slot_duration=slot_duration
        )

        # Check for overlaps with existing schedules
        existing_schedules = DoctorSchedule.query.filter_by(
            doctor_id=current_user.id,
            day_of_week=day
        ).all()

        has_overlap = any(new_schedule.has_overlap(schedule) for schedule in existing_schedules)

        if has_overlap:
            flash('This time slot overlaps with an existing schedule', 'error')
            return redirect(url_for('doctor.manage_schedule'))

        try:
            db.session.add(new_schedule)
            db.session.commit()
            flash('Schedule added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating schedule', 'error')

        return redirect(url_for('doctor.manage_schedule'))

    # Get schedules grouped by day
    schedules_by_day = {i: [] for i in range(7)}  # 0-6 for Monday-Sunday
    schedules = DoctorSchedule.query.filter_by(doctor_id=current_user.id).all()

    for schedule in schedules:
        schedules_by_day[schedule.day_of_week].append(schedule)

    # Sort schedules by start time within each day
    for day in schedules_by_day:
        schedules_by_day[day].sort(key=lambda x: x.start_time)

    return render_template('doctor/schedule.html', schedules_by_day=schedules_by_day)

@doctor_bp.route('/schedule/<int:schedule_id>/delete')
@login_required
@doctor_required
def delete_schedule(schedule_id):
    schedule = DoctorSchedule.query.get_or_404(schedule_id)

    if schedule.doctor_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('doctor.manage_schedule'))

    try:
        # Check for existing appointments
        existing_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            Appointment.status != 'cancelled'
        ).all()

        # Filter appointments that fall within this schedule
        affected_appointments = [
            apt for apt in existing_appointments
            if apt.datetime.weekday() == schedule.day_of_week
            and schedule.start_time <= apt.datetime.time() <= schedule.end_time
        ]

        if affected_appointments:
            flash('Cannot delete schedule with existing appointments', 'error')
            return redirect(url_for('doctor.manage_schedule'))

        db.session.delete(schedule)
        db.session.commit()
        flash('Schedule removed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while removing schedule', 'error')

    return redirect(url_for('doctor.manage_schedule'))

@doctor_bp.route('/today_appointments_count')
@login_required
@doctor_required
def today_appointments_count():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    count = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.datetime >= today,
        Appointment.datetime < tomorrow,
        Appointment.status != 'cancelled'
    ).count()

    return jsonify({'count': count})

@doctor_bp.route('/appointment/<int:appointment_id>/<action>')
@login_required
@doctor_required
def handle_appointment(appointment_id, action):
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.doctor_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('doctor.dashboard'))

    if action == 'confirm':
        appointment.status = 'confirmed'
        flash('Appointment confirmed')
    elif action == 'cancel':
        appointment.status = 'cancelled'
        flash('Appointment cancelled')

    db.session.commit()
    return redirect(url_for('doctor.dashboard'))