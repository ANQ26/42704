from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from models import Notification, User, Student
from config import Config


class NotificationService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_notification(
        self,
        user_id: Optional[int],
        student_id: Optional[int],
        title: str,
        content: str,
        notification_type: str
    ) -> Dict:
        try:
            if user_id is None and student_id is None:
                return {
                    "success": False,
                    "message": "必须指定用户ID或学生ID",
                    "code": "MISSING_RECIPIENT"
                }
            
            notification = Notification(
                user_id=user_id,
                student_id=student_id,
                title=title,
                content=content,
                type=notification_type,
                is_read=False
            )
            
            self.db.add(notification)
            self.db.flush()
            
            if Config.NOTIFICATION_ENABLED:
                self._send_external_notification(notification)
            
            return {
                "success": True,
                "message": "通知创建成功",
                "notification_id": notification.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def _send_external_notification(self, notification: Notification) -> bool:
        try:
            recipient = None
            contact_info = None
            
            if notification.user_id:
                user = self.db.query(User).filter(User.id == notification.user_id).first()
                if user:
                    recipient = user.name
            
            if notification.student_id:
                student = self.db.query(Student).filter(Student.id == notification.student_id).first()
                if student:
                    recipient = student.name
            
            print(f"[通知] 发送给: {recipient}")
            print(f"[通知] 标题: {notification.title}")
            print(f"[通知] 内容: {notification.content}")
            print(f"[通知] 类型: {notification.type}")
            print("-" * 50)
            
            return True
            
        except Exception as e:
            print(f"[通知] 发送失败: {str(e)}")
            return False
    
    def get_notifications_by_user(self, user_id: int, unread_only: bool = False) -> List[Dict]:
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        notifications = query.order_by(Notification.created_at.desc()).all()
        
        return [self._format_notification(n) for n in notifications]
    
    def get_notifications_by_student(self, student_id: int, unread_only: bool = False) -> List[Dict]:
        query = self.db.query(Notification).filter(Notification.student_id == student_id)
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        notifications = query.order_by(Notification.created_at.desc()).all()
        
        return [self._format_notification(n) for n in notifications]
    
    def mark_as_read(self, notification_id: int) -> Dict:
        try:
            notification = self.db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            
            if not notification:
                return {
                    "success": False,
                    "message": "通知不存在",
                    "code": "NOTIFICATION_NOT_FOUND"
                }
            
            notification.is_read = True
            
            return {
                "success": True,
                "message": "标记为已读成功"
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def mark_all_as_read(self, user_id: Optional[int] = None, student_id: Optional[int] = None) -> Dict:
        try:
            query = self.db.query(Notification)
            
            if user_id:
                query = query.filter(Notification.user_id == user_id)
            if student_id:
                query = query.filter(Notification.student_id == student_id)
            
            query = query.filter(Notification.is_read == False)
            
            count = query.update({'is_read': True}, synchronize_session=False)
            
            return {
                "success": True,
                "message": f"已标记 {count} 条通知为已读",
                "count": count
            }
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "message": str(e), "code": "SYSTEM_ERROR"}
    
    def _format_notification(self, notification: Notification) -> Dict:
        return {
            'id': notification.id,
            'user_id': notification.user_id,
            'student_id': notification.student_id,
            'title': notification.title,
            'content': notification.content,
            'type': notification.type,
            'is_read': notification.is_read,
            'created_at': notification.created_at
        }
    
    def get_unread_count(self, user_id: Optional[int] = None, student_id: Optional[int] = None) -> int:
        query = self.db.query(Notification).filter(Notification.is_read == False)
        
        if user_id:
            query = query.filter(Notification.user_id == user_id)
        if student_id:
            query = query.filter(Notification.student_id == student_id)
        
        return query.count()
    
    def send_application_reminder(self, student_id: int, scholarship_name: str) -> Dict:
        return self.create_notification(
            user_id=None,
            student_id=student_id,
            title="奖助金申报提醒",
            content=f"{scholarship_name}的申报即将截止，请尽快提交申请。",
            notification_type=Config.NOTIFICATION_TYPES['APPLICATION_REMINDER']
        )
    
    def send_approval_todo(self, user_id: int, student_name: str, scholarship_name: str) -> Dict:
        return self.create_notification(
            user_id=user_id,
            student_id=None,
            title="审核待办提醒",
            content=f"学生{student_name}的{scholarship_name}申请等待您的审核。",
            notification_type=Config.NOTIFICATION_TYPES['APPROVAL_TODO']
        )
    
    def send_public_notice(self, student_id: int, scholarship_name: str) -> Dict:
        return self.create_notification(
            user_id=None,
            student_id=student_id,
            title="公示通知",
            content=f"您的{scholarship_name}申请已进入公示阶段，请关注公示结果。",
            notification_type=Config.NOTIFICATION_TYPES['PUBLIC_NOTICE']
        )
    
    def send_disbursement_progress(self, student_id: int, scholarship_name: str, amount: float) -> Dict:
        return self.create_notification(
            user_id=None,
            student_id=student_id,
            title="发放进度通知",
            content=f"您的{scholarship_name}已发放，金额：{amount}元，请注意查收。",
            notification_type=Config.NOTIFICATION_TYPES['DISBURSEMENT_PROGRESS']
        )
    
    def send_quota_warning(self, department_name: str, scholarship_name: str, 
                            remaining_quota: int, remaining_budget: float) -> Dict:
        return self.create_notification(
            user_id=None,
            student_id=None,
            title="院系额度预警",
            content=f"院系{department_name}的{scholarship_name}额度即将用尽。"
                   f"剩余名额: {remaining_quota}, 剩余预算: {remaining_budget}元。",
            notification_type=Config.NOTIFICATION_TYPES['QUOTA_WARNING']
        )
    
    def get_notification_statistics(self) -> Dict:
        total = self.db.query(Notification).count()
        unread = self.db.query(Notification).filter(Notification.is_read == False).count()
        
        type_stats = {}
        for notification_type in Config.NOTIFICATION_TYPES.values():
            count = self.db.query(Notification).filter(
                Notification.type == notification_type
            ).count()
            type_stats[notification_type] = count
        
        return {
            "total_notifications": total,
            "unread_notifications": unread,
            "notifications_by_type": type_stats,
            "read_rate": round((total - unread) / total * 100, 2) if total > 0 else 0
        }
