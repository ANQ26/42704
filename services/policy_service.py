from datetime import datetime, date
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import json

from models import ScholarshipType, Department, DepartmentQuota
from config import Config


class PolicyService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
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
        disbursement_date: Optional[date] = None
    ) -> Dict:
        try:
            existing = self.db.query(ScholarshipType).filter(
                (ScholarshipType.name == name) | (ScholarshipType.code == code)
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "message": "奖助金名称或代码已存在",
                    "code": "POLICY_EXISTS"
                }
            
            if policy_type not in [Config.SCHOLARSHIP_TYPES['SCHOLARSHIP'], Config.SCHOLARSHIP_TYPES['GRANT']]:
                return {
                    "success": False,
                    "message": "奖助金类型无效",
                    "code": "INVALID_TYPE"
                }
            
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
            
            return {
                "success": True,
                "message": "奖助金政策创建成功",
                "policy_id": scholarship_type.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def update_scholarship_policy(
        self,
        policy_id: int,
        **kwargs
    ) -> Dict:
        try:
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == policy_id
            ).first()
            
            if not scholarship_type:
                return {
                    "success": False,
                    "message": "奖助金政策不存在",
                    "code": "POLICY_NOT_FOUND"
                }
            
            valid_fields = [
                'name', 'code', 'type', 'description', 'amount', 'min_gpa',
                'max_application_count', 'application_start_date', 'application_end_date',
                'review_start_date', 'review_end_date', 'disbursement_date'
            ]
            
            for key, value in kwargs.items():
                if key in valid_fields:
                    setattr(scholarship_type, key, value)
            
            return {
                "success": True,
                "message": "奖助金政策更新成功",
                "policy_id": scholarship_type.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def get_policy_by_id(self, policy_id: int) -> Optional[Dict]:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == policy_id
        ).first()
        
        if not scholarship_type:
            return None
        
        return self._format_policy(scholarship_type)
    
    def get_all_policies(self) -> List[Dict]:
        policies = self.db.query(ScholarshipType).all()
        return [self._format_policy(p) for p in policies]
    
    def get_active_policies(self) -> List[Dict]:
        today = datetime.utcnow().date()
        
        policies = self.db.query(ScholarshipType).filter(
            ScholarshipType.application_start_date <= today,
            ScholarshipType.application_end_date >= today
        ).all()
        
        return [self._format_policy(p) for p in policies]
    
    def _format_policy(self, policy: ScholarshipType) -> Dict:
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
            'is_active': self._is_policy_active(policy)
        }
    
    def _is_policy_active(self, policy: ScholarshipType) -> bool:
        today = datetime.utcnow().date()
        
        if policy.application_start_date and policy.application_end_date:
            return policy.application_start_date <= today <= policy.application_end_date
        
        return True
    
    def set_department_quotas_for_policy(
        self,
        policy_id: int,
        year: int,
        department_quotas: List[Dict]
    ) -> Dict:
        try:
            policy = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == policy_id
            ).first()
            
            if not policy:
                return {
                    "success": False,
                    "message": "奖助金政策不存在",
                    "code": "POLICY_NOT_FOUND"
                }
            
            results = []
            for quota_data in department_quotas:
                department_id = quota_data.get('department_id')
                quota = quota_data.get('quota')
                budget = quota_data.get('budget')
                
                if not department_id or quota is None or budget is None:
                    results.append({
                        'department_id': department_id,
                        'success': False,
                        'message': '缺少必要参数'
                    })
                    continue
                
                department = self.db.query(Department).filter(
                    Department.id == department_id
                ).first()
                
                if not department:
                    results.append({
                        'department_id': department_id,
                        'success': False,
                        'message': '院系不存在'
                    })
                    continue
                
                existing = self.db.query(DepartmentQuota).filter(
                    DepartmentQuota.department_id == department_id,
                    DepartmentQuota.scholarship_type_id == policy_id,
                    DepartmentQuota.year == year
                ).first()
                
                if existing:
                    existing.quota = quota
                    existing.budget = budget
                    results.append({
                        'department_id': department_id,
                        'success': True,
                        'message': '额度更新成功'
                    })
                else:
                    new_quota = DepartmentQuota(
                        department_id=department_id,
                        scholarship_type_id=policy_id,
                        year=year,
                        quota=quota,
                        budget=budget,
                        used_quota=0,
                        used_budget=0.0
                    )
                    self.db.add(new_quota)
                    results.append({
                        'department_id': department_id,
                        'success': True,
                        'message': '额度创建成功'
                    })
            
            return {
                "success": True,
                "message": "院系额度配置完成",
                "results": results
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def validate_application_period(self, policy_id: int) -> Dict:
        policy = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == policy_id
        ).first()
        
        if not policy:
            return {
                "valid": False,
                "message": "奖助金政策不存在",
                "code": "POLICY_NOT_FOUND"
            }
        
        today = datetime.utcnow().date()
        
        if policy.application_start_date and policy.application_end_date:
            if today < policy.application_start_date:
                return {
                    "valid": False,
                    "message": f"申报尚未开始，开始日期：{policy.application_start_date}",
                    "code": "APPLICATION_NOT_STARTED"
                }
            if today > policy.application_end_date:
                return {
                    "valid": False,
                    "message": f"申报已结束，结束日期：{policy.application_end_date}",
                    "code": "APPLICATION_ENDED"
                }
        
        return {
            "valid": True,
            "message": "申报期有效",
            "current_date": today
        }
    
    def get_policy_statistics(self, policy_id: int, year: Optional[int] = None) -> Dict:
        if year is None:
            year = datetime.utcnow().year
        
        policy = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == policy_id
        ).first()
        
        if not policy:
            return {"error": "奖助金政策不存在"}
        
        quotas = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.scholarship_type_id == policy_id,
            DepartmentQuota.year == year
        ).all()
        
        total_quota = sum(q.quota for q in quotas)
        total_budget = sum(q.budget for q in quotas)
        total_used_quota = sum(q.used_quota for q in quotas)
        total_used_budget = sum(q.used_budget for q in quotas)
        
        return {
            "policy_name": policy.name,
            "year": year,
            "statistics": {
                "total_departments": len(quotas),
                "total_quota": total_quota,
                "total_budget": total_budget,
                "total_used_quota": total_used_quota,
                "total_used_budget": total_used_budget,
                "remaining_quota": total_quota - total_used_quota,
                "remaining_budget": total_budget - total_used_budget,
                "quota_utilization": round(total_used_quota / total_quota * 100, 2) if total_quota > 0 else 0,
                "budget_utilization": round(total_used_budget / total_budget * 100, 2) if total_budget > 0 else 0
            },
            "department_details": [
                {
                    "department_name": q.department.name,
                    "quota": q.quota,
                    "budget": q.budget,
                    "used_quota": q.used_quota,
                    "used_budget": q.used_budget
                } for q in quotas
            ]
        }
