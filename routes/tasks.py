from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Task, Comment, db
from routes.auth import login_required, leader_or_manager_required
from datetime import datetime

task_bp = Blueprint('tasks', __name__)

@task_bp.route('/create', methods=['GET', 'POST'])
@leader_or_manager_required
def create_task():
    if request.method == 'GET':
        current_user = User.query.get(session['user_id'])
        assignable_employees = current_user.get_assignable_employees()
        return render_template('tasks/create.html', 
                             current_user=current_user,
                             assignable_employees=assignable_employees)

    try:
        current_user = User.query.get(session['user_id'])

        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'Medium')
        tags = request.form.get('tags', '').strip()
        assigned_to_id = request.form.get('assigned_to_id')
        deadline_str = request.form.get('deadline', '').strip()  # NEW

        if not title:
            flash('Task title is required.', 'error')
            return redirect(url_for('tasks.create_task'))

        if not assigned_to_id:
            flash('Please select an employee to assign the task to.', 'error')
            return redirect(url_for('tasks.create_task'))

        # Validate assigned user
        assigned_user = User.query.get(assigned_to_id)
        if not assigned_user or not current_user.can_assign_task_to(assigned_user):
            flash('Cannot assign task to selected user.', 'error')
            return redirect(url_for('tasks.create_task'))

        # Parse deadline (NEW)
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid deadline format.', 'error')
                return redirect(url_for('tasks.create_task'))

        # Create new task
        new_task = Task(
            title=title,
            description=description if description else None,
            priority=priority,
            tags=tags if tags else None,
            status='todo',
            assigned_to_id=assigned_to_id,
            created_by_id=current_user.id,
            deadline=deadline  # NEW
        )

        db.session.add(new_task)
        db.session.commit()
        flash(f'Task "{title}" created and assigned to {assigned_user.username}.', 'success')

        # Redirect based on user role
        if current_user.role == 'manager':
            return redirect(url_for('manager.dashboard'))
        elif current_user.is_leader:
            return redirect(url_for('employee.kanban'))
        else:
            return redirect(url_for('employee.dashboard'))

    except Exception as e:
        db.session.rollback()
        print(f"Create task error: {e}")
        flash('An error occurred while creating the task.', 'error')
        return redirect(url_for('tasks.create_task'))


@task_bp.route('/list')
@login_required
def task_list():
    """List all tasks with filtering options - THIS WAS MISSING!"""
    try:
        current_user = User.query.get(session['user_id'])
        
        # Get filter parameters
        status_filter = request.args.get('status')
        priority_filter = request.args.get('priority')
        assigned_filter = request.args.get('assigned')
        
        # Base query based on user role
        if current_user.role == 'admin':
            tasks_query = Task.query
        elif current_user.role == 'manager':
            # Get all tasks for employees under this manager
            employees = User.query.filter_by(manager_id=current_user.id, is_active=True).all()
            if employees:
                employee_ids = [emp.id for emp in employees]
                tasks_query = Task.query.filter(Task.assigned_to_id.in_(employee_ids))
            else:
                tasks_query = Task.query.filter(Task.id == 0)  # No results
        elif current_user.is_leader:
            # Get tasks for direct reports and own tasks
            direct_reports = User.query.filter_by(leader_id=current_user.id, is_active=True).all()
            report_ids = [emp.id for emp in direct_reports] + [current_user.id]
            tasks_query = Task.query.filter(Task.assigned_to_id.in_(report_ids))
        else:
            # Only own tasks
            tasks_query = Task.query.filter_by(assigned_to_id=current_user.id)
        
        # Apply filters
        if status_filter and status_filter != 'all':
            tasks_query = tasks_query.filter_by(status=status_filter)
        
        if priority_filter and priority_filter != 'all':
            tasks_query = tasks_query.filter_by(priority=priority_filter)
        
        if assigned_filter and assigned_filter != 'all':
            tasks_query = tasks_query.filter_by(assigned_to_id=assigned_filter)
        
        # Get filtered tasks
        tasks = tasks_query.order_by(Task.created_at.desc()).all()
        
        # Get assignable employees for filter dropdown
        assignable_employees = []
        if current_user.role == 'manager':
            assignable_employees = User.query.filter_by(manager_id=current_user.id, is_active=True).all()
        elif current_user.is_leader:
            assignable_employees = User.query.filter_by(leader_id=current_user.id, is_active=True).all()
        
        return render_template('tasks/list.html',
                             current_user=current_user,
                             tasks=tasks,
                             assignable_employees=assignable_employees,
                             status_filter=status_filter,
                             priority_filter=priority_filter,
                             assigned_filter=assigned_filter)
                             
    except Exception as e:
        print(f"Task list error: {e}")
        flash('Error loading tasks. Please try again.', 'error')
        return redirect(url_for('home'))

@task_bp.route('/detail/<int:task_id>')
@login_required
def task_detail(task_id):
    try:
        current_user = User.query.get(session['user_id'])
        task = Task.query.get_or_404(task_id)

        # Check permissions - ADDED NULL CHECKS
        assigned_to = task.get_assigned_to()
        can_view = (
            current_user.role == 'admin' or
            task.created_by_id == current_user.id or
            task.assigned_to_id == current_user.id or
            (current_user.role == 'manager' and assigned_to and assigned_to.manager_id == current_user.id) or
            (current_user.is_leader and assigned_to and assigned_to.leader_id == current_user.id)
        )

        if not can_view:
            flash('You do not have permission to view this task.', 'error')
            return redirect(url_for('home'))

        # Get comments
        comments = Comment.query.filter_by(task_id=task_id).order_by(Comment.created_at.desc()).all()

        # Check if user can update this task - ADDED NULL CHECKS
        can_update = (
            current_user.role == 'admin' or
            task.created_by_id == current_user.id or
            task.assigned_to_id == current_user.id or
            (current_user.role == 'manager' and assigned_to and current_user.can_assign_task_to(assigned_to)) or
            (current_user.is_leader and assigned_to and assigned_to.leader_id == current_user.id)
        )

        return render_template('tasks/detail.html',
                             task=task,
                             comments=comments,
                             current_user=current_user,
                             can_update=can_update,
                             assigned_to=assigned_to,
                             created_by=task.get_created_by())

    except Exception as e:
        print(f"Task detail error: {e}")
        flash('Error loading task details.', 'error')
        return redirect(url_for('home'))

@task_bp.route('/my_tasks')
@login_required
def my_tasks():
    """View tasks assigned to current user"""
    try:
        current_user = User.query.get(session['user_id'])
        
        # Get tasks assigned to current user
        assigned_tasks = Task.query.filter_by(assigned_to_id=current_user.id).order_by(Task.created_at.desc()).all()
        
        # If user is a leader or manager, also get tasks they created
        created_tasks = []
        if current_user.is_leader or current_user.role in ['manager', 'admin']:
            created_tasks = Task.query.filter_by(created_by_id=current_user.id).order_by(Task.created_at.desc()).all()
        
        # Group tasks by status
        tasks_by_status = {
            'todo': [task for task in assigned_tasks if task.status == 'todo'],
            'in_progress': [task for task in assigned_tasks if task.status == 'in_progress'],
            'done': [task for task in assigned_tasks if task.status == 'done']
        }
        
        return render_template('tasks/my_tasks.html',
                             current_user=current_user,
                             assigned_tasks=assigned_tasks,
                             created_tasks=created_tasks,
                             tasks_by_status=tasks_by_status)
                             
    except Exception as e:
        print(f"My tasks error: {e}")
        flash('Error loading tasks. Please try again.', 'error')
        return redirect(url_for('home'))

@task_bp.route('/update_status/<int:task_id>', methods=['POST'])
@login_required
def update_task_status(task_id):
    try:
        current_user = User.query.get(session['user_id'])
        task = Task.query.get_or_404(task_id)

        # Check permissions - ADDED NULL CHECKS
        assigned_to = task.get_assigned_to()
        can_update = (
            current_user.role == 'admin' or
            task.created_by_id == current_user.id or
            task.assigned_to_id == current_user.id or
            (current_user.role == 'manager' and assigned_to and assigned_to.manager_id == current_user.id) or
            (current_user.is_leader and assigned_to and assigned_to.leader_id == current_user.id)
        )

        if not can_update:
            flash('You do not have permission to update this task.', 'error')
            return redirect(request.referrer or url_for('home'))

        new_status = request.form.get('status')

        if new_status not in ['todo', 'in_progress', 'done']:
            flash('Invalid status.', 'error')
            return redirect(request.referrer or url_for('home'))

        task.status = new_status
        task.updated_at = datetime.utcnow()
        
        # Track completion time (NEW)
        if new_status == 'done' and not task.completed_at:
            task.completed_at = datetime.utcnow()

        db.session.commit()

        flash('Task status updated successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        print(f"Update task status error: {e}")
        flash('An error occurred while updating the task status.', 'error')

    return redirect(request.referrer or url_for('home'))

@task_bp.route('/add_comment/<int:task_id>', methods=['POST'])
@login_required
def add_comment(task_id):
    try:
        current_user = User.query.get(session['user_id'])

        comment_text = request.form.get('comment', '').strip()

        if not comment_text:
            flash('Comment text is required.', 'error')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

        task = Task.query.get(task_id)
        if not task:
            flash('Task not found.', 'error')
            return redirect(url_for('home'))

        # Check if user can comment on this task - ADDED NULL CHECKS
        assigned_to = task.get_assigned_to()
        can_comment = (
            current_user.role == 'admin' or
            task.created_by_id == current_user.id or
            task.assigned_to_id == current_user.id or
            (current_user.role == 'manager' and assigned_to and assigned_to.manager_id == current_user.id) or
            (current_user.is_leader and assigned_to and assigned_to.leader_id == current_user.id)
        )

        if not can_comment:
            flash('You do not have permission to comment on this task.', 'error')
            return redirect(url_for('tasks.task_detail', task_id=task_id))

        # Create new comment
        new_comment = Comment(
            text=comment_text,
            task_id=task_id,
            author_id=current_user.id
        )

        db.session.add(new_comment)
        db.session.commit()
        flash('Comment added successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        print(f"Add comment error: {e}")
        flash('An error occurred while adding the comment.', 'error')

    return redirect(url_for('tasks.task_detail', task_id=task_id))