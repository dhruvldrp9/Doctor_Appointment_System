from datetime import datetime, timedelta
from flask import session
from models import User, Appointment, DoctorSchedule
from app import db
from werkzeug.security import generate_password_hash

class ChatbotHandler:
    def __init__(self):
        self.commands = {
            'register': self.handle_registration,
            'login': self.handle_login,
            'book': self.handle_booking,
            'schedule': self.handle_schedule,
            'help': self.show_help
        }
        self.current_step = {}

    def process_message(self, message, user=None):
        """Process incoming chat messages and return appropriate responses"""
        message = message.lower().strip()

        # Check if we're in the middle of a flow
        if session.get('chat_flow'):
            return self.continue_flow(message, user)

        # Handle commands
        command = message.split()[0] if message else 'help'
        if command in self.commands:
            return self.commands[command](message, user)

        return {
            'message': "I didn't understand that. Type 'help' to see what I can do!",
            'options': ['help']
        }

    def show_help(self, message=None, user=None):
        """Show available commands based on user role"""
        if not user:
            return {
                'message': "Welcome! Here's what I can help you with:\n"
                          "• register - Create a new account\n"
                          "• login - Log into your account\n"
                          "• help - Show this help message",
                'options': ['register', 'login', 'help']
            }

        if user.role == 'patient':
            return {
                'message': f"Hello {user.first_name}! Here's what I can help you with:\n"
                          "• book - Book a new appointment\n"
                          "• view - View your appointments\n"
                          "• cancel - Cancel an appointment\n"
                          "• help - Show this help message",
                'options': ['book', 'view', 'cancel', 'help']
            }

        if user.role == 'doctor':
            return {
                'message': f"Hello Dr. {user.first_name}! Here's what I can help you with:\n"
                          "• schedule - Manage your availability\n"
                          "• view - View your appointments\n"
                          "• help - Show this help message",
                'options': ['schedule', 'view', 'help']
            }

    def handle_registration(self, message, user=None):
        """Start registration flow"""
        if user:
            return {'message': "You're already logged in!"}

        session['chat_flow'] = 'register'
        session['register_data'] = {}

        return {
            'message': "Let's get you registered! What's your email address?",
            'expect_input': True
        }

    def handle_login(self, message, user=None):
        """Start login flow"""
        if user:
            return {'message': "You're already logged in!"}

        session['chat_flow'] = 'login'
        return {
            'message': "Please enter your email address:",
            'expect_input': True
        }

    def handle_booking(self, message, user=None):
        """Start appointment booking flow"""
        if not user:
            return {
                'message': "Please login first to book an appointment",
                'options': ['login', 'register']
            }

        if user.role != 'patient':
            return {'message': "Only patients can book appointments"}

        # Get available doctors
        doctors = User.query.filter_by(role='doctor').all()
        if not doctors:
            return {'message': "Sorry, no doctors are available at the moment"}

        session['chat_flow'] = 'booking'
        session['booking_data'] = {}

        # Format doctor options
        doctor_options = [f"{idx + 1}. Dr. {doctor.first_name} {doctor.last_name}"
                         for idx, doctor in enumerate(doctors)]

        return {
            'message': "Please select a doctor by entering their number:\n" + 
                      "\n".join(doctor_options),
            'expect_input': True,
            'options': [str(i+1) for i in range(len(doctors))],
            'context': {'doctors': [d.id for d in doctors]}
        }

    def handle_schedule(self, message, user=None):
        """Start schedule management flow"""
        if not user or user.role != 'doctor':
            return {'message': "Only doctors can manage schedules"}

        session['chat_flow'] = 'schedule'
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        return {
            'message': "Which day would you like to manage? (1-7):\n" +
                      "\n".join(f"{idx + 1}. {day}" for idx, day in enumerate(days)),
            'expect_input': True,
            'options': [str(i+1) for i in range(1, 8)]
        }

    def continue_flow(self, message, user):
        """Continue an ongoing chat flow"""
        flow = session.get('chat_flow')

        if flow == 'register':
            return self.continue_registration(message)
        elif flow == 'login':
            return self.continue_login(message)
        elif flow == 'booking':
            return self.continue_booking(message, user)
        elif flow == 'schedule':
            return self.continue_schedule(message, user)

        return {'message': "Something went wrong. Please try again."}

    def continue_registration(self, message):
        """Handle registration flow steps"""
        data = session.get('register_data', {})

        if 'email' not in data:
            # Validate email
            if '@' not in message or '.' not in message:
                return {
                    'message': "That doesn't look like a valid email. Please try again:",
                    'expect_input': True
                }

            # Check if email exists
            if User.query.filter_by(email=message).first():
                return {
                    'message': "This email is already registered. Please login instead:",
                    'options': ['login']
                }

            data['email'] = message
            session['register_data'] = data

            return {
                'message': "Great! Now enter your first name:",
                'expect_input': True
            }

        if 'first_name' not in data:
            data['first_name'] = message
            session['register_data'] = data

            return {
                'message': "And your last name:",
                'expect_input': True
            }

        if 'last_name' not in data:
            data['last_name'] = message
            session['register_data'] = data

            return {
                'message': "Are you a patient or a doctor? (Type 1 or 2)\n"
                          "1. Patient\n"
                          "2. Doctor",
                'expect_input': True,
                'options': ['1', '2']
            }

        if 'role' not in data:
            role = 'patient' if message == '1' else 'doctor'
            data['role'] = role
            session['register_data'] = data

            return {
                'message': "Finally, choose a password:",
                'expect_input': True,
                'password': True
            }

        # Create user
        try:
            user = User(
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role=data['role']
            )
            user.password_hash = generate_password_hash(message)

            db.session.add(user)
            db.session.commit()

            session.pop('chat_flow')
            session.pop('register_data')

            return {
                'message': "Registration successful! Please login:",
                'options': ['login']
            }
        except Exception as e:
            return {'message': "Registration failed. Please try again later."}

    def continue_login(self, message):
        """Handle login flow steps"""
        if 'email' not in session:
            session['email'] = message
            return {
                'message': "Please enter your password:",
                'expect_input': True,
                'password': True
            }

        email = session.pop('email')
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(message):
            session.pop('chat_flow')
            return {
                'message': "Invalid email or password. Please try again:",
                'options': ['login']
            }

        session.pop('chat_flow')
        return {
            'message': f"Welcome back {user.first_name}!",
            'login_success': True,
            'user_id': user.id
        }

    def continue_booking(self, message, user):
        """Handle booking flow steps"""
        data = session.get('booking_data', {})

        if 'doctor_id' not in data:
            try:
                idx = int(message) - 1
                doctors = session.get('context', {}).get('doctors', [])
                doctor_id = doctors[idx]

                data['doctor_id'] = doctor_id
                session['booking_data'] = data

                # Get available slots
                doctor = User.query.get(doctor_id)
                today = datetime.utcnow().date()
                next_week = today + timedelta(days=7)

                available_slots = []
                current_date = today

                while current_date <= next_week:
                    schedules = DoctorSchedule.query.filter_by(
                        doctor_id=doctor_id,
                        day_of_week=current_date.weekday()
                    ).all()

                    for schedule in schedules:
                        slots = schedule.get_available_slots(current_date)
                        available_slots.extend(slots)

                    current_date += timedelta(days=1)

                if not available_slots:
                    session.pop('chat_flow')
                    session.pop('booking_data')
                    return {
                        'message': f"Sorry, Dr. {doctor.first_name} {doctor.last_name} "
                                 "has no available slots in the next 7 days",
                        'options': ['book']
                    }

                # Format slots
                slot_options = [
                    f"{idx + 1}. {slot.strftime('%A, %B %d at %I:%M %p')}"
                    for idx, slot in enumerate(available_slots)
                ]

                session['context']['slots'] = available_slots

                return {
                    'message': "Please select an available time slot by entering its number:\n" +
                              "\n".join(slot_options),
                    'expect_input': True,
                    'options': [str(i+1) for i in range(len(available_slots))]
                }

            except (ValueError, IndexError):
                return {
                    'message': "Invalid selection. Please try again:",
                    'expect_input': True
                }

        if 'datetime' not in data:
            try:
                idx = int(message) - 1
                slots = session.get('context', {}).get('slots', [])
                slot_datetime = slots[idx]

                data['datetime'] = slot_datetime
                session['booking_data'] = data

                return {
                    'message': "Any notes for the doctor? (Type 'no' if none)",
                    'expect_input': True
                }

            except (ValueError, IndexError):
                return {
                    'message': "Invalid selection. Please try again:",
                    'expect_input': True
                }

        # Create appointment
        try:
            notes = None if message.lower() == 'no' else message

            appointment = Appointment(
                doctor_id=data['doctor_id'],
                patient_id=user.id,
                datetime=data['datetime'],
                notes=notes,
                status='pending'
            )

            db.session.add(appointment)
            db.session.commit()

            session.pop('chat_flow')
            session.pop('booking_data')
            session.pop('context')

            return {
                'message': "Appointment requested! You'll be notified once the doctor confirms.",
                'options': ['view']
            }

        except Exception as e:
            return {'message': "Booking failed. Please try again later."}

    def continue_schedule(self, message, user):
        """Handle schedule management flow"""
        data = session.get('schedule_data', {})

        if 'day' not in data:
            try:
                day = int(message) - 1
                data['day'] = day
                session['schedule_data'] = data

                return {
                    'message': "Enter start time (HH:MM, 24-hour format):",
                    'expect_input': True
                }

            except ValueError:
                return {
                    'message': "Invalid day. Please try again:",
                    'expect_input': True
                }

        if 'start_time' not in data:
            try:
                hour, minute = map(int, message.split(':'))
                start_time = f"{hour:02d}:{minute:02d}"

                data['start_time'] = start_time
                session['schedule_data'] = data

                return {
                    'message': "Enter end time (HH:MM, 24-hour format):",
                    'expect_input': True
                }

            except ValueError:
                return {
                    'message': "Invalid time format. Please use HH:MM (e.g., 09:00):",
                    'expect_input': True
                }

        if 'end_time' not in data:
            try:
                hour, minute = map(int, message.split(':'))
                end_time = f"{hour:02d}:{minute:02d}"

                data['end_time'] = end_time
                session['schedule_data'] = data

                return {
                    'message': "Select appointment duration:\n"
                              "1. 15 minutes\n"
                              "2. 30 minutes\n"
                              "3. 45 minutes\n"
                              "4. 60 minutes",
                    'expect_input': True,
                    'options': ['1', '2', '3', '4']
                }

            except ValueError:
                return {
                    'message': "Invalid time format. Please use HH:MM (e.g., 17:00):",
                    'expect_input': True
                }

        # Create schedule
        try:
            durations = {
                '1': 15,
                '2': 30,
                '3': 45,
                '4': 60
            }

            schedule = DoctorSchedule(
                doctor_id=user.id,
                day_of_week=data['day'],
                start_time=datetime.strptime(data['start_time'], '%H:%M').time(),
                end_time=datetime.strptime(data['end_time'], '%H:%M').time(),
                slot_duration=durations[message]
            )

            # Check for overlaps
            existing_schedules = DoctorSchedule.query.filter_by(
                doctor_id=user.id,
                day_of_week=data['day']
            ).all()

            if any(schedule.has_overlap(s) for s in existing_schedules):
                return {
                    'message': "This schedule overlaps with an existing one. Please try different times:",
                    'options': ['schedule']
                }

            db.session.add(schedule)
            db.session.commit()

            session.pop('chat_flow')
            session.pop('schedule_data')

            return {
                'message': "Schedule added successfully!",
                'options': ['schedule', 'view']
            }

        except Exception as e:
            return {'message': "Failed to add schedule. Please try again later."}