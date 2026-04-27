import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import traceback

from config import Config


class LogService:
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialize_logger()
        return cls._instance
    
    @classmethod
    def _initialize_logger(cls):
        if cls._logger is not None:
            return
        
        cls._logger = logging.getLogger('scholarship_system')
        cls._logger.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
        
        cls._logger.handlers = []
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
        
        file_handler = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
        file_handler.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))
        
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        cls._logger.addHandler(console_handler)
        cls._logger.addHandler(file_handler)
    
    @property
    def logger(self):
        return self._logger
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.DEBUG, message, extra)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.INFO, message, extra)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.WARNING, message, extra)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.ERROR, message, extra)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(logging.CRITICAL, message, extra)
    
    def _log(self, level: int, message: str, extra: Optional[Dict[str, Any]] = None):
        if extra:
            extra_str = ' | '.join(f'{k}={v}' for k, v in extra.items())
            full_message = f"{message} | {extra_str}"
        else:
            full_message = message
        
        self._logger.log(level, full_message)
    
    def log_operation(self, operation: str, user_id: Optional[int] = None, 
                       student_id: Optional[int] = None, details: Optional[Dict] = None):
        extra = {'operation': operation}
        if user_id:
            extra['user_id'] = user_id
        if student_id:
            extra['student_id'] = student_id
        if details:
            extra.update(details)
        
        self.info(f"执行操作: {operation}", extra)
    
    def log_error(self, operation: str, exception: Exception, 
                  user_id: Optional[int] = None, details: Optional[Dict] = None):
        extra = {
            'operation': operation,
            'error_type': type(exception).__name__,
            'error_message': str(exception),
            'traceback': traceback.format_exc()
        }
        if user_id:
            extra['user_id'] = user_id
        if details:
            extra.update(details)
        
        self.error(f"操作失败: {operation}", extra)
    
    def log_application_submit(self, application_id: int, student_id: int, 
                                 scholarship_type_id: int, success: bool = True):
        operation = "提交申请" if success else "提交申请失败"
        self.log_operation(
            operation=operation,
            student_id=student_id,
            details={
                'application_id': application_id,
                'scholarship_type_id': scholarship_type_id,
                'success': success
            }
        )
    
    def log_approval(self, application_id: int, reviewer_id: int, 
                     approval_status: str, level: int, success: bool = True):
        operation = f"审核操作 (级别{level})" if success else f"审核操作失败 (级别{level})"
        self.log_operation(
            operation=operation,
            user_id=reviewer_id,
            details={
                'application_id': application_id,
                'approval_status': approval_status,
                'level': level,
                'success': success
            }
        )
    
    def log_disbursement(self, application_id: int, disbursement_id: int,
                         amount: float, success: bool = True):
        operation = "发放资金" if success else "发放资金失败"
        self.log_operation(
            operation=operation,
            details={
                'application_id': application_id,
                'disbursement_id': disbursement_id,
                'amount': amount,
                'success': success
            }
        )
    
    def log_verification(self, disbursement_id: int, verifier_id: int,
                          transaction_id: str, success: bool = True):
        operation = "资金核销" if success else "资金核销失败"
        self.log_operation(
            operation=operation,
            user_id=verifier_id,
            details={
                'disbursement_id': disbursement_id,
                'transaction_id': transaction_id,
                'success': success
            }
        )
    
    def log_quota_update(self, department_id: int, scholarship_type_id: int,
                          used_quota: int, used_budget: float, success: bool = True):
        operation = "更新额度" if success else "更新额度失败"
        self.log_operation(
            operation=operation,
            details={
                'department_id': department_id,
                'scholarship_type_id': scholarship_type_id,
                'used_quota': used_quota,
                'used_budget': used_budget,
                'success': success
            }
        )
    
    def log_permission_denied(self, user_id: int, permission: str, operation: str):
        self.warning(
            f"权限拒绝: 用户 {user_id} 尝试执行 {operation}，缺少权限 {permission}",
            extra={'user_id': user_id, 'permission': permission, 'operation': operation}
        )
    
    def log_quota_warning(self, department_id: int, scholarship_type_id: int,
                           remaining_quota: int, remaining_budget: float):
        self.warning(
            f"额度预警: 院系 {department_id} 的奖助金 {scholarship_type_id} 额度即将用尽",
            extra={
                'department_id': department_id,
                'scholarship_type_id': scholarship_type_id,
                'remaining_quota': remaining_quota,
                'remaining_budget': remaining_budget
            }
        )


log_service = LogService()


def log_operation(operation_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log_service.info(f"开始执行: {operation_name}")
            try:
                result = func(*args, **kwargs)
                log_service.info(f"执行完成: {operation_name}")
                return result
            except Exception as e:
                log_service.log_error(operation_name, e)
                raise
        return wrapper
    return decorator
