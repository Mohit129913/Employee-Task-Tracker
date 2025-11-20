from flask import Flask, session, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash
from datetime import datetime
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'task-tracker-no-js-secret-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///task_tracker_no_js.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import and initialize database from models
from models import db, User, Task, Comment
db.init_app(app)

# Import blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp  
from routes.managers import manager_bp
from routes.tasks import task_bp
from routes.employees import employee_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(manager_bp, url_prefix='/manager')
app.register_blueprint(task_bp, url_prefix='/tasks')
app.register_blueprint(employee_bp, url_prefix='/employee')

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_active:
        session.clear()
        return redirect(url_for('auth.login'))

    # Redirect based on role
    if user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif user.role == 'manager':
        if not user.is_approved:
            flash('Your account is pending approval from admin.', 'warning')
            return redirect(url_for('auth.logout'))
        return redirect(url_for('manager.dashboard'))
    else:  # employee
        return redirect(url_for('employee.dashboard'))

@app.context_processor
def inject_user():
    """Make current user and User model available in all templates"""
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return dict(current_user=user, User=User)
    return dict(current_user=None, User=User)

def seed_database():
    """Seed the database with initial data"""
    try:
        print("Creating database tables...")
        db.create_all()

        # Check if admin already exists
        admin = User.query.filter_by(username='Mohit Nhayade').first()
        if not admin:
            admin = User(
                username='Mohit Nhayade',
                email='admin@example.com',
                password_hash=generate_password_hash('Mohit@129913'),
                role='admin',
                is_active=True,
                is_approved=True
            )
            db.session.add(admin)
            print("✓ Admin user created: Mohit Nhayade")

        # Create demo manager
        demo_manager = User.query.filter_by(username='manager_demo').first()
        if not demo_manager:
            demo_manager = User(
                username='manager_demo',
                email='manager@example.com',
                password_hash=generate_password_hash('Manager123'),
                role='manager',
                is_active=True,
                is_approved=True
            )
            db.session.add(demo_manager)
            db.session.flush()  # Get ID without full commit
            print("✓ Manager created: manager_demo")

        # Create demo employees
        employees_data = [
            {'username': 'john_doe', 'email': 'john@example.com', 'is_leader': True, 'capacity': 3},
            {'username': 'jane_smith', 'email': 'jane@example.com', 'is_leader': False, 'capacity': None},
            {'username': 'bob_wilson', 'email': 'bob@example.com', 'is_leader': False, 'capacity': None},
            {'username': 'alice_brown', 'email': 'alice@example.com', 'is_leader': False, 'capacity': None}
        ]

        created_employees = []
        for emp_data in employees_data:
            existing = User.query.filter_by(username=emp_data['username']).first()
            if not existing:
                employee = User(
                    username=emp_data['username'],
                    email=emp_data['email'],
                    password_hash=generate_password_hash('Employee123'),
                    role='employee',
                    is_active=True,
                    is_approved=True,
                    is_leader=emp_data['is_leader'],
                    leader_capacity=emp_data['capacity'],
                    manager_id=demo_manager.id if demo_manager else None
                )
                db.session.add(employee)
                created_employees.append(employee)
                print(f"✓ Employee created: {emp_data['username']}")

        db.session.flush()  # Get employee IDs

        # Set up leader relationships
        if created_employees:
            leader = None
            for emp in created_employees:
                if emp.is_leader:
                    leader = emp
                    break

            if leader:
                # Assign some employees to the leader
                for i, emp in enumerate(created_employees[1:3]):  # Skip leader, take next 2
                    emp.leader_id = leader.id
                    print(f"✓ {emp.username} assigned to leader {leader.username}")

        # Create demo tasks
        tasks_data = [
            {'title': 'User Authentication Setup', 'desc': 'Implement secure login system with role-based access', 'priority': 'High', 'status': 'in_progress'},
            {'title': 'Dashboard UI Design', 'desc': 'Create modern and responsive dashboard interface', 'priority': 'Medium', 'status': 'todo'},
            {'title': 'Database Optimization', 'desc': 'Optimize database queries and add proper indexing', 'priority': 'Low', 'status': 'done'},
            {'title': 'API Integration', 'desc': 'Connect and integrate third-party APIs for enhanced functionality', 'priority': 'Medium', 'status': 'todo'},
            {'title': 'Mobile Responsiveness', 'desc': 'Ensure application works seamlessly on mobile devices', 'priority': 'High', 'status': 'in_progress'},
            {'title': 'Testing & Quality Assurance', 'desc': 'Comprehensive testing of all features and functionality', 'priority': 'High', 'status': 'todo'},
            {'title': 'Documentation Update', 'desc': 'Update user documentation and technical guides', 'priority': 'Low', 'status': 'done'},
            {'title': 'Performance Monitoring', 'desc': 'Set up monitoring and performance tracking', 'priority': 'Medium', 'status': 'in_progress'}
        ]

        if created_employees and demo_manager:
            for i, task_data in enumerate(tasks_data):
                existing = Task.query.filter_by(title=task_data['title']).first()
                if not existing:
                    assigned_emp = created_employees[i % len(created_employees)]
                    creator = demo_manager if i % 2 == 0 else created_employees[0]

                    task = Task(
                        title=task_data['title'],
                        description=task_data['desc'],
                        priority=task_data['priority'],
                        status=task_data['status'],
                        tags='demo,sample,project',
                        assigned_to_id=assigned_emp.id,
                        created_by_id=creator.id
                    )
                    db.session.add(task)
                    print(f"✓ Task created: {task_data['title']}")

        # Commit all changes
        db.session.commit()
        print("✓ Database seeding completed successfully!")

    except Exception as e:
        print(f"✗ Error seeding database: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    with app.app_context():
        seed_database()

    print("\n" + "="*70)
    print("🚀 TASK TRACKER PRO (NO JavaScript) - SERVER STARTING")
    print("="*70)
    print("👨‍💼 Admin Login:")
    print("   Username: Mohit Nhayade")
    print("   Password: Mohit@129913")
    print("\n👔 Manager Login:")
    print("   Username: manager_demo") 
    print("   Password: Manager123")
    print("\n👤 Employee Login:")
    print("   Username: john_doe")
    print("   Password: Employee123")
    print("\n🌐 Access URL: http://127.0.0.1:5000")
    print("="*70)
    print()

    app.run(debug=True, port=5000, host='127.0.0.1')
