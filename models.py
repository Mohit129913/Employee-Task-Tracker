from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='employee')  # admin, manager, employee
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)  # For manager approval
    is_leader = db.Column(db.Boolean, default=False)  # Employee can be promoted to leader
    leader_capacity = db.Column(db.Integer, default=None)  # Max direct reports for leaders

    # Relationships
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    leader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Navigation properties
    direct_reports = db.relationship('User', backref=db.backref('manager', remote_side=[id]), lazy=True, foreign_keys=[manager_id])
    led_employees = db.relationship('User', backref=db.backref('leader', remote_side=[id]), lazy=True, foreign_keys=[leader_id])

    # Task relationships
    created_tasks = db.relationship('Task', backref='created_by_user', lazy=True, foreign_keys='Task.created_by_id')
    assigned_tasks = db.relationship('Task', backref='assigned_to_user', lazy=True, foreign_keys='Task.assigned_to_id')

    # Comment relationship
    comments = db.relationship('Comment', backref='author_user', lazy=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'

    def check_password(self, password):
        """Check if provided password matches the hashed password"""
        return check_password_hash(self.password_hash, password)

    def get_assignable_employees(self):
        """Get list of employees this user can assign tasks to"""
        try:
            if self.role == 'admin':
                return User.query.filter_by(role='employee', is_active=True).all()
            elif self.role == 'manager':
                return User.query.filter_by(manager_id=self.id, is_active=True).all()
            elif self.is_leader:
                return User.query.filter_by(leader_id=self.id, is_active=True).all()
            else:
                return []
        except Exception as e:
            print(f"Error getting assignable employees: {e}")
            return []

    def can_assign_task_to(self, user):
        """Check if this user can assign tasks to the given user"""
        try:
            if not user or not user.is_active:
                return False

            if self.role == 'admin':
                return True
            elif self.role == 'manager':
                return user.manager_id == self.id
            elif self.is_leader:
                return user.leader_id == self.id
            else:
                return False
        except Exception as e:
            print(f"Error checking task assignment permission: {e}")
            return False

    def get_all_subordinates(self):
        """Get all employees under this user's management hierarchy"""
        try:
            subordinates = []
            if self.role == 'manager':
                # Get direct reports
                direct_reports = User.query.filter_by(manager_id=self.id, is_active=True).all()
                subordinates.extend(direct_reports)

                # Get employees under leaders
                for report in direct_reports:
                    if report.is_leader:
                        led_employees = User.query.filter_by(leader_id=report.id, is_active=True).all()
                        subordinates.extend(led_employees)
            elif self.is_leader:
                subordinates = User.query.filter_by(leader_id=self.id, is_active=True).all()

            return subordinates
        except Exception as e:
            print(f"Error getting subordinates: {e}")
            return []

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='Medium')  # Low, Medium, High
    status = db.Column(db.String(20), default='todo')  # todo, in_progress, done
    tags = db.Column(db.Text)  # Comma-separated tags
    deadline = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Comments relationship
    comments = db.relationship('Comment', backref='task', lazy=True, cascade='all, delete-orphan')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_overdue(self):
        """Check if task is overdue"""
        from datetime import datetime
        if self.deadline and self.status != 'done':
            return datetime.utcnow() > self.deadline
        return False
    
    def get_time_remaining(self):
        """Get human-readable time remaining until deadline"""
        from datetime import datetime
        if not self.deadline:
            return None
        
        if self.status == 'done':
            return "Completed"
        
        now = datetime.utcnow()
        if now > self.deadline:
            delta = now - self.deadline
            days = delta.days
            hours = delta.seconds // 3600
            if days > 0:
                return f"Overdue by {days} day{'s' if days > 1 else ''}"
            elif hours > 0:
                return f"Overdue by {hours} hour{'s' if hours > 1 else ''}"
            else:
                return "Overdue"
        else:
            delta = self.deadline - now
            days = delta.days
            hours = delta.seconds // 3600
            if days > 0:
                return f"{days} day{'s' if days > 1 else ''} remaining"
            elif hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''} remaining"
            else:
                return "Less than 1 hour remaining"
    
    def get_completion_time(self):
        """Get time taken to complete task (in hours)"""
        if self.status == 'done' and self.completed_at:
            delta = self.completed_at - self.created_at
            hours = delta.total_seconds() / 3600
            days = int(hours // 24)
            remaining_hours = int(hours % 24)
            
            if days > 0:
                return f"{days} day{'s' if days > 1 else ''}, {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
            elif remaining_hours > 0:
                return f"{remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
            else:
                return "Less than 1 hour"
        return None


    def __repr__(self):
        return f'<Task {self.title}>'

    def get_assigned_to(self):
        """Get the user this task is assigned to"""
        try:
            return User.query.get(self.assigned_to_id)
        except Exception as e:
            print(f"Error getting assigned user: {e}")
            return None

    def get_created_by(self):
        """Get the user who created this task"""
        try:
            return User.query.get(self.created_by_id)
        except Exception as e:
            print(f"Error getting creator user: {e}")
            return None

    def get_tags_list(self):
        """Get tags as a list"""
        try:
            if self.tags:
                return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
            return []
        except Exception as e:
            print(f"Error parsing tags: {e}")
            return []

    def get_comments(self):
        """Get all comments for this task"""
        try:
            return Comment.query.filter_by(task_id=self.id).order_by(Comment.created_at.desc()).all()
        except Exception as e:
            print(f"Error getting comments: {e}")
            return []

class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # Relationships
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Comment {self.id}>'

    def get_author(self):
        """Get the user who authored this comment"""
        try:
            return User.query.get(self.author_id)
        except Exception as e:
            print(f"Error getting comment author: {e}")
            return None

    def get_task(self):
        """Get the task this comment belongs to"""
        try:
            return Task.query.get(self.task_id)
        except Exception as e:
            print(f"Error getting comment task: {e}")
            return None
