from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from models import Application, Student, ScholarshipType, ApprovalRecord, Disbursement, User
from config import Config


class ApplicationService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self._quota_service = None
        self._eligibility_service = None
        self._notification_service = None
    
    @property
    def quota_service(self):
        if self._quota_service is None:
            from .quota_service import QuotaService
            self._quota_service = QuotaService(self.db)
        return self._quota_service
    
    @property
    def eligibility_service(self):
        if self._eligibility_service is None:
            from .eligibility_service import EligibilityService
            self._eligibility_service = EligibilityService(self.db)
        return self._eligibility_service
    
    @property
    def notification_service(self):
        if self._notification_service is None:
            from .notification_service import NotificationService
            self._notification_service = NotificationService(self.db)
        return self._notification_service
    
    def submit_application(
        self,
        student_id: int,
        scholarship_type_id: int,
        reason: str = "",
        attachments: str = ""
    ) -> Dict:
        try:
            student = self.db.query(Student).filter(Student.id == student_id).first()
            if not student:
                return {"success": False, "message": "学生不存在", "code": "STUDENT_NOT_FOUND"}
            
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            if not scholarship_type:
                return {"success": False, "message": "奖助金类型不存在", "code": "SCHOLARSHIP_NOT_FOUND"}
            
            today = datetime.utcnow().date()
            if scholarship_type.application_start_date and today < scholarship_type.application_start_date:
                return {"success": False, "message": "申报尚未开始", "code": "APPLICATION_NOT_STARTED"}
            
            if scholarship_type.application_end_date and today > scholarship_type.application_end_date:
                return {"success": False, "message": "申报已结束", "code": "APPLICATION_ENDED"}
            
            existing_application = self.db.query(Application).filter(
                Application.student_id == student_id,
                Application.scholarship_type_id == scholarship_type_id,
                Application.status.notin_([
                    Config.APPLICATION_STATUS['REJECTED'],
                    Config.APPLICATION_STATUS['CANCELLED']
                ])
            ).first()
            if existing_application:
                return {"success": False, "message": "已存在相同类型的申请", "code": "DUPLICATE_APPLICATION"}
            
            eligibility_result = self.eligibility_service.check_eligibility(student_id, scholarship_type_id)
            if not eligibility_result['eligible']:
                return {
                    "success": False, 
                    "message": "资格校验未通过", 
                    "code": "ELIGIBILITY_FAILED",
                    "details": eligibility_result['issues']
                }
            
            quota_check = self.quota_service.check_quota_availability(
                student.department_id, scholarship_type_id
            )
            if not quota_check['available']:
                return {
                    "success": False, 
                    "message": "院系名额或预算不足", 
                    "code": "QUOTA_EXCEEDED",
                    "details": quota_check
                }
            
            application = Application(
                student_id=student_id,
                scholarship_type_id=scholarship_type_id,
                status=Config.APPLICATION_STATUS['SUBMITTED'],
                reason=reason,
                attachments=attachments
            )
            
            self.db.add(application)
            self.db.flush()
            
            self.notification_service.create_notification(
                user_id=None,
                student_id=student_id,
                title="奖助金申请提交成功",
                content=f"您已成功提交{scholarship_type.name}申请，请等待审核。",
                notification_type=Config.NOTIFICATION_TYPES['APPLICATION_REMINDER']
            )
            
            return {
                "success": True,
                "message": "申请提交成功",
                "application_id": application.id,
                "quota_warning": quota_check.get('warning', False)
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def review_application(
        self,
        application_id: int,
        reviewer_id: int,
        approval_status: str,
        comments: str = "",
        level: int = Config.APPROVAL_LEVELS['DEPARTMENT']
    ) -> Dict:
        try:
            application = self.db.query(Application).filter(Application.id == application_id).first()
            if not application:
                return {"success": False, "message": "申请不存在", "code": "APPLICATION_NOT_FOUND"}
            
            reviewer = self.db.query(User).filter(User.id == reviewer_id).first()
            if not reviewer:
                return {"success": False, "message": "审核人不存在", "code": "REVIEWER_NOT_FOUND"}
            
            if application.status != Config.APPLICATION_STATUS['SUBMITTED'] and \
               application.status != Config.APPLICATION_STATUS['REVIEWING']:
                return {"success": False, "message": "申请状态不可审核", "code": "INVALID_STATUS"}
            
            approval_record = ApprovalRecord(
                application_id=application_id,
                approver_id=reviewer_id,
                status=approval_status,
                comments=comments,
                level=level
            )
            
            self.db.add(approval_record)
            
            if approval_status == 'rejected':
                application.status = Config.APPLICATION_STATUS['REJECTED']
                self.notification_service.create_notification(
                    user_id=None,
                    student_id=application.student_id,
                    title="奖助金申请被拒绝",
                    content=f"您的{application.scholarship_type.name}申请已被拒绝。审核意见：{comments}",
                    notification_type=Config.NOTIFICATION_TYPES['APPROVAL_TODO']
                )
            else:
                if level == Config.APPROVAL_LEVELS['DEPARTMENT']:
                    application.status = Config.APPLICATION_STATUS['REVIEWING']
                elif level == Config.APPROVAL_LEVELS['SCHOOL']:
                    application.status = Config.APPLICATION_STATUS['REVIEWING']
                elif level == Config.APPROVAL_LEVELS['FINANCIAL']:
                    application.status = Config.APPLICATION_STATUS['APPROVED']
                    self.notification_service.create_notification(
                        user_id=None,
                        student_id=application.student_id,
                        title="奖助金申请已通过",
                        content=f"您的{application.scholarship_type.name}申请已通过审核，即将进入公示阶段。",
                        notification_type=Config.NOTIFICATION_TYPES['APPROVAL_TODO']
                    )
            
            return {
                "success": True,
                "message": "审核完成",
                "application_status": application.status
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def start_public_notice(self, application_id: int) -> Dict:
        try:
            application = self.db.query(Application).filter(Application.id == application_id).first()
            if not application:
                return {"success": False, "message": "申请不存在", "code": "APPLICATION_NOT_FOUND"}
            
            if application.status != Config.APPLICATION_STATUS['APPROVED']:
                return {"success": False, "message": "申请状态不可公示", "code": "INVALID_STATUS"}
            
            application.status = Config.APPLICATION_STATUS['PUBLIC_NOTICE']
            
            self.notification_service.create_notification(
                user_id=None,
                student_id=application.student_id,
                title="奖助金申请进入公示阶段",
                content=f"您的{application.scholarship_type.name}申请已进入公示阶段，请关注公示结果。",
                notification_type=Config.NOTIFICATION_TYPES['PUBLIC_NOTICE']
            )
            
            return {
                "success": True,
                "message": "公示已开始",
                "application_status": application.status
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def disburse_application(
        self,
        application_id: int,
        bank_account: str,
        amount: Optional[float] = None
    ) -> Dict:
        try:
            application = self.db.query(Application).filter(Application.id == application_id).first()
            if not application:
                return {"success": False, "message": "申请不存在", "code": "APPLICATION_NOT_FOUND"}
            
            if application.status != Config.APPLICATION_STATUS['PUBLIC_NOTICE']:
                return {"success": False, "message": "申请状态不可发放", "code": "INVALID_STATUS"}
            
            scholarship_type = application.scholarship_type
            disburse_amount = amount if amount else scholarship_type.amount
            
            if not disburse_amount or disburse_amount <= 0:
                return {"success": False, "message": "发放金额无效", "code": "INVALID_AMOUNT"}
            
            disbursement = Disbursement(
                application_id=application_id,
                amount=disburse_amount,
                bank_account=bank_account,
                status='pending'
            )
            
            self.db.add(disbursement)
            
            application.status = Config.APPLICATION_STATUS['DISBURSED']
            
            quota_update = self.quota_service.update_used_quota(
                application.student.department_id,
                scholarship_type.id,
                disburse_amount
            )
            
            if not quota_update['success']:
                self.db.rollback()
                return quota_update
            
            self.notification_service.create_notification(
                user_id=None,
                student_id=application.student_id,
                title="奖助金已发放",
                content=f"您的{scholarship_type.name}已发放，金额：{disburse_amount}元，银行账户：{bank_account}。",
                notification_type=Config.NOTIFICATION_TYPES['DISBURSEMENT_PROGRESS']
            )
            
            return {
                "success": True,
                "message": "发放成功",
                "disbursement_id": disbursement.id,
                "amount": disburse_amount
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def verify_disbursement(
        self,
        disbursement_id: int,
        verifier_id: int,
        transaction_id: str
    ) -> Dict:
        try:
            disbursement = self.db.query(Disbursement).filter(Disbursement.id == disbursement_id).first()
            if not disbursement:
                return {"success": False, "message": "发放记录不存在", "code": "DISBURSEMENT_NOT_FOUND"}
            
            if disbursement.status != 'pending':
                return {"success": False, "message": "发放状态不可核销", "code": "INVALID_STATUS"}
            
            verifier = self.db.query(User).filter(User.id == verifier_id).first()
            if not verifier:
                return {"success": False, "message": "核销人不存在", "code": "VERIFIER_NOT_FOUND"}
            
            disbursement.status = 'verified'
            disbursement.transaction_id = transaction_id
            disbursement.verified_by = verifier_id
            disbursement.verified_date = datetime.utcnow()
            
            application = disbursement.application
            application.status = Config.APPLICATION_STATUS['VERIFIED']
            
            return {
                "success": True,
                "message": "核销成功",
                "disbursement_id": disbursement.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def get_application_by_id(self, application_id: int) -> Optional[Application]:
        return self.db.query(Application).filter(Application.id == application_id).first()
    
    def get_applications_by_student(self, student_id: int) -> List[Application]:
        return self.db.query(Application).filter(Application.student_id == student_id).all()
    
    def get_applications_by_status(self, status: str) -> List[Application]:
        return self.db.query(Application).filter(Application.status == status).all()
    
    def get_pending_approvals(self, level: int) -> List[Dict]:
        applications = self.db.query(Application).filter(
            Application.status.in_([
                Config.APPLICATION_STATUS['SUBMITTED'],
                Config.APPLICATION_STATUS['REVIEWING']
            ])
        ).all()
        
        result = []
        for app in applications:
            last_approval = self.db.query(ApprovalRecord).filter(
                ApprovalRecord.application_id == app.id
            ).order_by(ApprovalRecord.created_at.desc()).first()
            
            next_level = 1
            if last_approval:
                next_level = last_approval.level + 1
            
            if next_level == level:
                result.append({
                    'application_id': app.id,
                    'student_name': app.student.name,
                    'scholarship_type': app.scholarship_type.name,
                    'application_date': app.application_date,
                    'status': app.status
                })
        
        return result
