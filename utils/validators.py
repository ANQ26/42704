from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
import re

from config import Config, ErrorCode, ApprovalStatus


class ValidationResult:
    def __init__(self, valid: bool = True, message: str = "", 
                 code: str = ErrorCode.SUCCESS.value, details: Optional[List] = None):
        self.valid = valid
        self.message = message
        self.code = code
        self.details = details or []
    
    def to_dict(self) -> Dict:
        return {
            'valid': self.valid,
            'message': self.message,
            'code': self.code,
            'details': self.details
        }
    
    @classmethod
    def success(cls, message: str = "验证通过") -> 'ValidationResult':
        return cls(valid=True, message=message, code=ErrorCode.SUCCESS.value)
    
    @classmethod
    def failure(cls, message: str, code: str = ErrorCode.INVALID_PARAMETER.value,
                details: Optional[List] = None) -> 'ValidationResult':
        return cls(valid=False, message=message, code=code, details=details)


class Validator:
    @staticmethod
    def validate_id(value: Any, field_name: str = "ID") -> ValidationResult:
        if value is None:
            return ValidationResult.failure(f"{field_name}不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        if not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return ValidationResult.failure(f"{field_name}必须是整数", ErrorCode.INVALID_PARAMETER.value)
        
        if value <= 0:
            return ValidationResult.failure(f"{field_name}必须大于0", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_student_id(student_id: str) -> ValidationResult:
        if not student_id or not isinstance(student_id, str) or not student_id.strip():
            return ValidationResult.failure("学号不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        student_id = student_id.strip()
        
        if len(student_id) < 5 or len(student_id) > 20:
            return ValidationResult.failure("学号长度应在5-20位之间", ErrorCode.INVALID_PARAMETER.value)
        
        if not re.match(r'^[A-Za-z0-9_]+$', student_id):
            return ValidationResult.failure("学号只能包含字母、数字和下划线", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_name(name: str, field_name: str = "姓名", min_length: int = 2, 
                      max_length: int = 50) -> ValidationResult:
        if not name or not isinstance(name, str) or not name.strip():
            return ValidationResult.failure(f"{field_name}不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        name = name.strip()
        
        if len(name) < min_length:
            return ValidationResult.failure(f"{field_name}长度不能少于{min_length}位", ErrorCode.INVALID_PARAMETER.value)
        
        if len(name) > max_length:
            return ValidationResult.failure(f"{field_name}长度不能超过{max_length}位", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_email(email: str, allow_empty: bool = False) -> ValidationResult:
        if not email or not email.strip():
            if allow_empty:
                return ValidationResult.success()
            return ValidationResult.failure("邮箱不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        email = email.strip()
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return ValidationResult.failure("邮箱格式不正确", ErrorCode.INVALID_PARAMETER.value)
        
        if len(email) > 100:
            return ValidationResult.failure("邮箱长度不能超过100位", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_phone(phone: str, allow_empty: bool = False) -> ValidationResult:
        if not phone or not phone.strip():
            if allow_empty:
                return ValidationResult.success()
            return ValidationResult.failure("手机号不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        phone = phone.strip()
        
        phone = re.sub(r'[\s\-\+]', '', phone)
        
        phone_pattern = r'^1[3-9]\d{9}$'
        if not re.match(phone_pattern, phone):
            return ValidationResult.failure("手机号格式不正确，必须是11位有效手机号", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_bank_account(account: str) -> ValidationResult:
        if not account or not isinstance(account, str) or not account.strip():
            return ValidationResult.failure("银行账号不能为空", ErrorCode.INVALID_BANK_ACCOUNT.value)
        
        account = account.strip()
        
        account = re.sub(r'[\s\-]', '', account)
        
        if len(account) < 10 or len(account) > 30:
            return ValidationResult.failure("银行账号长度应在10-30位之间", ErrorCode.INVALID_BANK_ACCOUNT.value)
        
        if not re.match(r'^\d+$', account):
            return ValidationResult.failure("银行账号只能包含数字", ErrorCode.INVALID_BANK_ACCOUNT.value)
        
        if not Validator._luhn_check(account):
            return ValidationResult.failure("银行账号校验失败", ErrorCode.INVALID_BANK_ACCOUNT.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def _luhn_check(account: str) -> bool:
        try:
            digits = [int(d) for d in account]
            if len(digits) < 2:
                return True
            
            check_digit = digits.pop()
            digits.reverse()
            
            total = 0
            for i, d in enumerate(digits):
                if i % 2 == 0:
                    d *= 2
                    if d > 9:
                        d -= 9
                total += d
            
            return (total + check_digit) % 10 == 0
        except Exception:
            return True
    
    @staticmethod
    def validate_amount(amount: Any, field_name: str = "金额", min_value: float = 0, 
                        max_value: float = 10000000) -> ValidationResult:
        if amount is None:
            return ValidationResult.failure(f"{field_name}不能为空", ErrorCode.INVALID_AMOUNT.value)
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return ValidationResult.failure(f"{field_name}必须是有效数字", ErrorCode.INVALID_AMOUNT.value)
        
        if amount < min_value:
            return ValidationResult.failure(f"{field_name}不能小于{min_value}", ErrorCode.INVALID_AMOUNT.value)
        
        if amount > max_value:
            return ValidationResult.failure(f"{field_name}不能超过{max_value}", ErrorCode.INVALID_AMOUNT.value)
        
        decimal_places = len(str(amount).split('.')[-1]) if '.' in str(amount) else 0
        if decimal_places > 2:
            return ValidationResult.failure(f"{field_name}最多保留2位小数", ErrorCode.INVALID_AMOUNT.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_gpa(gpa: Any) -> ValidationResult:
        if gpa is None:
            return ValidationResult.failure("GPA不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        try:
            gpa = float(gpa)
        except (ValueError, TypeError):
            return ValidationResult.failure("GPA必须是有效数字", ErrorCode.INVALID_PARAMETER.value)
        
        if gpa < 0 or gpa > 5:
            return ValidationResult.failure("GPA应在0-5之间", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_year(year: Any) -> ValidationResult:
        if year is None:
            return ValidationResult.failure("年份不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        try:
            year = int(year)
        except (ValueError, TypeError):
            return ValidationResult.failure("年份必须是整数", ErrorCode.INVALID_PARAMETER.value)
        
        current_year = datetime.now().year
        if year < current_year - 50 or year > current_year + 10:
            return ValidationResult.failure(f"年份应在{current_year-50}到{current_year+10}之间", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_quota(quota: Any, field_name: str = "名额") -> ValidationResult:
        if quota is None:
            return ValidationResult.failure(f"{field_name}不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        try:
            quota = int(quota)
        except (ValueError, TypeError):
            return ValidationResult.failure(f"{field_name}必须是整数", ErrorCode.INVALID_PARAMETER.value)
        
        if quota < 0:
            return ValidationResult.failure(f"{field_name}不能为负数", ErrorCode.INVALID_PARAMETER.value)
        
        if quota > 100000:
            return ValidationResult.failure(f"{field_name}超出合理范围", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_approval_level(level: Any) -> ValidationResult:
        if level is None:
            return ValidationResult.failure("审核级别不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        try:
            level = int(level)
        except (ValueError, TypeError):
            return ValidationResult.failure("审核级别必须是整数", ErrorCode.INVALID_PARAMETER.value)
        
        valid_levels = [
            Config.APPROVAL_LEVELS['DEPARTMENT'],
            Config.APPROVAL_LEVELS['SCHOOL'],
            Config.APPROVAL_LEVELS['FINANCIAL']
        ]
        
        if level not in valid_levels:
            return ValidationResult.failure(f"审核级别必须是 {valid_levels} 之一", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_approval_status(status: str) -> ValidationResult:
        if not status or not status.strip():
            return ValidationResult.failure("审核状态不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        status = status.strip().lower()
        
        valid_statuses = [
            ApprovalStatus.APPROVED.value,
            ApprovalStatus.REJECTED.value,
            ApprovalStatus.PENDING.value
        ]
        
        if status not in valid_statuses:
            return ValidationResult.failure(f"审核状态必须是 {valid_statuses} 之一", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_application_status(status: str) -> ValidationResult:
        if not status or not status.strip():
            return ValidationResult.failure("申请状态不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        status = status.strip().lower()
        
        valid_statuses = list(Config.APPLICATION_STATUS.values())
        
        if status not in valid_statuses:
            return ValidationResult.failure(f"申请状态必须是 {valid_statuses} 之一", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_date_range(start_date: Any, end_date: Any, 
                            field_name: str = "日期范围") -> ValidationResult:
        if start_date is None:
            return ValidationResult.failure(f"{field_name}开始日期不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        if end_date is None:
            return ValidationResult.failure(f"{field_name}结束日期不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        if isinstance(start_date, str):
            start_date = Validator._parse_date(start_date)
            if start_date is None:
                return ValidationResult.failure("开始日期格式无效", ErrorCode.INVALID_PARAMETER.value)
        
        if isinstance(end_date, str):
            end_date = Validator._parse_date(end_date)
            if end_date is None:
                return ValidationResult.failure("结束日期格式无效", ErrorCode.INVALID_PARAMETER.value)
        
        if start_date > end_date:
            return ValidationResult.failure("开始日期不能晚于结束日期", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%m-%Y', '%d/%m/%Y']
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except (ValueError, TypeError):
                continue
        return None
    
    @staticmethod
    def validate_pagination(page: Any = 1, page_size: Any = None) -> Tuple[int, int]:
        try:
            page = int(page) if page else 1
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1
        
        try:
            page_size = int(page_size) if page_size else Config.DEFAULT_PAGE_SIZE
            if page_size < 1:
                page_size = Config.DEFAULT_PAGE_SIZE
            if page_size > Config.MAX_PAGE_SIZE:
                page_size = Config.MAX_PAGE_SIZE
        except (ValueError, TypeError):
            page_size = Config.DEFAULT_PAGE_SIZE
        
        return page, page_size
    
    @staticmethod
    def validate_text(text: str, field_name: str = "文本", max_length: int = 2000, 
                      allow_empty: bool = True) -> ValidationResult:
        if text is None:
            text = ""
        
        if isinstance(text, str):
            text = text.strip()
        else:
            try:
                text = str(text).strip()
            except Exception:
                text = ""
        
        if not text and not allow_empty:
            return ValidationResult.failure(f"{field_name}不能为空", ErrorCode.INVALID_PARAMETER.value)
        
        if len(text) > max_length:
            return ValidationResult.failure(f"{field_name}不能超过{max_length}字", ErrorCode.INVALID_PARAMETER.value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_submit_application(student_id: int, scholarship_type_id: int,
                                     reason: str = "", attachments: str = "") -> ValidationResult:
        errors = []
        
        result = Validator.validate_id(student_id, "学生ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_id(scholarship_type_id, "奖助金类型ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_text(reason, "申请理由", max_length=2000, allow_empty=True)
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_text(attachments, "附件信息", max_length=500, allow_empty=True)
        if not result.valid:
            errors.append(result.message)
        
        if errors:
            return ValidationResult.failure(
                message="; ".join(errors),
                code=ErrorCode.INVALID_PARAMETER.value,
                details=errors
            )
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_review_application(application_id: int, reviewer_id: int,
                                     approval_status: str, level: int) -> ValidationResult:
        errors = []
        
        result = Validator.validate_id(application_id, "申请ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_id(reviewer_id, "审核人ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_approval_status(approval_status)
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_approval_level(level)
        if not result.valid:
            errors.append(result.message)
        
        if errors:
            return ValidationResult.failure(
                message="; ".join(errors),
                code=ErrorCode.INVALID_PARAMETER.value,
                details=errors
            )
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_disburse_application(application_id: int, bank_account: str,
                                       amount: float = None) -> ValidationResult:
        errors = []
        
        result = Validator.validate_id(application_id, "申请ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_bank_account(bank_account)
        if not result.valid:
            errors.append(result.message)
        
        if amount is not None:
            result = Validator.validate_amount(amount, "发放金额")
            if not result.valid:
                errors.append(result.message)
        
        if errors:
            return ValidationResult.failure(
                message="; ".join(errors),
                code=ErrorCode.INVALID_PARAMETER.value,
                details=errors
            )
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_create_quota(department_id: int, scholarship_type_id: int,
                               year: int, quota: int, budget: float) -> ValidationResult:
        errors = []
        
        result = Validator.validate_id(department_id, "院系ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_id(scholarship_type_id, "奖助金类型ID")
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_year(year)
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_quota(quota)
        if not result.valid:
            errors.append(result.message)
        
        result = Validator.validate_amount(budget, "预算")
        if not result.valid:
            errors.append(result.message)
        
        if errors:
            return ValidationResult.failure(
                message="; ".join(errors),
                code=ErrorCode.INVALID_PARAMETER.value,
                details=errors
            )
        
        return ValidationResult.success()
