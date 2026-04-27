from datetime import datetime
from sqlalchemy.orm import Session
from models import DepartmentQuota, Department, ScholarshipType, Application
from config import Config

class QuotaService:
    def __init__(self, db: Session):
        self.db = db
        self.warning_threshold = Config.QUOTA_WARNING_THRESHOLD

    def set_quota(self, department_id: int, scholarship_type_id: int, year: int, quota: int, budget: float) -> dict:
        department = self.db.query(Department).filter(Department.id == department_id).first()
        if not department:
            return {'success': False, 'error': '院系不存在'}

        scholarship_type = self.db.query(ScholarshipType).filter(ScholarshipType.id == scholarship_type_id).first()
        if not scholarship_type:
            return {'success': False, 'error': '奖助学金类型不存在'}

        existing = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()

        if existing:
            existing.quota = quota
            existing.budget = budget
            existing.updated_at = datetime.utcnow()
        else:
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

        self.db.commit()
        return {'success': True}

    def get_quota(self, department_id: int, scholarship_type_id: int, year: int) -> dict:
        quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()

        if not quota:
            return {
                'exists': False,
                'quota': 0,
                'budget': 0,
                'used_quota': 0,
                'used_budget': 0,
                'available_quota': 0,
                'available_budget': 0
            }

        return {
            'exists': True,
            'quota': quota.quota,
            'budget': quota.budget,
            'used_quota': quota.used_quota,
            'used_budget': quota.used_budget,
            'available_quota': quota.quota - quota.used_quota,
            'available_budget': quota.budget - quota.used_budget,
            'usage_rate': quota.used_quota / quota.quota if quota.quota > 0 else 0
        }

    def check_and_use_quota(self, department_id: int, scholarship_type_id: int, amount: float) -> dict:
        year = datetime.now().year
        quota_info = self.get_quota(department_id, scholarship_type_id, year)

        if not quota_info['exists']:
            return {'success': False, 'error': '该院系本年度未设置奖助学金额度'}

        if quota_info['used_quota'] >= quota_info['quota']:
            return {
                'success': False,
                'error': '名额已用完',
                'requires_multi_level_review': True,
                'quota_info': quota_info
            }

        if quota_info['used_budget'] + amount > quota_info['budget']:
            return {
                'success': False,
                'error': '预算不足',
                'requires_multi_level_review': True,
                'quota_info': quota_info
            }

        usage_rate = (quota_info['used_quota'] + 1) / quota_info['quota']
        if usage_rate >= self.warning_threshold:
            return {
                'success': True,
                'warning': True,
                'message': f'名额使用率已达{int(usage_rate * 100)}%，即将用完',
                'quota_info': quota_info
            }

        return {'success': True, 'quota_info': quota_info}

    def confirm_quota_usage(self, department_id: int, scholarship_type_id: int, amount: float):
        year = datetime.now().year
        quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()

        if quota:
            quota.used_quota += 1
            quota.used_budget += amount
            quota.updated_at = datetime.utcnow()
            self.db.commit()

    def release_quota(self, department_id: int, scholarship_type_id: int, amount: float):
        year = datetime.now().year
        quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()

        if quota:
            quota.used_quota = max(0, quota.used_quota - 1)
            quota.used_budget = max(0, quota.used_budget - amount)
            quota.updated_at = datetime.utcnow()
            self.db.commit()

    def get_department_quotas(self, department_id: int, year: int = None) -> list:
        if year is None:
            year = datetime.now().year

        quotas = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.year == year
        ).all()

        result = []
        for quota in quotas:
            result.append({
                'scholarship_type': quota.scholarship_type.name,
                'quota': quota.quota,
                'budget': quota.budget,
                'used_quota': quota.used_quota,
                'used_budget': quota.used_budget,
                'available_quota': quota.quota - quota.used_quota,
                'available_budget': quota.budget - quota.used_budget,
                'usage_rate': quota.used_quota / quota.quota if quota.quota > 0 else 0
            })
        return result

    def get_all_quotas_overview(self, year: int = None) -> list:
        if year is None:
            year = datetime.now().year

        quotas = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.year == year
        ).all()

        result = []
        for quota in quotas:
            result.append({
                'department': quota.department.name,
                'scholarship_type': quota.scholarship_type.name,
                'quota': quota.quota,
                'budget': quota.budget,
                'used_quota': quota.used_quota,
                'used_budget': quota.used_budget,
                'usage_rate': quota.used_quota / quota.quota if quota.quota > 0 else 0,
                'is_over_quota': quota.used_quota > quota.quota,
                'is_over_budget': quota.used_budget > quota.budget
            })
        return result

    def auto_adjust_quotas(self, department_id: int, scholarship_type_id: int, year: int, adjustment: dict) -> dict:
        quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()

        if not quota:
            return {'success': False, 'error': '额度记录不存在'}

        if 'quota' in adjustment:
            new_quota = quota.quota + adjustment['quota']
            if new_quota < quota.used_quota:
                return {'success': False, 'error': '新名额不能小于已使用名额'}
            quota.quota = new_quota

        if 'budget' in adjustment:
            new_budget = quota.budget + adjustment['budget']
            if new_budget < quota.used_budget:
                return {'success': False, 'error': '新预算不能小于已使用预算'}
            quota.budget = new_budget

        quota.updated_at = datetime.utcnow()
        self.db.commit()
        return {'success': True}