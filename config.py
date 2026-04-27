import os
from datetime import datetime
from enum import Enum, unique


@unique
class ErrorCode(Enum):
    SUCCESS = "SUCCESS"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    
    STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"
    STUDENT_NOT_ACTIVE = "STUDENT_NOT_ACTIVE"
    
    SCHOLARSHIP_NOT_FOUND = "SCHOLARSHIP_NOT_FOUND"
    APPLICATION_NOT_STARTED = "APPLICATION_NOT_STARTED"
    APPLICATION_ENDED = "APPLICATION_ENDED"
    
    APPLICATION_NOT_FOUND = "APPLICATION_NOT_FOUND"
    DUPLICATE_APPLICATION = "DUPLICATE_APPLICATION"
    INVALID_STATUS = "INVALID_STATUS"
    
    ELIGIBILITY_FAILED = "ELIGIBILITY_FAILED"
    GPA_TOO_LOW = "GPA_TOO_LOW"
    NO_GRADES = "NO_GRADES"
    
    QUOTA_EXISTS = "QUOTA_EXISTS"
    QUOTA_NOT_FOUND = "QUOTA_NOT_FOUND"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    QUOTA_TOO_SMALL = "QUOTA_TOO_SMALL"
    
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_TOO_SMALL = "BUDGET_TOO_SMALL"
    
    REVIEWER_NOT_FOUND = "REVIEWER_NOT_FOUND"
    VERIFIER_NOT_FOUND = "VERIFIER_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    
    DISBURSEMENT_NOT_FOUND = "DISBURSEMENT_NOT_FOUND"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    INVALID_BANK_ACCOUNT = "INVALID_BANK_ACCOUNT"
    
    DEPARTMENT_NOT_FOUND = "DEPARTMENT_NOT_FOUND"
    NO_QUOTA_SET = "NO_QUOTA_SET"
    
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    CONCURRENT_MODIFICATION = "CONCURRENT_MODIFICATION"


@unique
class ApprovalStatus(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@unique
class DisbursementStatus(Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    VERIFIED = "verified"


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///scholarship_management.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    NOTIFICATION_ENABLED = True
    SMS_ENABLED = False
    EMAIL_ENABLED = False
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'scholarship_system.log')
    
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    QUOTA_WARNING_THRESHOLD = 0.1
    
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
    
    APPROVAL_STATUS_TRANSITION = {
        1: {
            ApprovalStatus.APPROVED.value: 'reviewing',
            ApprovalStatus.REJECTED.value: 'rejected'
        },
        2: {
            ApprovalStatus.APPROVED.value: 'reviewing',
            ApprovalStatus.REJECTED.value: 'rejected'
        },
        3: {
            ApprovalStatus.APPROVED.value: 'approved',
            ApprovalStatus.REJECTED.value: 'rejected'
        }
    }
    
    VALID_STATUS_TRANSITIONS = {
        'submitted': ['reviewing', 'rejected', 'cancelled'],
        'reviewing': ['reviewing', 'approved', 'rejected'],
        'approved': ['public_notice', 'rejected'],
        'public_notice': ['disbursed', 'rejected'],
        'disbursed': ['verified'],
        'rejected': [],
        'verified': [],
        'cancelled': []
    }
    
    USER_ROLES = {
        'ADMIN': 'admin',
        'DEPARTMENT_ADMIN': 'department_admin',
        'FINANCIAL_ADMIN': 'financial_admin',
        'STUDENT': 'student'
    }
    
    ROLE_PERMISSIONS = {
        'admin': [
            'create_policy', 'update_policy', 'delete_policy',
            'create_quota', 'update_quota', 'delete_quota',
            'review_level_1', 'review_level_2', 'review_level_3',
            'start_public_notice', 'disburse', 'verify',
            'view_all_applications', 'view_all_quotas',
            'manage_users'
        ],
        'department_admin': [
            'review_level_1',
            'view_department_applications', 'view_department_quotas'
        ],
        'financial_admin': [
            'review_level_3',
            'disburse', 'verify',
            'view_all_applications', 'view_all_quotas'
        ],
        'student': [
            'submit_application', 'view_own_applications'
        ]
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
        'ELIGIBILITY_CHECK': 'eligibility_check',
        'SYSTEM_NOTICE': 'system_notice'
    }
    
    DISBURSEMENT_STATUS = {
        'PENDING': DisbursementStatus.PENDING.value,
        'PROCESSED': DisbursementStatus.PROCESSED.value,
        'VERIFIED': DisbursementStatus.VERIFIED.value
    }
    
    APPROVAL_STATUS = {
        'APPROVED': ApprovalStatus.APPROVED.value,
        'REJECTED': ApprovalStatus.REJECTED.value,
        'PENDING': ApprovalStatus.PENDING.value
    }
    
    ERROR_CODE = {member.value: member.value for member in ErrorCode}
    
    @classmethod
    def is_valid_status_transition(cls, from_status: str, to_status: str) -> bool:
        if from_status not in cls.VALID_STATUS_TRANSITIONS:
            return False
        return to_status in cls.VALID_STATUS_TRANSITIONS[from_status]
    
    @classmethod
    def get_next_approval_level(cls, current_level: int) -> int:
        level_order = [
            cls.APPROVAL_LEVELS['DEPARTMENT'],
            cls.APPROVAL_LEVELS['SCHOOL'],
            cls.APPROVAL_LEVELS['FINANCIAL']
        ]
        
        try:
            current_index = level_order.index(current_level)
            if current_index < len(level_order) - 1:
                return level_order[current_index + 1]
            return None
        except ValueError:
            return None
    
    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        if role not in cls.ROLE_PERMISSIONS:
            return False
        return permission in cls.ROLE_PERMISSIONS[role]
    
    @classmethod
    def get_error_message(cls, error_code: str) -> str:
        error_messages = {
            ErrorCode.STUDENT_NOT_FOUND.value: "学生不存在",
            ErrorCode.STUDENT_NOT_ACTIVE.value: "学生状态非活跃",
            ErrorCode.SCHOLARSHIP_NOT_FOUND.value: "奖助金类型不存在",
            ErrorCode.APPLICATION_NOT_STARTED.value: "申报尚未开始",
            ErrorCode.APPLICATION_ENDED.value: "申报已结束",
            ErrorCode.APPLICATION_NOT_FOUND.value: "申请不存在",
            ErrorCode.DUPLICATE_APPLICATION.value: "已存在相同类型的有效申请",
            ErrorCode.INVALID_STATUS.value: "当前状态不允许该操作",
            ErrorCode.ELIGIBILITY_FAILED.value: "资格校验未通过",
            ErrorCode.GPA_TOO_LOW.value: "GPA不满足最低要求",
            ErrorCode.NO_GRADES.value: "没有成绩记录",
            ErrorCode.QUOTA_EXISTS.value: "额度配置已存在",
            ErrorCode.QUOTA_NOT_FOUND.value: "额度记录不存在",
            ErrorCode.QUOTA_EXCEEDED.value: "名额已用尽",
            ErrorCode.QUOTA_TOO_SMALL.value: "新名额不能小于已使用名额",
            ErrorCode.BUDGET_EXCEEDED.value: "预算已用尽",
            ErrorCode.BUDGET_TOO_SMALL.value: "新预算不能小于已使用预算",
            ErrorCode.REVIEWER_NOT_FOUND.value: "审核人不存在",
            ErrorCode.VERIFIER_NOT_FOUND.value: "核销人不存在",
            ErrorCode.USER_NOT_FOUND.value: "用户不存在",
            ErrorCode.DISBURSEMENT_NOT_FOUND.value: "发放记录不存在",
            ErrorCode.INVALID_AMOUNT.value: "金额无效",
            ErrorCode.INVALID_BANK_ACCOUNT.value: "银行账号无效",
            ErrorCode.DEPARTMENT_NOT_FOUND.value: "院系不存在",
            ErrorCode.NO_QUOTA_SET.value: "未设置额度",
            ErrorCode.PERMISSION_DENIED.value: "权限不足",
            ErrorCode.INVALID_PARAMETER.value: "参数无效",
            ErrorCode.CONCURRENT_MODIFICATION.value: "并发修改冲突，请重试",
            ErrorCode.SYSTEM_ERROR.value: "系统错误"
        }
        return error_messages.get(error_code, "未知错误")
