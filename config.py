import os
from datetime import datetime

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'scholarship-management-secret-key-2024')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///scholarship.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'false')
    SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
    SMS_API_SECRET = os.environ.get('SMS_API_SECRET', '')

    CAMPUS_PLATFORM_ENABLED = os.environ.get('CAMPUS_PLATFORM_ENABLED', 'true')
    CAMPUS_PLATFORM_URL = os.environ.get('CAMPUS_PLATFORM_URL', 'http://campus-platform.local')

    NOTIFICATION_CHANNELS = ['in_app', 'sms', 'campus_platform']

    APPLICATION_OPEN_HOURS = 72
    APPROVAL_TIMEOUT_HOURS = 48

    QUOTA_WARNING_THRESHOLD = 0.9

    PUBLICITY_DURATION_DAYS = 7

    DISBURSEMENT_BATCH_SIZE = 100

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}