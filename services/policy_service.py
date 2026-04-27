from datetime import datetime, date
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func

from models import ScholarshipType, Department, DepartmentQuota, Application
from config import Config, ErrorCode
from utils.validators import Validator
from services.log_service import log_service


class PolicyService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def _build_response(self, success: bool, code: str = ErrorCode.SUCCESS.value,
                        message: str = "", data: Optional[Dict] = None) -> Dict[str, Any]:
        return {
            'success': success,
            'code': code,
            'message': message or Config.get_error_message(code),
            'data': data or {}
        }
    
    def _build_error_response(self, code: str, message: Optional[str] = None,
                               details: Optional[List] = None) -> Dict[str, Any]:
        response = {
            'success': False,
            'code': code,
            'message': message or Config.get_error_message(code),
            'data': {}
        }
        if details:
            response['details'] = details
        return response
    
    def _check_permission(self, user_id: int, permission: str) -> Dict[str, Any]:
        try:
            from models import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return self._build_error_response(ErrorCode.USER_NOT_FOUND.value)
            
            if not Config.has_permission(user.role, permission):
                log_service.log_permission_denied(user_id, permission, "policy_operation")
                return self._build_error_response(ErrorCode.PERMISSION_DENIED.value)
            
            return self._build_response(True, data={'user': user})
            
        except SQLAlchemyError as e:
            log_service.log_error("检查政策权限", e, user_id=user_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def create_scholarship_policy(
        self,
        name: str,
        code: str,
        policy_type: str,
        description: str = "",
        amount: float = 0.0,
        min_gpa: float = 0.0,
        max_application_count: int = 0,
        application_start_date: Optional[date] = None,
        application_end_date: Optional[date] = None,
        review_start_date: Optional[date] = None,
        review_end_date: Optional[date] = None,
        disbursement_date: Optional[date] = None,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"开始创建奖助金政策: name={name}, code={code}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'create_policy')
            if not perm_check['success']:
                return perm_check
        
        name_validation = Validator.validate_name(name, "奖助金名称", min_length=2, max_length=100)
        if not name_validation.valid:
            return self._build_error_response(name_validation.code, name_validation.message)
        
        if not code or not code.strip():
            return self._build_error_response(ErrorCode.INVALID_PARAMETER.value, "奖助金代码不能为空")
        
        code = code.strip().upper()
        if len(code) > 50:
            return self._build_error_response(ErrorCode.INVALID_PARAMETER.value, "奖助金代码长度不能超过50位")
        
        if policy_type not in [
            Config.SCHOLARSHIP_TYPES['SCHOLARSHIP'],
            Config.SCHOLARSHIP_TYPES['GRANT']
        ]:
            return self._build_error_response(
                ErrorCode.INVALID_PARAMETER.value,
                f"政策类型必须是 {Config.SCHOLARSHIP_TYPES['SCHOLARSHIP']} 或 {Config.SCHOLARSHIP_TYPES['GRANT']}"
            )
        
        if amount is not None:
            amount_validation = Validator.validate_amount(amount, "金额", min_value=0)
            if not amount_validation.valid:
                return self._build_error_response(amount_validation.code, amount_validation.message)
        
        if min_gpa is not None and min_gpa > 0:
            gpa_validation = Validator.validate_gpa(min_gpa)
            if not gpa_validation.valid:
                return self._build_error_response(gpa_validation.code, gpa_validation.message)
        
        if application_start_date and application_end_date:
            date_validation = Validator.validate_date_range(
                application_start_date, application_end_date, "申报期"
            )
            if not date_validation.valid:
                return self._build_error_response(date_validation.code, date_validation.message)
        
        if review_start_date and review_end_date:
            date_validation = Validator.validate_date_range(
                review_start_date, review_end_date, "审核期"
            )
            if not date_validation.valid:
                return self._build_error_response(date_validation.code, date_validation.message)
        
        try:
            existing = self.db.query(ScholarshipType).filter(
                (ScholarshipType.name == name) | (ScholarshipType.code == code)
            ).first()
            
            if existing:
                log_service.warning(f"奖助金名称或代码已存在: name={name}, code={code}")
                return self._build_error_response(ErrorCode.QUOTA_EXISTS.value, "奖助金名称或代码已存在")
            
            scholarship_type = ScholarshipType(
                name=name,
                code=code,
                type=policy_type,
                description=description,
                amount=amount,
                min_gpa=min_gpa,
                max_application_count=max_application_count,
                application_start_date=application_start_date,
                application_end_date=application_end_date,
                review_start_date=review_start_date,
                review_end_date=review_end_date,
                disbursement_date=disbursement_date
            )
            
            self.db.add(scholarship_type)
            self.db.flush()
            
            log_service.log_operation(
                operation="创建奖助金政策",
                details={
                    'policy_id': scholarship_type.id,
                    'name': name,
                    'code': code,
                    'type': policy_type,
                    'amount': amount
                }
            )
            
            return self._build_response(
                success=True,
                data={
                    'policy_id': scholarship_type.id,
                    'name': name,
                    'code': code
                },
                message="奖助金政策创建成功"
            )
            
        except IntegrityError as e:
            self.db.rollback()
            log_service.log_error("创建奖助金政策", e)
            return self._build_error_response(ErrorCode.CONCURRENT_MODIFICATION.value)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("创建奖助金政策", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def update_scholarship_policy(
        self,
        policy_id: int,
        operator_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        log_service.info(f"开始更新奖助金政策: policy_id={policy_id}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'update_policy')
            if not perm_check['success']:
                return perm_check
        
        validation = Validator.validate_id(policy_id, "政策ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        try:
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == policy_id
            ).with_for_update().first()
            
            if not scholarship_type:
                log_service.warning(f"奖助金政策不存在: policy_id={policy_id}")
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            valid_fields = [
                'name', 'code', 'type', 'description', 'amount', 'min_gpa',
                'max_application_count', 'application_start_date', 'application_end_date',
                'review_start_date', 'review_end_date', 'disbursement_date'
            ]
            
            updated_fields = {}
            
            for key, value in kwargs.items():
                if key in valid_fields and value is not None:
                    if key == 'name':
                        name_validation = Validator.validate_name(value, "奖助金名称")
                        if not name_validation.valid:
                            return self._build_error_response(name_validation.code, name_validation.message)
                    
                    if key == 'code':
                        value = value.strip().upper() if value else value
                    
                    if key == 'amount' and value is not None:
                        amount_validation = Validator.validate_amount(value, "金额")
                        if not amount_validation.valid:
                            return self._build_error_response(amount_validation.code, amount_validation.message)
                    
                    if key == 'min_gpa' and value is not None and value > 0:
                        gpa_validation = Validator.validate_gpa(value)
                        if not gpa_validation.valid:
                            return self._build_error_response(gpa_validation.code, gpa_validation.message)
                    
                    setattr(scholarship_type, key, value)
                    updated_fields[key] = value
            
            if updated_fields:
                self.db.flush()
                
                log_service.log_operation(
                    operation="更新奖助金政策",
                    details={
                        'policy_id': policy_id,
                        'updated_fields': updated_fields
                    }
                )
            
            return self._build_response(
                success=True,
                data={
                    'policy_id': policy_id,
                    'updated_fields': updated_fields
                },
                message="奖助金政策更新成功"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("更新奖助金政策", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_policy_by_id(self, policy_id: int) -> Dict[str, Any]:
        try:
            policy = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == policy_id
            ).first()
            
            if not policy:
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            return self._build_response(
                success=True,
                data=self._format_policy(policy)
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询奖助金政策", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_all_policies(
        self,
        page: int = 1,
        page_size: int = None,
        policy_type: Optional[str] = None,
        active_only: bool = False
    ) -> Dict[str, Any]:
        try:
            page, page_size = Validator.validate_pagination(page, page_size)
            
            query = self.db.query(ScholarshipType)
            
            if policy_type:
                if policy_type not in [
                    Config.SCHOLARSHIP_TYPES['SCHOLARSHIP'],
                    Config.SCHOLARSHIP_TYPES['GRANT']
                ]:
                    return self._build_error_response(
                        ErrorCode.INVALID_PARAMETER.value,
                        f"政策类型必须是 {Config.SCHOLARSHIP_TYPES['SCHOLARSHIP']} 或 {Config.SCHOLARSHIP_TYPES['GRANT']}"
                    )
                query = query.filter(ScholarshipType.type == policy_type)
            
            if active_only:
                today = datetime.utcnow().date()
                query = query.filter(
                    ScholarshipType.application_start_date <= today,
                    ScholarshipType.application_end_date >= today
                )
            
            total = query.count()
            
            policies = query.order_by(
                ScholarshipType.created_at.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_policy(p) for p in policies],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    }
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询所有奖助金政策", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_active_policies(self, page: int = 1, page_size: int = None) -> Dict[str, Any]:
        return self.get_all_policies(page, page_size, active_only=True)
    
    def validate_application_period(self, policy_id: int) -> Dict[str, Any]:
        try:
            policy = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == policy_id
            ).first()
            
            if not policy:
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            today = datetime.utcnow().date()
            
            in_period = True
            message = "当前在申报期内"
            
            if policy.application_start_date and policy.application_end_date:
                if today < policy.application_start_date:
                    in_period = False
                    message = f"申报尚未开始，开始日期：{policy.application_start_date}"
                elif today > policy.application_end_date:
                    in_period = False
                    message = f"申报已结束，结束日期：{policy.application_end_date}"
            
            return self._build_response(
                success=True,
                data={
                    'in_period': in_period,
                    'application_start_date': policy.application_start_date,
                    'application_end_date': policy.application_end_date,
                    'current_date': today
                },
                message=message
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("验证申报期", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_policy_statistics(
        self,
        policy_id: int,
        year: Optional[int] = None,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"获取政策统计: policy_id={policy_id}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'view_all_quotas')
            if not perm_check['success']:
                return perm_check
        
        if year is None:
            year = datetime.utcnow().year
        
        try:
            policy = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == policy_id
            ).first()
            
            if not policy:
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            quotas = self.db.query(DepartmentQuota).options(
                joinedload(DepartmentQuota.department)
            ).filter(
                DepartmentQuota.scholarship_type_id == policy_id,
                DepartmentQuota.year == year
            ).all()
            
            total_quota = sum(q.quota for q in quotas)
            total_budget = sum(q.budget for q in quotas)
            total_used_quota = sum(q.used_quota for q in quotas)
            total_used_budget = sum(q.used_budget for q in quotas)
            
            applications = self.db.query(Application).filter(
                Application.scholarship_type_id == policy_id
            ).all()
            
            total_applications = len(applications)
            approved_applications = sum(
                1 for app in applications
                if app.status in [
                    Config.APPLICATION_STATUS['APPROVED'],
                    Config.APPLICATION_STATUS['PUBLIC_NOTICE'],
                    Config.APPLICATION_STATUS['DISBURSED'],
                    Config.APPLICATION_STATUS['VERIFIED']
                ]
            )
            
            statistics = {
                'policy': {
                    'id': policy.id,
                    'name': policy.name,
                    'code': policy.code,
                    'type': policy.type,
                    'amount': policy.amount,
                    'min_gpa': policy.min_gpa
                },
                'year': year,
                'quota_summary': {
                    'total_departments': len(quotas),
                    'total_quota': total_quota,
                    'total_budget': total_budget,
                    'total_used_quota': total_used_quota,
                    'total_used_budget': total_used_budget,
                    'remaining_quota': total_quota - total_used_quota,
                    'remaining_budget': total_budget - total_used_budget,
                    'quota_utilization': round(total_used_quota / total_quota * 100, 2) if total_quota > 0 else 0,
                    'budget_utilization': round(total_used_budget / total_budget * 100, 2) if total_budget > 0 else 0
                },
                'application_summary': {
                    'total_applications': total_applications,
                    'approved_applications': approved_applications,
                    'approval_rate': round(approved_applications / total_applications * 100, 2) if total_applications > 0 else 0
                },
                'department_details': [
                    {
                        'department_id': q.department_id,
                        'department_name': q.department.name if q.department else None,
                        'quota': q.quota,
                        'budget': q.budget,
                        'used_quota': q.used_quota,
                        'used_budget': q.used_budget,
                        'remaining_quota': q.quota - q.used_quota,
                        'remaining_budget': q.budget - q.used_budget,
                        'quota_utilization': round(q.used_quota / q.quota * 100, 2) if q.quota > 0 else 0,
                        'budget_utilization': round(q.used_budget / q.budget * 100, 2) if q.budget > 0 else 0
                    }
                    for q in quotas
                ]
            }
            
            return self._build_response(
                success=True,
                data=statistics
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("获取政策统计", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _format_policy(self, policy: ScholarshipType) -> Dict[str, Any]:
        today = datetime.utcnow().date()
        is_active = True
        
        if policy.application_start_date and policy.application_end_date:
            is_active = policy.application_start_date <= today <= policy.application_end_date
        
        return {
            'id': policy.id,
            'name': policy.name,
            'code': policy.code,
            'type': policy.type,
            'description': policy.description,
            'amount': policy.amount,
            'min_gpa': policy.min_gpa,
            'max_application_count': policy.max_application_count,
            'application_period': {
                'start': policy.application_start_date,
                'end': policy.application_end_date
            },
            'review_period': {
                'start': policy.review_start_date,
                'end': policy.review_end_date
            },
            'disbursement_date': policy.disbursement_date,
            'is_active': is_active,
            'created_at': policy.created_at,
            'updated_at': policy.updated_at
        }
