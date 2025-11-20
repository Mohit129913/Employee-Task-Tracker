from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from models import User, db
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('auth.login'))

            user = User.query.get(session['user_id'])
            if not user or user.role != role:
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('home'))

            if role == 'manager' and not user.is_approved:
                flash('Your account is pending approval.', 'warning')
                return redirect(url_for('auth.logout'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))

        user = User.query.get(session['user_id'])
        if not user or user.role != 'manager':
            flash('Access denied. Manager privileges required.', 'error')
            return redirect(url_for('home'))

        if not user.is_approved:
            flash('Your account is pending approval.', 'warning')
            return redirect(url_for('auth.logout'))

        return f(*args, **kwargs)
    return decorated_function

def leader_or_manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('auth.login'))

        user = User.query.get(session['user_id'])
        if not user:
            return redirect(url_for('auth.login'))

        has_permission = False
        if user.role == 'manager' and user.is_approved:
            has_permission = True
        elif user.role == 'employee' and user.is_leader:
            has_permission = True
        elif user.role == 'admin':
            has_permission = True

        if not has_permission:
            flash('Access denied. Manager or Leader privileges required.', 'error')
            return redirect(url_for('home'))

        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(username=username, is_active=True).first()

        if user and user.check_password(password):
            # Check if manager is approved
            if user.role == 'manager' and not user.is_approved:
                flash('Your account is pending admin approval. Please wait for approval.', 'warning')
                return render_template('login.html')

            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role

            flash(f'Welcome back, {user.username}!', 'success')

            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'manager':
                return redirect(url_for('manager.dashboard'))
            else:
                return redirect(url_for('employee.dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '').strip()

        # Basic validation
        if not username or not email or not password or not role:
            flash('All fields are required.', 'error')
            return render_template('signup.html')

        if role not in ['manager', 'employee']:
            flash('Invalid role selected.', 'error')
            return render_template('signup.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('signup.html')

        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            if existing_user.username == username:
                flash('Username already exists. Please choose a different one.', 'error')
            else:
                flash('Email already exists. Please use a different email.', 'error')
            return render_template('signup.html')

        try:
            # Create new user
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                is_active=True,
                is_approved=True if role == 'employee' else False  # Managers need approval
            )

            db.session.add(new_user)
            db.session.commit()

            if role == 'manager':
                flash('Manager account created successfully! Please wait for admin approval before logging in.', 'info')
            else:
                flash('Employee account created successfully! You can now log in.', 'success')

            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating your account. Please try again.', 'error')
            print(f"Signup error: {e}")

    return render_template('signup.html')

@auth_bp.route('/logout')
def logout():
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye {username}! You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
