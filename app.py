from flask import Flask, render_template, redirect, request, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_bcrypt import Bcrypt  # If you are using bcrypt for password hashing
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import re  # For regular expressions
import json # For JSON handling
import google.generativeai as genai
  # Importing the Google Gemini AI package
from sqlalchemy import and_, or_
import logging  # Import logging
load_dotenv()  # Load environment variables from .env


load_dotenv()  # Load environment variables from .env

API_KEY = os.getenv("GEMINI_API_KEY")
# Configure logging(before app initialization)
logging.basicConfig(level=logging.ERROR)


app = Flask(__name__, instance_relative_config=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)

# Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'patient' or 'doctor'

class DoctorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    experience = db.Column(db.Integer, nullable=False)

class DoctorProfileDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)  # Ensure one profile per user
    phone_number = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    google_maps_url = db.Column(db.String(300), nullable=True)
    city = db.Column(db.String(50), nullable=False)
    area = db.Column(db.String(50), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=True)
    specialization = db.Column(db.String(100), nullable=False)
    qualifications = db.Column(db.String(200), nullable=False)
    certificate_photo = db.Column(db.String(200), nullable=False)
    years_of_experience = db.Column(db.Integer, nullable=False)
    user = db.relationship('User', backref='doctor_profile_details', lazy=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Reviewer
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Reviewed doctor
    rating = db.Column(db.Integer, nullable=False)  # Rating out of 5
    comment = db.Column(db.Text, nullable=False)  # Review comment
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
    patient = db.relationship('User', foreign_keys=[patient_id], backref='reviews_written', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='reviews_received', lazy=True)

class LabResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Reference to the patient
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Reference to the doctor
    file_path = db.Column(db.String(300), nullable=False)  # Path to the uploaded lab result file
    description = db.Column(db.String(200), nullable=True)  # Optional description of the lab result
    upload_date = db.Column(db.DateTime, default=db.func.current_timestamp())  # Auto-filled upload date

    patient = db.relationship('User', foreign_keys=[patient_id], backref='lab_results_received', lazy=True)
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='lab_results_uploaded', lazy=True)

class AvailableSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    slot_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='available')  # 'available', 'booked'

    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='available_slots', lazy=True)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_time = db.Column(db.DateTime, nullable=False)  # Store the appointment time
    reason = db.Column(db.String(200), nullable=True)  # Ensure this column is present
    status = db.Column(db.String(50), default="requested")  # requested, confirmed, rejected
    
    patient = db.relationship('User', foreign_keys=[patient_id], backref='patient_appointments')
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref='doctor_appointments')




if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
# Routes
@app.route('/')
def home():
    return render_template('homepage.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Query the user from the database based on the email
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            # If user exists and password is correct, log the user in
            session['user_id'] = user.id
            if user.role == 'patient':
                return redirect(url_for('patient_dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('doctor_dashboard'))
        else:
            # Flash an error message and redirect to login
            flash('Invalid credentials. Please try again.', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if user:
        # Delete related appointments
        Appointment.query.filter_by(patient_id=user_id).delete()
        Appointment.query.filter_by(doctor_id=user_id).delete()

        # Delete related available slots
        AvailableSlot.query.filter_by(doctor_id=user_id).delete()

        # Delete related reviews
        Review.query.filter_by(patient_id=user_id).delete()
        Review.query.filter_by(doctor_id=user_id).delete()

        # Delete related lab results
        LabResult.query.filter_by(patient_id=user_id).delete()
        LabResult.query.filter_by(doctor_id=user_id).delete()

        if user.role == 'doctor':
            DoctorProfile.query.filter_by(user_id=user_id).delete()
            DoctorProfileDetails.query.filter_by(user_id=user_id).delete()

        db.session.delete(user)
        db.session.commit()
        session.clear()
        flash('Your account has been deleted successfully.', 'success')
    else:
        flash('User not found.', 'danger')

    return redirect(url_for('login'))


@app.route('/logout') 
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')

@app.route('/signup_patient', methods=['GET', 'POST'])
def signup_patient():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if email already exists *before* creating the user
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("This email is already registered. Please login or use a different email.", 'error')
            return render_template('signup_patient.html', name=name, email=email) # Repopulate the form

        # Email is unique, proceed with signup
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password, role='patient')
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('signup_patient.html') # No need to pass anything here for GET


@app.route('/signup_doctor', methods=['GET', 'POST'])
def signup_doctor():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        specialization = request.form['specialization']
        experience = request.form['experience']

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("This email is already registered. Please login or use a different email.", 'error')
            return render_template('signup_doctor.html', name=name, email=email, specialization=specialization, experience=experience) # Repopulate form

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password, role='doctor')
        db.session.add(new_user)
        db.session.commit()

        doctor_profile = DoctorProfile(user_id=new_user.id, specialization=specialization, experience=experience)
        db.session.add(doctor_profile)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('signup_doctor.html')

@app.route('/patient_dashboard')
def patient_dashboard():
    # Fetch all doctor profiles with their associated user details
    results = db.session.query(DoctorProfileDetails, User).join(User, DoctorProfileDetails.user_id == User.id).all()

    # Prepare data for the template
    doctors = []
    for profile, user in results:
        doctors.append({
            'id': user.id,
            'name': user.name,
            'specialization': profile.specialization,
            'city': profile.city,
            'area': profile.area,
            'location': profile.location,
            'profile_picture': profile.profile_picture,
            'google_maps_url': profile.google_maps_url,
            'qualifications': profile.qualifications,
            'years_of_experience': profile.years_of_experience,
        })

    return render_template('index.html', doctors=doctors)

@app.route('/doctor_dashboard')
def doctor_dashboard():
    return render_template('doctor_dashboard.html')

@app.route('/about')
def about():
    return render_template('about.html')  # The "About Us" page template

@app.route('/submit_profile', methods=['POST'])
def submit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.filter_by(id=user_id).first()

    if not user or user.role != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Extract form data
    phone_number = request.form['phone_number']
    location = request.form['location']
    city = request.form['city']
    area = request.form['area']
    specialization = request.form['specialization']
    qualifications = request.form['qualifications']
    years_of_experience = request.form['years_of_experience']
    google_maps_url = request.form['google_maps_url']  # Extract Google Maps URL

    # Handle file uploads
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    profile_picture = request.files.get('profile_picture')
    certificate_photo = request.files.get('certificate_photo')

    # Get existing profile or create new
    doctor_profile = DoctorProfileDetails.query.filter_by(user_id=user.id).first()

    # If no profile exists, create one
    if not doctor_profile:
        doctor_profile = DoctorProfileDetails(
            user_id=user.id,
            phone_number=phone_number,
            location=location,
            city=city,
            area=area,
            specialization=specialization,
            qualifications=qualifications,
            years_of_experience=years_of_experience,
            google_maps_url=google_maps_url,  # Save the Google Maps link
        )

    # Update fields regardless of new or existing profile
    doctor_profile.phone_number = phone_number
    doctor_profile.location = location
    doctor_profile.city = city
    doctor_profile.area = area
    doctor_profile.specialization = specialization
    doctor_profile.qualifications = qualifications
    doctor_profile.years_of_experience = years_of_experience
    doctor_profile.google_maps_url = google_maps_url  # Save the Google Maps link

    # Handle file uploads and update if necessary
    if profile_picture and profile_picture.filename != '':
        profile_picture_filename = f"profile_{user_id}_{profile_picture.filename}"
        profile_picture.save(os.path.join(upload_dir, profile_picture_filename))
        doctor_profile.profile_picture = profile_picture_filename

    if certificate_photo and certificate_photo.filename != '':
        certificate_filename = f"certificate_{user_id}_{certificate_photo.filename}"
        certificate_photo.save(os.path.join(upload_dir, certificate_filename))
        doctor_profile.certificate_photo = certificate_filename

    db.session.add(doctor_profile)  # This will add the profile if it was new or update it if it exists
    db.session.commit()

    flash('Profile updated successfully!', 'success')
    return redirect(url_for('doctor_dashboard'))

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the logged-in user's email
    user_id = session['user_id']
    user = User.query.filter_by(id=user_id).first()

    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('login'))

    # Find the doctor's profile using the user's email or ID
    doctor_profile = DoctorProfileDetails.query.filter_by(user_id=user.id).first()

    if doctor_profile:
        # Delete the profile
        db.session.delete(doctor_profile)
        db.session.commit()
        flash('Doctor profile deleted successfully!', 'success')
    else:
        flash('No profile found to delete.', 'warning')

    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor_profile')
def doctor_profile():
    # Fetch all doctor profiles with their associated user details
    results = db.session.query(DoctorProfileDetails, User).join(User, DoctorProfileDetails.user_id == User.id).all()

    # Prepare data for the template
    doctors = []
    for profile, user in results:
        doctors.append({
            'name': user.name,  # Get the doctor's name from the User table
            'specialization': profile.specialization,
            'city': profile.city,
            'area': profile.area,
            'location': profile.location,
            'profile_picture': profile.profile_picture,
            'google_maps_url': profile.google_maps_url,  # Include Google Maps URL
            'qualifications': profile.qualifications,
            'years_of_experience': profile.years_of_experience,
        })

    return render_template('doctor_profile.html', doctors=doctors)

@app.route('/doctordash_profile')
def doctordash_profile():
    return render_template('doctordash_profile.html')

@app.route('/search_doctors', methods=['GET'])
def search_doctors():
    city = request.args.get('city')
    area = request.args.get('area')
    specialization = request.args.get('specialization')

    # Build the query dynamically with a join to the User table
    query = db.session.query(DoctorProfileDetails, User).join(User, DoctorProfileDetails.user_id == User.id)

    if city:
        query = query.filter(DoctorProfileDetails.city.ilike(f"%{city}%"))
    if area:
        query = query.filter(DoctorProfileDetails.area.ilike(f"%{area}%"))
    if specialization:
        query = query.filter(DoctorProfileDetails.specialization.ilike(f"%{specialization}%"))

    results = query.all()

    # Prepare data for the template
    doctors = []
    for profile, user in results:
        doctors.append({
            'id': user.id,
            'name': user.name,  # Get the doctor's name from the User table
            'specialization': profile.specialization,
            'city': profile.city,
            'area': profile.area,
            'location': profile.location,
            'profile_picture': profile.profile_picture,
            'google_maps_url': profile.google_maps_url,  # Include Google Maps URL
            'qualifications': profile.qualifications,
            'years_of_experience': profile.years_of_experience,
        })

    return render_template('doctor_profile.html', doctors=doctors)

@app.route('/my_profile')
def my_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    doctor_profile = DoctorProfileDetails.query.filter_by(user_id=user_id).first()

    if not doctor_profile:
        flash('Profile not found! Please update your profile.', 'warning')
        return redirect(url_for('doctordash_profile'))

    return render_template('doctor_my_profile.html', profile=doctor_profile)

@app.route('/delete_doctor_profile', methods=['POST'])
def delete_doctor_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.filter_by(id=user_id).first()

    if not user or user.role != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Find the doctor's profile
    doctor_profile = DoctorProfileDetails.query.filter_by(user_id=user.id).first()

    if doctor_profile:
        # Delete only the doctor profile data (not the user account)
        db.session.delete(doctor_profile)
        db.session.commit()
        flash('Your doctor profile information has been deleted.', 'success')
    else:
        flash('No profile found to delete.', 'warning')

    return redirect(url_for('doctor_dashboard'))

@app.route('/patient_reviews', methods=['GET', 'POST'])
def patient_reviews():
    # Handle the search functionality
    city = request.args.get('city')
    area = request.args.get('area')
    specialization = request.args.get('specialization')

    # Build the query dynamically with a join to the User table
    query = db.session.query(DoctorProfileDetails, User.name).join(User, DoctorProfileDetails.user_id == User.id)

    if city:
        query = query.filter(DoctorProfileDetails.city.ilike(f"%{city}%"))
    if area:
        query = query.filter(DoctorProfileDetails.area.ilike(f"%{area}%"))
    if specialization:
        query = query.filter(DoctorProfileDetails.specialization.ilike(f"%{specialization}%"))

    doctors = []
    for profile, name in query.all():
        doctors.append({
            'id': profile.user_id,
            'name': name,
            'specialization': profile.specialization,
            'city': profile.city,
            'area': profile.area,
            'location': profile.location,
            'profile_picture': profile.profile_picture,
            'qualifications': profile.qualifications,
            'years_of_experience': profile.years_of_experience,
        })

    # If a specific doctor is selected, show reviews
    doctor = None
    reviews = []
    if request.args.get('doctor_id'):
        doctor_id = request.args.get('doctor_id')
        doctor = User.query.filter_by(id=doctor_id, role='doctor').first()
        if doctor:       
            reviews = Review.query.filter_by(doctor_id=doctor_id).order_by(Review.timestamp.desc()).all()

    return render_template('patient_reviews.html', doctors=doctors, doctor=doctor, reviews=reviews)

@app.route('/submit_review/<int:doctor_id>', methods=['POST'])
def submit_review(doctor_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    patient_id = session['user_id']
    user = User.query.filter_by(id=patient_id).first()
    
    if not user or user.role != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    rating = request.form['rating']
    comment = request.form['comment']
    
    # Save the review to the database
    review = Review(patient_id=patient_id, doctor_id=doctor_id, rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    
    flash('Your review has been submitted successfully!', 'success')
    return redirect(url_for('patient_reviews', doctor_id=doctor_id))



@app.route('/edit_review/<int:review_id>', methods=['POST'])
def edit_review(review_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    patient_id = session['user_id']
    review = Review.query.filter_by(id=review_id, patient_id=patient_id).first()
    
    if not review:
        flash('Unauthorized action or review not found.', 'danger')
        return redirect(url_for('patient_reviews', doctor_id=review.doctor_id))
    
    # Update the review's details
    review.comment = request.form['comment']
    review.rating = request.form['rating']
    db.session.commit()
    
    flash('Your review has been updated successfully!', 'success')
    return redirect(url_for('patient_reviews', doctor_id=review.doctor_id))

@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    patient_id = session['user_id']
    review = Review.query.filter_by(id=review_id, patient_id=patient_id).first()
    
    if not review:
        flash('Unauthorized action or review not found.', 'danger')
        return redirect(url_for('patient_reviews'))
    
    # Delete the review
    db.session.delete(review)
    db.session.commit()
    
    flash('Your review has been deleted successfully!', 'success')
    return redirect(url_for('patient_reviews', doctor_id=review.doctor_id))

@app.route('/docpatient_reviews')
def docpatient_reviews():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    user = User.query.filter_by(id=doctor_id, role='doctor').first()

    if not user:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Fetch reviews for the logged-in doctor
    reviews = Review.query.filter_by(doctor_id=doctor_id).order_by(Review.timestamp.desc()).all()

    return render_template('docpatient_reviews.html', reviews=reviews)

@app.route('/upload_lab_results', methods=['GET', 'POST'])
def upload_lab_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    user = User.query.filter_by(id=doctor_id).first()

    if not user or user.role != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Handle POST request (when form is submitted)
    if request.method == 'POST':
        # Extract form data
        patient_email = request.form['patient_email']
        description = request.form.get('description', '')

        # Find the patient by email
        patient = User.query.filter_by(email=patient_email, role='patient').first()
        if not patient:
            flash('Patient not found!', 'danger')
            return redirect(url_for('upload_lab_results'))

        # Handle file upload
        lab_file = request.files['lab_file']
        if lab_file and lab_file.filename != '':
            upload_dir = os.path.join(app.root_path, 'static', 'lab_results')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, lab_file.filename)
            lab_file.save(file_path)

            # Save lab result to the database
            lab_result = LabResult(
                patient_id=patient.id,
                doctor_id=doctor_id,
                file_path=f'lab_results/{lab_file.filename}',
                description=description
            )
            db.session.add(lab_result)
            db.session.commit()

            flash('Lab result uploaded successfully!', 'success')
            return redirect(url_for('doctor_dashboard'))
        else:
            flash('Failed to upload lab result. Please try again.', 'danger')
            return redirect(url_for('upload_lab_results'))

    # GET request: Render the upload lab result form
    return render_template('upload_lab_results.html')

@app.route('/view_lab_results')
def view_lab_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    patient_id = session['user_id']
    user = User.query.filter_by(id=patient_id).first()

    if not user or user.role != 'patient':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Fetch lab results for the patient
    lab_results = LabResult.query.filter_by(patient_id=patient_id).all()

    # Prepare data for the template
    results = []
    for result in lab_results:
        doctor = User.query.filter_by(id=result.doctor_id).first()
        results.append({
            'doctor_name': doctor.name,
            'description': result.description,
            'upload_date': result.upload_date,
            'file_path': result.file_path
        })

    return render_template('view_lab_results.html', lab_results=results)

@app.route('/manage_lab_results', methods=['GET'])
def manage_lab_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    user = User.query.filter_by(id=doctor_id, role='doctor').first()

    if not user:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    # Fetch all lab results uploaded by the logged-in doctor
    lab_results = LabResult.query.filter_by(doctor_id=doctor_id).all()

    # Prepare data for rendering
    results = []
    for result in lab_results:
        patient = User.query.filter_by(id=result.patient_id).first()
        results.append({
            'id': result.id,
            'patient_name': patient.name,
            'upload_date': result.upload_date,
            'description': result.description,
            'file_path': result.file_path
        })

    return render_template('manage_lab_results.html', lab_results=results)

@app.route('/update_lab_result/<int:result_id>', methods=['POST'])
def update_lab_result(result_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    lab_result = LabResult.query.filter_by(id=result_id, doctor_id=doctor_id).first()

    if not lab_result:
        flash('Unauthorized access or lab result not found!', 'danger')
        return redirect(url_for('manage_lab_results'))

    # Update the description
    lab_result.description = request.form['description']

    # Handle file upload
    lab_file = request.files.get('lab_file')
    if lab_file and lab_file.filename != '':
        upload_dir = os.path.join(app.root_path, 'static', 'lab_results')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, lab_file.filename)
        lab_file.save(file_path)

        # Update file path
        lab_result.file_path = f'lab_results/{lab_file.filename}'

    db.session.commit()
    flash('Lab result updated successfully!', 'success')
    return redirect(url_for('manage_lab_results'))

@app.route('/delete_lab_result/<int:result_id>', methods=['POST'])
def delete_lab_result(result_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    lab_result = LabResult.query.filter_by(id=result_id, doctor_id=doctor_id).first()

    if not lab_result:
        flash('Unauthorized access or lab result not found!', 'danger')
        return redirect(url_for('manage_lab_results'))

    # Delete the lab result from the database
    db.session.delete(lab_result)
    db.session.commit()
    flash('Lab result deleted successfully!', 'success')
    return redirect(url_for('manage_lab_results'))

@app.route('/doctor_manage_slots', methods=['GET', 'POST'])
def doctor_manage_slots():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    
    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        slot_time_str = f"{date} {time}:00"
        slot_time = datetime.strptime(slot_time_str, '%Y-%m-%d %H:%M:%S')

        slot = AvailableSlot(doctor_id=doctor_id, slot_time=slot_time)
        db.session.add(slot)
        db.session.commit()
        flash('Slot added successfully!', 'success')
    
    slots = AvailableSlot.query.filter_by(doctor_id=doctor_id).all()
    return render_template('manage_timeslots.html', time_slots=slots)

@app.route('/patient_appointments', methods=['GET'])
def patient_appointments():
    city = request.args.get('city')
    area = request.args.get('area')
    specialization = request.args.get('specialization')

    # Build the query dynamically with a join to the User table
    query = db.session.query(DoctorProfileDetails, User).join(User, DoctorProfileDetails.user_id == User.id)

    if city:
        query = query.filter(DoctorProfileDetails.city.ilike(f"%{city}%"))
    if area:
        query = query.filter(DoctorProfileDetails.area.ilike(f"%{area}%"))
    if specialization:
        query = query.filter(DoctorProfileDetails.specialization.ilike(f"%{specialization}%"))

    results = query.all()

    # Prepare data for the template
    doctors = []
    for profile, user in results:
        doctors.append({
            'id': user.id,
            'name': user.name,  # Get the doctor's name from the User table
            'specialization': profile.specialization,
            'city': profile.city,
            'area': profile.area,
            'location': profile.location,
            'profile_picture': profile.profile_picture,
            'google_maps_url': profile.google_maps_url,  # Include Google Maps URL
            'qualifications': profile.qualifications,
            'years_of_experience': profile.years_of_experience,
        })

    return render_template('patient_appointments.html', doctors=doctors)

@app.route('/book_appointment/<int:doctor_id>', methods=['POST'])
def book_appointment(doctor_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    patient_id = session['user_id']
    slot_id = request.form['slot_id']
    reason = request.form['reason']

    slot = AvailableSlot.query.get(slot_id)
    if slot and slot.status == 'available':
        slot.status = 'booked'
        db.session.commit()

        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_time=slot.slot_time,
            reason=reason,
            status='requested'
        )
        db.session.add(appointment)
        db.session.commit()

        flash('Your appointment request has been submitted successfully!', 'success')
    else:
        flash('Selected time slot is no longer available.', 'danger')

    return redirect(url_for('patient_appointments'))
@app.route('/request_appointment/<int:doctor_id>', methods=['POST', 'GET'])
def request_appointment(doctor_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        patient_id = session['user_id']
        slot_id = request.form['slot_id']
        reason = request.form['reason']

        slot = AvailableSlot.query.get(slot_id)
        if slot and slot.status == 'available':
            slot.status = 'booked'
            db.session.commit()

            appointment = Appointment(
                patient_id=patient_id,
                doctor_id=doctor_id,
                appointment_time=slot.slot_time,
                reason=reason,
                status='requested'
            )
            db.session.add(appointment)
            db.session.commit()

            flash('Your appointment request has been submitted successfully!', 'success')
        else:
            flash('Selected time slot is no longer available.', 'danger')

        return redirect(url_for('patient_appointments'))
    
    else:
        doctor = User.query.get(doctor_id)
        available_slots = AvailableSlot.query.filter_by(doctor_id=doctor_id, status='available').all()
        return render_template('request_appointment.html', doctor=doctor, available_slots=available_slots)

@app.route('/doctor_appointments', methods=['GET'])
def doctor_appointments():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    appointments = Appointment.query.filter_by(doctor_id=doctor_id, status='requested').all()
    
    return render_template('doctor_appointments.html', appointments=appointments)

@app.route('/manage_appointment/<int:appointment_id>', methods=['POST'])
def manage_appointment(appointment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=doctor_id).first()
    
    if not appointment:
        flash('Invalid appointment!', 'danger')
        return redirect(url_for('doctor_appointments'))

    action = request.form['action']
    
    if action == 'accept':
        appointment.status = 'confirmed'
    elif action == 'reject':
        appointment.status = 'rejected'
        slot = AvailableSlot.query.filter_by(doctor_id=doctor_id, slot_time=appointment.appointment_time).first()
        slot.status = 'available'
    
    db.session.commit()
    flash(f'Appointment {action} successfully!', 'success')
    return redirect(url_for('doctor_appointments'))

@app.route('/manage_time_slots', methods=['GET', 'POST'])
def manage_time_slots():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    user = User.query.filter_by(id=doctor_id).first()

    if not user or user.role != 'doctor':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']

        new_slot = AvailableSlot(doctor_id=doctor_id, slot_time=f"{date} {time}:00")
        db.session.add(new_slot)
        db.session.commit()

        flash('Time slot added successfully!', 'success')
        return redirect(url_for('manage_time_slots'))

    time_slots = AvailableSlot.query.filter_by(doctor_id=doctor_id).all()

    return render_template('manage_timeslots.html', time_slots=time_slots)

@app.route('/update_time_slot/<int:slot_id>', methods=['POST'])
def update_time_slot(slot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    time_slot = AvailableSlot.query.filter_by(id=slot_id, doctor_id=doctor_id).first()

    if not time_slot:
        flash('Unauthorized access or time slot not found!', 'danger')
        return redirect(url_for('manage_time_slots'))

    date = request.form['date']
    time = request.form['time']
    slot_time_str = f"{date} {time}:00"
    slot_time = datetime.strptime(slot_time_str, '%Y-%m-%d %H:%M:%S')
    
    time_slot.slot_time = slot_time
    db.session.commit()

    flash('Time slot updated successfully!', 'success')
    return redirect(url_for('manage_time_slots'))

@app.route('/delete_time_slot/<int:slot_id>', methods=['POST'])
def delete_time_slot(slot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    time_slot = AvailableSlot.query.filter_by(id=slot_id, doctor_id=doctor_id).first()

    if not time_slot:
        flash('Unauthorized access or time slot not found!', 'danger')
        return redirect(url_for('manage_time_slots'))

    db.session.delete(time_slot)
    db.session.commit()

    flash('Time slot deleted successfully!', 'success')
    return redirect(url_for('manage_time_slots'))

@app.route('/available_slots/<int:doctor_id>')
def available_slots(doctor_id):
    slots = AvailableSlot.query.filter_by(doctor_id=doctor_id, status='available').all()
    return jsonify([{
        'id': slot.id,
        'slot_time': slot.slot_time.isoformat()
    } for slot in slots])

@app.route('/my_appointments')
def my_appointments():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    patient_id = session['user_id']
    appointments = Appointment.query.filter_by(patient_id=patient_id, status='confirmed').all()

    return render_template('my_appointments.html', appointments=appointments)
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set.")


@app.route('/ai_diagnosis', methods=['POST'])
def ai_diagnosis():
    data = request.get_json()
    patient_input = data.get('input')

    if not patient_input:
        return jsonify({'error': 'Please describe your symptoms and location'}), 400

    try:
        analysis_result = analyze_patient_input(patient_input)
        if 'error' in analysis_result:
            return jsonify({'error': analysis_result['error']}), 400

        specialty = analysis_result.get('specialty', '').strip()
        city = analysis_result.get('city', '').strip()  # Extract city
        area = analysis_result.get('area', '').strip()  # Extract area

        location_info = {'city': city, 'area': area}  # Create location dictionary

        doctors = query_doctors(specialty, location_info)  # Pass location_info

        if not doctors:
            return jsonify({
                'message': 'No doctors found matching your symptoms and location',
                'suggested_specialty': specialty,
                'suggested_location': location_info, # Return location info
                'doctors': []
            })

        return jsonify({
            'suggested_specialty': specialty,
            'suggested_location': location_info,  # Return location info
            'doctors': doctors
        })

    except Exception as e:
        app.logger.error(f"AI diagnosis error: {str(e)}")
        return jsonify({'error': 'Failed to process your request'}), 500


def analyze_patient_input(input_text):
    client = genai.Client(api_key=API_KEY)
    prompt = f"""Analyze this medical query and extract:
    1. Medical specialty needed (e.g., Dentist for toothache)
    2. City
    3. Area

    Query: {input_text}

    Respond ONLY with JSON format: {{"specialty": "...", "city": "...", "area": "..."}}
    Use "General Physician" if specialty unclear, and empty strings for missing location parts."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return parse_ai_response(response.text)

    except Exception as e:
        app.logger.error(f"AI service error: {str(e)}")  # Log the error for debugging
        return {'error': f"AI service error: {str(e)}"}


def parse_ai_response(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            result = json.loads(json_str)
            return {
                'specialty': result.get('specialty', 'General Physician'),
                'city': result.get('city', '').strip(),
                'area': result.get('area', '').strip()
            }
        else:
            app.logger.error(f"Could not find JSON in AI response: {text}")
            return {'error': 'Could not understand medical query. Please be more specific.'}
    except (json.JSONDecodeError, AttributeError) as e:
        app.logger.error(f"Failed to parse AI response: {text}. Error: {e}")
        return {'error': 'Could not understand medical query. Please be more specific.'}


def query_doctors(specialty, location_info):
    query = db.session.query(DoctorProfileDetails, User).join(User)
    filters = []

    specialty_filter = DoctorProfileDetails.specialization.ilike(f"%{specialty}%")
    filters.append(specialty_filter)

    location_filters = []
    if location_info.get('city'):
        location_filters.append(DoctorProfileDetails.city.ilike(f"%{location_info['city']}%"))
    if location_info.get('area'):
        location_filters.append(DoctorProfileDetails.area.ilike(f"%{location_info['area']}%"))

    if location_filters:
        filters.append(or_(*location_filters))  # Use OR for city/area

    results = query.filter(and_(*filters)).all()  # Use AND to combine specialty and location

    doctors = []
    for profile, user in results:
        doctors.append({
            'id': user.id,
            'name': user.name,
            'specialization': profile.specialization,
            'city': profile.city,
            'area': profile.area,
            'experience': profile.years_of_experience,
            'profile_pic': profile.profile_picture,
            'map_url': profile.google_maps_url,
            'qualifications': profile.qualifications
        })

    return doctors


@app.route('/ai_suggestion')
def ai_suggestion():
    return render_template('ai_suggestions.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)