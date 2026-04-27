from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy import and_, func

from models import Application, Student, ScholarshipType, ApprovalRecord, Disbursement, User, Department
from config import Config, ErrorCode, ApprovalStatus, DisbursementStatus
from utils.validators import Validator
from services.log_service import log_service


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
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return self._build_error_response(ErrorCode.USER_NOT_FOUND.value)
            
            if not Config.has_permission(user.role, permission):
                log_service.log_permission_denied(user_id, permission, "application_operation")
                return self._build_error_response(ErrorCode.PERMISSION_DENIED.value)
            
            return self._build_response(True, data={'user': user})
            
        except SQLAlchemyError as e:
            log_service.log_error("检查权限", e, user_id=user_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def submit_application(
        self,
        student_id: int,
        scholarship_type_id: int,
        reason: str = "",
        attachments: str = ""
    ) -> Dict[str, Any]:
        log_service.info(f"开始提交申请: student_id={student_id}, scholarship_type_id={scholarship_type_id}")
        
        validation = Validator.validate_submit_application(
            student_id, scholarship_type_id, reason, attachments
        )
        if not validation.valid:
            log_service.warning(f"参数校验失败: {validation.message}")
            return self._build_error_response(
                validation.code, validation.message, validation.details
            )
        
        try:
            student = self.db.query(Student).options(
                joinedload(Student.department)
            ).filter(Student.id == student_id).first()
            
            if not student:
                log_service.warning(f"学生不存在: student_id={student_id}")
                return self._build_error_response(ErrorCode.STUDENT_NOT_FOUND.value)
            
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            
            if not scholarship_type:
                log_service.warning(f"奖助金类型不存在: scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            today = datetime.utcnow().date()
            if scholarship_type.application_start_date and today < scholarship_type.application_start_date:
                log_service.info(f"申报尚未开始: scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.APPLICATION_NOT_STARTED.value)
            
            if scholarship_type.application_end_date and today > scholarship_type.application_end_date:
                log_service.info(f"申报已结束: scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.APPLICATION_ENDED.value)
            
            existing_application = self.db.query(Application).filter(
                Application.student_id == student_id,
                Application.scholarship_type_id == scholarship_type_id,
                Application.status.notin_([
                    Config.APPLICATION_STATUS['REJECTED'],
                    Config.APPLICATION_STATUS['CANCELLED']
                ])
            ).first()
            
            if existing_application:
                log_service.warning(f"重复申请: student_id={student_id}, scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(ErrorCode.DUPLICATE_APPLICATION.value)
            
            eligibility_result = self.eligibility_service.check_eligibility(
                student_id, scholarship_type_id
            )
            
            if not eligibility_result.get('eligible', False):
                log_service.info(f"资格校验失败: student_id={student_id}")
                return self._build_error_response(
                    ErrorCode.ELIGIBILITY_FAILED.value,
                    details=eligibility_result.get('issues', [])
                )
            
            if not student.department:
                log_service.warning(f"学生未分配院系: student_id={student_id}")
                return self._build_error_response(ErrorCode.DEPARTMENT_NOT_FOUND.value)
            
            quota_check = self.quota_service.check_quota_availability(
                student.department.id, scholarship_type_id
            )
            
            if not quota_check.get('available', False):
                log_service.warning(f"额度不足: department_id={student.department.id}, scholarship_type_id={scholarship_type_id}")
                return self._build_error_response(
                    ErrorCode.QUOTA_EXCEEDED.value,
                    details=quota_check
                )
            
            application = Application(
                student_id=student_id,
                scholarship_type_id=scholarship_type_id,
                status=Config.APPLICATION_STATUS['SUBMITTED'],
                reason=reason,
                attachments=attachments
            )
            
            self.db.add(application)
            self.db.flush()
            
            log_service.log_application_submit(
                application_id=application.id,
                student_id=student_id,
                scholarship_type_id=scholarship_type_id,
                success=True
            )
            
            scholarship_name = scholarship_type.name if scholarship_type else "未知奖助金"
            self.notification_service.create_notification(
                user_id=None,
                student_id=student_id,
                title="奖助金申请提交成功",
                content=f"您已成功提交{scholarship_name}申请，请等待审核。",
                notification_type=Config.NOTIFICATION_TYPES['APPLICATION_REMINDER']
            )
            
            return self._build_response(
                success=True,
                data={
                    'application_id': application.id,
                    'quota_warning': quota_check.get('warning', False)
                },
                message="申请提交成功"
            )
            
        except IntegrityError as e:
            self.db.rollback()
            log_service.log_error("提交申请", e, student_id=student_id)
            return self._build_error_response(ErrorCode.CONCURRENT_MODIFICATION.value, "数据完整性冲突")
            
        except OperationalError as e:
            self.db.rollback()
            log_service.log_error("提交申请", e, student_id=student_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, "数据库操作失败")
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("提交申请", e, student_id=student_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def review_application(
        self,
        application_id: int,
        reviewer_id: int,
        approval_status: str,
        comments: str = "",
        level: int = Config.APPROVAL_LEVELS['DEPARTMENT']
    ) -> Dict[str, Any]:
        log_service.info(f"开始审核申请: application_id={application_id}, reviewer_id={reviewer_id}")
        
        validation = Validator.validate_review_application(
            application_id, reviewer_id, approval_status, level
        )
        if not validation.valid:
            log_service.warning(f"参数校验失败: {validation.message}")
            return self._build_error_response(
                validation.code, validation.message, validation.details
            )
        
        try:
            permission_map = {
                Config.APPROVAL_LEVELS['DEPARTMENT']: 'review_level_1',
                Config.APPROVAL_LEVELS['SCHOOL']: 'review_level_2',
                Config.APPROVAL_LEVELS['FINANCIAL']: 'review_level_3'
            }
            permission = permission_map.get(level)
            if permission:
                perm_check = self._check_permission(reviewer_id, permission)
                if not perm_check['success']:
                    return perm_check
            
            application = self.db.query(Application).options(
                joinedload(Application.student),
                joinedload(Application.scholarship_type)
            ).filter(Application.id == application_id).with_for_update().first()
            
            if not application:
                log_service.warning(f"申请不存在: application_id={application_id}")
                return self._build_error_response(ErrorCode.APPLICATION_NOT_FOUND.value)
            
            reviewer = self.db.query(User).filter(User.id == reviewer_id).first()
            if not reviewer:
                log_service.warning(f"审核人不存在: reviewer_id={reviewer_id}")
                return self._build_error_response(ErrorCode.REVIEWER_NOT_FOUND.value)
            
            valid_statuses = [
                Config.APPLICATION_STATUS['SUBMITTED'],
                Config.APPLICATION_STATUS['REVIEWING']
            ]
            if application.status not in valid_statuses:
                log_service.warning(f"申请状态不可审核: application_id={application_id}, status={application.status}")
                return self._build_error_response(ErrorCode.INVALID_STATUS.value)
            
            next_approval_level = self._get_next_approval_level(application_id)
            if next_approval_level and next_approval_level != level:
                log_service.warning(f"审核级别不正确: 期望={next_approval_level}, 实际={level}")
                return self._build_error_response(
                    ErrorCode.INVALID_STATUS.value,
                    f"当前应进行级别{next_approval_level}的审核"
                )
            
            approval_record = ApprovalRecord(
                application_id=application_id,
                approver_id=reviewer_id,
                status=approval_status.lower(),
                comments=comments,
                level=level
            )
            self.db.add(approval_record)
            
            new_status = self._determine_new_status(approval_status, level, application)
            application.status = new_status
            
            self.db.flush()
            
            log_service.log_approval(
                application_id=application_id,
                reviewer_id=reviewer_id,
                approval_status=approval_status,
                level=level,
                success=True
            )
            
            if application.student and application.scholarship_type:
                student_name = application.student.name
                scholarship_name = application.scholarship_type.name
                
                if approval_status.lower() == ApprovalStatus.REJECTED.value:
                    self.notification_service.create_notification(
                        user_id=None,
                        student_id=application.student_id,
                        title="奖助金申请被拒绝",
                        content=f"您的{scholarship_name}申请已被拒绝。审核意见：{comments}",
                        notification_type=Config.NOTIFICATION_TYPES['APPROVAL_TODO']
                    )
                elif new_status == Config.APPLICATION_STATUS['APPROVED']:
                    self.notification_service.create_notification(
                        user_id=None,
                        student_id=application.student_id,
                        title="奖助金申请已通过",
                        content=f"您的{scholarship_name}申请已通过审核，即将进入公示阶段。",
                        notification_type=Config.NOTIFICATION_TYPES['APPROVAL_TODO']
                    )
            
            return self._build_response(
                success=True,
                data={
                    'application_id': application.id,
                    'application_status': application.status,
                    'approval_record_id': approval_record.id
                },
                message="审核完成"
            )
            
        except IntegrityError as e:
            self.db.rollback()
            log_service.log_error("审核申请", e)
            return self._build_error_response(ErrorCode.CONCURRENT_MODIFICATION.value)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("审核申请", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _get_next_approval_level(self, application_id: int) -> Optional[int]:
        last_approval = self.db.query(ApprovalRecord).filter(
            ApprovalRecord.application_id == application_id,
            ApprovalRecord.status == ApprovalStatus.APPROVED.value
        ).order_by(ApprovalRecord.created_at.desc()).first()
        
        if not last_approval:
            return Config.APPROVAL_LEVELS['DEPARTMENT']
        
        return Config.get_next_approval_level(last_approval.level)
    
    def _determine_new_status(self, approval_status: str, level: int, 
                                application: Application) -> str:
        approval_status_lower = approval_status.lower()
        
        if approval_status_lower == ApprovalStatus.REJECTED.value:
            return Config.APPLICATION_STATUS['REJECTED']
        
        if level == Config.APPROVAL_LEVELS['FINANCIAL']:
            return Config.APPLICATION_STATUS['APPROVED']
        
        return Config.APPLICATION_STATUS['REVIEWING']
    
    def start_public_notice(
        self,
        application_id: int,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"开始公示: application_id={application_id}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'start_public_notice')
            if not perm_check['success']:
                return perm_check
        
        try:
            application = self.db.query(Application).options(
                joinedload(Application.student),
                joinedload(Application.scholarship_type)
            ).filter(Application.id == application_id).with_for_update().first()
            
            if not application:
                return self._build_error_response(ErrorCode.APPLICATION_NOT_FOUND.value)
            
            if application.status != Config.APPLICATION_STATUS['APPROVED']:
                log_service.warning(f"申请状态不可公示: application_id={application_id}, status={application.status}")
                return self._build_error_response(ErrorCode.INVALID_STATUS.value)
            
            application.status = Config.APPLICATION_STATUS['PUBLIC_NOTICE']
            self.db.flush()
            
            log_service.log_operation(
                operation="开始公示",
                details={'application_id': application_id}
            )
            
            if application.student and application.scholarship_type:
                self.notification_service.create_notification(
                    user_id=None,
                    student_id=application.student_id,
                    title="奖助金申请进入公示阶段",
                    content=f"您的{application.scholarship_type.name}申请已进入公示阶段，请关注公示结果。",
                    notification_type=Config.NOTIFICATION_TYPES['PUBLIC_NOTICE']
                )
            
            return self._build_response(
                success=True,
                data={
                    'application_id': application.id,
                    'application_status': application.status
                },
                message="公示已开始"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("开始公示", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def disburse_application(
        self,
        application_id: int,
        bank_account: str,
        amount: Optional[float] = None,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"开始发放资金: application_id={application_id}")
        
        if operator_id:
            perm_check = self._check_permission(operator_id, 'disburse')
            if not perm_check['success']:
                return perm_check
        
        validation = Validator.validate_disburse_application(
            application_id, bank_account, amount
        )
        if not validation.valid:
            return self._build_error_response(
                validation.code, validation.message, validation.details
            )
        
        try:
            application = self.db.query(Application).options(
                joinedload(Application.student).joinedload(Student.department),
                joinedload(Application.scholarship_type)
            ).filter(Application.id == application_id).with_for_update().first()
            
            if not application:
                return self._build_error_response(ErrorCode.APPLICATION_NOT_FOUND.value)
            
            if application.status != Config.APPLICATION_STATUS['PUBLIC_NOTICE']:
                log_service.warning(f"申请状态不可发放: application_id={application_id}, status={application.status}")
                return self._build_error_response(ErrorCode.INVALID_STATUS.value)
            
            scholarship_type = application.scholarship_type
            if not scholarship_type:
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            disburse_amount = amount if amount else scholarship_type.amount
            
            if not disburse_amount or disburse_amount <= 0:
                return self._build_error_response(ErrorCode.INVALID_AMOUNT.value)
            
            disbursement = Disbursement(
                application_id=application_id,
                amount=disburse_amount,
                bank_account=bank_account,
                status=Config.DISBURSEMENT_STATUS['PENDING']
            )
            self.db.add(disbursement)
            
            application.status = Config.APPLICATION_STATUS['DISBURSED']
            self.db.flush()
            
            student = application.student
            if not student or not student.department:
                self.db.rollback()
                return self._build_error_response(ErrorCode.DEPARTMENT_NOT_FOUND.value)
            
            quota_update = self.quota_service.update_used_quota(
                student.department.id,
                scholarship_type.id,
                disburse_amount
            )
            
            if not quota_update.get('success', False):
                self.db.rollback()
                return self._build_error_response(
                    quota_update.get('code', ErrorCode.SYSTEM_ERROR.value),
                    quota_update.get('message', '')
                )
            
            log_service.log_disbursement(
                application_id=application_id,
                disbursement_id=disbursement.id,
                amount=disburse_amount,
                success=True
            )
            
            if student and scholarship_type:
                self.notification_service.create_notification(
                    user_id=None,
                    student_id=student.id,
                    title="奖助金已发放",
                    content=f"您的{scholarship_type.name}已发放，金额：{disburse_amount}元，银行账户：{bank_account}。",
                    notification_type=Config.NOTIFICATION_TYPES['DISBURSEMENT_PROGRESS']
                )
            
            return self._build_response(
                success=True,
                data={
                    'disbursement_id': disbursement.id,
                    'application_id': application_id,
                    'amount': disburse_amount
                },
                message="发放成功"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("发放资金", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def verify_disbursement(
        self,
        disbursement_id: int,
        verifier_id: int,
        transaction_id: str
    ) -> Dict[str, Any]:
        log_service.info(f"开始核销: disbursement_id={disbursement_id}")
        
        perm_check = self._check_permission(verifier_id, 'verify')
        if not perm_check['success']:
            return perm_check
        
        if not transaction_id or not transaction_id.strip():
            return self._build_error_response(
                ErrorCode.INVALID_PARAMETER.value, "交易流水号不能为空"
            )
        
        try:
            disbursement = self.db.query(Disbursement).options(
                joinedload(Disbursement.application)
            ).filter(Disbursement.id == disbursement_id).with_for_update().first()
            
            if not disbursement:
                return self._build_error_response(ErrorCode.DISBURSEMENT_NOT_FOUND.value)
            
            if disbursement.status != Config.DISBURSEMENT_STATUS['PENDING']:
                log_service.warning(f"发放状态不可核销: disbursement_id={disbursement_id}, status={disbursement.status}")
                return self._build_error_response(ErrorCode.INVALID_STATUS.value)
            
            verifier = self.db.query(User).filter(User.id == verifier_id).first()
            if not verifier:
                return self._build_error_response(ErrorCode.VERIFIER_NOT_FOUND.value)
            
            disbursement.status = Config.DISBURSEMENT_STATUS['VERIFIED']
            disbursement.transaction_id = transaction_id.strip()
            disbursement.verified_by = verifier_id
            disbursement.verified_date = datetime.utcnow()
            
            application = disbursement.application
            if application:
                application.status = Config.APPLICATION_STATUS['VERIFIED']
            
            self.db.flush()
            
            log_service.log_verification(
                disbursement_id=disbursement_id,
                verifier_id=verifier_id,
                transaction_id=transaction_id,
                success=True
            )
            
            return self._build_response(
                success=True,
                data={
                    'disbursement_id': disbursement.id,
                    'transaction_id': transaction_id
                },
                message="核销成功"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("核销发放", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_application_by_id(self, application_id: int, 
                                load_relations: bool = True) -> Dict[str, Any]:
        try:
            query = self.db.query(Application)
            
            if load_relations:
                query = query.options(
                    joinedload(Application.student).joinedload(Student.department),
                    joinedload(Application.scholarship_type),
                    joinedload(Application.approval_records).joinedload(ApprovalRecord.approver),
                    joinedload(Application.disbursement)
                )
            
            application = query.filter(Application.id == application_id).first()
            
            if not application:
                return self._build_error_response(ErrorCode.APPLICATION_NOT_FOUND.value)
            
            return self._build_response(
                success=True,
                data=self._format_application(application)
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询申请", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_applications_by_student(
        self,
        student_id: int,
        page: int = 1,
        page_size: int = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            page, page_size = Validator.validate_pagination(page, page_size)
            
            query = self.db.query(Application).options(
                joinedload(Application.scholarship_type)
            ).filter(Application.student_id == student_id)
            
            if status:
                validation = Validator.validate_application_status(status)
                if not validation.valid:
                    return self._build_error_response(validation.code, validation.message)
                query = query.filter(Application.status == status)
            
            total = query.count()
            
            applications = query.order_by(
                Application.application_date.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_application(app) for app in applications],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    }
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询学生申请", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_applications_by_status(
        self,
        status: str,
        page: int = 1,
        page_size: int = None
    ) -> Dict[str, Any]:
        try:
            validation = Validator.validate_application_status(status)
            if not validation.valid:
                return self._build_error_response(validation.code, validation.message)
            
            page, page_size = Validator.validate_pagination(page, page_size)
            
            query = self.db.query(Application).options(
                joinedload(Application.student),
                joinedload(Application.scholarship_type)
            ).filter(Application.status == status)
            
            total = query.count()
            
            applications = query.order_by(
                Application.application_date.asc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_application(app) for app in applications],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    }
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("按状态查询申请", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_pending_approvals(
        self,
        level: int,
        department_id: Optional[int] = None,
        page: int = 1,
        page_size: int = None
    ) -> Dict[str, Any]:
        try:
            validation = Validator.validate_approval_level(level)
            if not validation.valid:
                return self._build_error_response(validation.code, validation.message)
            
            page, page_size = Validator.validate_pagination(page, page_size)
            
            applications_query = self.db.query(Application).options(
                joinedload(Application.student).joinedload(Student.department),
                joinedload(Application.scholarship_type)
            ).filter(
                Application.status.in_([
                    Config.APPLICATION_STATUS['SUBMITTED'],
                    Config.APPLICATION_STATUS['REVIEWING']
                ])
            )
            
            if department_id:
                applications_query = applications_query.join(Student).filter(
                    Student.department_id == department_id
                )
            
            applications = applications_query.order_by(
                Application.application_date.asc()
            ).all()
            
            pending_applications = []
            for app in applications:
                next_level = self._get_next_approval_level(app.id)
                if next_level == level:
                    pending_applications.append(app)
            
            total = len(pending_applications)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_apps = pending_applications[start:end]
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_application(app) for app in paginated_apps],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    },
                    'next_approval_level': level
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询待审核申请", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_application_statistics(self, department_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            query = self.db.query(
                Application.status,
                func.count(Application.id).label('count')
            )
            
            if department_id:
                query = query.join(Student).filter(Student.department_id == department_id)
            
            results = query.group_by(Application.status).all()
            
            statistics = {
                'total': 0,
                'by_status': {}
            }
            
            for status, count in results:
                statistics['by_status'][status] = count
                statistics['total'] += count
            
            return self._build_response(
                success=True,
                data=statistics
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询申请统计", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _format_application(self, application: Application) -> Dict[str, Any]:
        result = {
            'id': application.id,
            'student_id': application.student_id,
            'scholarship_type_id': application.scholarship_type_id,
            'application_date': application.application_date,
            'status': application.status,
            'reason': application.reason,
            'attachments': application.attachments,
            'created_at': application.created_at,
            'updated_at': application.updated_at
        }
        
        if application.student:
            result['student'] = {
                'id': application.student.id,
                'student_id': application.student.student_id,
                'name': application.student.name,
                'department': application.student.department.name if application.student.department else None
            }
        
        if application.scholarship_type:
            result['scholarship_type'] = {
                'id': application.scholarship_type.id,
                'name': application.scholarship_type.name,
                'code': application.scholarship_type.code,
                'type': application.scholarship_type.type,
                'amount': application.scholarship_type.amount
            }
        
        if application.approval_records:
            result['approval_records'] = [
                {
                    'id': r.id,
                    'approver_name': r.approver.name if r.approver else None,
                    'status': r.status,
                    'comments': r.comments,
                    'level': r.level,
                    'created_at': r.created_at
                }
                for r in sorted(application.approval_records, key=lambda x: x.created_at)
            ]
        
        if application.disbursement:
            result['disbursement'] = {
                'id': application.disbursement.id,
                'amount': application.disbursement.amount,
                'bank_account': application.disbursement.bank_account,
                'status': application.disbursement.status,
                'transaction_id': application.disbursement.transaction_id,
                'disbursement_date': application.disbursement.disbursement_date,
                'verified_date': application.disbursement.verified_date
            }
        
        return result
