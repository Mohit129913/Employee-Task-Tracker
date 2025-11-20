from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import User, Task, Comment, db
from routes.auth import login_required, role_required
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    try:
        # Get statistics
        total_managers = User.query.filter_by(role='manager', is_approved=True, is_active=True).count()
        total_employees = User.query.filter_by(role='employee', is_active=True).count()
        pending_managers = User.query.filter_by(role='manager', is_approved=False, is_active=True).count()
        total_tasks = Task.query.count()
        
        # Get task status breakdown
        task_stats = db.session.query(
            Task.status,
            func.count(Task.id).label('count')
        ).group_by(Task.status).all()
        
        task_status_dict = {}
        for status, count in task_stats:
            task_status_dict[status] = count
        
        # Get pending manager requests
        pending_manager_list = User.query.filter_by(
            role='manager', 
            is_approved=False, 
            is_active=True
        ).all()
        
        # Get recent activities
        recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
        recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()
        
        return render_template('dashboard_admin.html',
                             total_managers=total_managers,
                             total_employees=total_employees,
                             pending_managers=pending_managers,
                             total_tasks=total_tasks,
                             task_status_dict=task_status_dict,
                             pending_manager_list=pending_manager_list,
                             recent_tasks=recent_tasks,
                             recent_comments=recent_comments)
                             
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        flash('Error loading dashboard. Please try again.', 'error')
        return redirect(url_for('home'))

@admin_bp.route('/approve_manager/<int:manager_id>', methods=['POST'])
@role_required('admin')
def approve_manager(manager_id):
    try:
        manager = User.query.get_or_404(manager_id)
        
        if manager.role != 'manager':
            flash('Invalid user type.', 'error')
            return redirect(url_for('admin.dashboard'))
        
        action = request.form.get('action')
        
        if action == 'approve':
            manager.is_approved = True
            manager.is_active = True
            flash(f'Manager {manager.username} has been approved successfully.', 'success')
        elif action == 'reject':
            manager.is_approved = False
            manager.is_active = False
            flash(f'Manager {manager.username} has been rejected.', 'info')
        else:
            flash('Invalid action.', 'error')
            return redirect(url_for('admin.dashboard'))
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"Manager approval error: {e}")
        flash('An error occurred while processing the request.', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/manage_employees')
@role_required('admin')
def manage_employees():
    """Admin page to manage employee-manager assignments"""
    try:
        # Get all employees and managers
        employees = User.query.filter_by(role='employee', is_active=True).all()
        managers = User.query.filter_by(role='manager', is_approved=True, is_active=True).all()
        
        # Group employees by their manager
        employees_by_manager = {}
        unassigned_employees = []
        
        for employee in employees:
            if employee.manager_id:
                manager = User.query.get(employee.manager_id)
                if manager:
                    if manager.username not in employees_by_manager:
                        employees_by_manager[manager.username] = {
                            'manager': manager,
                            'employees': []
                        }
                    employees_by_manager[manager.username]['employees'].append(employee)
                else:
                    unassigned_employees.append(employee)
            else:
                unassigned_employees.append(employee)
        
        return render_template('admin/manage_employees.html',
                             employees=employees,
                             managers=managers,
                             employees_by_manager=employees_by_manager,
                             unassigned_employees=unassigned_employees)
                             
    except Exception as e:
        print(f"Manage employees error: {e}")
        flash('Error loading employee management page.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/assign_manager', methods=['POST'])
@role_required('admin')
def assign_manager():
    """Assign or reassign employee to manager"""
    try:
        employee_id = request.form.get('employee_id')
        manager_id = request.form.get('manager_id')
        
        if not employee_id:
            flash('Please select an employee.', 'error')
            return redirect(url_for('admin.manage_employees'))
        
        employee = User.query.get_or_404(employee_id)
        
        if employee.role != 'employee':
            flash('Selected user is not an employee.', 'error')
            return redirect(url_for('admin.manage_employees'))
        
        # If manager_id is empty, unassign the employee
        if not manager_id or manager_id == '':
            old_manager_name = employee.manager.username if employee.manager_id else 'None'
            employee.manager_id = None
            employee.leader_id = None  # Also clear leader assignment
            db.session.commit()
            flash(f'{employee.username} has been unassigned from manager {old_manager_name}.', 'info')
            return redirect(url_for('admin.manage_employees'))
        
        # Assign to new manager
        manager = User.query.get_or_404(manager_id)
        
        if manager.role != 'manager' or not manager.is_approved:
            flash('Selected user is not an approved manager.', 'error')
            return redirect(url_for('admin.manage_employees'))
        
        old_manager_name = employee.manager.username if employee.manager_id else 'None'
        employee.manager_id = manager.id
        employee.leader_id = None  # Clear leader assignment when changing manager
        
        db.session.commit()
        flash(f'{employee.username} has been assigned from {old_manager_name} to manager {manager.username}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Assign manager error: {e}")
        flash('An error occurred while assigning the manager.', 'error')
    
    return redirect(url_for('admin.manage_employees'))

@admin_bp.route('/bulk_assign', methods=['POST'])
@role_required('admin')
def bulk_assign():
    """Bulk assign multiple employees to a manager"""
    try:
        employee_ids = request.form.getlist('employee_ids')
        manager_id = request.form.get('manager_id')
        
        if not employee_ids:
            flash('Please select at least one employee.', 'error')
            return redirect(url_for('admin.manage_employees'))
        
        if not manager_id:
            flash('Please select a manager.', 'error')
            return redirect(url_for('admin.manage_employees'))
        
        manager = User.query.get_or_404(manager_id)
        
        if manager.role != 'manager' or not manager.is_approved:
            flash('Selected user is not an approved manager.', 'error')
            return redirect(url_for('admin.manage_employees'))
        
        assigned_count = 0
        for emp_id in employee_ids:
            employee = User.query.get(emp_id)
            if employee and employee.role == 'employee':
                employee.manager_id = manager.id
                employee.leader_id = None  # Clear leader assignment
                assigned_count += 1
        
        db.session.commit()
        flash(f'Successfully assigned {assigned_count} employees to manager {manager.username}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"Bulk assign error: {e}")
        flash('An error occurred during bulk assignment.', 'error')
    
    return redirect(url_for('admin.manage_employees'))
