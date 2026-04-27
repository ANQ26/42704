__all__ = [
    'ApplicationService',
    'QuotaService',
    'EligibilityService',
    'PolicyService',
    'NotificationService'
]

def get_application_service(db_session):
    from .application_service import ApplicationService
    return ApplicationService(db_session)

def get_quota_service(db_session):
    from .quota_service import QuotaService
    return QuotaService(db_session)

def get_eligibility_service(db_session):
    from .eligibility_service import EligibilityService
    return EligibilityService(db_session)

def get_policy_service(db_session):
    from .policy_service import PolicyService
    return PolicyService(db_session)

def get_notification_service(db_session):
    from .notification_service import NotificationService
    return NotificationService(db_session)
