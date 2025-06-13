from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask.cli import with_appcontext
from sqlalchemy import case
import click

app = Flask(__name__)
app.secret_key = 'secret_key_here'  # Change in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True)

# Task model with priority
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(10), default='Medium')  # High / Medium / Low
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_task_user_id'), nullable=False)

# CLI command to create database tables
@app.cli.command("create-db")
@with_appcontext
def create_db():
    db.create_all()
    click.echo("Database tables created.")

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            return "Username already exists!"
        user = User(username=username, password_hash=password)
        db.session.add(user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.id
            return redirect('/')
        return "Invalid credentials!"
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/login')

# Home page (task list) - with priority sorting
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')
    
    priority_order = case(
        (Task.priority == 'High', 1),
        (Task.priority == 'Medium', 2),
        (Task.priority == 'Low', 3),
        else_=4
    )
    
    tasks = Task.query.filter_by(user_id=session['user_id']).order_by(
        case((Task.due_date != None, Task.due_date), else_=Task.date_created),
        priority_order
    ).all()
    return render_template('index.html', tasks=tasks)

# Add task with priority
@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')
    content = request.form['content']
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority', 'Medium')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M') if due_date_str else None
    new_task = Task(content=content, user_id=session['user_id'], due_date=due_date, priority=priority)
    db.session.add(new_task)
    db.session.commit()
    return redirect('/')

# Delete task
@app.route('/delete/<int:id>')
def delete(id):
    task = Task.query.get_or_404(id)
    if task.user_id != session.get('user_id'):
        return "Unauthorized!"
    db.session.delete(task)
    db.session.commit()
    return redirect('/')

# Toggle completion
@app.route('/complete/<int:id>')
def complete(id):
    task = Task.query.get_or_404(id)
    if task.user_id != session.get('user_id'):
        return "Unauthorized!"
    task.completed = not task.completed
    db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
