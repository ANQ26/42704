from datetime import datetime, date
from typing import Dict, List, Optional, Any
import re


class Validator:
    @staticmethod
    def validate_student_id(student_id: str) -> Dict:
        if not student_id or not student_id.strip():
            return {"valid": False, "message": "学号不能为空"}
        
        if len(student_id) < 5 or len(student_id) > 20:
            return {"valid": False, "message": "学号长度应在5-20位之间"}
        
        if not re.match(r'^[A-Za-z0-9]+$', student_id):
            return {"valid": False, "message": "学号只能包含字母和数字"}
        
        return {"valid": True, "message": "学号有效"}
    
    @staticmethod
    def validate_name(name: str) -> Dict:
        if not name or not name.strip():
            return {"valid": False, "message": "姓名不能为空"}
        
        if len(name) < 2 or len(name) > 50:
            return {"valid": False, "message": "姓名长度应在2-50位之间"}
        
        return {"valid": True, "message": "姓名有效"}
    
    @staticmethod
    def validate_email(email: str) -> Dict:
        if not email or not email.strip():
            return {"valid": False, "message": "邮箱不能为空"}
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return {"valid": False, "message": "邮箱格式不正确"}
        
        return {"valid": True, "message": "邮箱有效"}
    
    @staticmethod
    def validate_phone(phone: str) -> Dict:
        if not phone or not phone.strip():
            return {"valid": False, "message": "手机号不能为空"}
        
        phone_pattern = r'^1[3-9]\d{9}$'
        if not re.match(phone_pattern, phone):
            return {"valid": False, "message": "手机号格式不正确"}
        
        return {"valid": True, "message": "手机号有效"}
    
    @staticmethod
    def validate_bank_account(account: str) -> Dict:
        if not account or not account.strip():
            return {"valid": False, "message": "银行账号不能为空"}
        
        if len(account) < 10 or len(account) > 30:
            return {"valid": False, "message": "银行账号长度应在10-30位之间"}
        
        if not re.match(r'^\d+$', account):
            return {"valid": False, "message": "银行账号只能包含数字"}
        
        return {"valid": True, "message": "银行账号有效"}
    
    @staticmethod
    def validate_amount(amount: float) -> Dict:
        if amount is None:
            return {"valid": False, "message": "金额不能为空"}
        
        if amount < 0:
            return {"valid": False, "message": "金额不能为负数"}
        
        if amount > 10000000:
            return {"valid": False, "message": "金额超出合理范围"}
        
        return {"valid": True, "message": "金额有效"}
    
    @staticmethod
    def validate_gpa(gpa: float) -> Dict:
        if gpa is None:
            return {"valid": False, "message": "GPA不能为空"}
        
        if gpa < 0 or gpa > 5:
            return {"valid": False, "message": "GPA应在0-5之间"}
        
        return {"valid": True, "message": "GPA有效"}
    
    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> Dict:
        if not start_date:
            return {"valid": False, "message": "开始日期不能为空"}
        
        if not end_date:
            return {"valid": False, "message": "结束日期不能为空"}
        
        if start_date > end_date:
            return {"valid": False, "message": "开始日期不能晚于结束日期"}
        
        return {"valid": True, "message": "日期范围有效"}
    
    @staticmethod
    def validate_year(year: int) -> Dict:
        if not year:
            return {"valid": False, "message": "年份不能为空"}
        
        current_year = datetime.now().year
        if year < current_year - 10 or year > current_year + 10:
            return {"valid": False, "message": f"年份应在{current_year-10}到{current_year+10}之间"}
        
        return {"valid": True, "message": "年份有效"}
    
    @staticmethod
    def validate_quota(quota: int) -> Dict:
        if quota is None:
            return {"valid": False, "message": "名额不能为空"}
        
        if quota < 0:
            return {"valid": False, "message": "名额不能为负数"}
        
        if quota > 10000:
            return {"valid": False, "message": "名额超出合理范围"}
        
        return {"valid": True, "message": "名额有效"}
    
    @staticmethod
    def validate_application_data(data: Dict) -> Dict:
        errors = []
        
        if 'student_id' not in data or data['student_id'] is None:
            errors.append("学生ID不能为空")
        
        if 'scholarship_type_id' not in data or data['scholarship_type_id'] is None:
            errors.append("奖助金类型ID不能为空")
        
        if 'reason' in data and len(data['reason']) > 2000:
            errors.append("申请理由不能超过2000字")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "message": "申请数据有效"}
    
    @staticmethod
    def validate_approval_data(data: Dict) -> Dict:
        errors = []
        
        if 'application_id' not in data or data['application_id'] is None:
            errors.append("申请ID不能为空")
        
        if 'reviewer_id' not in data or data['reviewer_id'] is None:
            errors.append("审核人ID不能为空")
        
        if 'status' not in data or data['status'] not in ['approved', 'rejected', 'pending']:
            errors.append("审核状态必须为 approved、rejected 或 pending")
        
        if 'level' in data and data['level'] not in [1, 2, 3]:
            errors.append("审核级别必须为 1、2 或 3")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "message": "审核数据有效"}
    
    @staticmethod
    def validate_disbursement_data(data: Dict) -> Dict:
        errors = []
        
        if 'application_id' not in data or data['application_id'] is None:
            errors.append("申请ID不能为空")
        
        if 'bank_account' not in data or not data['bank_account']:
            errors.append("银行账号不能为空")
        else:
            account_validation = Validator.validate_bank_account(data['bank_account'])
            if not account_validation['valid']:
                errors.append(account_validation['message'])
        
        if 'amount' in data:
            amount_validation = Validator.validate_amount(data['amount'])
            if not amount_validation['valid']:
                errors.append(amount_validation['message'])
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "message": "发放数据有效"}
