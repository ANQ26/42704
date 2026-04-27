from datetime import datetime, date
from typing import Dict, Optional, List, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy import func

from models import DepartmentQuota, Department, ScholarshipType, Application
from config import Config, ErrorCode
from utils.validators import Validator
from services.log_service import log_service


class QuotaService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self._notification_service = None
    
    @property
    def notification_service(self):
        if self._notification_service is None:
            from .notification_service import NotificationService
            self._notification_service = NotificationService(self.db)
        return self._notification_service
    
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
                log_service.log_permission_denied(user_id, permission, "quota_operation")
                return self._build_error_response(ErrorCode.PERMISSION_DENIED.value)
            
            return self._build_response(True, data={'user': user})
            
        except SQLAlchemyError as e:
            log_service.log_error("检查配额权限", e, user_id=user_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def create_department_quota(
        self,
        department_id: int,
        scholarship_type_id: int,
        year: int,
        quota: int,
        budget: float,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"开始创建院系额度: department_id={department_id}, scholarship_type_id={scholarship_type_id}, year={year}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'create_quota')
            if not perm_check['success']:
                return perm_check
        
        validation = Validator.validate_create_quota(
            department_id, scholarship_type_id, year, quota, budget
        )
        if not validation.valid:
            log_service.warning(f"参数校验失败: {validation.message}")
            return self._build_error_response(
                validation.code, validation.message, validation.details
            )
        
        try:
            existing = self.db.query(DepartmentQuota).filter(
                DepartmentQuota.department_id == department_id,
                DepartmentQuota.scholarship_type_id == scholarship_type_id,
                DepartmentQuota.year == year
            ).first()
            
            if existing:
                log_service.warning(f"额度配置已存在: department_id={department_id}, scholarship_type_id={scholarship_type_id}, year={year}")
                return self._build_error_response(ErrorCode.QUOTA_EXISTS.value)
            
            department = self.db.query(Department).filter(Department.id == department_id).first()
            if not department:
                log_service.warning(f"院系不存在: department_id={department_id}")
                return self._build_error_response(ErrorCode.DEPARTMENT_NOT_FOUND.value)
            
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            if not scholarship_type:
                log_service.warning(f"奖助金类型不存在: scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            department_quota = DepartmentQuota(
                department_id=department_id,
                scholarship_type_id=scholarship_type_id,
                year=year,
                quota=quota,
                budget=budget,
                used_quota=0,
                used_budget=0.0
            )
            
            self.db.add(department_quota)
            self.db.flush()
            
            log_service.log_operation(
                operation="创建院系额度",
                details={
                    'department_id': department_id,
                    'scholarship_type_id': scholarship_type_id,
                    'year': year,
                    'quota': quota,
                    'budget': budget
                }
            )
            
            return self._build_response(
                success=True,
                data={
                    'quota_id': department_quota.id,
                    'department_id': department_id,
                    'scholarship_type_id': scholarship_type_id,
                    'year': year,
                    'quota': quota,
                    'budget': budget
                },
                message="院系额度创建成功"
            )
            
        except IntegrityError as e:
            self.db.rollback()
            log_service.log_error("创建院系额度", e)
            return self._build_error_response(ErrorCode.CONCURRENT_MODIFICATION.value)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("创建院系额度", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def update_department_quota(
        self,
        quota_id: int,
        quota: Optional[int] = None,
        budget: Optional[float] = None,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"开始更新院系额度: quota_id={quota_id}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'update_quota')
            if not perm_check['success']:
                return perm_check
        
        validation = Validator.validate_id(quota_id, "额度ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        try:
            department_quota = self.db.query(DepartmentQuota).options(
                joinedload(DepartmentQuota.department),
                joinedload(DepartmentQuota.scholarship_type)
            ).filter(DepartmentQuota.id == quota_id).with_for_update().first()
            
            if not department_quota:
                log_service.warning(f"额度记录不存在: quota_id={quota_id}")
                return self._build_error_response(ErrorCode.QUOTA_NOT_FOUND.value)
            
            updated_fields = {}
            
            if quota is not None:
                quota_validation = Validator.validate_quota(quota)
                if not quota_validation.valid:
                    return self._build_error_response(quota_validation.code, quota_validation.message)
                
                if quota < department_quota.used_quota:
                    log_service.warning(f"新名额小于已使用名额: quota_id={quota_id}, new={quota}, used={department_quota.used_quota}")
                    return self._build_error_response(ErrorCode.QUOTA_TOO_SMALL.value)
                
                department_quota.quota = quota
                updated_fields['quota'] = quota
            
            if budget is not None:
                budget_validation = Validator.validate_amount(budget, "预算")
                if not budget_validation.valid:
                    return self._build_error_response(budget_validation.code, budget_validation.message)
                
                if budget < department_quota.used_budget:
                    log_service.warning(f"新预算小于已使用预算: quota_id={quota_id}, new={budget}, used={department_quota.used_budget}")
                    return self._build_error_response(ErrorCode.BUDGET_TOO_SMALL.value)
                
                department_quota.budget = budget
                updated_fields['budget'] = budget
            
            self.db.flush()
            
            log_service.log_operation(
                operation="更新院系额度",
                details={
                    'quota_id': quota_id,
                    'updated_fields': updated_fields
                }
            )
            
            return self._build_response(
                success=True,
                data={
                    'quota_id': department_quota.id,
                    'quota': department_quota.quota,
                    'budget': department_quota.budget
                },
                message="额度更新成功"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("更新院系额度", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def check_quota_availability(
        self,
        department_id: int,
        scholarship_type_id: int,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"检查额度可用性: department_id={department_id}, scholarship_type_id={scholarship_type_id}")
        
        if year is None:
            year = datetime.utcnow().year
        
        try:
            department_quota = self.db.query(DepartmentQuota).options(
                joinedload(DepartmentQuota.department),
                joinedload(DepartmentQuota.scholarship_type)
            ).filter(
                DepartmentQuota.department_id == department_id,
                DepartmentQuota.scholarship_type_id == scholarship_type_id,
                DepartmentQuota.year == year
            ).first()
            
            if not department_quota:
                log_service.info(f"未设置额度限制: department_id={department_id}, scholarship_type_id={scholarship_type_id}, year={year}")
                return self._build_response(
                    success=True,
                    data={
                        'available': True,
                        'warning': False,
                        'quota': None,
                        'budget': None,
                        'used_quota': 0,
                        'used_budget': 0.0,
                        'remaining_quota': None,
                        'remaining_budget': None
                    },
                    message="未设置额度限制"
                )
            
            remaining_quota = department_quota.quota - department_quota.used_quota
            remaining_budget = department_quota.budget - department_quota.used_budget
            
            scholarship_type = department_quota.scholarship_type
            estimated_budget_needed = scholarship_type.amount if scholarship_type else 0
            
            available = remaining_quota > 0 and (
                estimated_budget_needed == 0 or remaining_budget >= estimated_budget_needed
            )
            
            warning = False
            if department_quota.quota > 0:
                if remaining_quota <= department_quota.quota * Config.QUOTA_WARNING_THRESHOLD:
                    warning = True
            
            if department_quota.budget > 0:
                if remaining_budget <= department_quota.budget * Config.QUOTA_WARNING_THRESHOLD:
                    warning = True
            
            if warning:
                log_service.log_quota_warning(
                    department_id=department_id,
                    scholarship_type_id=scholarship_type_id,
                    remaining_quota=remaining_quota,
                    remaining_budget=remaining_budget
                )
                
                department_name = department_quota.department.name if department_quota.department else "未知院系"
                scholarship_name = scholarship_type.name if scholarship_type else "未知奖助金"
                
                self.notification_service.create_notification(
                    user_id=None,
                    student_id=None,
                    title="院系额度预警",
                    content=f"院系{department_name}的{scholarship_name}"
                           f"额度即将用尽。剩余名额: {remaining_quota}, 剩余预算: {remaining_budget}元",
                    notification_type=Config.NOTIFICATION_TYPES['QUOTA_WARNING']
                )
            
            return self._build_response(
                success=True,
                data={
                    'available': available,
                    'warning': warning,
                    'quota': department_quota.quota,
                    'budget': department_quota.budget,
                    'used_quota': department_quota.used_quota,
                    'used_budget': department_quota.used_budget,
                    'remaining_quota': remaining_quota,
                    'remaining_budget': remaining_budget
                },
                message="额度可用" if available else "额度不足"
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("检查额度可用性", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def update_used_quota(
        self,
        department_id: int,
        scholarship_type_id: int,
        amount: float,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"更新已使用额度: department_id={department_id}, scholarship_type_id={scholarship_type_id}, amount={amount}")
        
        if year is None:
            year = datetime.utcnow().year
        
        amount_validation = Validator.validate_amount(amount, "发放金额")
        if not amount_validation.valid:
            return self._build_error_response(amount_validation.code, amount_validation.message)
        
        try:
            department_quota = self.db.query(DepartmentQuota).filter(
                DepartmentQuota.department_id == department_id,
                DepartmentQuota.scholarship_type_id == scholarship_type_id,
                DepartmentQuota.year == year
            ).with_for_update().first()
            
            if not department_quota:
                log_service.info(f"未设置额度，跳过更新: department_id={department_id}, scholarship_type_id={scholarship_type_id}, year={year}")
                return self._build_response(
                    success=True,
                    data={'code': ErrorCode.NO_QUOTA_SET.value},
                    message="未设置额度，跳过更新"
                )
            
            if department_quota.used_quota + 1 > department_quota.quota:
                log_service.warning(f"名额已用尽: department_id={department_id}, scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.QUOTA_EXCEEDED.value)
            
            if department_quota.used_budget + amount > department_quota.budget:
                log_service.warning(f"预算已用尽: department_id={department_id}, scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.BUDGET_EXCEEDED.value)
            
            department_quota.used_quota += 1
            department_quota.used_budget += amount
            
            self.db.flush()
            
            log_service.log_quota_update(
                department_id=department_id,
                scholarship_type_id=scholarship_type_id,
                used_quota=department_quota.used_quota,
                used_budget=department_quota.used_budget,
                success=True
            )
            
            return self._build_response(
                success=True,
                data={
                    'used_quota': department_quota.used_quota,
                    'used_budget': department_quota.used_budget,
                    'remaining_quota': department_quota.quota - department_quota.used_quota,
                    'remaining_budget': department_quota.budget - department_quota.used_budget
                },
                message="额度更新成功"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("更新已使用额度", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_department_quota(
        self,
        department_id: int,
        scholarship_type_id: int,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        if year is None:
            year = datetime.utcnow().year
        
        try:
            department_quota = self.db.query(DepartmentQuota).options(
                joinedload(DepartmentQuota.department),
                joinedload(DepartmentQuota.scholarship_type)
            ).filter(
                DepartmentQuota.department_id == department_id,
                DepartmentQuota.scholarship_type_id == scholarship_type_id,
                DepartmentQuota.year == year
            ).first()
            
            if not department_quota:
                return self._build_error_response(ErrorCode.QUOTA_NOT_FOUND.value)
            
            return self._build_response(
                success=True,
                data=self._format_quota(department_quota)
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询院系额度", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_all_quotas_by_department(
        self,
        department_id: int,
        year: Optional[int] = None,
        page: int = 1,
        page_size: int = None
    ) -> Dict[str, Any]:
        try:
            page, page_size = Validator.validate_pagination(page, page_size)
            
            query = self.db.query(DepartmentQuota).options(
                joinedload(DepartmentQuota.scholarship_type)
            ).filter(DepartmentQuota.department_id == department_id)
            
            if year:
                year_validation = Validator.validate_year(year)
                if not year_validation.valid:
                    return self._build_error_response(year_validation.code, year_validation.message)
                query = query.filter(DepartmentQuota.year == year)
            
            total = query.count()
            
            quotas = query.order_by(
                DepartmentQuota.year.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_quota(q) for q in quotas],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    }
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("按院系查询额度", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_quota_statistics(
        self,
        year: Optional[int] = None,
        department_id: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            if year is None:
                year = datetime.utcnow().year
            
            query = self.db.query(DepartmentQuota).options(
                joinedload(DepartmentQuota.department),
                joinedload(DepartmentQuota.scholarship_type)
            ).filter(DepartmentQuota.year == year)
            
            if department_id:
                query = query.filter(DepartmentQuota.department_id == department_id)
            
            quotas = query.all()
            
            statistics = []
            total_quota = 0
            total_used_quota = 0
            total_budget = 0.0
            total_used_budget = 0.0
            
            for quota in quotas:
                quota_utilization = (quota.used_quota / quota.quota * 100) if quota.quota > 0 else 0
                budget_utilization = (quota.used_budget / quota.budget * 100) if quota.budget > 0 else 0
                
                total_quota += quota.quota
                total_used_quota += quota.used_quota
                total_budget += quota.budget
                total_used_budget += quota.used_budget
                
                statistics.append({
                    'quota_id': quota.id,
                    'department': quota.department.name if quota.department else None,
                    'department_id': quota.department_id,
                    'scholarship_type': quota.scholarship_type.name if quota.scholarship_type else None,
                    'scholarship_type_id': quota.scholarship_type_id,
                    'year': quota.year,
                    'quota': quota.quota,
                    'budget': quota.budget,
                    'used_quota': quota.used_quota,
                    'used_budget': quota.used_budget,
                    'remaining_quota': quota.quota - quota.used_quota,
                    'remaining_budget': quota.budget - quota.used_budget,
                    'quota_utilization': round(quota_utilization, 2),
                    'budget_utilization': round(budget_utilization, 2)
                })
            
            overall_statistics = {
                'total_quota': total_quota,
                'total_used_quota': total_used_quota,
                'total_budget': total_budget,
                'total_used_budget': total_used_budget,
                'overall_quota_utilization': round(total_used_quota / total_quota * 100, 2) if total_quota > 0 else 0,
                'overall_budget_utilization': round(total_used_budget / total_budget * 100, 2) if total_budget > 0 else 0
            }
            
            return self._build_response(
                success=True,
                data={
                    'year': year,
                    'statistics': statistics,
                    'summary': overall_statistics,
                    'total_departments': len(set(q.department_id for q in quotas))
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询额度统计", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _format_quota(self, quota: DepartmentQuota) -> Dict[str, Any]:
        result = {
            'id': quota.id,
            'department_id': quota.department_id,
            'scholarship_type_id': quota.scholarship_type_id,
            'year': quota.year,
            'quota': quota.quota,
            'budget': quota.budget,
            'used_quota': quota.used_quota,
            'used_budget': quota.used_budget,
            'remaining_quota': quota.quota - quota.used_quota,
            'remaining_budget': quota.budget - quota.used_budget,
            'created_at': quota.created_at,
            'updated_at': quota.updated_at
        }
        
        if quota.scholarship_type:
            result['scholarship_type'] = {
                'id': quota.scholarship_type.id,
                'name': quota.scholarship_type.name,
                'code': quota.scholarship_type.code,
                'type': quota.scholarship_type.type,
                'amount': quota.scholarship_type.amount
            }
        
        if quota.department:
            result['department'] = {
                'id': quota.department.id,
                'name': quota.department.name,
                'code': quota.department.code
            }
        
        return result
