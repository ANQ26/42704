import os
from datetime import datetime

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///scholarship_management.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    NOTIFICATION_ENABLED = True
    SMS_ENABLED = False
    EMAIL_ENABLED = False
    
    APPLICATION_STATUS = {
        'SUBMITTED': 'submitted',
        'REVIEWING': 'reviewing',
        'APPROVED': 'approved',
        'REJECTED': 'rejected',
        'PUBLIC_NOTICE': 'public_notice',
        'DISBURSED': 'disbursed',
        'VERIFIED': 'verified',
        'CANCELLED': 'cancelled'
    }
    
    APPROVAL_LEVELS = {
        'DEPARTMENT': 1,
        'SCHOOL': 2,
        'FINANCIAL': 3
    }
    
    USER_ROLES = {
        'ADMIN': 'admin',
        'DEPARTMENT_ADMIN': 'department_admin',
        'FINANCIAL_ADMIN': 'financial_admin',
        'STUDENT': 'student'
    }
    
    SCHOLARSHIP_TYPES = {
        'SCHOLARSHIP': 'scholarship',
        'GRANT': 'grant'
    }
    
    STUDENT_STATUS = {
        'ACTIVE': 'active',
        'GRADUATED': 'graduated',
        'SUSPENDED': 'suspended',
        'EXPELLED': 'expelled'
    }
    
    NOTIFICATION_TYPES = {
        'APPLICATION_REMINDER': 'application_reminder',
        'APPROVAL_TODO': 'approval_todo',
        'PUBLIC_NOTICE': 'public_notice',
        'DISBURSEMENT_PROGRESS': 'disbursement_progress',
        'QUOTA_WARNING': 'quota_warning',
        'ELIGIBILITY_CHECK': 'eligibility_check'
    }
