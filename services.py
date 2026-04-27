from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple

from models import (
    Department, Student, ScholarshipType, Application, ApprovalRecord, 
    Disbursement, DepartmentQuota, User, Notification, Grade, StudentStatus
)
from config import Config

class ApplicationService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def submit_application(self, student_id: int, scholarship_type_id: int, 
                           reason: str = "", attachments: str = "") -> Tuple[bool, str, Optional[Application]]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return False, "学生不存在", None
        
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        if not scholarship_type:
            return False, "奖学金类型不存在", None
        
        today = datetime.now().date()
        if today < scholarship_type.application_start_date:
            return False, "申报期尚未开始", None
        if today > scholarship_type.application_end_date:
            return False, "申报期已结束", None
        
        existing_application = self.db.query(Application).filter(
            Application.student_id == student_id,
            Application.scholarship_type_id == scholarship_type_id,
            Application.status.notin_(['rejected', '已核销'])
        ).first()
        if existing_application:
            return False, "您已提交过同类奖学金申请", None
        
        from services import QuotaService
        quota_service = QuotaService(self.db)
        can_apply, message = quota_service.check_quota_availability(
            student.department_id, scholarship_type_id, datetime.now().year
        )
        if not can_apply:
            return False, message, None
        
        application = Application(
            student_id=student_id,
            scholarship_type_id=scholarship_type_id,
            reason=reason,
            attachments=attachments,
            status='submitted'
        )
        self.db.add(application)
        self.db.flush()
        
        from services import NotificationService
        notification_service = NotificationService(self.db)
        notification_service.send_application_submitted_notification(student.id, application.id)
        
        return True, "申请提交成功", application
    
    def get_application_by_id(self, application_id: int) -> Optional[Application]:
        return self.db.query(Application).filter(Application.id == application_id).first()
    
    def get_student_applications(self, student_id: int) -> List[Application]:
        return self.db.query(Application).filter(
            Application.student_id == student_id
        ).order_by(Application.application_date.desc()).all()
    
    def get_applications_by_status(self, status: str) -> List[Application]:
        return self.db.query(Application).filter(
            Application.status == status
        ).order_by(Application.application_date.desc()).all()
    
    def get_pending_approvals(self, user_role: str, department_id: Optional[int] = None) -> List[Application]:
        query = self.db.query(Application)
        
        if user_role == 'department_admin':
            query = query.join(Student).filter(
                Student.department_id == department_id,
                Application.status == 'submitted'
            )
        elif user_role == 'school_admin':
            query = query.filter(Application.status == 'reviewed')
        elif user_role == 'financial_admin':
            query = query.filter(Application.status == 'approved')
        else:
            return []
        
        return query.order_by(Application.application_date.desc()).all()


class ApprovalService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def process_approval(self, application_id: int, approver_id: int, 
                          approval_level: int, status: str, comments: str = "") -> Tuple[bool, str]:
        application = self.db.query(Application).filter(
            Application.id == application_id
        ).first()
        if not application:
            return False, "申请不存在"
        
        approver = self.db.query(User).filter(User.id == approver_id).first()
        if not approver:
            return False, "审批人不存在"
        
        expected_status = None
        if approval_level == 1:
            expected_status = 'submitted'
        elif approval_level == 2:
            expected_status = 'reviewed'
        elif approval_level == 3:
            expected_status = 'approved'
        
        if application.status != expected_status:
            return False, f"申请状态不正确，当前状态: {application.status}"
        
        approval_record = ApprovalRecord(
            application_id=application_id,
            approver_id=approver_id,
            status=status,
            comments=comments,
            level=approval_level
        )
        self.db.add(approval_record)
        
        if status == 'rejected':
            application.status = 'rejected'
            from services import NotificationService
            notification_service = NotificationService(self.db)
            notification_service.send_application_rejected_notification(
                application.student_id, application.id, comments
            )
            return True, "申请已驳回"
        
        if approval_level == 1:
            application.status = 'reviewed'
        elif approval_level == 2:
            application.status = 'approved'
        elif approval_level == 3:
            application.status = '公示中'
            from services import NotificationService
            notification_service = NotificationService(self.db)
            notification_service.send_public_notice_notification(application.id)
        
        return True, f"{Config.APPROVAL_LEVELS[approval_level]}完成"
    
    def start_public_notice(self, application_id: int) -> Tuple[bool, str]:
        application = self.db.query(Application).filter(
            Application.id == application_id
        ).first()
        if not application:
            return False, "申请不存在"
        
        if application.status != 'approved':
            return False, f"申请状态不正确，当前状态: {application.status}"
        
        application.status = '公示中'
        
        from services import NotificationService
        notification_service = NotificationService(self.db)
        notification_service.send_public_notice_notification(application.id)
        
        return True, "公示已开始"
    
    def complete_public_notice(self, application_id: int, has_objection: bool = False, 
                                objection_comments: str = "") -> Tuple[bool, str]:
        application = self.db.query(Application).filter(
            Application.id == application_id
        ).first()
        if not application:
            return False, "申请不存在"
        
        if application.status != '公示中':
            return False, f"申请状态不正确，当前状态: {application.status}"
        
        if has_objection:
            application.status = 'rejected'
            from services import NotificationService
            notification_service = NotificationService(self.db)
            notification_service.send_application_rejected_notification(
                application.student_id, application.id, objection_comments
            )
            return True, "公示有异议，申请已驳回"
        else:
            application.status = '已发放'
            from services import NotificationService
            notification_service = NotificationService(self.db)
            notification_service.send_disbursement_notification(application.id)
            
            return True, "公示无异议，已进入发放环节"


class DisbursementService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_disbursement(self, application_id: int, amount: float, 
                             bank_account: str) -> Tuple[bool, str, Optional[Disbursement]]:
        application = self.db.query(Application).filter(
            Application.id == application_id
        ).first()
        if not application:
            return False, "申请不存在", None
        
        if application.status != '已发放':
            return False, f"申请状态不正确，当前状态: {application.status}", None
        
        existing_disbursement = self.db.query(Disbursement).filter(
            Disbursement.application_id == application_id
        ).first()
        if existing_disbursement:
            return False, "该申请已有发放记录", None
        
        disbursement = Disbursement(
            application_id=application_id,
            amount=amount,
            bank_account=bank_account,
            status='pending'
        )
        self.db.add(disbursement)
        
        return True, "发放记录创建成功", disbursement
    
    def process_disbursement(self, disbursement_id: int, transaction_id: str) -> Tuple[bool, str]:
        disbursement = self.db.query(Disbursement).filter(
            Disbursement.id == disbursement_id
        ).first()
        if not disbursement:
            return False, "发放记录不存在"
        
        if disbursement.status != 'pending':
            return False, f"发放记录状态不正确，当前状态: {disbursement.status}"
        
        disbursement.transaction_id = transaction_id
        disbursement.status = 'processed'
        
        from services import NotificationService
        notification_service = NotificationService(self.db)
        notification_service.send_disbursement_progress_notification(
            disbursement.application.student_id, disbursement.application_id, '已发放'
        )
        
        return True, "发放处理完成"
    
    def verify_disbursement(self, disbursement_id: int, verifier_id: int) -> Tuple[bool, str]:
        disbursement = self.db.query(Disbursement).filter(
            Disbursement.id == disbursement_id
        ).first()
        if not disbursement:
            return False, "发放记录不存在"
        
        if disbursement.status != 'processed':
            return False, f"发放记录状态不正确，当前状态: {disbursement.status}"
        
        disbursement.verified_by = verifier_id
        disbursement.verified_date = datetime.utcnow()
        disbursement.status = 'verified'
        
        application = disbursement.application
        application.status = '已核销'
        
        from services import QuotaService
        quota_service = QuotaService(self.db)
        quota_service.update_used_quota(
            application.student.department_id,
            application.scholarship_type_id,
            datetime.now().year,
            disbursement.amount
        )
        
        from services import NotificationService
        notification_service = NotificationService(self.db)
        notification_service.send_disbursement_progress_notification(
            application.student_id, application.id, '已核销'
        )
        
        return True, "发放核销完成"
    
    def get_disbursement_by_id(self, disbursement_id: int) -> Optional[Disbursement]:
        return self.db.query(Disbursement).filter(Disbursement.id == disbursement_id).first()
    
    def get_application_disbursement(self, application_id: int) -> Optional[Disbursement]:
        return self.db.query(Disbursement).filter(
            Disbursement.application_id == application_id
        ).first()


class QuotaService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_department_quota(self, department_id: int, scholarship_type_id: int, 
                                 year: int, quota: int, budget: float) -> Tuple[bool, str, Optional[DepartmentQuota]]:
        existing_quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()
        
        if existing_quota:
            return False, "该院系该年度该类型奖学金额度已存在", None
        
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
        
        return True, "院系额度创建成功", department_quota
    
    def update_department_quota(self, quota_id: int, quota: Optional[int] = None, 
                                 budget: Optional[float] = None) -> Tuple[bool, str]:
        department_quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.id == quota_id
        ).first()
        
        if not department_quota:
            return False, "院系额度不存在"
        
        if quota is not None:
            if quota < department_quota.used_quota:
                return False, f"新名额不能少于已使用名额({department_quota.used_quota})"
            department_quota.quota = quota
        
        if budget is not None:
            if budget < department_quota.used_budget:
                return False, f"新预算不能少于已使用预算({department_quota.used_budget})"
            department_quota.budget = budget
        
        return True, "院系额度更新成功"
    
    def check_quota_availability(self, department_id: int, scholarship_type_id: int, 
                                  year: int) -> Tuple[bool, str]:
        department_quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()
        
        if not department_quota:
            return False, "该院系该年度该类型奖学金未设置额度"
        
        if department_quota.used_quota >= department_quota.quota:
            return False, f"名额不足，已使用{department_quota.used_quota}/{department_quota.quota}"
        
        return True, "额度充足"
    
    def update_used_quota(self, department_id: int, scholarship_type_id: int, 
                           year: int, amount: float) -> Tuple[bool, str]:
        department_quota = self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()
        
        if not department_quota:
            return False, "院系额度不存在"
        
        department_quota.used_quota += 1
        department_quota.used_budget += amount
        
        return True, "已使用额度更新成功"
    
    def get_department_quota(self, department_id: int, scholarship_type_id: int, 
                             year: int) -> Optional[DepartmentQuota]:
        return self.db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == department_id,
            DepartmentQuota.scholarship_type_id == scholarship_type_id,
            DepartmentQuota.year == year
        ).first()
    
    def get_all_department_quotas(self, department_id: Optional[int] = None, 
                                   year: Optional[int] = None) -> List[DepartmentQuota]:
        query = self.db.query(DepartmentQuota)
        
        if department_id:
            query = query.filter(DepartmentQuota.department_id == department_id)
        if year:
            query = query.filter(DepartmentQuota.year == year)
        
        return query.order_by(DepartmentQuota.year.desc()).all()


class ValidationService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def validate_student_eligibility(self, student_id: int, 
                                      scholarship_type_id: int) -> Tuple[bool, Dict[str, Any]]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return False, {"error": "学生不存在"}
        
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        if not scholarship_type:
            return False, {"error": "奖学金类型不存在"}
        
        validation_report = {
            "student_id": student.student_id,
            "student_name": student.name,
            "scholarship_type": scholarship_type.name,
            "checks": [],
            "eligible": True
        }
        
        status_check = self._check_student_status(student_id)
        validation_report["checks"].append(status_check)
        if not status_check["passed"]:
            validation_report["eligible"] = False
        
        if scholarship_type.min_gpa:
            gpa_check = self._check_min_gpa(student_id, scholarship_type.min_gpa)
            validation_report["checks"].append(gpa_check)
            if not gpa_check["passed"]:
                validation_report["eligible"] = False
        
        if scholarship_type.max_application_count:
            count_check = self._check_application_count(
                student_id, scholarship_type_id, scholarship_type.max_application_count
            )
            validation_report["checks"].append(count_check)
            if not count_check["passed"]:
                validation_report["eligible"] = False
        
        return validation_report["eligible"], validation_report
    
    def _check_student_status(self, student_id: int) -> Dict[str, Any]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        
        latest_status = self.db.query(StudentStatus).filter(
            StudentStatus.student_id == student_id
        ).order_by(StudentStatus.effective_date.desc()).first()
        
        status = latest_status.status if latest_status else student.status
        
        passed = status == 'active'
        return {
            "check_type": "student_status",
            "description": "学生学籍状态检查",
            "passed": passed,
            "details": f"当前状态: {status}",
            "requirement": "状态需为active(在读)"
        }
    
    def _check_min_gpa(self, student_id: int, min_gpa: float) -> Dict[str, Any]:
        grades = self.db.query(Grade).filter(Grade.student_id == student_id).all()
        
        if not grades:
            return {
                "check_type": "gpa",
                "description": "GPA检查",
                "passed": False,
                "details": "无成绩记录",
                "requirement": f"最低GPA要求: {min_gpa}"
            }
        
        total_credit = sum(grade.credit for grade in grades)
        total_score = sum(grade.score * grade.credit for grade in grades)
        
        if total_credit == 0:
            return {
                "check_type": "gpa",
                "description": "GPA检查",
                "passed": False,
                "details": "总学分为0",
                "requirement": f"最低GPA要求: {min_gpa}"
            }
        
        gpa = total_score / total_credit
        passed = gpa >= min_gpa
        
        return {
            "check_type": "gpa",
            "description": "GPA检查",
            "passed": passed,
            "details": f"当前GPA: {gpa:.2f}",
            "requirement": f"最低GPA要求: {min_gpa}"
        }
    
    def _check_application_count(self, student_id: int, scholarship_type_id: int, 
                                  max_count: int) -> Dict[str, Any]:
        count = self.db.query(Application).filter(
            Application.student_id == student_id,
            Application.scholarship_type_id == scholarship_type_id,
            Application.status.notin_(['rejected'])
        ).count()
        
        passed = count < max_count
        
        return {
            "check_type": "application_count",
            "description": "申请次数检查",
            "passed": passed,
            "details": f"已申请次数: {count}",
            "requirement": f"最多可申请: {max_count}次"
        }
    
    def generate_qualification_report(self, student_id: int, 
                                       scholarship_type_id: int) -> Dict[str, Any]:
        eligible, validation_report = self.validate_student_eligibility(
            student_id, scholarship_type_id
        )
        
        student = self.db.query(Student).filter(Student.id == student_id).first()
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        
        report = {
            "report_date": datetime.now().isoformat(),
            "student": {
                "id": student.id,
                "student_id": student.student_id,
                "name": student.name,
                "department": student.department.name if student.department else None,
                "major": student.major,
                "grade": student.grade,
                "status": student.status
            },
            "scholarship": {
                "id": scholarship_type.id,
                "name": scholarship_type.name,
                "type": scholarship_type.type,
                "amount": scholarship_type.amount,
                "min_gpa": scholarship_type.min_gpa
            },
            "validation": validation_report,
            "eligible": eligible
        }
        
        return report
    
    def generate_disbursement_statistics(self, year: Optional[int] = None,
                                          department_id: Optional[int] = None) -> Dict[str, Any]:
        query = self.db.query(Disbursement).join(Application).join(Student)
        
        if year:
            query = query.filter(
                Application.application_date.between(
                    datetime(year, 1, 1),
                    datetime(year, 12, 31)
                )
            )
        
        if department_id:
            query = query.filter(Student.department_id == department_id)
        
        disbursements = query.all()
        
        total_amount = sum(d.amount for d in disbursements)
        total_count = len(disbursements)
        
        status_counts = {}
        for d in disbursements:
            status = d.status
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        statistics = {
            "report_date": datetime.now().isoformat(),
            "year": year,
            "department_id": department_id,
            "summary": {
                "total_disbursements": total_count,
                "total_amount": total_amount,
                "average_amount": total_amount / total_count if total_count > 0 else 0
            },
            "status_breakdown": status_counts,
            "disbursements": [
                {
                    "id": d.id,
                    "application_id": d.application_id,
                    "student_name": d.application.student.name,
                    "student_id": d.application.student.student_id,
                    "scholarship_type": d.application.scholarship_type.name,
                    "amount": d.amount,
                    "status": d.status,
                    "disbursement_date": d.disbursement_date.isoformat() if d.disbursement_date else None
                }
                for d in disbursements
            ]
        }
        
        return statistics


class ScholarshipTypeService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_scholarship_type(self, name: str, code: str, type: str,
                                 description: str = "", application_start_date: Optional[datetime] = None,
                                 application_end_date: Optional[datetime] = None,
                                 review_start_date: Optional[datetime] = None,
                                 review_end_date: Optional[datetime] = None,
                                 disbursement_date: Optional[datetime] = None,
                                 amount: float = 0.0, min_gpa: Optional[float] = None,
                                 max_application_count: Optional[int] = None) -> Tuple[bool, str, Optional[ScholarshipType]]:
        existing = self.db.query(ScholarshipType).filter(
            (ScholarshipType.name == name) | (ScholarshipType.code == code)
        ).first()
        
        if existing:
            if existing.name == name:
                return False, "奖学金名称已存在", None
            else:
                return False, "奖学金代码已存在", None
        
        scholarship_type = ScholarshipType(
            name=name,
            code=code,
            type=type,
            description=description,
            application_start_date=application_start_date,
            application_end_date=application_end_date,
            review_start_date=review_start_date,
            review_end_date=review_end_date,
            disbursement_date=disbursement_date,
            amount=amount,
            min_gpa=min_gpa,
            max_application_count=max_application_count
        )
        self.db.add(scholarship_type)
        
        return True, "奖学金类型创建成功", scholarship_type
    
    def update_scholarship_type(self, scholarship_type_id: int, **kwargs) -> Tuple[bool, str]:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        
        if not scholarship_type:
            return False, "奖学金类型不存在"
        
        allowed_fields = ['name', 'code', 'type', 'description', 
                          'application_start_date', 'application_end_date',
                          'review_start_date', 'review_end_date', 'disbursement_date',
                          'amount', 'min_gpa', 'max_application_count']
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(scholarship_type, key, value)
        
        return True, "奖学金类型更新成功"
    
    def get_scholarship_type_by_id(self, scholarship_type_id: int) -> Optional[ScholarshipType]:
        return self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
    
    def get_all_scholarship_types(self, type_filter: Optional[str] = None) -> List[ScholarshipType]:
        query = self.db.query(ScholarshipType)
        
        if type_filter:
            query = query.filter(ScholarshipType.type == type_filter)
        
        return query.order_by(ScholarshipType.created_at.desc()).all()
    
    def get_active_scholarship_types(self) -> List[ScholarshipType]:
        today = datetime.now().date()
        return self.db.query(ScholarshipType).filter(
            ScholarshipType.application_start_date <= today,
            ScholarshipType.application_end_date >= today
        ).order_by(ScholarshipType.application_end_date.asc()).all()


class NotificationService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_notification(self, user_id: int, title: str, content: str, 
                            notification_type: str, student_id: Optional[int] = None) -> Notification:
        notification = Notification(
            user_id=user_id,
            student_id=student_id,
            title=title,
            content=content,
            type=notification_type,
            is_read=False
        )
        self.db.add(notification)
        return notification
    
    def send_application_submitted_notification(self, student_id: int, application_id: int) -> None:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        application = self.db.query(Application).filter(Application.id == application_id).first()
        
        if not student or not application:
            return
        
        users = self.db.query(User).filter(
            User.role == 'department_admin',
            User.department_id == student.department_id
        ).all()
        
        for user in users:
            self.create_notification(
                user_id=user.id,
                title="新申请待审核",
                content=f"学生 {student.name} 提交了 {application.scholarship_type.name} 申请，请及时审核。",
                notification_type='approval_todo',
                student_id=student_id
            )
    
    def send_application_rejected_notification(self, student_id: int, application_id: int, 
                                                reason: str) -> None:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        application = self.db.query(Application).filter(Application.id == application_id).first()
        
        if not student or not application:
            return
        
        users = self.db.query(User).filter(User.role == 'student', User.id == student_id).all()
        
        for user in users:
            self.create_notification(
                user_id=user.id,
                title="申请被驳回",
                content=f"您的 {application.scholarship_type.name} 申请已被驳回。原因：{reason}",
                notification_type='application_reminder',
                student_id=student_id
            )
    
    def send_public_notice_notification(self, application_id: int) -> None:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        
        if not application:
            return
        
        self.create_notification(
            user_id=application.student_id,
            title="申请进入公示期",
            content=f"您的 {application.scholarship_type.name} 申请已通过审核，进入公示期。",
            notification_type='public_notice',
            student_id=application.student_id
        )
        
        all_students = self.db.query(Student).all()
        for student in all_students:
            if student.id != application.student_id:
                self.create_notification(
                    user_id=student.id,
                    title="奖学金公示通知",
                    content=f"{application.scholarship_type.name} 奖学金正在公示中，如有异议请及时反馈。",
                    notification_type='public_notice',
                    student_id=student.id
                )
    
    def send_disbursement_notification(self, application_id: int) -> None:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        
        if not application:
            return
        
        self.create_notification(
            user_id=application.student_id,
            title="奖学金发放通知",
            content=f"您的 {application.scholarship_type.name} 奖学金已通过公示，即将发放。",
            notification_type='disbursement_progress',
            student_id=application.student_id
        )
    
    def send_disbursement_progress_notification(self, student_id: int, application_id: int, 
                                                 status: str) -> None:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        
        if not application:
            return
        
        self.create_notification(
            user_id=student_id,
            title="发放进度更新",
            content=f"您的 {application.scholarship_type.name} 奖学金状态已更新为：{status}。",
            notification_type='disbursement_progress',
            student_id=student_id
        )
    
    def send_application_reminder(self, scholarship_type_id: int) -> None:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        
        if not scholarship_type:
            return
        
        all_students = self.db.query(Student).filter(Student.status == 'active').all()
        
        for student in all_students:
            self.create_notification(
                user_id=student.id,
                title="奖学金申报提醒",
                content=f"{scholarship_type.name} 奖学金申报即将截止，请及时提交申请。截止日期：{scholarship_type.application_end_date}",
                notification_type='application_reminder',
                student_id=student.id
            )
    
    def get_user_notifications(self, user_id: int, unread_only: bool = False) -> List[Notification]:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        return query.order_by(Notification.created_at.desc()).all()
    
    def mark_notification_as_read(self, notification_id: int) -> Tuple[bool, str]:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()
        
        if not notification:
            return False, "通知不存在"
        
        notification.is_read = True
        return True, "通知已标记为已读"
    
    def mark_all_notifications_as_read(self, user_id: int) -> Tuple[bool, str]:
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).all()
        
        for notification in notifications:
            notification.is_read = True
        
        return True, f"已标记 {len(notifications)} 条通知为已读"
