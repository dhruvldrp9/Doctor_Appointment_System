from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, doctor, patient
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    # Doctor specific fields
    specialization_id = db.Column(db.Integer, db.ForeignKey('specialization.id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Specialization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    doctors = db.relationship('User', backref='specialization')

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    doctor = db.relationship('User', foreign_keys=[doctor_id])
    patient = db.relationship('User', foreign_keys=[patient_id])

class DoctorSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0-6 (Monday-Sunday)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_duration = db.Column(db.Integer, default=30)  # Duration in minutes

    doctor = db.relationship('User', backref='schedules')

    def has_overlap(self, other_schedule):
        """Check if this schedule overlaps with another schedule"""
        if self.day_of_week != other_schedule.day_of_week:
            return False

        return not (self.end_time <= other_schedule.start_time or 
                   self.start_time >= other_schedule.end_time)

    def get_available_slots(self, date):
        """Returns available time slots for the given date"""
        if date.weekday() != self.day_of_week:
            return []

        slots = []
        current_time = datetime.combine(date, self.start_time)
        end_datetime = datetime.combine(date, self.end_time)

        while current_time + timedelta(minutes=self.slot_duration) <= end_datetime:
            # Check if the slot is already booked
            existing_appointment = Appointment.query.filter_by(
                doctor_id=self.doctor_id,
                datetime=current_time,
                status='confirmed'
            ).first()

            if not existing_appointment:
                slots.append(current_time)

            current_time += timedelta(minutes=self.slot_duration)

        return slots

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow())

    user = db.relationship('User', backref='notifications')