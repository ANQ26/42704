from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session

from models import DepartmentQuota, Department, ScholarshipType, Application
from config import Config


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
    
    def create_department_quota(
        self,
        department_id: int,
        scholarship_type_id: int,
        year: int,
        quota: int,
        budget: float
    ) -> Dict:
        try:
            existing = self.db.query(DepartmentQuota).filter(
                DepartmentQuota.department_id == department_id,
                DepartmentQuota.scholarship_type_id == scholarship_type_id,
                DepartmentQuota.year == year
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "message": "该院系该年度该奖助金类型的额度已存在",
                    "code": "QUOTA_EXISTS"
                }
            
            department = self.db.query(Department).filter(Department.id == department_id).first()
            if not department:
                return {"success": False, "message": "院系不存在", "code": "DEPARTMENT_NOT_FOUND"}
            
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            if not scholarship_type:
                return {"success": False, "message": "奖助金类型不存在", "code": "SCHOLARSHIP_NOT_FOUND"}
            
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
            
            return {
                "success": True,
                "message": "院系额度创建成功",
                "quota_id": department_quota.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def update_department_quota(
        self,
        quota_id: int,
        quota: Optional[int] = None,
        budget: Optional[float] = None
    ) -> Dict:
        try:
            department_quota = self.db.query(DepartmentQuota).filter(
                DepartmentQuota.id == quota_id
            ).first()
            
            if not department_quota:
                return {"success": False, "message": "额度记录不存在", "code": "QUOTA_NOT_FOUND"}
            
            if quota is not None:
                if quota < department_quota.used_quota:
                    return {
                        "success": False,
                        "message": "新名额不能小于已使用名额",
                        "code": "QUOTA_TOO_SMALL"
                    }
                department_quota.quota = quota
            
            if budget is not None:
                if budget < department_quota.used_budget:
                    return {
                        "success": False,
                        "message": "新预算不能小于已使用预算",
                        "code": "BUDGET_TOO_SMALL"
                    }
                department_quota.budget = budget
            
            return {
                "success": True,
                "message": "额度更新成功",
                "quota_id": department_quota.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def check_quota_availability(
        self,
        department_id: int,
        scholarship_type_id: int,
        year: Optional[int] = None
    ) -> Dict:
        if year is None:
            year = datetime.utcnow().year
        
        department_quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()
        
        if not department_quota:
            return {
                "available": True,
                "warning": False,
                "message": "未设置额度限制",
                "quota": None,
                "budget": None,
                "used_quota": 0,
                "used_budget": 0.0
            }
        
        remaining_quota = department_quota.quota - department_quota.used_quota
        remaining_budget = department_quota.budget - department_quota.used_budget
        
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        
        estimated_budget_needed = scholarship_type.amount if scholarship_type else 0
        
        available = remaining_quota > 0 and (
            estimated_budget_needed == 0 or remaining_budget >= estimated_budget_needed
        )
        
        warning = False
        if remaining_quota <= department_quota.quota * 0.1:
            warning = True
        
        if remaining_budget <= department_quota.budget * 0.1:
            warning = True
        
        if warning:
            self.notification_service.create_notification(
                user_id=None,
                student_id=None,
                title="院系额度预警",
                content=f"院系{department_quota.department.name}的{department_quota.scholarship_type.name}"
                       f"额度即将用尽。剩余名额: {remaining_quota}, 剩余预算: {remaining_budget}",
                notification_type=Config.NOTIFICATION_TYPES['QUOTA_WARNING']
            )
        
        return {
            "available": available,
            "warning": warning,
            "message": "额度可用" if available else "额度不足",
            "quota": department_quota.quota,
            "budget": department_quota.budget,
            "used_quota": department_quota.used_quota,
            "used_budget": department_quota.used_budget,
            "remaining_quota": remaining_quota,
            "remaining_budget": remaining_budget
        }
    
    def update_used_quota(
        self,
        department_id: int,
        scholarship_type_id: int,
        amount: float,
        year: Optional[int] = None
    ) -> Dict:
        try:
            if year is None:
                year = datetime.utcnow().year
            
            department_quota = self.db.query(DepartmentQuota).filter(
                DepartmentQuota.department_id == department_id,
                DepartmentQuota.scholarship_type_id == scholarship_type_id,
                DepartmentQuota.year == year
            ).first()
            
            if not department_quota:
                return {
                    "success": True,
                    "message": "未设置额度，跳过更新",
                    "code": "NO_QUOTA_SET"
                }
            
            if department_quota.used_quota + 1 > department_quota.quota:
                return {
                    "success": False,
                    "message": "名额已用尽",
                    "code": "QUOTA_EXCEEDED"
                }
            
            if department_quota.used_budget + amount > department_quota.budget:
                return {
                    "success": False,
                    "message": "预算已用尽",
                    "code": "BUDGET_EXCEEDED"
                }
            
            department_quota.used_quota += 1
            department_quota.used_budget += amount
            
            return {
                "success": True,
                "message": "额度更新成功",
                "used_quota": department_quota.used_quota,
                "used_budget": department_quota.used_budget
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def get_department_quota(
        self,
        department_id: int,
        scholarship_type_id: int,
        year: Optional[int] = None
    ) -> Optional[DepartmentQuota]:
        if year is None:
            year = datetime.utcnow().year
        
        return self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()
    
    def get_all_quotas_by_department(self, department_id: int, year: Optional[int] = None) -> List[Dict]:
        query = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id
        )
        
        if year:
            query = query.filter(DepartmentQuota.year == year)
        
        quotas = query.all()
        
        result = []
        for quota in quotas:
            result.append({
                'id': quota.id,
                'scholarship_type': quota.scholarship_type.name,
                'year': quota.year,
                'quota': quota.quota,
                'budget': quota.budget,
                'used_quota': quota.used_quota,
                'used_budget': quota.used_budget,
                'remaining_quota': quota.quota - quota.used_quota,
                'remaining_budget': quota.budget - quota.used_budget
            })
        
        return result
    
    def get_quota_statistics(self, year: Optional[int] = None) -> List[Dict]:
        if year is None:
            year = datetime.utcnow().year
        
        quotas = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.year == year
        ).all()
        
        statistics = []
        for quota in quotas:
            quota_utilization = (quota.used_quota / quota.quota * 100) if quota.quota > 0 else 0
            budget_utilization = (quota.used_budget / quota.budget * 100) if quota.budget > 0 else 0
            
            statistics.append({
                'department': quota.department.name,
                'scholarship_type': quota.scholarship_type.name,
                'quota_utilization': round(quota_utilization, 2),
                'budget_utilization': round(budget_utilization, 2),
                'remaining_quota': quota.quota - quota.used_quota,
                'remaining_budget': quota.budget - quota.used_budget
            })
        
        return statistics
