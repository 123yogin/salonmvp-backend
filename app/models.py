import uuid
from datetime import datetime
from app.extensions import db

def generate_uuid():
    return str(uuid.uuid4())

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    phone = db.Column(db.String(20), unique=True)
    email = db.Column(db.String(255), unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    salons = db.relationship('Salon', backref='owner', lazy=True)

class Salon(db.Model):
    __tablename__ = 'salons'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    owner_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text)
    timezone = db.Column(db.String(64), default='Asia/Kolkata')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    staff = db.relationship('Staff', backref='salon', lazy=True)
    services = db.relationship('Service', backref='salon', lazy=True)
    logs = db.relationship('ServiceLog', backref='salon', lazy=True)
    daily_closings = db.relationship('DailyClosing', backref='salon', lazy=True)

class Staff(db.Model):
    __tablename__ = 'staff'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    salon_id = db.Column(db.String(36), db.ForeignKey('salons.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    logs = db.relationship('ServiceLog', backref='staff', lazy=True)

class Service(db.Model):
    __tablename__ = 'services'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    salon_id = db.Column(db.String(36), db.ForeignKey('salons.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    default_price = db.Column(db.Numeric(10, 2), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    logs = db.relationship('ServiceLog', backref='service', lazy=True)

class ServiceLog(db.Model):
    __tablename__ = 'service_logs'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    salon_id = db.Column(db.String(36), db.ForeignKey('salons.id'), nullable=False)
    staff_id = db.Column(db.String(36), db.ForeignKey('staff.id'))
    service_id = db.Column(db.String(36), db.ForeignKey('services.id'))
    custom_service = db.Column(db.String(255))
    price = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(10), nullable=False) # 'cash' or 'upi'
    served_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class DailyClosing(db.Model):
    __tablename__ = 'daily_closings'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    salon_id = db.Column(db.String(36), db.ForeignKey('salons.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=False)
    total_revenue = db.Column(db.Numeric(10, 2), nullable=False)
    cash_total = db.Column(db.Numeric(10, 2), nullable=False)
    upi_total = db.Column(db.Numeric(10, 2), nullable=False)

    __table_args__ = (db.UniqueConstraint('salon_id', 'date', name='_salon_date_uc'),)
