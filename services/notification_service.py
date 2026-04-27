from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy import and_, func

from models import Notification, User, Student
from config import Config, ErrorCode
from utils.validators import Validator
from services.log_service import log_service


class NotificationService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
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
                log_service.log_permission_denied(user_id, permission, "notification_operation")
                return self._build_error_response(ErrorCode.PERMISSION_DENIED.value)
            
            return self._build_response(True, data={'user': user})
            
        except SQLAlchemyError as e:
            log_service.log_error("检查通知权限", e, user_id=user_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _validate_create_notification(
        self,
        user_id: Optional[int],
        student_id: Optional[int],
        title: str,
        content: str,
        notification_type: str
    ) -> Dict[str, Any]:
        if user_id is None and student_id is None:
            return self._build_error_response(
                ErrorCode.INVALID_PARAMETER.value, 
                "必须指定用户ID或学生ID"
            )
        
        if user_id is not None:
            result = Validator.validate_id(user_id, "用户ID")
            if not result.valid:
                return self._build_error_response(result.code, result.message)
        
        if student_id is not None:
            result = Validator.validate_id(student_id, "学生ID")
            if not result.valid:
                return self._build_error_response(result.code, result.message)
        
        result = Validator.validate_text(title, "通知标题", max_length=100, allow_empty=False)
        if not result.valid:
            return self._build_error_response(result.code, result.message)
        
        result = Validator.validate_text(content, "通知内容", max_length=2000, allow_empty=False)
        if not result.valid:
            return self._build_error_response(result.code, result.message)
        
        valid_types = list(Config.NOTIFICATION_TYPES.values())
        if notification_type not in valid_types:
            return self._build_error_response(
                ErrorCode.INVALID_PARAMETER.value,
                f"通知类型必须是 {valid_types} 之一"
            )
        
        return self._build_response(True)
    
    def create_notification(
        self,
        user_id: Optional[int],
        student_id: Optional[int],
        title: str,
        content: str,
        notification_type: str
    ) -> Dict[str, Any]:
        log_service.info(f"开始创建通知: user_id={user_id}, student_id={student_id}, type={notification_type}")
        
        validation = self._validate_create_notification(
            user_id, student_id, title, content, notification_type
        )
        if not validation['success']:
            log_service.warning(f"创建通知参数校验失败: {validation['message']}")
            return validation
        
        try:
            if user_id:
                user = self.db.query(User).filter(User.id == user_id).first()
                if not user:
                    log_service.warning(f"用户不存在: user_id={user_id}")
                    return self._build_error_response(ErrorCode.USER_NOT_FOUND.value)
            
            if student_id:
                student = self.db.query(Student).filter(Student.id == student_id).first()
                if not student:
                    log_service.warning(f"学生不存在: student_id={student_id}")
                    return self._build_error_response(ErrorCode.STUDENT_NOT_FOUND.value)
            
            notification = Notification(
                user_id=user_id,
                student_id=student_id,
                title=title.strip(),
                content=content.strip(),
                type=notification_type,
                is_read=False
            )
            
            self.db.add(notification)
            self.db.flush()
            
            log_service.log_operation(
                operation="创建通知",
                user_id=user_id,
                student_id=student_id,
                details={
                    'notification_id': notification.id,
                    'notification_type': notification_type,
                    'success': True
                }
            )
            
            if Config.NOTIFICATION_ENABLED:
                self._send_external_notification(notification)
            
            return self._build_response(
                success=True,
                data={
                    'notification_id': notification.id,
                    'created_at': notification.created_at
                },
                message="通知创建成功"
            )
            
        except IntegrityError as e:
            self.db.rollback()
            log_service.log_error("创建通知", e)
            return self._build_error_response(ErrorCode.CONCURRENT_MODIFICATION.value, "数据完整性冲突")
        
        except OperationalError as e:
            self.db.rollback()
            log_service.log_error("创建通知", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, "数据库操作失败")
        
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("创建通知", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
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
            
            log_service.info(
                f"发送外部通知: 接收者={recipient}, 标题={notification.title}, 类型={notification.type}"
            )
            
            return True
            
        except Exception as e:
            log_service.warning(f"外部通知发送失败: {str(e)}")
            return False
    
    def get_notifications_by_user(
        self,
        user_id: int,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = None
    ) -> Dict[str, Any]:
        log_service.info(f"查询用户通知: user_id={user_id}, unread_only={unread_only}")
        
        validation = Validator.validate_id(user_id, "用户ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        try:
            page, page_size = Validator.validate_pagination(page, page_size)
            
            query = self.db.query(Notification).options(
                joinedload(Notification.user)
            ).filter(Notification.user_id == user_id)
            
            if unread_only:
                query = query.filter(Notification.is_read == False)
            
            total = query.count()
            
            notifications = query.order_by(
                Notification.created_at.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_notification(n) for n in notifications],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    },
                    'unread_only': unread_only
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询用户通知", e, user_id=user_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_notifications_by_student(
        self,
        student_id: int,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = None
    ) -> Dict[str, Any]:
        log_service.info(f"查询学生通知: student_id={student_id}, unread_only={unread_only}")
        
        validation = Validator.validate_id(student_id, "学生ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        try:
            page, page_size = Validator.validate_pagination(page, page_size)
            
            query = self.db.query(Notification).options(
                joinedload(Notification.student)
            ).filter(Notification.student_id == student_id)
            
            if unread_only:
                query = query.filter(Notification.is_read == False)
            
            total = query.count()
            
            notifications = query.order_by(
                Notification.created_at.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            return self._build_response(
                success=True,
                data={
                    'items': [self._format_notification(n) for n in notifications],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total,
                        'total_pages': (total + page_size - 1) // page_size
                    },
                    'unread_only': unread_only
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询学生通知", e, student_id=student_id)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def mark_as_read(
        self,
        notification_id: int,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"标记通知为已读: notification_id={notification_id}")
        
        validation = Validator.validate_id(notification_id, "通知ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        try:
            notification = self.db.query(Notification).options(
                joinedload(Notification.user),
                joinedload(Notification.student)
            ).filter(Notification.id == notification_id).with_for_update().first()
            
            if not notification:
                log_service.warning(f"通知不存在: notification_id={notification_id}")
                return self._build_error_response(ErrorCode.APPLICATION_NOT_FOUND.value, "通知不存在")
            
            if notification.is_read:
                return self._build_response(
                    success=True,
                    data={'notification_id': notification.id, 'is_read': True},
                    message="通知已为已读状态"
                )
            
            notification.is_read = True
            self.db.flush()
            
            log_service.log_operation(
                operation="标记通知已读",
                details={
                    'notification_id': notification_id,
                    'success': True
                }
            )
            
            return self._build_response(
                success=True,
                data={
                    'notification_id': notification.id,
                    'is_read': True,
                    'marked_at': datetime.utcnow()
                },
                message="标记为已读成功"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("标记通知已读", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def mark_all_as_read(
        self,
        user_id: Optional[int] = None,
        student_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"批量标记通知已读: user_id={user_id}, student_id={student_id}")
        
        if user_id is None and student_id is None:
            return self._build_error_response(
                ErrorCode.INVALID_PARAMETER.value,
                "必须指定用户ID或学生ID"
            )
        
        try:
            query = self.db.query(Notification)
            
            if user_id:
                validation = Validator.validate_id(user_id, "用户ID")
                if not validation.valid:
                    return self._build_error_response(validation.code, validation.message)
                query = query.filter(Notification.user_id == user_id)
            
            if student_id:
                validation = Validator.validate_id(student_id, "学生ID")
                if not validation.valid:
                    return self._build_error_response(validation.code, validation.message)
                query = query.filter(Notification.student_id == student_id)
            
            query = query.filter(Notification.is_read == False)
            
            count = query.update({'is_read': True}, synchronize_session=False)
            self.db.flush()
            
            log_service.log_operation(
                operation="批量标记通知已读",
                user_id=user_id,
                student_id=student_id,
                details={
                    'marked_count': count,
                    'success': True
                }
            )
            
            return self._build_response(
                success=True,
                data={
                    'count': count,
                    'user_id': user_id,
                    'student_id': student_id
                },
                message=f"已标记 {count} 条通知为已读"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            log_service.log_error("批量标记通知已读", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _format_notification(self, notification: Notification) -> Dict[str, Any]:
        result = {
            'id': notification.id,
            'user_id': notification.user_id,
            'student_id': notification.student_id,
            'title': notification.title,
            'content': notification.content,
            'type': notification.type,
            'is_read': notification.is_read,
            'created_at': notification.created_at
        }
        
        if notification.user:
            result['user'] = {
                'id': notification.user.id,
                'name': notification.user.name,
                'role': notification.user.role
            }
        
        if notification.student:
            result['student'] = {
                'id': notification.student.id,
                'student_id': notification.student.student_id,
                'name': notification.student.name
            }
        
        return result
    
    def get_unread_count(
        self,
        user_id: Optional[int] = None,
        student_id: Optional[int] = None
    ) -> Dict[str, Any]:
        log_service.info(f"查询未读通知数量: user_id={user_id}, student_id={student_id}")
        
        try:
            query = self.db.query(Notification).filter(Notification.is_read == False)
            
            if user_id:
                validation = Validator.validate_id(user_id, "用户ID")
                if not validation.valid:
                    return self._build_error_response(validation.code, validation.message)
                query = query.filter(Notification.user_id == user_id)
            
            if student_id:
                validation = Validator.validate_id(student_id, "学生ID")
                if not validation.valid:
                    return self._build_error_response(validation.code, validation.message)
                query = query.filter(Notification.student_id == student_id)
            
            count = query.count()
            
            return self._build_response(
                success=True,
                data={
                    'unread_count': count,
                    'user_id': user_id,
                    'student_id': student_id
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询未读通知数量", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def send_application_reminder(
        self,
        student_id: int,
        scholarship_name: str
    ) -> Dict[str, Any]:
        log_service.info(f"发送申请提醒: student_id={student_id}")
        
        validation = Validator.validate_id(student_id, "学生ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        result = Validator.validate_text(scholarship_name, "奖助金名称", max_length=100, allow_empty=False)
        if not result.valid:
            return self._build_error_response(result.code, result.message)
        
        return self.create_notification(
            user_id=None,
            student_id=student_id,
            title="奖助金申报提醒",
            content=f"{scholarship_name}的申报即将截止，请尽快提交申请。",
            notification_type=Config.NOTIFICATION_TYPES['APPLICATION_REMINDER']
        )
    
    def send_approval_todo(
        self,
        user_id: int,
        student_name: str,
        scholarship_name: str
    ) -> Dict[str, Any]:
        log_service.info(f"发送审核待办: user_id={user_id}")
        
        validation = Validator.validate_id(user_id, "用户ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        return self.create_notification(
            user_id=user_id,
            student_id=None,
            title="审核待办提醒",
            content=f"学生{student_name}的{scholarship_name}申请等待您的审核。",
            notification_type=Config.NOTIFICATION_TYPES['APPROVAL_TODO']
        )
    
    def send_public_notice(
        self,
        student_id: int,
        scholarship_name: str
    ) -> Dict[str, Any]:
        log_service.info(f"发送公示通知: student_id={student_id}")
        
        validation = Validator.validate_id(student_id, "学生ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        return self.create_notification(
            user_id=None,
            student_id=student_id,
            title="公示通知",
            content=f"您的{scholarship_name}申请已进入公示阶段，请关注公示结果。",
            notification_type=Config.NOTIFICATION_TYPES['PUBLIC_NOTICE']
        )
    
    def send_disbursement_progress(
        self,
        student_id: int,
        scholarship_name: str,
        amount: float
    ) -> Dict[str, Any]:
        log_service.info(f"发送发放进度: student_id={student_id}, amount={amount}")
        
        validation = Validator.validate_id(student_id, "学生ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        validation = Validator.validate_amount(amount, "发放金额")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        return self.create_notification(
            user_id=None,
            student_id=student_id,
            title="发放进度通知",
            content=f"您的{scholarship_name}已发放，金额：{amount}元，请注意查收。",
            notification_type=Config.NOTIFICATION_TYPES['DISBURSEMENT_PROGRESS']
        )
    
    def send_quota_warning(
        self,
        department_name: str,
        scholarship_name: str,
        remaining_quota: int,
        remaining_budget: float
    ) -> Dict[str, Any]:
        log_service.info(
            f"发送额度预警: department={department_name}, "
            f"remaining_quota={remaining_quota}, remaining_budget={remaining_budget}"
        )
        
        return self.create_notification(
            user_id=None,
            student_id=None,
            title="院系额度预警",
            content=f"院系{department_name}的{scholarship_name}额度即将用尽。"
                   f"剩余名额: {remaining_quota}, 剩余预算: {remaining_budget}元。",
            notification_type=Config.NOTIFICATION_TYPES['QUOTA_WARNING']
        )
    
    def get_notification_statistics(self) -> Dict[str, Any]:
        log_service.info("查询通知统计")
        
        try:
            total = self.db.query(Notification).count()
            unread = self.db.query(Notification).filter(Notification.is_read == False).count()
            
            type_stats = {}
            for notification_type in Config.NOTIFICATION_TYPES.values():
                count = self.db.query(Notification).filter(
                    Notification.type == notification_type
                ).count()
                type_stats[notification_type] = count
            
            read_rate = round((total - unread) / total * 100, 2) if total > 0 else 0
            
            return self._build_response(
                success=True,
                data={
                    'total_notifications': total,
                    'unread_notifications': unread,
                    'notifications_by_type': type_stats,
                    'read_rate': read_rate
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("查询通知统计", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
