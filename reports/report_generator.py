from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Application, Student, Department, ScholarshipType, Disbursement, DepartmentQuota, Grade
from services.qualification_service import QualificationService

class ReportGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.qualification_service = QualificationService(db)

    def generate_application_statistics(self, year: int = None, department_id: int = None) -> dict:
        if year is None:
            year = datetime.now().year

        query = self.db.query(Application)

        if year:
            query = query.filter(func.strftime('%Y', Application.application_date) == str(year))
        if department_id:
            query = query.join(Student).filter(Student.department_id == department_id)

        applications = query.all()

        by_status = {}
        for app in applications:
            status = app.status
            by_status[status] = by_status.get(status, 0) + 1

        by_type = {}
        for app in applications:
            type_name = app.scholarship_type.name
            by_type[type_name] = by_type.get(type_name, 0) + 1

        by_department = {}
        for app in applications:
            dept_name = app.student.department.name if app.student.department else '未知'
            by_department[dept_name] = by_department.get(dept_name, 0) + 1

        return {
            'year': year,
            'department_id': department_id,
            'total_applications': len(applications),
            'by_status': by_status,
            'by_type': by_type,
            'by_department': by_department,
            'generated_at': datetime.utcnow()
        }

    def generate_quota_usage_report(self, year: int = None) -> dict:
        if year is None:
            year = datetime.now().year

        quotas = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.year == year
        ).all()

        total_quota = sum(q.quota for q in quotas)
        total_used = sum(q.used_quota for q in quotas)
        total_budget = sum(q.budget for q in quotas)
        total_used_budget = sum(q.used_budget for q in quotas)

        details = []
        for quota in quotas:
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == quota.scholarship_type_id
            ).first()

            department = self.db.query(Department).filter(
                Department.id == quota.department_id
            ).first()

            details.append({
                'department': department.name if department else '未知',
                'scholarship_type': scholarship_type.name if scholarship_type else '未知',
                'quota': quota.quota,
                'used_quota': quota.used_quota,
                'available_quota': quota.quota - quota.used_quota,
                'budget': quota.budget,
                'used_budget': quota.used_budget,
                'available_budget': quota.budget - quota.used_budget,
                'usage_rate': quota.used_quota / quota.quota if quota.quota > 0 else 0,
                'over_quota': quota.used_quota > quota.quota,
                'over_budget': quota.used_budget > quota.budget
            })

        return {
            'year': year,
            'summary': {
                'total_quota': total_quota,
                'total_used': total_used,
                'total_budget': total_budget,
                'total_used_budget': total_used_budget,
                'overall_usage_rate': total_used / total_quota if total_quota > 0 else 0
            },
            'details': details,
            'generated_at': datetime.utcnow()
        }

    def generate_disbursement_report(self, year: int = None, quarter: int = None) -> dict:
        if year is None:
            year = datetime.now().year

        query = self.db.query(Disbursement).join(Application)

        query = query.filter(func.strftime('%Y', Disbursement.disbursement_date) == str(year))

        if quarter:
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            query = query.filter(
                func.cast(func.substr(Disbursement.disbursement_date, 6, 2) as Integer) >= start_month,
                func.cast(func.substr(Disbursement.disbursement_date, 6, 2) as Integer) <= end_month
            )

        disbursements = query.all()

        total_amount = sum(d.amount for d in disbursements)
        by_status = {}
        for d in disbursements:
            status = d.status
            by_status[status] = {
                'count': by_status.get(status, {}).get('count', 0) + 1,
                'amount': by_status.get(status, {}).get('amount', 0) + d.amount
            }

        by_month = {}
        for d in disbursements:
            month = d.disbursement_date.month
            by_month[month] = by_month.get(month, 0) + d.amount

        by_scholarship_type = {}
        for d in disbursements:
            type_name = d.application.scholarship_type.name
            by_scholarship_type[type_name] = by_scholarship_type.get(type_name, 0) + d.amount

        return {
            'year': year,
            'quarter': quarter,
            'total_disbursements': len(disbursements),
            'total_amount': total_amount,
            'average_amount': total_amount / len(disbursements) if disbursements else 0,
            'by_status': by_status,
            'by_month': by_month,
            'by_scholarship_type': by_scholarship_type,
            'generated_at': datetime.utcnow()
        }

    def generate_eligibility_report(self, scholarship_type_id: int = None, department_id: int = None) -> dict:
        return self.qualification_service.generate_qualification_report(
            scholarship_type_id=scholarship_type_id,
            department_id=department_id
        )

    def generate_student_summary_report(self, student_id: int) -> dict:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {'error': '学生不存在'}

        assistance_history = self.qualification_service.get_student_assistance_history(student_id)
        grade_stats = self.qualification_service.get_grade_statistics(student_id)
        data_validation = self.qualification_service.validate_student_data(student_id)

        applications = self.db.query(Application).filter(
            Application.student_id == student_id
        ).all()

        application_summary = []
        for app in applications:
            application_summary.append({
                'id': app.id,
                'scholarship_name': app.scholarship_type.name,
                'type': app.scholarship_type.type,
                'amount': app.scholarship_type.amount,
                'status': app.status,
                'application_date': app.application_date
            })

        return {
            'student': {
                'id': student.id,
                'student_id': student.student_id,
                'name': student.name,
                'department': student.department.name if student.department else None,
                'major': student.major,
                'grade': student.grade
            },
            'assistance_history': assistance_history,
            'grade_statistics': grade_stats,
            'data_validation': data_validation,
            'application_summary': application_summary,
            'generated_at': datetime.utcnow()
        }

    def generate_department_summary_report(self, department_id: int, year: int = None) -> dict:
        if year is None:
            year = datetime.now().year

        department = self.db.query(Department).filter(Department.id == department_id).first()
        if not department:
            return {'error': '院系不存在'}

        students = self.db.query(Student).filter(Student.department_id == department_id).all()
        student_count = len(students)

        applications = self.db.query(Application).join(Student).filter(
            Student.department_id == department_id,
            func.strftime('%Y', Application.application_date) == str(year)
        ).all()

        disbursements = self.db.query(Disbursement).join(Application).join(Student).filter(
            Student.department_id == department_id,
            func.strftime('%Y', Disbursement.disbursement_date) == str(year)
        ).all()

        quotas = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.year == year
        ).all()

        quota_summary = []
        for quota in quotas:
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == quota.scholarship_type_id
            ).first()

            quota_summary.append({
                'scholarship_type': scholarship_type.name if scholarship_type else '未知',
                'quota': quota.quota,
                'used_quota': quota.used_quota,
                'usage_rate': quota.used_quota / quota.quota if quota.quota > 0 else 0
            })

        return {
            'department': {
                'id': department.id,
                'name': department.name,
                'code': department.code
            },
            'year': year,
            'student_count': student_count,
            'application_count': len(applications),
            'disbursement_count': len(disbursements),
            'total_disbursement_amount': sum(d.amount for d in disbursements),
            'quota_summary': quota_summary,
            'generated_at': datetime.utcnow()
        }