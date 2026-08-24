from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quizops_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quizops.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) # Student, Teacher, Admin

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False) # In minutes
    pass_mark = db.Column(db.Float, nullable=False) # Passing Percentage
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option1 = db.Column(db.String(200), nullable=False)
    option2 = db.Column(db.String(200), nullable=False)
    option3 = db.Column(db.String(200), nullable=False)
    option4 = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(200), nullable=False)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    quiz_title = db.Column(db.String(150), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False) # Pass or Fail
    date_taken = db.Column(db.String(50), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- COMMON ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('login'))

# Login Route (Case-Insensitive & Strip Bug Fix)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        username_input = request.form.get('username', '').strip()
        password_input = request.form.get('password', '').strip()

        user = User.query.filter(
            (db.func.lower(User.username) == username_input.lower()) | 
            (db.func.lower(User.email) == username_input.lower())
        ).first()

        if user and user.password == password_input and user.role == role:
            login_user(user)
            flash('Login Successful!', 'success')
            if user.role == 'Student':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'Teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid Credentials or Role Selected!', 'danger')

    return render_template('login.html')

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        existing_user = User.query.filter(
            (db.func.lower(User.username) == username.lower()) | 
            (db.func.lower(User.email) == email.lower())
        ).first()
        
        if existing_user:
            flash('Username or Email already exists!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email, password=password, role='Student')
        db.session.add(new_user)
        db.session.commit()
        flash('Account Created Successfully! Please Login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Logout Route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# --- STUDENT ROUTES ---

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'Student':
        return redirect(url_for('login'))

    available_quizzes = Quiz.query.all()
    history = Result.query.filter_by(user_id=current_user.id).order_by(Result.id.desc()).all()
    
    return render_template('student_dashboard.html', available_quizzes=available_quizzes, history=history)

@app.route('/take_quiz/<int:quiz_id>')
@login_required
def take_quiz(quiz_id):
    if current_user.role != 'Student':
        return redirect(url_for('login'))
        
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    return render_template('take_quiz.html', quiz=quiz, questions=questions)

@app.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    
    score = 0
    total_questions = len(questions)
    
    for question in questions:
        selected_option = request.form.get(f'question_{question.id}')
        if selected_option and selected_option.strip() == question.correct_option.strip():
            score += 1

    if total_questions > 0:
        percentage = (score / total_questions) * 100.0
    else:
        percentage = 0.0

    passing_limit = float(quiz.pass_mark) if quiz.pass_mark else 50.0
    
    if percentage >= passing_limit:
        status = "Pass"
    else:
        status = "Fail"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = Result(
        user_id=current_user.id,
        quiz_id=quiz.id,
        quiz_title=quiz.title,
        score=score,
        total_questions=total_questions,
        percentage=round(percentage, 1),
        status=status,
        date_taken=now
    )
    
    db.session.add(result)
    db.session.commit()

    flash('Quiz submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))

# --- TEACHER ROUTES ---

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'Teacher':
        return redirect(url_for('login'))

    quizzes = Quiz.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher_dashboard.html', quizzes=quizzes)

@app.route('/teacher/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if current_user.role != 'Teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        subject = request.form.get('subject')
        duration = request.form.get('duration')
        pass_mark = request.form.get('pass_mark')

        new_quiz = Quiz(
            title=title,
            subject=subject,
            duration=int(duration),
            pass_mark=float(pass_mark),
            teacher_id=current_user.id
        )
        db.session.add(new_quiz)
        db.session.commit()
        flash('Quiz Created Successfully! Now add questions.', 'success')
        return redirect(url_for('manage_questions', quiz_id=new_quiz.id))

    return render_template('create_quiz.html')

@app.route('/teacher/manage_questions/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def manage_questions(quiz_id):
    if current_user.role != 'Teacher':
        return redirect(url_for('login'))

    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        question_text = request.form.get('question_text')
        option1 = request.form.get('option1')
        option2 = request.form.get('option2')
        option3 = request.form.get('option3')
        option4 = request.form.get('option4')
        correct_option = request.form.get('correct_option')

        new_q = Question(
            quiz_id=quiz.id,
            question_text=question_text,
            option1=option1,
            option2=option2,
            option3=option3,
            option4=option4,
            correct_option=correct_option
        )
        db.session.add(new_q)
        db.session.commit()
        flash('Question Added Successfully!', 'success')
        return redirect(url_for('manage_questions', quiz_id=quiz.id))

    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    return render_template('manage_questions.html', quiz=quiz, questions=questions)

# --- ADMIN ROUTES ---

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'Admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role')

        existing = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing:
            flash('User with this username/email already exists!', 'danger')
        else:
            new_u = User(username=username, email=email, password=password, role=role)
            db.session.add(new_u)
            db.session.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('admin_dashboard'))

    users = User.query.all()
    quizzes = Quiz.query.all()
    return render_template('admin_dashboard.html', users=users, quizzes=quizzes)

# Edit User Route (Fixed 404 Error)
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'Admin':
        return redirect(url_for('login'))

    user_to_edit = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user_to_edit.username = request.form.get('username', '').strip()
        user_to_edit.email = request.form.get('email', '').strip()
        user_to_edit.role = request.form.get('role')
        
        new_password = request.form.get('password')
        if new_password and new_password.strip():
            user_to_edit.password = new_password.strip()

        db.session.commit()
        flash('User details updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_user.html', user=user_to_edit)

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'Admin':
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own admin account!', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
        
    return redirect(url_for('admin_dashboard'))

# --- SETUP DEFAULT ADMIN ---
def create_admin():
    admin = User.query.filter_by(role='Admin').first()
    if not admin:
        default_admin = User(username='admin', email='admin@quizops.com', password='adminpassword', role='Admin')
        db.session.add(default_admin)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(debug=True)