import os
from datetime import datetime

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'scholarship-management-secret-key'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'scholarship.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    NOTIFICATION_METHODS = ['system', 'email', 'sms']
    DEFAULT_NOTIFICATION_METHOD = 'system'
    
    APPLICATION_STATUSES = [
        'submitted', 'reviewed', 'approved', 'rejected', 
        '公示中', '已发放', '已核销'
    ]
    
    APPROVAL_LEVELS = {
        1: '院系审核',
        2: '学校审核', 
        3: '财务审核'
    }
    
    ROLES = {
        'student': '学生',
        'department_admin': '院系管理员',
        'school_admin': '学校管理员',
        'financial_admin': '财务管理员',
        'admin': '系统管理员'
    }
    
    @staticmethod
    def init_app(app):
        pass
