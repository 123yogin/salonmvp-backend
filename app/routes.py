from flask import Blueprint, jsonify, request, session
from datetime import datetime, date, timedelta
from sqlalchemy import func
from app.models import User, Salon, Staff, Service, ServiceLog, DailyClosing
from app.extensions import db
from app.auth import hash_password, verify_password, login_required

main = Blueprint('main', __name__)

# ============================================
# Health & Info Routes
# ============================================

@main.route('/')
def index():
    return jsonify({"message": "Welcome to Salon MVP Backend!"})

@main.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ============================================
# Authentication Routes
# ============================================

@main.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user and create a default salon"""
    data = request.get_json()
    
    # Validate input
    if not data.get('password'):
        return jsonify({'error': 'Password is required'}), 400
    
    if not data.get('email') and not data.get('phone'):
        return jsonify({'error': 'Email or phone is required'}), 400
    
    # Check if user already exists
    if data.get('email'):
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return jsonify({'error': 'Email already registered'}), 400
    
    if data.get('phone'):
        existing_user = User.query.filter_by(phone=data['phone']).first()
        if existing_user:
            return jsonify({'error': 'Phone already registered'}), 400
    
    try:
        # Create user
        user = User(
            email=data.get('email'),
            phone=data.get('phone'),
            password_hash=hash_password(data['password'])
        )
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create default salon
        salon = Salon(
            owner_id=user.id,
            name=data.get('salon_name', 'My Salon'),
            address=data.get('address', ''),
            timezone=data.get('timezone', 'Asia/Kolkata')
        )
        db.session.add(salon)
        db.session.commit()
        
        # Log user in
        session['user_id'] = user.id
        session['salon_id'] = salon.id
        
        return jsonify({
            'message': 'Registration successful',
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': user.phone
            },
            'salon': {
                'id': salon.id,
                'name': salon.name
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    
    if not data.get('password'):
        return jsonify({'error': 'Password is required'}), 400
    
    # Find user by email or phone
    user = None
    if data.get('email'):
        user = User.query.filter_by(email=data['email']).first()
    elif data.get('phone'):
        user = User.query.filter_by(phone=data['phone']).first()
    else:
        return jsonify({'error': 'Email or phone is required'}), 400
    
    if not user or not verify_password(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Get user's salon
    salon = Salon.query.filter_by(owner_id=user.id).first()
    if not salon:
        return jsonify({'error': 'No salon found for user'}), 404
    
    # Set session
    session['user_id'] = user.id
    session['salon_id'] = salon.id
    
    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'email': user.email,
            'phone': user.phone
        },
        'salon': {
            'id': salon.id,
            'name': salon.name,
            'address': salon.address
        }
    }), 200

@main.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200

@main.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user info"""
    user = User.query.get(session['user_id'])
    salon = Salon.query.get(session['salon_id'])
    
    if not user or not salon:
        return jsonify({'error': 'User or salon not found'}), 404
    
    return jsonify({
        'user': {
            'id': user.id,
            'email': user.email,
            'phone': user.phone
        },
        'salon': {
            'id': salon.id,
            'name': salon.name,
            'address': salon.address,
            'timezone': salon.timezone
        }
    }), 200

# ============================================
# Service Routes
# ============================================

@main.route('/api/services', methods=['GET'])
@login_required
def get_services():
    """Get all active services for the salon"""
    salon_id = session['salon_id']
    services = Service.query.filter_by(
        salon_id=salon_id,
        is_active=True
    ).order_by(Service.sort_order, Service.name).all()
    
    return jsonify({
        'services': [{
            'id': s.id,
            'name': s.name,
            'default_price': float(s.default_price),
            'sort_order': s.sort_order
        } for s in services]
    }), 200

@main.route('/api/services', methods=['POST'])
@login_required
def create_service():
    """Create a new service"""
    data = request.get_json()
    salon_id = session['salon_id']
    
    if not data.get('name') or not data.get('default_price'):
        return jsonify({'error': 'Name and price are required'}), 400
    
    try:
        service = Service(
            salon_id=salon_id,
            name=data['name'],
            default_price=data['default_price'],
            sort_order=data.get('sort_order', 0)
        )
        db.session.add(service)
        db.session.commit()
        
        return jsonify({
            'message': 'Service created successfully',
            'service': {
                'id': service.id,
                'name': service.name,
                'default_price': float(service.default_price),
                'sort_order': service.sort_order
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/api/services/<service_id>', methods=['PUT'])
@login_required
def update_service(service_id):
    """Update a service"""
    salon_id = session['salon_id']
    service = Service.query.filter_by(id=service_id, salon_id=salon_id).first()
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    data = request.get_json()
    
    try:
        if 'name' in data:
            service.name = data['name']
        if 'default_price' in data:
            service.default_price = data['default_price']
        if 'sort_order' in data:
            service.sort_order = data['sort_order']
        
        service.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Service updated successfully',
            'service': {
                'id': service.id,
                'name': service.name,
                'default_price': float(service.default_price),
                'sort_order': service.sort_order
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/api/services/<service_id>', methods=['DELETE'])
@login_required
def delete_service(service_id):
    """Delete (deactivate) a service"""
    salon_id = session['salon_id']
    service = Service.query.filter_by(id=service_id, salon_id=salon_id).first()
    
    if not service:
        return jsonify({'error': 'Service not found'}), 404
    
    try:
        service.is_active = False
        service.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Service deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================
# Service Log Routes
# ============================================

@main.route('/api/logs', methods=['POST'])
@login_required
def add_service_log():
    """Add a service log entry"""
    data = request.get_json()
    salon_id = session['salon_id']
    
    if not data.get('price') or not data.get('payment_method'):
        return jsonify({'error': 'Price and payment method are required'}), 400
    
    if data['payment_method'] not in ['cash', 'upi']:
        return jsonify({'error': 'Payment method must be cash or upi'}), 400
    
    try:
        log = ServiceLog(
            salon_id=salon_id,
            staff_id=data.get('staff_id'),
            service_id=data.get('service_id'),
            custom_service=data.get('custom_service'),
            price=data['price'],
            payment_method=data['payment_method'],
            served_at=datetime.fromisoformat(data['served_at']) if data.get('served_at') else datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'message': 'Service log added successfully',
            'log': {
                'id': log.id,
                'price': float(log.price),
                'payment_method': log.payment_method,
                'served_at': log.served_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/api/logs/today', methods=['GET'])
@login_required
def get_today_logs():
    """Get today's service logs"""
    salon_id = session['salon_id']
    today = date.today()
    
    logs = ServiceLog.query.filter(
        ServiceLog.salon_id == salon_id,
        func.date(ServiceLog.served_at) == today
    ).order_by(ServiceLog.served_at.desc()).all()
    
    return jsonify({
        'logs': [{
            'id': log.id,
            'service_name': log.service.name if log.service else log.custom_service,
            'staff_name': log.staff.name if log.staff else None,
            'price': float(log.price),
            'payment_method': log.payment_method,
            'served_at': log.served_at.isoformat()
        } for log in logs]
    }), 200

@main.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    """Get service logs with optional date filtering"""
    salon_id = session['salon_id']
    
    # Get date parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = ServiceLog.query.filter_by(salon_id=salon_id)
    
    if start_date:
        query = query.filter(func.date(ServiceLog.served_at) >= start_date)
    if end_date:
        query = query.filter(func.date(ServiceLog.served_at) <= end_date)
    
    logs = query.order_by(ServiceLog.served_at.desc()).all()
    
    return jsonify({
        'logs': [{
            'id': log.id,
            'service_name': log.service.name if log.service else log.custom_service,
            'staff_name': log.staff.name if log.staff else None,
            'price': float(log.price),
            'payment_method': log.payment_method,
            'served_at': log.served_at.isoformat()
        } for log in logs]
    }), 200

# ============================================
# Summary & Analytics Routes
# ============================================

@main.route('/api/summary/today', methods=['GET'])
@login_required
def get_today_summary():
    """Get today's revenue summary"""
    salon_id = session['salon_id']
    today = date.today()
    
    # Get all logs for today
    logs = ServiceLog.query.filter(
        ServiceLog.salon_id == salon_id,
        func.date(ServiceLog.served_at) == today
    ).all()
    
    total_revenue = sum(float(log.price) for log in logs)
    cash_total = sum(float(log.price) for log in logs if log.payment_method == 'cash')
    upi_total = sum(float(log.price) for log in logs if log.payment_method == 'upi')
    
    return jsonify({
        'date': today.isoformat(),
        'total_revenue': total_revenue,
        'cash_total': cash_total,
        'upi_total': upi_total,
        'transaction_count': len(logs)
    }), 200

@main.route('/api/summary/breakdown', methods=['GET'])
@login_required
def get_service_breakdown():
    """Get service breakdown for today"""
    salon_id = session['salon_id']
    today = date.today()
    
    # Get service breakdown
    breakdown = db.session.query(
        Service.name,
        func.count(ServiceLog.id).label('count'),
        func.sum(ServiceLog.price).label('total')
    ).join(
        ServiceLog, ServiceLog.service_id == Service.id
    ).filter(
        ServiceLog.salon_id == salon_id,
        func.date(ServiceLog.served_at) == today
    ).group_by(Service.name).all()
    
    return jsonify({
        'breakdown': [{
            'service_name': item[0],
            'count': item[1],
            'total': float(item[2]) if item[2] else 0
        } for item in breakdown]
    }), 200

@main.route('/api/daily-closing', methods=['POST'])
@login_required
def create_daily_closing():
    """Create a daily closing entry"""
    salon_id = session['salon_id']
    data = request.get_json()
    
    closing_date = date.fromisoformat(data['date']) if data.get('date') else date.today()
    
    # Check if closing already exists
    existing = DailyClosing.query.filter_by(
        salon_id=salon_id,
        date=closing_date
    ).first()
    
    if existing:
        return jsonify({'error': 'Daily closing already exists for this date'}), 400
    
    try:
        # Calculate totals from logs
        logs = ServiceLog.query.filter(
            ServiceLog.salon_id == salon_id,
            func.date(ServiceLog.served_at) == closing_date
        ).all()
        
        total_revenue = sum(float(log.price) for log in logs)
        cash_total = sum(float(log.price) for log in logs if log.payment_method == 'cash')
        upi_total = sum(float(log.price) for log in logs if log.payment_method == 'upi')
        
        closing = DailyClosing(
            salon_id=salon_id,
            date=closing_date,
            closed_at=datetime.utcnow(),
            total_revenue=total_revenue,
            cash_total=cash_total,
            upi_total=upi_total
        )
        db.session.add(closing)
        db.session.commit()
        
        return jsonify({
            'message': 'Daily closing created successfully',
            'closing': {
                'id': closing.id,
                'date': closing.date.isoformat(),
                'total_revenue': float(closing.total_revenue),
                'cash_total': float(closing.cash_total),
                'upi_total': float(closing.upi_total)
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================
# Staff Routes (Optional)
# ============================================

@main.route('/api/staff', methods=['GET'])
@login_required
def get_staff():
    """Get all active staff members"""
    salon_id = session['salon_id']
    staff = Staff.query.filter_by(
        salon_id=salon_id,
        is_active=True
    ).order_by(Staff.name).all()
    
    return jsonify({
        'staff': [{
            'id': s.id,
            'name': s.name,
            'phone': s.phone,
            'role': s.role
        } for s in staff]
    }), 200

@main.route('/api/staff', methods=['POST'])
@login_required
def create_staff():
    """Create a new staff member"""
    data = request.get_json()
    salon_id = session['salon_id']
    
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    try:
        staff = Staff(
            salon_id=salon_id,
            name=data['name'],
            phone=data.get('phone'),
            role=data.get('role')
        )
        db.session.add(staff)
        db.session.commit()
        
        return jsonify({
            'message': 'Staff member created successfully',
            'staff': {
                'id': staff.id,
                'name': staff.name,
                'phone': staff.phone,
                'role': staff.role
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
