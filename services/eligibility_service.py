from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

from models import Student, ScholarshipType, Application, Grade, StudentStatus, Department
from config import Config, ErrorCode
from utils.validators import Validator
from services.log_service import log_service


class EligibilityService:
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
    
    def check_eligibility(self, student_id: int, scholarship_type_id: int) -> Dict[str, Any]:
        log_service.info(f"检查资格: student_id={student_id}, scholarship_type_id={scholarship_type_id}")
        
        validation = Validator.validate_id(student_id, "学生ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        validation = Validator.validate_id(scholarship_type_id, "奖助金类型ID")
        if not validation.valid:
            return self._build_error_response(validation.code, validation.message)
        
        try:
            student = self.db.query(Student).options(
                joinedload(Student.department)
            ).filter(Student.id == student_id).first()
            
            if not student:
                log_service.warning(f"学生不存在: student_id={student_id}")
                return self._build_response(
                    success=False,
                    code=ErrorCode.STUDENT_NOT_FOUND.value,
                    data={'eligible': False, 'issues': ["学生不存在"]}
                )
            
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            
            if not scholarship_type:
                log_service.warning(f"奖助金类型不存在: scholarship_type_id={scholarship_type_id}")
                return self._build_response(
                    success=False,
                    code=ErrorCode.SCHOLARSHIP_NOT_FOUND.value,
                    data={'eligible': False, 'issues': ["奖助金类型不存在"]}
                )
            
            issues = []
            eligible = True
            
            status_check = self._check_student_status(student)
            if not status_check['eligible']:
                eligible = False
                issues.extend(status_check['issues'])
            
            gpa_check = self._check_gpa_requirement(student, scholarship_type)
            if not gpa_check['eligible']:
                eligible = False
                issues.extend(gpa_check['issues'])
            
            application_count_check = self._check_application_count(student, scholarship_type)
            if not application_count_check['eligible']:
                eligible = False
                issues.extend(application_count_check['issues'])
            
            previous_awards_check = self._check_previous_awards(student, scholarship_type)
            if not previous_awards_check['eligible']:
                eligible = False
                issues.extend(previous_awards_check['issues'])
            
            student_name = student.name if student else "未知学生"
            scholarship_name = scholarship_type.name if scholarship_type else "未知奖助金"
            
            log_service.info(f"资格检查结果: student={student_name}, scholarship={scholarship_name}, eligible={eligible}")
            
            return self._build_response(
                success=True,
                data={
                    'eligible': eligible,
                    'issues': issues,
                    'student_name': student_name,
                    'scholarship_name': scholarship_name,
                    'gpa': gpa_check.get('gpa'),
                    'current_application_count': application_count_check.get('current_count', 0),
                    'previous_awards_count': previous_awards_check.get('previous_awards_count', 0)
                }
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("检查资格", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def _check_student_status(self, student: Student) -> Dict[str, Any]:
        issues = []
        eligible = True
        
        if not student:
            return {'eligible': False, 'issues': ["学生对象为空"]}
        
        if student.status != Config.STUDENT_STATUS['ACTIVE']:
            eligible = False
            issues.append(f"学生状态为{student.status}，不是活跃状态")
        
        latest_status = self.db.query(StudentStatus).filter(
            StudentStatus.student_id == student.id
        ).order_by(StudentStatus.effective_date.desc()).first()
        
        if latest_status:
            if latest_status.status != Config.STUDENT_STATUS['ACTIVE']:
                eligible = False
                issues.append(f"最新学籍状态为{latest_status.status}")
            
            if latest_status.expiry_date and latest_status.expiry_date < datetime.utcnow().date():
                eligible = False
                issues.append("学籍状态已过期")
        
        return {'eligible': eligible, 'issues': issues}
    
    def _check_gpa_requirement(self, student: Student, scholarship_type: ScholarshipType) -> Dict[str, Any]:
        issues = []
        eligible = True
        
        if not scholarship_type:
            return {'eligible': True, 'issues': [], 'gpa': None}
        
        min_gpa = scholarship_type.min_gpa
        if min_gpa is None or min_gpa <= 0:
            return {'eligible': True, 'issues': [], 'gpa': None}
        
        grades = self.db.query(Grade).filter(Grade.student_id == student.id).all()
        
        if not grades:
            eligible = False
            issues.append("没有成绩记录")
            return {'eligible': eligible, 'issues': issues}
        
        total_credits = sum(grade.credit for grade in grades)
        if total_credits == 0:
            eligible = False
            issues.append("总学分为0，无法计算GPA")
            return {'eligible': eligible, 'issues': issues}
        
        weighted_sum = sum(grade.score * grade.credit for grade in grades)
        gpa = weighted_sum / total_credits
        
        if gpa < min_gpa:
            eligible = False
            issues.append(f"GPA要求为{min_gpa}，当前GPA为{round(gpa, 2)}，不满足要求")
        
        return {'eligible': eligible, 'issues': issues, 'gpa': round(gpa, 2)}
    
    def _check_application_count(self, student: Student, scholarship_type: ScholarshipType) -> Dict[str, Any]:
        issues = []
        eligible = True
        
        if not scholarship_type:
            return {'eligible': True, 'issues': [], 'current_count': 0}
        
        max_count = scholarship_type.max_application_count
        if max_count is None or max_count <= 0:
            return {'eligible': True, 'issues': [], 'current_count': 0}
        
        applications = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.scholarship_type_id == scholarship_type.id,
            Application.status.notin_([
                Config.APPLICATION_STATUS['REJECTED'],
                Config.APPLICATION_STATUS['CANCELLED']
            ])
        ).all()
        
        current_count = len(applications)
        
        if current_count >= max_count:
            eligible = False
            issues.append(f"该奖助金类型最多可申请{max_count}次，当前已申请{current_count}次")
        
        return {'eligible': eligible, 'issues': issues, 'current_count': current_count}
    
    def _check_previous_awards(self, student: Student, scholarship_type: ScholarshipType) -> Dict[str, Any]:
        issues = []
        eligible = True
        
        if not scholarship_type:
            return {'eligible': True, 'issues': [], 'previous_awards_count': 0}
        
        if scholarship_type.type != Config.SCHOLARSHIP_TYPES['GRANT']:
            return {'eligible': True, 'issues': [], 'previous_awards_count': 0}
        
        previous_awards = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.scholarship_type_id == scholarship_type.id,
            Application.status.in_([
                Config.APPLICATION_STATUS['DISBURSED'],
                Config.APPLICATION_STATUS['VERIFIED']
            ])
        ).all()
        
        return {
            'eligible': eligible,
            'issues': issues,
            'previous_awards_count': len(previous_awards)
        }
    
    def generate_eligibility_report(self, student_id: int, scholarship_type_id: int) -> Dict[str, Any]:
        log_service.info(f"生成资格报告: student_id={student_id}, scholarship_type_id={scholarship_type_id}")
        
        try:
            student = self.db.query(Student).options(
                joinedload(Student.department)
            ).filter(Student.id == student_id).first()
            
            if not student:
                return self._build_error_response(ErrorCode.STUDENT_NOT_FOUND.value)
            
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            
            if not scholarship_type:
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            eligibility_result = self.check_eligibility(student_id, scholarship_type_id)
            
            grades = self.db.query(Grade).filter(Grade.student_id == student_id).all()
            gpa_info = self._check_gpa_requirement(student, scholarship_type)
            
            applications = self.db.query(Application).filter(
                Application.student_id == student_id,
                Application.scholarship_type_id == scholarship_type_id
            ).all()
            
            report = {
                'student_info': {
                    'id': student.id,
                    'student_id': student.student_id,
                    'name': student.name,
                    'department': student.department.name if student.department else None,
                    'department_id': student.department_id,
                    'major': student.major,
                    'grade': student.grade,
                    'class_name': student.class_name,
                    'status': student.status
                },
                'scholarship_info': {
                    'id': scholarship_type.id,
                    'name': scholarship_type.name,
                    'code': scholarship_type.code,
                    'type': scholarship_type.type,
                    'description': scholarship_type.description,
                    'amount': scholarship_type.amount,
                    'min_gpa': scholarship_type.min_gpa,
                    'max_application_count': scholarship_type.max_application_count,
                    'application_period': {
                        'start': scholarship_type.application_start_date,
                        'end': scholarship_type.application_end_date
                    },
                    'review_period': {
                        'start': scholarship_type.review_start_date,
                        'end': scholarship_type.review_end_date
                    },
                    'disbursement_date': scholarship_type.disbursement_date
                },
                'eligibility_check': eligibility_result.get('data', {}),
                'academic_performance': {
                    'gpa': gpa_info.get('gpa'),
                    'min_gpa_required': scholarship_type.min_gpa,
                    'total_grades': len(grades),
                    'total_credits': sum(g.credit for g in grades) if grades else 0,
                    'grades': [
                        {
                            'id': g.id,
                            'semester': g.semester,
                            'course_name': g.course_name,
                            'credit': g.credit,
                            'score': g.score
                        } for g in grades
                    ]
                },
                'application_history': [
                    {
                        'id': app.id,
                        'application_date': app.application_date,
                        'status': app.status,
                        'reason': app.reason
                    } for app in applications
                ],
                'report_generated_at': datetime.utcnow()
            }
            
            return self._build_response(
                success=True,
                data=report
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("生成资格报告", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def get_eligibility_statistics(self, scholarship_type_id: int, 
                                     department_id: Optional[int] = None) -> Dict[str, Any]:
        log_service.info(f"获取资格统计: scholarship_type_id={scholarship_type_id}")
        
        try:
            scholarship_type = self.db.query(ScholarshipType).filter(
                ScholarshipType.id == scholarship_type_id
            ).first()
            
            if not scholarship_type:
                return self._build_error_response(ErrorCode.SCHOLARSHIP_NOT_FOUND.value)
            
            query = self.db.query(Application).options(
                joinedload(Application.student)
            ).filter(Application.scholarship_type_id == scholarship_type_id)
            
            if department_id:
                query = query.join(Student).filter(Student.department_id == department_id)
            
            applications = query.all()
            
            total_applications = len(applications)
            
            approved = sum(1 for app in applications if app.status in [
                Config.APPLICATION_STATUS['APPROVED'],
                Config.APPLICATION_STATUS['PUBLIC_NOTICE'],
                Config.APPLICATION_STATUS['DISBURSED'],
                Config.APPLICATION_STATUS['VERIFIED']
            ])
            
            rejected = sum(1 for app in applications if app.status == Config.APPLICATION_STATUS['REJECTED'])
            pending = total_applications - approved - rejected
            
            eligible_students = 0
            ineligible_students = 0
            
            for app in applications:
                result = self.check_eligibility(app.student_id, scholarship_type_id)
                result_data = result.get('data', {})
                if result_data.get('eligible', False):
                    eligible_students += 1
                else:
                    ineligible_students += 1
            
            statistics = {
                'scholarship_type': {
                    'id': scholarship_type.id,
                    'name': scholarship_type.name,
                    'code': scholarship_type.code,
                    'type': scholarship_type.type
                },
                'department_id': department_id,
                'total_applications': total_applications,
                'approved': approved,
                'rejected': rejected,
                'pending': pending,
                'eligible_students': eligible_students,
                'ineligible_students': ineligible_students,
                'approval_rate': round(approved / total_applications * 100, 2) if total_applications > 0 else 0,
                'eligibility_rate': round(eligible_students / total_applications * 100, 2) if total_applications > 0 else 0
            }
            
            return self._build_response(
                success=True,
                data=statistics
            )
            
        except SQLAlchemyError as e:
            log_service.log_error("获取资格统计", e)
            return self._build_error_response(ErrorCode.SYSTEM_ERROR.value, str(e))
    
    def batch_check_eligibility(self, student_ids: List[int], 
                                  scholarship_type_id: int) -> Dict[str, Any]:
        log_service.info(f"批量检查资格: 学生数量={len(student_ids)}, scholarship_type_id={scholarship_type_id}")
        
        results = []
        for student_id in student_ids:
            result = self.check_eligibility(student_id, scholarship_type_id)
            results.append({
                'student_id': student_id,
                'result': result
            })
        
        eligible_count = sum(1 for r in results if r['result'].get('data', {}).get('eligible', False))
        ineligible_count = len(results) - eligible_count
        
        return self._build_response(
            success=True,
            data={
                'total': len(results),
                'eligible_count': eligible_count,
                'ineligible_count': ineligible_count,
                'results': results
            }
        )
