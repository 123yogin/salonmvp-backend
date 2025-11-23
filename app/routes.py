from flask import Blueprint, jsonify, request, g, current_app
from datetime import datetime, date, timedelta
import pytz
from sqlalchemy import func
from app.models import User, Salon, Staff, Service, ServiceLog, DailyClosing
from app.extensions import db
from app.auth import login_required
from app.utils_cognito import cognito_client, get_secret_hash

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
# Helper Functions
# ============================================

def get_day_range_utc(salon, target_date=None):
    """
    Calculates the start and end datetime in UTC for a specific date 
    in the salon's local timezone. Defaults to today if no date provided.
    target_date: datetime.date object
    """
    tz = pytz.timezone(salon.timezone)
    
    if not target_date:
        target_date = datetime.now(tz).date()
    
    start_local = tz.localize(datetime.combine(target_date, datetime.min.time()))
    end_local = tz.localize(datetime.combine(target_date, datetime.max.time()))
    
    return start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)

# ============================================
# Authentication / User Sync Routes
# ============================================

@main.route('/api/auth/cognito-login', methods=['POST'])
def cognito_login():
    """
    Proxies login request to Cognito, handling SECRET_HASH.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    client = cognito_client()
    client_id = current_app.config.get('COGNITO_APP_CLIENT_ID')
    
    try:
        print(f"Attempting login for: {email}")
        secret_hash = get_secret_hash(email)
        
        params = {
            'ClientId': client_id,
            'AuthFlow': 'USER_PASSWORD_AUTH',
            'AuthParameters': {
                'USERNAME': email,
                'PASSWORD': password,
            }
        }
        
        if secret_hash:
            params['AuthParameters']['SECRET_HASH'] = secret_hash
            
        print("Calling Cognito initiate_auth...")
        response = client.initiate_auth(**params)
        print("Cognito response received.")
        
        # Extract tokens
        auth_result = response.get('AuthenticationResult', {})
        return jsonify({
            'accessToken': auth_result.get('AccessToken'),
            'idToken': auth_result.get('IdToken'),
            'refreshToken': auth_result.get('RefreshToken'),
            'expiresIn': auth_result.get('ExpiresIn'),
            'tokenType': auth_result.get('TokenType')
        }), 200
        
    except client.exceptions.NotAuthorizedException:
        return jsonify({'error': 'Incorrect username or password'}), 401
    except client.exceptions.UserNotConfirmedException:
        return jsonify({'error': 'User is not confirmed'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@main.route('/api/auth/cognito-register', methods=['POST'])
def cognito_register():
    """
    Proxies registration request to Cognito, handling SECRET_HASH.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    client = cognito_client()
    client_id = current_app.config.get('COGNITO_APP_CLIENT_ID')
    
    try:
        secret_hash = get_secret_hash(email)
        
        user_attrs = [{'Name': 'email', 'Value': email}]
        # Phone removed

        params = {
            'ClientId': client_id,
            'Username': email,
            'Password': password,
            'UserAttributes': user_attrs
        }
        
        if secret_hash:
            params['SecretHash'] = secret_hash
            
        response = client.sign_up(**params)
        
        return jsonify({
            'message': 'Registration successful',
            'userSub': response.get('UserSub'),
            'userConfirmed': response.get('UserConfirmed')
        }), 200
        
    except client.exceptions.UsernameExistsException:
        return jsonify({'error': 'User already exists'}), 400
    except client.exceptions.InvalidParameterException as e:
         return jsonify({'error': f'Invalid Parameter: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@main.route('/api/auth/cognito-confirm', methods=['POST'])
def cognito_confirm():
    """
    Proxies confirmation code to Cognito, handling SECRET_HASH.
    """
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')

    if not email or not code:
        return jsonify({'error': 'Email and code are required'}), 400

    client = cognito_client()
    client_id = current_app.config.get('COGNITO_APP_CLIENT_ID')
    
    try:
        secret_hash = get_secret_hash(email)
        
        params = {
            'ClientId': client_id,
            'Username': email,
            'ConfirmationCode': code,
        }
        
        if secret_hash:
            params['SecretHash'] = secret_hash
            
        client.confirm_sign_up(**params)
        
        return jsonify({'message': 'Account confirmed successfully'}), 200
        
    except client.exceptions.CodeMismatchException:
        return jsonify({'error': 'Invalid verification code'}), 400
    except client.exceptions.ExpiredCodeException:
        return jsonify({'error': 'Verification code expired'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@main.route('/api/auth/sync-profile', methods=['POST'])
@login_required
def sync_profile():
    """
    Ensures the user exists in our DB after they sign up/in via Cognito.
    Handles automatic linking of invited Staff members.
    """
    claims = g.cognito_claims
    sub = claims.get('sub')
    email = claims.get('email')
    phone = claims.get('phone_number') # might be None
    
    # Check if user already exists
    user = User.query.filter_by(cognito_sub=sub).first()
    
    if not user:
        # Create new user
        try:
            # Determine Role: Check if this email was invited as Staff
            invited_staff = Staff.query.filter_by(email=email).first()
            
            role = 'STAFF' if invited_staff else 'OWNER'
            
            user = User(
                cognito_sub=sub,
                email=email,
                phone=phone,
                role=role
            )
            db.session.add(user)
            db.session.flush() # Get ID
            
            if role == 'STAFF':
                # Link to existing staff record
                invited_staff.user_id = user.id
                # Staff uses the existing salon, doesn't create one
                salon = invited_staff.salon
            else:
                # Create default salon for new OWNER
                data = request.get_json() or {}
                salon = Salon(
                    owner_id=user.id,
                    name=data.get('salon_name', 'My Salon'),
                    address=data.get('address', ''),
                    timezone=data.get('timezone', 'Asia/Kolkata')
                )
                db.session.add(salon)
            
            db.session.commit()
            
            return jsonify({
                'message': 'Profile created successfully',
                'user': {'id': user.id, 'email': user.email, 'role': user.role},
                'salon': {'id': salon.id, 'name': salon.name}
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    else:
        # User exists
        if user.role == 'STAFF':
            # Find their salon via Staff table
            staff_record = Staff.query.filter_by(user_id=user.id).first()
            salon = staff_record.salon if staff_record else None
        else:
            # Owner finds salon via Owner ID
            salon = Salon.query.filter_by(owner_id=user.id).first()
            
        return jsonify({
            'message': 'Profile synced',
            'user': {'id': user.id, 'email': user.email, 'role': user.role},
            'salon': {'id': salon.id, 'name': salon.name} if salon else None
        }), 200

@main.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user info"""
    if not g.current_user:
        return jsonify({'error': 'User profile not found. Please call /sync-profile first.'}), 404
        
    user = g.current_user
    
    # Determine Salon based on Role
    if user.role == 'STAFF':
        staff_record = Staff.query.filter_by(user_id=user.id).first()
        salon = staff_record.salon if staff_record else None
        # Also verify the staff record is active?
        if not staff_record or not staff_record.is_active:
             return jsonify({'error': 'Staff account is inactive'}), 403
    else:
        # Owner
        salon = Salon.query.filter_by(owner_id=user.id).first()
    
    if not salon:
         return jsonify({'error': 'No salon found linked to this user'}), 404
    
    # Set global context for subsequent decorators if any (though auth.py does this too, but simple)
    # Actually auth.py logic for g.current_salon needs update too if we rely on it!
    
    return jsonify({
        'user': {
            'id': user.id,
            'email': user.email,
            'phone': user.phone,
            'role': user.role
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
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
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
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    data = request.get_json()
    salon_id = g.current_salon.id
    
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
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
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
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
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
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    data = request.get_json()
    salon_id = g.current_salon.id
    
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
    """Get service logs for today (or specific date)"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
    
    # Parse date param (optional, defaults to today if not provided)
    date_str = request.args.get('date')
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            # If invalid date, just ignore and use today, or return error. 
            # Let's return error to be consistent
            return jsonify({'error': 'Invalid date format'}), 400

    start_utc, end_utc = get_day_range_utc(g.current_salon, target_date)
    
    query = ServiceLog.query.filter(
        ServiceLog.salon_id == salon_id,
        ServiceLog.served_at >= start_utc,
        ServiceLog.served_at <= end_utc
    )

    # If Staff, filter by their ID so they only see THEIR logs
    if g.current_user.role == 'STAFF':
        staff_record = Staff.query.filter_by(user_id=g.current_user.id).first()
        if staff_record:
            query = query.filter(ServiceLog.staff_id == staff_record.id)
    
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

@main.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    """Get service logs with optional date filtering"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
    
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

@main.route('/api/summary', methods=['GET'])
@login_required
def get_summary():
    """Get revenue summary for a specific date (or today)"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
    
    # Parse date param
    date_str = request.args.get('date')
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
            
    start_utc, end_utc = get_day_range_utc(g.current_salon, target_date)
    
    query = ServiceLog.query.filter(
        ServiceLog.salon_id == salon_id,
        ServiceLog.served_at >= start_utc,
        ServiceLog.served_at <= end_utc
    )

    # If Staff, filter by their ID so they only see THEIR revenue
    if g.current_user.role == 'STAFF':
        staff_record = Staff.query.filter_by(user_id=g.current_user.id).first()
        if staff_record:
            query = query.filter(ServiceLog.staff_id == staff_record.id)

    logs = query.all()
    
    total_revenue = sum(float(log.price) for log in logs)
    cash_total = sum(float(log.price) for log in logs if log.payment_method and log.payment_method.lower() == 'cash')
    upi_total = sum(float(log.price) for log in logs if log.payment_method and log.payment_method.lower() == 'upi')
    
    return jsonify({
        'date': target_date.isoformat() if target_date else datetime.now(pytz.timezone(g.current_salon.timezone)).date().isoformat(),
        'total_revenue': round(total_revenue, 2),
        'cash_total': round(cash_total, 2),
        'upi_total': round(upi_total, 2),
        'transaction_count': len(logs)
    }), 200

@main.route('/api/summary/breakdown', methods=['GET'])
@login_required
def get_service_breakdown():
    """Get service breakdown for a date"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
    
    # Parse date param
    date_str = request.args.get('date')
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
            
    start_utc, end_utc = get_day_range_utc(g.current_salon, target_date)
    
    breakdown = db.session.query(
        Service.name,
        func.count(ServiceLog.id).label('count'),
        func.sum(ServiceLog.price).label('total')
    ).join(
        ServiceLog, ServiceLog.service_id == Service.id
    ).filter(
        ServiceLog.salon_id == salon_id,
        ServiceLog.served_at >= start_utc,
        ServiceLog.served_at <= end_utc
    ).group_by(Service.name).all()
    
    return jsonify({
        'breakdown': [{
            'service_name': item[0],
            'count': item[1],
            'total': round(float(item[2]) if item[2] else 0, 2)
        } for item in breakdown]
    }), 200

@main.route('/api/summary/staff-performance', methods=['GET'])
@login_required
def get_staff_performance():
    """Get sales performance by staff for a date"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    # Only OWNER can see this report
    if g.current_user.role != 'OWNER':
         return jsonify({'error': 'Unauthorized'}), 403
         
    salon_id = g.current_salon.id
    
    # Parse date param
    date_str = request.args.get('date')
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
            
    start_utc, end_utc = get_day_range_utc(g.current_salon, target_date)
    
    # Query: Group by staff_id, Sum Price
    results = db.session.query(
        Staff.name,
        func.count(ServiceLog.id).label('count'),
        func.sum(ServiceLog.price).label('total')
    ).join(
        ServiceLog, ServiceLog.staff_id == Staff.id
    ).filter(
        ServiceLog.salon_id == salon_id,
        ServiceLog.served_at >= start_utc,
        ServiceLog.served_at <= end_utc
    ).group_by(Staff.name).all()
    
    return jsonify({
        'performance': [{
            'staff_name': item[0],
            'count': item[1],
            'total': round(float(item[2]) if item[2] else 0, 2)
        } for item in results]
    }), 200

@main.route('/api/analytics/monthly', methods=['GET'])
@login_required
def get_monthly_analytics():
    """Get daily revenue for a specific month"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    if g.current_user.role != 'OWNER':
         return jsonify({'error': 'Unauthorized'}), 403

    salon_id = g.current_salon.id
    tz = pytz.timezone(g.current_salon.timezone)
    now = datetime.now(tz)
    
    try:
        month = request.args.get('month', type=int, default=now.month)
        year = request.args.get('year', type=int, default=now.year)
    except ValueError:
        return jsonify({'error': 'Invalid month/year'}), 400
    
    # Calculate range
    start_local = tz.localize(datetime(year, month, 1, 0, 0, 0))
    
    if month == 12:
        next_month_start = datetime(year + 1, 1, 1, 0, 0, 0)
    else:
        next_month_start = datetime(year, month + 1, 1, 0, 0, 0)
    
    end_local = tz.localize(next_month_start - timedelta(seconds=1))
    
    start_utc = start_local.astimezone(pytz.utc)
    end_utc = end_local.astimezone(pytz.utc)
    
    logs = ServiceLog.query.filter(
        ServiceLog.salon_id == salon_id,
        ServiceLog.served_at >= start_utc,
        ServiceLog.served_at <= end_utc
    ).all()
    
    daily_data = {}
    for log in logs:
        # Convert to local time to determine the day
        local_time = log.served_at.replace(tzinfo=pytz.utc).astimezone(tz)
        day = local_time.day
        daily_data[day] = daily_data.get(day, 0) + float(log.price)
        
    import calendar
    _, num_days = calendar.monthrange(year, month)
    
    chart_data = []
    total_revenue = 0
    for d in range(1, num_days + 1):
        val = daily_data.get(d, 0)
        chart_data.append({'name': str(d), 'value': round(val, 2)})
        total_revenue += val
        
    return jsonify({'data': chart_data, 'total': round(total_revenue, 2)}), 200

@main.route('/api/analytics/yearly', methods=['GET'])
@login_required
def get_yearly_analytics():
    """Get monthly revenue for a specific year"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    if g.current_user.role != 'OWNER':
         return jsonify({'error': 'Unauthorized'}), 403

    salon_id = g.current_salon.id
    tz = pytz.timezone(g.current_salon.timezone)
    now = datetime.now(tz)
    
    try:
        year = request.args.get('year', type=int, default=now.year)
    except ValueError:
        return jsonify({'error': 'Invalid year'}), 400
        
    start_local = tz.localize(datetime(year, 1, 1, 0, 0, 0))
    end_local = tz.localize(datetime(year, 12, 31, 23, 59, 59))
    
    start_utc = start_local.astimezone(pytz.utc)
    end_utc = end_local.astimezone(pytz.utc)
    
    logs = ServiceLog.query.filter(
        ServiceLog.salon_id == salon_id,
        ServiceLog.served_at >= start_utc,
        ServiceLog.served_at <= end_utc
    ).all()
    
    monthly_data = {}
    for log in logs:
        local_time = log.served_at.replace(tzinfo=pytz.utc).astimezone(tz)
        m = local_time.month
        monthly_data[m] = monthly_data.get(m, 0) + float(log.price)
        
    chart_data = []
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    total_revenue = 0
    
    for i in range(1, 13):
        val = monthly_data.get(i, 0)
        chart_data.append({'name': month_names[i-1], 'value': round(val, 2)})
        total_revenue += val
        
    return jsonify({'data': chart_data, 'total': round(total_revenue, 2)}), 200

@main.route('/api/daily-closing', methods=['POST'])
@login_required
def create_daily_closing():
    """Create a daily closing entry"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
    data = request.get_json()
    
    closing_date = date.fromisoformat(data['date']) if data.get('date') else date.today()
    
    existing = DailyClosing.query.filter_by(
        salon_id=salon_id,
        date=closing_date
    ).first()
    
    if existing:
        return jsonify({'error': 'Daily closing already exists for this date'}), 400
    
    try:
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
# Staff Routes
# ============================================

@main.route('/api/staff', methods=['GET'])
@login_required
def get_staff():
    """Get all active staff members"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    salon_id = g.current_salon.id
    staff = Staff.query.filter_by(
        salon_id=salon_id,
        is_active=True
    ).order_by(Staff.name).all()
    
    return jsonify({
        'staff': [{
            'id': s.id,
            'name': s.name,
            'email': s.email, # Include email
            'phone': s.phone,
            'role': s.role,
            'user_id': s.user_id # See if they are linked
        } for s in staff]
    }), 200

@main.route('/api/staff', methods=['POST'])
@login_required
def create_staff():
    """Create a new staff member (Invite)"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    # Only OWNER can add staff
    if g.current_user.role != 'OWNER':
         return jsonify({'error': 'Only salon owners can manage staff'}), 403
    
    data = request.get_json()
    salon_id = g.current_salon.id
    
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    email = data.get('email')
    if not email:
         return jsonify({'error': 'Email is required for invitation'}), 400
    
    # Check if staff email already exists in this salon
    existing = Staff.query.filter_by(salon_id=salon_id, email=email, is_active=True).first()
    if existing:
         return jsonify({'error': 'Staff with this email already exists'}), 400
    
    try:
        staff = Staff(
            salon_id=salon_id,
            name=data['name'],
            email=email,
            phone=data.get('phone'),
            role=data.get('role', 'Stylist')
        )
        db.session.add(staff)
        db.session.commit()
        
        return jsonify({
            'message': 'Staff invited successfully. They can now log in with this email.',
            'staff': {
                'id': staff.id,
                'name': staff.name,
                'email': staff.email,
                'phone': staff.phone,
                'role': staff.role
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/api/staff/<staff_id>', methods=['DELETE'])
@login_required
def delete_staff(staff_id):
    """Deactivate a staff member"""
    if not g.current_salon: return jsonify({'error': 'No salon found'}), 404
    
    # Only OWNER can delete staff
    if g.current_user.role != 'OWNER':
         return jsonify({'error': 'Only salon owners can manage staff'}), 403
    
    salon_id = g.current_salon.id
    staff = Staff.query.filter_by(id=staff_id, salon_id=salon_id).first()
    
    if not staff:
        return jsonify({'error': 'Staff member not found'}), 404
    
    try:
        staff.is_active = False
        # Optionally, if they have a linked user_id, we might want to unlink it or block that user?
        # For now, just removing from salon visibility is enough. 
        # If they login, sync_profile checks is_active via "find salon via Staff table" logic?
        # Wait, sync_profile links them. get_current_user checks if staff is active!
        
        db.session.commit()
        return jsonify({'message': 'Staff deactivated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
