from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Task, Comment, db
from routes.auth import login_required, manager_required
from werkzeug.security import generate_password_hash

manager_bp = Blueprint('manager', __name__)

@manager_bp.route('/dashboard')
@manager_required
def dashboard():
    try:
        current_user = User.query.get(session['user_id'])
        
        # Get employees under this manager
        employees = User.query.filter_by(manager_id=current_user.id, is_active=True).all()
        
        # Get leaders under this manager
        leaders = [emp for emp in employees if emp.is_leader]
        
        # Get tasks for the team
        team_tasks = []
        if employees:
            employee_ids = [emp.id for emp in employees]
            team_tasks = Task.query.filter(Task.assigned_to_id.in_(employee_ids)).all()
        
        # Task statistics
        task_stats = {
            'total': len(team_tasks),
            'todo': len([t for t in team_tasks if t.status == 'todo']),
            'in_progress': len([t for t in team_tasks if t.status == 'in_progress']),
            'done': len([t for t in team_tasks if t.status == 'done'])
        }
        
        # Recent activities
        recent_tasks = sorted(team_tasks, key=lambda x: x.created_at, reverse=True)[:5]
        
        return render_template('dashboard_manager.html',
                             current_user=current_user,
                             employees=employees,
                             leaders=leaders,
                             team_tasks=team_tasks,
                             task_stats=task_stats,
                             recent_tasks=recent_tasks)
                             
    except Exception as e:
        print(f"Manager dashboard error: {e}")
        flash('Error loading dashboard. Please try again.', 'error')
        return redirect(url_for('home'))

@manager_bp.route('/kanban')
@manager_required
def kanban():
    try:
        current_user = User.query.get(session['user_id'])
        
        # Get all employees under this manager
        employees = User.query.filter_by(manager_id=current_user.id, is_active=True).all()
        
        # Get all tasks for the team
        team_tasks = []
        if employees:
            employee_ids = [emp.id for emp in employees]
            team_tasks = Task.query.filter(Task.assigned_to_id.in_(employee_ids)).all()
        
        # Group tasks by status
        tasks_by_status = {
            'todo': [task for task in team_tasks if task.status == 'todo'],
            'in_progress': [task for task in team_tasks if task.status == 'in_progress'],
            'done': [task for task in team_tasks if task.status == 'done']
        }
        
        # Get assignable employees
        assignable_employees = employees
        
        return render_template('kanban.html',
                             current_user=current_user,
                             tasks_by_status=tasks_by_status,
                             assignable_employees=assignable_employees,
                             user_role='manager')
                             
    except Exception as e:
        print(f"Manager kanban error: {e}")
        flash('Error loading kanban board. Please try again.', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/promote_leader/<int:employee_id>', methods=['POST'])
@manager_required
def promote_leader(employee_id):
    """Promote employee to team leader"""
    try:
        current_user = User.query.get(session['user_id'])
        employee = User.query.get_or_404(employee_id)
        
        # Check if this employee belongs to current manager
        if employee.manager_id != current_user.id:
            flash('You can only promote employees in your team.', 'error')
            return redirect(url_for('manager.dashboard'))
        
        # Check if employee is already a leader
        if employee.is_leader:
            flash(f'{employee.username} is already a team leader.', 'warning')
            return redirect(url_for('manager.dashboard'))
        
        # Promote employee to leader
        employee.is_leader = True
        employee.leader_capacity = 5  # Default capacity of 5 direct reports
        
        db.session.commit()
        flash(f'🎉 {employee.username} has been promoted to Team Leader!', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Promote leader error: {e}")
        flash('An error occurred while promoting the employee.', 'error')
    
    return redirect(url_for('manager.dashboard'))

@manager_bp.route('/demote_leader/<int:employee_id>', methods=['POST'])
@manager_required
def demote_leader(employee_id):
    """Demote team leader back to regular employee"""
    try:
        current_user = User.query.get(session['user_id'])
        employee = User.query.get_or_404(employee_id)
        
        # Check if this employee belongs to current manager
        if employee.manager_id != current_user.id:
            flash('You can only demote employees in your team.', 'error')
            return redirect(url_for('manager.dashboard'))
        
        # Check if employee is actually a leader
        if not employee.is_leader:
            flash(f'{employee.username} is not a team leader.', 'warning')
            return redirect(url_for('manager.dashboard'))
        
        # Check if leader has direct reports
        direct_reports = User.query.filter_by(leader_id=employee.id, is_active=True).all()
        if direct_reports:
            flash(f'Cannot demote {employee.username}. Please reassign their {len(direct_reports)} direct report(s) first.', 'error')
            return redirect(url_for('manager.dashboard'))
        
        # Demote leader to regular employee
        employee.is_leader = False
        employee.leader_capacity = None
        
        db.session.commit()
        flash(f'{employee.username} has been demoted to regular employee.', 'info')
        
    except Exception as e:
        db.session.rollback()
        print(f"Demote leader error: {e}")
        flash('An error occurred while demoting the leader.', 'error')
    
    return redirect(url_for('manager.dashboard'))

@manager_bp.route('/assign_to_leader', methods=['POST'])
@manager_required
def assign_to_leader():
    """Assign employees to team leaders"""
    try:
        current_user = User.query.get(session['user_id'])
        employee_id = request.form.get('employee_id')
        leader_id = request.form.get('leader_id')
        
        if not employee_id or not leader_id:
            flash('Please select both employee and leader.', 'error')
            return redirect(url_for('manager.dashboard'))
        
        employee = User.query.get_or_404(employee_id)
        leader = User.query.get_or_404(leader_id)
        
        # Validate permissions
        if (employee.manager_id != current_user.id or 
            leader.manager_id != current_user.id or 
            not leader.is_leader):
            flash('Invalid assignment request.', 'error')
            return redirect(url_for('manager.dashboard'))
        
        # Check leader capacity
        current_reports = User.query.filter_by(leader_id=leader.id, is_active=True).count()
        if leader.leader_capacity and current_reports >= leader.leader_capacity:
            flash(f'{leader.username} has reached maximum capacity ({leader.leader_capacity} direct reports).', 'error')
            return redirect(url_for('manager.dashboard'))
        
        # Assign employee to leader
        old_leader_name = employee.leader.username if employee.leader_id else 'None'
        employee.leader_id = leader.id
        
        db.session.commit()
        flash(f'{employee.username} has been assigned from {old_leader_name} to team leader {leader.username}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Assign to leader error: {e}")
        flash('An error occurred while assigning to leader.', 'error')
    
    return redirect(url_for('manager.dashboard'))
