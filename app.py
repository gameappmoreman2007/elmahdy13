from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.secret_key = 'moadalah_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///moadalah.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
db = SQLAlchemy(app)

# إنشاء فولدر الرفع
os.makedirs('static/uploads', exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ====== Models ======
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

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    expiry_date = db.Column(db.Date)
    user = db.relationship('User', backref='subscription')

with app.app_context():
    db.create_all()

# ====== Helper Function ======
def user_has_active_subscription(user_id):
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if not sub:
        return False
    return sub.expiry_date >= date.today()

# ====== Error Handler ======
@app.errorhandler(RequestEntityTooLarge)
def handle_big_file(e):
    return "حجم الملف كبير جدًا!", 413

# ====== Routes ======
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
        role = 'admin' if admin_code == 'MOADALAH2026' else 'student'
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
            return redirect(url_for('admin' if user.role == 'admin' else 'home'))
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
        course_id = int(request.form['course_id'])
        file = request.files['video']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            lecture = Lecture(title=title, description=description, filename=filename, course_id=course_id)
            db.session.add(lecture)
            db.session.commit()
            return redirect(url_for('courses'))
        else:
            return render_template('add_lecture.html', courses=all_courses, error='صيغة الملف غير مسموح بها!')
    return render_template('add_lecture.html', courses=all_courses)

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

# ====== Watch Lecture with Subscription Check ======
@app.route('/watch/<int:id>')
def watch(id):
    if not session.get('user_id'):
        return redirect(url_for('login'))

    lecture = Lecture.query.get_or_404(id)
    user_id = session['user_id']
    is_subscribed = user_has_active_subscription(user_id)

    # السماح بالقديم فقط إذا الاشتراك انتهى
    if not is_subscribed and lecture.id > 5:  # الدروس بعد id 5 تعتبر جديدة
        return render_template('subscription_needed.html')

    return render_template('watch.html', lecture=lecture, subscribed=is_subscribed)

# ====== Renew Routes ======
@app.route('/renew')
def renew():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template('renew.html')

@app.route('/admin/add_subscription/<int:user_id>', methods=['POST'])
def add_subscription(user_id):
    if session.get('role') != 'admin':
        return "Unauthorized"

    days = int(request.form['days'])
    sub = Subscription.query.filter_by(user_id=user_id).first()

    if sub:
        sub.expiry_date = max(sub.expiry_date, date.today()) + timedelta(days=days)
    else:
        sub = Subscription(user_id=user_id, expiry_date=date.today() + timedelta(days=days))

    db.session.add(sub)
    db.session.commit()
    return "Subscription added!"

# ====== Run Server ======
if __name__ == '__main__':
    app.run(debug=True, port=5000)