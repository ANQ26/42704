from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    students = relationship('Student', back_populates='department')
    department_quotas = relationship('DepartmentQuota', back_populates='department')

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    student_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    gender = Column(String(10))
    birthdate = Column(Date)
    department_id = Column(Integer, ForeignKey('departments.id'))
    major = Column(String(100))
    grade = Column(String(20))
    class_name = Column(String(50))
    status = Column(String(20), default='active')  # active, graduated, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    department = relationship('Department', back_populates='students')
    applications = relationship('Application', back_populates='student')
    grades = relationship('Grade', back_populates='student')
    student_status = relationship('StudentStatus', back_populates='student')

class ScholarshipType(Base):
    __tablename__ = 'scholarship_types'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    type = Column(String(20))  # scholarship, grant
    description = Column(Text)
    application_start_date = Column(Date)
    application_end_date = Column(Date)
    review_start_date = Column(Date)
    review_end_date = Column(Date)
    disbursement_date = Column(Date)
    amount = Column(Float)
    min_gpa = Column(Float)
    max_application_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = relationship('Application', back_populates='scholarship_type')
    department_quotas = relationship('DepartmentQuota', back_populates='scholarship_type')

class Application(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    scholarship_type_id = Column(Integer, ForeignKey('scholarship_types.id'))
    application_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='submitted')  # submitted, reviewed, approved, rejected,公示中,已发放,已核销
    reason = Column(Text)
    attachments = Column(Text)  # JSON string of file paths
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', back_populates='applications')
    scholarship_type = relationship('ScholarshipType', back_populates='applications')
    approval_records = relationship('ApprovalRecord', back_populates='application')
    disbursement = relationship('Disbursement', back_populates='application')

class ApprovalRecord(Base):
    __tablename__ = 'approval_records'
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('applications.id'))
    approver_id = Column(Integer, ForeignKey('users.id'))
    approval_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20))  # approved, rejected, pending
    comments = Column(Text)
    level = Column(Integer)  # 1: 院系审核, 2: 学校审核, 3: 财务审核
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship('Application', back_populates='approval_records')
    approver = relationship('User', back_populates='approval_records')

class Disbursement(Base):
    __tablename__ = 'disbursements'
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('applications.id'))
    amount = Column(Float, nullable=False)
    disbursement_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')  # pending, processed, verified
    bank_account = Column(String(50))
    transaction_id = Column(String(100))
    verified_by = Column(Integer, ForeignKey('users.id'))
    verified_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    application = relationship('Application', back_populates='disbursement')
    verifier = relationship('User', back_populates='disbursements')

class DepartmentQuota(Base):
    __tablename__ = 'department_quotas'
    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey('departments.id'))
    scholarship_type_id = Column(Integer, ForeignKey('scholarship_types.id'))
    year = Column(Integer, nullable=False)
    quota = Column(Integer, nullable=False)  # 名额
    budget = Column(Float, nullable=False)  # 预算
    used_quota = Column(Integer, default=0)
    used_budget = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    department = relationship('Department', back_populates='department_quotas')
    scholarship_type = relationship('ScholarshipType', back_populates='department_quotas')

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    name = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False)  # admin, department_admin, financial_admin
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approval_records = relationship('ApprovalRecord', back_populates='approver')
    disbursements = relationship('Disbursement', back_populates='verifier')
    notifications = relationship('Notification', back_populates='user')

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    student_id = Column(Integer, ForeignKey('students.id'), nullable=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(20))  # application_reminder, approval_todo, public_notice, disbursement_progress
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship('User', back_populates='notifications')
    student = relationship('Student')

class Grade(Base):
    __tablename__ = 'grades'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    semester = Column(String(20), nullable=False)
    course_name = Column(String(100), nullable=False)
    credit = Column(Float, nullable=False)
    score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship('Student', back_populates='grades')

class StudentStatus(Base):
    __tablename__ = 'student_status'
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    status = Column(String(20), nullable=False)  # active, graduated, suspended, expelled
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship('Student', back_populates='student_status')
