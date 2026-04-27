from datetime import datetime, date
from typing import Dict, List, Optional, Any
import json
import hashlib
import random
import string


class Helpers:
    @staticmethod
    def generate_unique_id(prefix: str = "", length: int = 8) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        return f"{prefix}{timestamp}{random_chars}"
    
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return hashlib.sha256(password.encode()).hexdigest() == hashed
    
    @staticmethod
    def format_date(date_obj: date, format_str: str = "%Y-%m-%d") -> str:
        if not date_obj:
            return ""
        return date_obj.strftime(format_str)
    
    @staticmethod
    def format_datetime(datetime_obj: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        if not datetime_obj:
            return ""
        return datetime_obj.strftime(format_str)
    
    @staticmethod
    def parse_date(date_str: str, format_str: str = "%Y-%m-%d") -> Optional[date]:
        try:
            return datetime.strptime(date_str, format_str).date()
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def to_json(data: Any) -> str:
        def default(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
        
        return json.dumps(data, default=default, ensure_ascii=False, indent=2)
    
    @staticmethod
    def from_json(json_str: str) -> Any:
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return None
    
    @staticmethod
    def calculate_gpa(grades: List[Dict]) -> float:
        if not grades:
            return 0.0
        
        total_credits = sum(grade.get('credit', 0) for grade in grades)
        if total_credits == 0:
            return 0.0
        
        weighted_sum = sum(
            grade.get('score', 0) * grade.get('credit', 0)
            for grade in grades
        )
        
        return round(weighted_sum / total_credits, 2)
    
    @staticmethod
    def convert_score_to_gpa(score: float) -> float:
        if score >= 90:
            return 4.0
        elif score >= 85:
            return 3.7
        elif score >= 82:
            return 3.3
        elif score >= 78:
            return 3.0
        elif score >= 75:
            return 2.7
        elif score >= 72:
            return 2.3
        elif score >= 68:
            return 2.0
        elif score >= 64:
            return 1.5
        elif score >= 60:
            return 1.0
        else:
            return 0.0
    
    @staticmethod
    def get_age(birthdate: date) -> int:
        if not birthdate:
            return 0
        
        today = date.today()
        age = today.year - birthdate.year
        
        if today.month < birthdate.month or \
           (today.month == birthdate.month and today.day < birthdate.day):
            age -= 1
        
        return age
    
    @staticmethod
    def generate_transaction_id() -> str:
        return Helpers.generate_unique_id("TXN", 6)
    
    @staticmethod
    def generate_application_number() -> str:
        return Helpers.generate_unique_id("APP", 4)
    
    @staticmethod
    def mask_bank_account(account: str) -> str:
        if not account or len(account) < 8:
            return account
        
        prefix = account[:4]
        suffix = account[-4:]
        middle = '*' * (len(account) - 8)
        
        return f"{prefix}{middle}{suffix}"
    
    @staticmethod
    def format_currency(amount: float) -> str:
        return f"¥{amount:,.2f}"
    
    @staticmethod
    def calculate_percentage(part: float, whole: float) -> float:
        if whole == 0:
            return 0.0
        return round(part / whole * 100, 2)
    
    @staticmethod
    def get_status_display(status: str) -> str:
        status_mapping = {
            'submitted': '已提交',
            'reviewing': '审核中',
            'approved': '已通过',
            'rejected': '已拒绝',
            'public_notice': '公示中',
            'disbursed': '已发放',
            'verified': '已核销',
            'cancelled': '已取消',
            'pending': '待处理',
            'processed': '已处理',
            'active': '活跃',
            'graduated': '已毕业',
            'suspended': '休学',
            'expelled': '开除',
            'scholarship': '奖学金',
            'grant': '助学金'
        }
        return status_mapping.get(status, status)
    
    @staticmethod
    def get_role_display(role: str) -> str:
        role_mapping = {
            'admin': '系统管理员',
            'department_admin': '院系管理员',
            'financial_admin': '财务管理员',
            'student': '学生'
        }
        return role_mapping.get(role, role)
    
    @staticmethod
    def paginate_list(items: List[Any], page: int = 1, page_size: int = 10) -> Dict:
        if not items:
            return {
                'items': [],
                'total': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0
            }
        
        total = len(items)
        total_pages = (total + page_size - 1) // page_size
        
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_items = items[start:end]
        
        return {
            'items': paginated_items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }
