from datetime import datetime, date
from sqlalchemy.orm import Session
from models import Application, ApprovalRecord, Disbursement, Student, ScholarshipType, DepartmentQuota
from services.quota_service import QuotaService
from services.notification_service import NotificationService

class ApplicationService:
    def __init__(self, db: Session):
        self.db = db
        self.quota_service = QuotaService(db)
        self.notification_service = NotificationService(db)

    def submit_application(self, student_id: int, scholarship_type_id: int, reason: str = None, attachments: str = None) -> dict:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {'success': False, 'error': '学生不存在'}

        scholarship_type = self.db.query(ScholarshipType).filter(ScholarshipType.id == scholarship_type_id).first()
        if not scholarship_type:
            return {'success': False, 'error': '奖助学金类型不存在'}

        today = date.today()
        if scholarship_type.application_start_date and scholarship_type.application_end_date:
            if not (scholarship_type.application_start_date <= today <= scholarship_type.application_end_date):
                return {'success': False, 'error': '不在申报时间内'}

        existing = self.db.query(Application).filter(
            Application.student_id == student_id,
            Application.scholarship_type_id == scholarship_type_id,
            Application.status.in_(['submitted', 'reviewed', 'approved', '公示中'])
        ).first()
        if existing:
            return {'success': False, 'error': '已存在正在处理中的申请'}

        if scholarship_type.max_application_count:
            count = self.db.query(Application).filter(
                Application.student_id == student_id,
                Application.scholarship_type_id == scholarship_type_id
            ).count()
            if count >= scholarship_type.max_application_count:
                return {'success': False, 'error': f'超出最大申请次数({scholarship_type.max_application_count})'}

        application = Application(
            student_id=student_id,
            scholarship_type_id=scholarship_type_id,
            application_date=datetime.utcnow(),
            status='submitted',
            reason=reason,
            attachments=attachments
        )
        self.db.add(application)
        self.db.commit()

        self.notification_service.notify_approvers(
            application,
            f'新申请待审核: {student.name} 申请 {scholarship_type.name}',
            'approval_todo'
        )

        return {'success': True, 'application_id': application.id}

    def review_application(self, application_id: int, approver_id: int, status: str, comments: str = None, level: int = 1) -> dict:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return {'success': False, 'error': '申请不存在'}

        if status == 'approved':
            if level == 1:
                application.status = 'reviewed'
            elif level == 2:
                application.status = 'approved'
            elif level == 3:
                application.status = 'approved'
        elif status == 'rejected':
            application.status = 'rejected'

        approval_record = ApprovalRecord(
            application_id=application_id,
            approver_id=approver_id,
            approval_date=datetime.utcnow(),
            status=status,
            comments=comments,
            level=level
        )
        self.db.add(approval_record)
        self.db.commit()

        if status == 'approved' and level == 2:
            self.notification_service.notify_student(
                application.student_id,
                f'您的申请已通过院系审核: {application.scholarship_type.name}',
                'public_notice'
            )
        elif status == 'rejected':
            self.notification_service.notify_student(
                application.student_id,
                f'您的申请未通过审核',
                'public_notice'
            )

        return {'success': True}

    def publish_application(self, application_id: int) -> dict:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return {'success': False, 'error': '申请不存在'}

        if application.status != 'approved':
            return {'success': False, 'error': '只有已批准的申请才能公示'}

        application.status = '公示中'
        self.db.commit()

        self.notification_service.notify_student(
            application.student_id,
            f'您的申请已进入公示期: {application.scholarship_type.name}',
            'public_notice'
        )

        return {'success': True}

    def disburse_application(self, application_id: int, amount: float, bank_account: str = None) -> dict:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return {'success': False, 'error': '申请不存在'}

        if application.status != '公示中':
            return {'success': False, 'error': '只有公示结束的申请才能发放'}

        quota_result = self.quota_service.check_and_use_quota(
            application.student.department_id,
            application.scholarship_type_id,
            amount
        )
        if not quota_result['success']:
            return quota_result

        disbursement = Disbursement(
            application_id=application_id,
            amount=amount,
            disbursement_date=datetime.utcnow(),
            status='pending',
            bank_account=bank_account
        )
        self.db.add(disbursement)

        application.status = '已发放'
        self.db.commit()

        self.notification_service.notify_student(
            application.student_id,
            f'奖助学金已发放: {amount}元',
            'disbursement_progress'
        )

        return {'success': True, 'disbursement_id': disbursement.id}

    def verify_disbursement(self, disbursement_id: int, verifier_id: int, transaction_id: str = None) -> dict:
        disbursement = self.db.query(Disbursement).filter(Disbursement.id == disbursement_id).first()
        if not disbursement:
            return {'success': False, 'error': '发放记录不存在'}

        disbursement.status = 'verified'
        disbursement.verified_by = verifier_id
        disbursement.verified_date = datetime.utcnow()
        if transaction_id:
            disbursement.transaction_id = transaction_id

        application = disbursement.application
        application.status = '已核销'

        self.quota_service.confirm_quota_usage(
            application.student.department_id,
            application.scholarship_type_id,
            disbursement.amount
        )

        self.db.commit()
        return {'success': True}

    def get_application_flow(self, application_id: int) -> dict:
        application = self.db.query(Application).filter(Application.id == application_id).first()
        if not application:
            return None

        approval_records = self.db.query(ApprovalRecord).filter(
            ApprovalRecord.application_id == application_id
        ).order_by(ApprovalRecord.level).all()

        disbursement = self.db.query(Disbursement).filter(
            Disbursement.application_id == application_id
        ).first()

        return {
            'application_id': application.id,
            'student_name': application.student.name,
            'scholarship_name': application.scholarship_type.name,
            'status': application.status,
            'application_date': application.application_date,
            'approval_records': [
                {
                    'level': r.level,
                    'status': r.status,
                    'comments': r.comments,
                    'approval_date': r.approval_date
                } for r in approval_records
            ],
            'disbursement': {
                'amount': disbursement.amount,
                'status': disbursement.status,
                'disbursement_date': disbursement.disbursement_date
            } if disbursement else None
        }

    def get_pending_applications(self, department_id: int = None, status: str = None) -> list:
        query = self.db.query(Application)
        if department_id:
            query = query.join(Student).filter(Student.department_id == department_id)
        if status:
            query = query.filter(Application.status == status)
        return query.all()