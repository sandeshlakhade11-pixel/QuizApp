import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quizops_secret_key_123'

# Permanent Database Config (Render/Railway support with Local Fallback)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///quizops.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
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
    
    # फिक्स: युझरचे नाव HTML मध्ये मिळण्यासाठी ही रिलेशनशिप जोडली आहे
    user = db.relationship('User', backref='results')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- COMMON ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        username_input = request.form.get('username', '').strip()
        password_input = request.form.get('password', '').strip()

        user = User.query.filter(
            (db.func.lower(User.username) == username_input.lower()) | 
            (db.func.lower(User.email) == username_input.lower())
        ).first()

        if user and user.password == password_input and user.role.lower() == role.lower():
            login_user(user)
            flash('Login Successful!', 'success')
            
            user_role = user.role.lower()
            if user_role in ['student', 'user']:
                return redirect(url_for('student_dashboard'))
            elif user_role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user_role == 'admin':
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid Credentials or Role Selected!', 'danger')

    return render_template('login.html')

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
    quizzes = Quiz.query.all() 
    results = Result.query.filter_by(user_id=current_user.id).all()
    return render_template('student_dashboard.html', quizzes=quizzes, results=results)

@app.route('/take_quiz/<int:quiz_id>')
@login_required
def take_quiz(quiz_id):
    if current_user.role.lower() not in ['student', 'user']:
        return redirect(url_for('login'))
        
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    return render_template('take_quiz.html', quiz=quiz, questions=questions)

import datetime

@app.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    score = 0
    total_questions = len(questions)
    
    for q in questions:
        selected_option = request.form.get(f'question_{q.id}')
        
        if selected_option:
            selected = str(selected_option).strip().lower()
            correct = str(q.correct_option).strip().lower() if q.correct_option else ""
            
            if selected == correct:
                score += 1
            elif selected.replace('option ', '') == correct:
                score += 1
            elif selected == 'option a' and str(q.option1).strip().lower() == correct:
                score += 1
            elif selected == 'option b' and str(q.option2).strip().lower() == correct:
                score += 1
            elif selected == 'option c' and str(q.option3).strip().lower() == correct:
                score += 1
            elif selected == 'option d' and str(q.option4).strip().lower() == correct:
                score += 1

    percentage = (score / total_questions * 100) if total_questions > 0 else 0
    passing_limit = getattr(quiz, 'passing_percentage', getattr(quiz, 'passing_limit', 80))
    status = 'Passed' if percentage >= passing_limit else 'Failed'
    
    # Save Result with quiz_title and total_questions
    new_result = Result(
        user_id=current_user.id,
        quiz_id=quiz.id,
        quiz_title=quiz.title,              
        score=score,
        total_questions=total_questions,    
        percentage=percentage,
        status=status,
        date_taken=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    db.session.add(new_result)
    db.session.commit()
    
    flash('Quiz submitted successfully!', 'success')
    return redirect(url_for('student_dashboard'))

# --- TEACHER ROUTES ---

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    quizzes = Quiz.query.filter_by(teacher_id=current_user.id).all()
    quiz_ids = [q.id for q in quizzes]
    
    results = Result.query.filter(Result.quiz_id.in_(quiz_ids)).order_by(Result.id.desc()).all()
    
    return render_template('teacher_dashboard.html', 
                           quizzes=quizzes, 
                           results=results)

@app.route('/create_quiz', methods=['GET', 'POST'])
@app.route('/teacher/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if current_user.role.lower() != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        subject = request.form.get('subject')
        
        # Safe Typecasting
        duration_val = request.form.get('duration')
        pass_mark_val = request.form.get('pass_mark') or request.form.get('passing_percentage') or request.form.get('pass_percentage')

        duration = int(duration_val) if duration_val else 10
        pass_mark = float(pass_mark_val) if pass_mark_val else 50.0

        new_quiz = Quiz(
            title=title,
            subject=subject,
            duration=duration,
            pass_mark=pass_mark,
            teacher_id=current_user.id
        )
        db.session.add(new_quiz)
        db.session.commit()
        flash('Quiz Created Successfully! Now add questions.', 'success')
        return redirect(url_for('manage_questions', quiz_id=new_quiz.id))

    return render_template('create_quiz.html')

@app.route('/manage_questions/<int:quiz_id>', methods=['GET', 'POST'])
@app.route('/teacher/manage_questions/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def manage_questions(quiz_id):
    if current_user.role.lower() != 'teacher':
        return redirect(url_for('login'))

    quiz = Quiz.query.get_or_404(quiz_id)
    
    if request.method == 'POST':
        question_text = request.form.get('question_text')
        option1 = request.form.get('option1') or request.form.get('option_a')
        option2 = request.form.get('option2') or request.form.get('option_b')
        option3 = request.form.get('option3') or request.form.get('option_c')
        option4 = request.form.get('option4') or request.form.get('option_d')
        correct_option = request.form.get('correct_option')

        # जर युझरने 'Option A' सिलेक्ट केले असेल तर त्यानुसार योग्य व्हॅल्यू सेट करणे
        if correct_option == 'Option A':
            correct_val = option1
        elif correct_option == 'Option B':
            correct_val = option2
        elif correct_option == 'Option C':
            correct_val = option3
        elif correct_option == 'Option D':
            correct_val = option4
        else:
            correct_val = correct_option

        new_q = Question(
            quiz_id=quiz.id,
            question_text=question_text,
            option1=option1,
            option2=option2,
            option3=option3,
            option4=option4,
            correct_option=correct_val
        )
        db.session.add(new_q)
        db.session.commit()
        flash('Question Added Successfully!', 'success')
        return redirect(url_for('manage_questions', quiz_id=quiz.id))

    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    try:
        return render_template('add_questions.html', quiz=quiz, questions=questions)
    except:
        return render_template('manage_questions.html', quiz=quiz, questions=questions)

# --- ADMIN ROUTES ---

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role.lower() != 'admin':
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

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        
        new_password = request.form.get('password')
        if new_password:
            user.password = new_password
            
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('edit_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role.lower() != 'admin':
        return redirect(url_for('login'))

    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own admin account!', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/download_certificate/<int:result_id>')
def download_certificate(result_id):
    result = Result.query.get_or_404(result_id)
    user_name = getattr(current_user, 'name', None) or getattr(current_user, 'username', 'Student')
    date_str = result.date_taken.split(' ')[0] if result.date_taken else '2026-08-25'
    
    certificate_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Certificate_{user_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Alex+Brush&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            
            body {{
                background-color: #0f172a;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px 10px;
                font-family: 'Plus Jakarta Sans', sans-serif;
            }}

            .cert-viewport {{
                width: 100%;
                max-width: 1000px;
                display: flex;
                justify-content: center;
            }}

            .cert-card {{
                width: 297mm;
                height: 210mm;
                background: #ffffff;
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 45px 65px;
                border: 12px solid #0f172a;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                flex-shrink: 0;
            }}

            @media screen and (max-width: 1150px) {{
                .cert-viewport {{
                    zoom: 0.75;
                }}
            }}

            @media screen and (max-width: 768px) {{
                .cert-viewport {{
                    zoom: 0.35;
                }}
            }}
            
            .gold-border {{
                position: absolute;
                top: 12px; left: 12px; right: 12px; bottom: 12px;
                border: 2px solid #c5a059;
                pointer-events: none;
                z-index: 1;
            }}
            .inner-thin-border {{
                position: absolute;
                top: 18px; left: 18px; right: 18px; bottom: 18px;
                border: 1px solid #e2e8f0;
                pointer-events: none;
                z-index: 1;
            }}
            
            .watermark {{
                position: absolute;
                top: 50%; left: 50%;
                transform: translate(-50%, -50%);
                font-family: 'Cinzel', serif;
                font-size: 130px;
                font-weight: 900;
                color: rgba(197, 160, 89, 0.03);
                letter-spacing: 15px;
                pointer-events: none;
                white-space: nowrap;
                z-index: 0;
            }}

            .header {{
                text-align: center;
                z-index: 3;
                margin-top: 5px;
            }}
            .brand-badge {{
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-size: 13px;
                font-weight: 700;
                color: #c5a059;
                letter-spacing: 6px;
                text-transform: uppercase;
                margin-bottom: 8px;
            }}
            .cert-title {{
                font-family: 'Cinzel', serif;
                font-size: 42px;
                font-weight: 800;
                color: #0f172a;
                letter-spacing: 6px;
                text-transform: uppercase;
                line-height: 1.1;
            }}
            .gold-line-divider {{
                width: 140px;
                height: 3px;
                background: linear-gradient(90deg, transparent, #c5a059, transparent);
                margin: 15px auto 0 auto;
            }}

            .body-content {{
                text-align: center;
                z-index: 3;
                margin: 15px 0;
            }}
            .present-text {{
                font-size: 14px;
                color: #64748b;
                letter-spacing: 2px;
                text-transform: uppercase;
                font-weight: 600;
            }}
            .student-name {{
                font-family: 'Alex Brush', cursive;
                font-size: 64px;
                color: #0f172a;
                margin: 8px 0 12px 0;
                line-height: 1.1;
            }}
            .reason-text {{
                font-size: 15px;
                color: #475569;
                max-width: 720px;
                margin: 0 auto;
                line-height: 1.5;
            }}
            .course-highlight {{
                font-weight: 700;
                color: #0f172a;
                font-size: 22px;
                font-family: 'Plus Jakarta Sans', sans-serif;
            }}
            
            .metrics-card {{
                display: inline-flex;
                align-items: center;
                gap: 20px;
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                padding: 8px 25px;
                border-radius: 50px;
                margin-top: 20px;
            }}
            .metric-item {{
                font-size: 14px;
                color: #475569;
                font-weight: 600;
            }}
            .metric-val {{
                color: #059669;
                font-weight: 700;
            }}

            .footer {{
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                z-index: 3;
                padding: 0 30px;
                margin-bottom: 5px;
            }}
            .footer-col {{
                text-align: center;
                width: 220px;
            }}
            .sig-text {{
                font-family: 'Alex Brush', cursive;
                font-size: 32px;
                color: #0f172a;
                margin-bottom: 3px;
            }}
            .date-display {{
                font-weight: 700;
                color: #0f172a;
                font-size: 15px;
                margin-bottom: 12px;
            }}
            .sig-line {{
                border-bottom: 1.5px solid #94a3b8;
                margin-bottom: 8px;
            }}
            .footer-label {{
                font-size: 11px;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                font-weight: 700;
            }}
            
            .seal-container {{
                text-align: center;
            }}
            .svg-seal {{
                width: 70px;
                height: 70px;
            }}

            .action-btn-container {{
                margin-top: 25px;
                z-index: 10;
                text-align: center;
            }}
            .download-btn {{
                background: #059669;
                color: #ffffff;
                padding: 14px 32px;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                font-size: 18px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(5, 150, 105, 0.4);
            }}
        </style>
    </head>
    <body>

        <div class="cert-viewport">
            <div id="certificate" class="cert-card">
                <div class="gold-border"></div>
                <div class="inner-thin-border"></div>
                <div class="watermark">QUIZOPS</div>

                <div class="header">
                    <div class="brand-badge">✦ QuizOps Examination Authority ✦</div>
                    <div class="cert-title">Certificate of Excellence</div>
                    <div class="gold-line-divider"></div>
                </div>

                <div class="body-content">
                    <div class="present-text">This official certificate is proudly presented to</div>
                    <div class="student-name">{user_name}</div>
                    
                    <div class="reason-text">
                        for successfully demonstrating outstanding proficiency and completing the examination for<br>
                        <span class="course-highlight">"{result.quiz_title}"</span>
                    </div>

                    <div class="metrics-card">
                        <div class="metric-item">Score: <span class="metric-val">{result.score}/{result.total_questions}</span></div>
                        <div style="color: #cbd5e1;">•</div>
                        <div class="metric-item">Percentage: <span class="metric-val">{result.percentage:.1f}%</span></div>
                        <div style="color: #cbd5e1;">•</div>
                        <div class="metric-item">Result: <span style="color: #059669; font-weight: 800;">PASSED</span></div>
                    </div>
                </div>

                <div class="footer">
                    <div class="footer-col">
                        <div class="date-display">{date_str}</div>
                        <div class="sig-line"></div>
                        <div class="footer-label">Date of Issue</div>
                    </div>

                    <div class="seal-container">
                        <svg class="svg-seal" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <circle cx="50" cy="50" r="45" fill="#F8B500" stroke="#FFFFFF" stroke-width="2"/>
                            <circle cx="50" cy="50" r="38" stroke="#FFFFFF" stroke-dasharray="2 2" stroke-width="1.5"/>
                            <path d="M50 22L56.5 35.5L71.5 37.5L60.5 48L63 63L50 56L37 63L39.5 48L28.5 37.5L43.5 35.5L50 22Z" fill="#FFFFFF"/>
                        </svg>
                        <div class="footer-label" style="margin-top: 3px; color: #c5a059; font-weight: 800;">VERIFIED SEAL</div>
                    </div>

                    <div class="footer-col">
                        <div class="sig-text">QuizOps Authority</div>
                        <div class="sig-line"></div>
                        <div class="footer-label">Authorized Signatory</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="action-btn-container">
            <button onclick="downloadPDF()" class="download-btn">📥 Save PDF Directly</button>
        </div>

        <script>
            function downloadPDF() {{
                window.scrollTo(0, 0);

                const element = document.getElementById('certificate');
                const parentViewport = document.querySelector('.cert-viewport');
                
                let oldZoom = '';
                if (parentViewport) {{
                    oldZoom = parentViewport.style.zoom;
                    parentViewport.style.zoom = '1';
                }}

                const opt = {{
                    margin:       0,
                    filename:     'Certificate_{user_name}.pdf',
                    image:        {{ type: 'jpeg', quality: 1.0 }},
                    html2canvas:  {{ 
                        scale: 2, 
                        useCORS: true,
                        scrollX: 0,
                        scrollY: 0,
                        width: element.offsetWidth,
                        height: element.offsetHeight
                    }},
                    jsPDF:        {{ unit: 'mm', format: 'a4', orientation: 'landscape' }}
                }};

                html2pdf().set(opt).from(element).save().then(() => {{
                    if (parentViewport) {{
                        parentViewport.style.zoom = oldZoom;
                    }}
                }});
            }}
        </script>

    </body>
    </html>
    """
    return certificate_html

# --- SETUP DEFAULT ADMIN ---
def create_admin():
    admin = User.query.filter(db.func.lower(User.role) == 'admin').first()
    if not admin:
        default_admin = User(username='admin', email='admin@quizops.com', password='adminpassword', role='Admin')
        db.session.add(default_admin)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(host='0.0.0.0', port=5000, debug=True)