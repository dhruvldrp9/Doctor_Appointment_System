from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import User, Appointment, DoctorSchedule
from datetime import datetime, timedelta
from functools import wraps

patient_bp = Blueprint('patient', __name__)

def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'patient':
            flash('You need patient privileges to access this page.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@patient_bp.route('/dashboard')
@login_required
@patient_required
def dashboard():
    now = datetime.utcnow()
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        Appointment.datetime >= now
    ).order_by(Appointment.datetime).all()
    return render_template('patient/dashboard.html',
                         upcoming_appointments=upcoming_appointments,
                         now=now)

@patient_bp.route('/book_appointment', methods=['GET', 'POST'])
@login_required
@patient_required
def book_appointment():
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('date')
        appointment_time = request.form.get('time')
        notes = request.form.get('notes', '').strip()

        try:
            appointment_datetime = datetime.strptime(
                f"{appointment_date} {appointment_time}",
                '%Y-%m-%d %H:%M'
            )

            now = datetime.utcnow()
            if appointment_datetime <= now:
                flash('Please select a future date and time', 'error')
                return redirect(url_for('patient.book_appointment'))

            one_week_later = now + timedelta(days=7)
            if appointment_datetime > one_week_later:
                flash('Appointments can only be booked within the next 7 days', 'error')
                return redirect(url_for('patient.book_appointment'))

            doctor = User.query.filter_by(id=doctor_id, role='doctor').first()
            if not doctor:
                flash('Selected doctor is not available', 'error')
                return redirect(url_for('patient.book_appointment'))

            schedule = DoctorSchedule.query.filter_by(
                doctor_id=doctor_id,
                day_of_week=appointment_datetime.weekday()
            ).first()

            if not schedule:
                flash('Doctor is not available on the selected day', 'error')
                return redirect(url_for('patient.book_appointment'))

            available_slots = schedule.get_available_slots(appointment_datetime.date())
            if not any(slot.time() == appointment_datetime.time() for slot in available_slots):
                flash('Selected time slot is not available', 'error')
                return redirect(url_for('patient.book_appointment'))

            existing_appointment = Appointment.query.filter_by(
                doctor_id=doctor_id,
                datetime=appointment_datetime,
                status='confirmed'
            ).first()

            if existing_appointment:
                flash('This time slot is already booked', 'error')
                return redirect(url_for('patient.book_appointment'))

            appointment = Appointment(
                doctor_id=doctor_id,
                patient_id=current_user.id,
                datetime=appointment_datetime,
                notes=notes,
                status='pending'
            )

            db.session.add(appointment)
            db.session.commit()

            flash('Appointment requested successfully! You will be notified once the doctor confirms.', 'success')
            return redirect(url_for('patient.dashboard'))

        except ValueError:
            flash('Invalid date or time format', 'error')
            return redirect(url_for('patient.book_appointment'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while booking the appointment. Please try again.', 'error')
            return redirect(url_for('patient.book_appointment'))

    doctors = User.query.filter_by(role='doctor').all()
    today = datetime.utcnow().date()
    next_week = today + timedelta(days=7)

    return render_template('patient/book_appointment.html',
                         doctors=doctors,
                         today=today.strftime('%Y-%m-%d'),
                         max_date=next_week.strftime('%Y-%m-%d'))

@patient_bp.route('/api/doctor/<int:doctor_id>/available_slots')
@login_required
@patient_required
def get_doctor_available_slots(doctor_id):
    try:
        today = datetime.utcnow().date()
        next_week = today + timedelta(days=7)

        schedules = DoctorSchedule.query.filter_by(doctor_id=doctor_id).all()

        available_slots = []
        current_date = today

        while current_date <= next_week:
            for schedule in schedules:
                if current_date.weekday() == schedule.day_of_week:
                    slots = schedule.get_available_slots(current_date)
                    filtered_slots = []
                    for slot in slots:
                        if slot <= datetime.utcnow():
                            continue
                        existing_appointment = Appointment.query.filter_by(
                            doctor_id=doctor_id,
                            datetime=slot,
                            status='confirmed'
                        ).first()
                        if not existing_appointment:
                            filtered_slots.append({
                                'datetime': slot.strftime('%Y-%m-%d %H:%M'),
                                'date': slot.strftime('%Y-%m-%d'),
                                'time': slot.strftime('%H:%M'),
                                'display': slot.strftime('%A, %B %d at %I:%M %p')
                            })

                    if filtered_slots:
                        available_slots.extend(filtered_slots)
            current_date += timedelta(days=1)

        return jsonify({'slots': sorted(available_slots, key=lambda x: x['datetime'])})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@patient_bp.route('/appointment/<int:appointment_id>/cancel')
@login_required
@patient_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.patient_id != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('patient.dashboard'))

    if appointment.datetime <= datetime.utcnow():
        flash('Cannot cancel past appointments', 'error')
        return redirect(url_for('patient.dashboard'))

    appointment.status = 'cancelled'
    db.session.commit()

    flash('Appointment cancelled successfully', 'success')
    return redirect(url_for('patient.dashboard'))