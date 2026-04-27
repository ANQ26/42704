from datetime import datetime
from sqlalchemy.orm import Session
from models import Notification, User, Student
from config import Config
import json

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def send_notification(self, user_id: int = None, student_id: int = None, title: str, content: str, notification_type: str, channels: list = None) -> dict:
        if channels is None:
            channels = Config.NOTIFICATION_CHANNELS

        notification = Notification(
            user_id=user_id,
            student_id=student_id,
            title=title,
            content=content,
            type=notification_type,
            is_read=False,
            created_at=datetime.utcnow()
        )
        self.db.add(notification)
        self.db.commit()

        results = {'in_app': True}

        if 'sms' in channels and Config.SMS_ENABLED:
            results['sms'] = self._send_sms(user_id, student_id, content)

        if 'campus_platform' in channels and Config.CAMPUS_PLATFORM_ENABLED:
            results['campus_platform'] = self._send_to_campus_platform(user_id, student_id, title, content)

        return {
            'success': True,
            'notification_id': notification.id,
            'channels': results
        }

    def _send_sms(self, user_id: int, student_id: int, content: str) -> bool:
        return True

    def _send_to_campus_platform(self, user_id: int, student_id: int, title: str, content: str) -> bool:
        return True

    def notify_student(self, student_id: int, message: str, notification_type: str):
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return

        user = self.db.query(User).filter(User.name == student.name).first()
        if user:
            self.send_notification(
                user_id=user.id,
                student_id=student_id,
                title=f'奖助学金通知',
                content=message,
                notification_type=notification_type
            )
        else:
            notification = Notification(
                student_id=student_id,
                title=f'奖助学金通知',
                content=message,
                type=notification_type,
                is_read=False,
                created_at=datetime.utcnow()
            )
            self.db.add(notification)
            self.db.commit()

    def notify_approvers(self, application, message: str, notification_type: str):
        from models import User

        if application.student and application.student.department_id:
            department_admins = self.db.query(User).filter(
                User.department_id == application.student.department_id,
                User.role.in_(['department_admin', 'admin'])
            ).all()

            for admin in department_admins:
                self.send_notification(
                    user_id=admin.id,
                    student_id=application.student_id,
                    title=f'申请待审核',
                    content=message,
                    notification_type=notification_type
                )

    def get_user_notifications(self, user_id: int, unread_only: bool = False) -> list:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.is_read == False)
        return query.order_by(Notification.created_at.desc()).all()

    def mark_as_read(self, notification_id: int) -> dict:
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return {'success': False, 'error': '通知不存在'}

        notification.is_read = True
        self.db.commit()
        return {'success': True}

    def mark_all_as_read(self, user_id: int) -> dict:
        self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({'is_read': True})
        self.db.commit()
        return {'success': True}

    def send_batch_notifications(self, user_ids: list, title: str, content: str, notification_type: str) -> dict:
        notifications = []
        for user_id in user_ids:
            notification = Notification(
                user_id=user_id,
                title=title,
                content=content,
                type=notification_type,
                is_read=False,
                created_at=datetime.utcnow()
            )
            notifications.append(notification)

        self.db.bulk_save_objects(notifications)
        self.db.commit()

        return {'success': True, 'count': len(notifications)}

    def send_application_reminder(self, student_id: int):
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return

        self.notify_student(
            student_id,
            '您有奖助学金申请待提交，请尽快完成申报',
            'application_reminder'
        )

    def send_review_todo(self, approver_id: int, application_info: str):
        self.send_notification(
            user_id=approver_id,
            title='新的审核任务',
            content=application_info,
            notification_type='approval_todo'
        )

    def send_publicity_notification(self, student_id: int, scholarship_name: str):
        self.notify_student(
            student_id,
            f'您的{scholarship_name}申请已进入公示期',
            'public_notice'
        )

    def send_disbursement_notification(self, student_id: int, amount: float):
        self.notify_student(
            student_id,
            f'您的奖助学金 {amount}元 已发放，请注意查收',
            'disbursement_progress'
        )

    def get_unread_count(self, user_id: int) -> int:
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

    def cleanup_old_notifications(self, days: int = 90) -> dict:
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        count = self.db.query(Notification).filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).delete()

        self.db.commit()
        return {'success': True, 'deleted_count': count}