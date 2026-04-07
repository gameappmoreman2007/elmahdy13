from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'moadalah_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///moadalah.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
db = SQLAlchemy(app)

os.makedirs('static/uploads', exist_ok=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    subject = db.Column(db.String(100))
    image = db.Column(db.String(200), default='📚')
    active = db.Column(db.Boolean, default=True)

class Lecture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    filename = db.Column(db.String(300))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    course = db.relationship('Course', backref='lectures')
    active = db.Column(db.Boolean, default=True)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    return render_template('admin.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        admin_code = request.form.get('admin_code', '')
        if admin_code == 'MOADALAH2026':
            role = 'admin'
        else:
            role = 'student'
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error='الإيميل ده مسجل قبل كده!')
        user = User(name=name, email=email, password=password, role=role, active=True)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.active:
                return render_template('login.html', error='حسابك موقوف! تواصل مع الأدمين.')
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('home'))
        return render_template('login.html', error='الإيميل أو كلمة السر غلط!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/courses')
def courses():
    all_courses = Course.query.filter_by(active=True).all()
    return render_template('courses.html', courses=all_courses)

@app.route('/course/<int:id>')
def course_detail(id):
    course = Course.query.get_or_404(id)
    lectures = Lecture.query.filter_by(course_id=id, active=True).all()
    return render_template('course_detail.html', course=course, lectures=lectures)

@app.route('/admin/add_course', methods=['GET', 'POST'])
def add_course():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        subject = request.form['subject']
        image = request.form['image']
        course = Course(title=title, description=description, subject=subject, image=image)
        db.session.add(course)
        db.session.commit()
        return redirect(url_for('courses'))
    return render_template('add_course.html')

@app.route('/admin/add_lecture', methods=['GET', 'POST'])
def add_lecture():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    all_courses = Course.query.all()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        course_id = request.form['course_id']
        file = request.files['video']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            lecture = Lecture(title=title, description=description, filename=filename, course_id=course_id)
            db.session.add(lecture)
            db.session.commit()
            return redirect(url_for('courses'))
    return render_template('add_lecture.html', courses=all_courses)

@app.route('/watch/<int:id>')
def watch(id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    lecture = Lecture.query.get_or_404(id)
    return render_template('watch.html', lecture=lecture)

@app.route('/profile')
def profile():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/api/students')
def api_students():
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'role': u.role,
        'active': u.active
    } for u in users])

@app.route('/api/toggle_user/<int:id>', methods=['POST'])
def toggle_user(id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'unauthorized'}), 401
    user = User.query.get(id)
    if not user:
        return jsonify({'error': 'user not found'}), 404
    data = request.get_json()
    user.active = data['active']
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)