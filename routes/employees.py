from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Task, Comment, db
from routes.auth import login_required
from datetime import datetime

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        current_user = User.query.get(session['user_id'])

        if current_user.role != 'employee':
            flash('Access denied.', 'error')
            return redirect(url_for('home'))

        # Get tasks assigned to current user
        my_tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()

        # Task statistics
        task_stats = {
            'total': len(my_tasks),
            'todo': len([t for t in my_tasks if t.status == 'todo']),
            'in_progress': len([t for t in my_tasks if t.status == 'in_progress']),
            'done': len([t for t in my_tasks if t.status == 'done'])
        }

        # Recent tasks
        recent_tasks = sorted(my_tasks, key=lambda x: x.created_at, reverse=True)[:5]

        # If user is a leader, get their direct reports and tasks they created
        direct_reports = []
        created_tasks = []
        if current_user.is_leader:
            direct_reports = User.query.filter_by(leader_id=current_user.id, is_active=True).all()
            created_tasks = Task.query.filter_by(created_by_id=current_user.id).all()

        return render_template('dashboard_employee.html',
                             current_user=current_user,
                             my_tasks=my_tasks,
                             task_stats=task_stats,
                             recent_tasks=recent_tasks,
                             direct_reports=direct_reports,
                             created_tasks=created_tasks)

    except Exception as e:
        print(f"Employee dashboard error: {e}")
        flash('Error loading dashboard. Please try again.', 'error')
        return redirect(url_for('home'))

@employee_bp.route('/kanban')
@login_required
def kanban():
    try:
        current_user = User.query.get(session['user_id'])

        if current_user.role != 'employee':
            flash('Access denied.', 'error')
            return redirect(url_for('home'))

        # Get tasks for kanban view
        if current_user.is_leader:
            # Leaders see their own tasks and tasks of their direct reports
            direct_report_ids = [user.id for user in User.query.filter_by(leader_id=current_user.id, is_active=True).all()]
            all_task_ids = [current_user.id] + direct_report_ids
            all_tasks = Task.query.filter(Task.assigned_to_id.in_(all_task_ids)).all()
        else:
            # Regular employees see only their tasks
            all_tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()

        # Group tasks by status
        tasks_by_status = {
            'todo': [task for task in all_tasks if task.status == 'todo'],
            'in_progress': [task for task in all_tasks if task.status == 'in_progress'],
            'done': [task for task in all_tasks if task.status == 'done']
        }

        # Get assignable employees for leaders
        assignable_employees = []
        if current_user.is_leader:
            assignable_employees = User.query.filter_by(leader_id=current_user.id, is_active=True).all()

        return render_template('kanban.html',
                             current_user=current_user,
                             tasks_by_status=tasks_by_status,
                             assignable_employees=assignable_employees,
                             user_role='employee')

    except Exception as e:
        print(f"Employee kanban error: {e}")
        flash('Error loading kanban board. Please try again.', 'error')
        return redirect(url_for('employee.dashboard'))
