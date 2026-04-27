from datetime import date, datetime
import re

class Validator:
    @staticmethod
    def validate_student_id(student_id: str) -> tuple:
        if not student_id or len(student_id) < 6:
            return False, '学号长度至少6位'
        if not re.match(r'^[A-Za-z0-9]+$', student_id):
            return False, '学号只能包含字母和数字'
        return True, None

    @staticmethod
    def validate_name(name: str) -> tuple:
        if not name or len(name) < 2:
            return False, '姓名长度至少2个字符'
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', name):
            return False, '姓名只能包含中文和字母'
        return True, None

    @staticmethod
    def validate_date_range(start_date: date, end_date: date) -> tuple:
        if start_date and end_date:
            if start_date > end_date:
                return False, '开始日期不能晚于结束日期'
        return True, None

    @staticmethod
    def validate_amount(amount: float) -> tuple:
        if amount < 0:
            return False, '金额不能为负数'
        if amount > 1000000:
            return False, '金额超出合理范围'
        return True, None

    @staticmethod
    def validate_gpa(gpa: float) -> tuple:
        if gpa < 0 or gpa > 4.0:
            return False, 'GPA必须在0-4.0之间'
        return True, None

    @staticmethod
    def validate_email(email: str) -> tuple:
        if not email:
            return True, None
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, '邮箱格式不正确'
        return True, None

    @staticmethod
    def validate_phone(phone: str) -> tuple:
        if not phone:
            return True, None
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, phone):
            return False, '手机号格式不正确'
        return True, None

    @staticmethod
    def validate_year(year: int) -> tuple:
        current_year = datetime.now().year
        if year < 2000 or year > current_year + 5:
            return False, f'年份必须在2000-{current_year + 5}之间'
        return True, None

    @staticmethod
    def validate_application_data(data: dict) -> tuple:
        errors = []

        if 'student_id' not in data or not data['student_id']:
            errors.append('学生ID不能为空')

        if 'scholarship_type_id' not in data or not data['scholarship_type_id']:
            errors.append('奖助学金类型ID不能为空')

        if 'reason' in data and len(data['reason']) > 1000:
            errors.append('申请原因不能超过1000字符')

        if errors:
            return False, errors
        return True, None

    @staticmethod
    def validate_quota_data(data: dict) -> tuple:
        errors = []

        if 'quota' in data and data['quota'] < 0:
            errors.append('名额不能为负数')

        if 'budget' in data:
            valid, msg = Validator.validate_amount(data['budget'])
            if not valid:
                errors.append(msg)

        if 'year' in data:
            valid, msg = Validator.validate_year(data['year'])
            if not valid:
                errors.append(msg)

        if errors:
            return False, errors
        return True, None

    @staticmethod
    def sanitize_input(text: str) -> str:
        if not text:
            return text
        text = text.strip()
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`']
        for char in dangerous_chars:
            text = text.replace(char, '')
        return text