from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Student, ScholarshipType, Application, Grade, StudentStatus
from config import Config
from services.notification_service import NotificationService


class EligibilityService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.notification_service = NotificationService(db_session)
    
    def check_eligibility(self, student_id: int, scholarship_type_id: int) -> Dict:
        issues = []
        eligible = True
        
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {"eligible": False, "issues": ["学生不存在"]}
        
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        if not scholarship_type:
            return {"eligible": False, "issues": ["奖助金类型不存在"]}
        
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
        
        return {
            "eligible": eligible,
            "issues": issues,
            "student_name": student.name,
            "scholarship_name": scholarship_type.name
        }
    
    def _check_student_status(self, student: Student) -> Dict:
        issues = []
        eligible = True
        
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
        
        return {"eligible": eligible, "issues": issues}
    
    def _check_gpa_requirement(self, student: Student, scholarship_type: ScholarshipType) -> Dict:
        issues = []
        eligible = True
        
        min_gpa = scholarship_type.min_gpa
        if min_gpa is None or min_gpa <= 0:
            return {"eligible": True, "issues": []}
        
        grades = self.db.query(Grade).filter(Grade.student_id == student.id).all()
        
        if not grades:
            eligible = False
            issues.append("没有成绩记录")
            return {"eligible": eligible, "issues": issues}
        
        total_credits = sum(grade.credit for grade in grades)
        if total_credits == 0:
            eligible = False
            issues.append("总学分为0，无法计算GPA")
            return {"eligible": eligible, "issues": issues}
        
        weighted_sum = sum(grade.score * grade.credit for grade in grades)
        gpa = weighted_sum / total_credits
        
        if gpa < min_gpa:
            eligible = False
            issues.append(f"GPA要求为{min_gpa}，当前GPA为{round(gpa, 2)}，不满足要求")
        
        return {"eligible": eligible, "issues": issues, "gpa": round(gpa, 2)}
    
    def _check_application_count(self, student: Student, scholarship_type: ScholarshipType) -> Dict:
        issues = []
        eligible = True
        
        max_count = scholarship_type.max_application_count
        if max_count is None or max_count <= 0:
            return {"eligible": True, "issues": []}
        
        current_year = datetime.utcnow().year
        
        applications = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.scholarship_type_id == scholarship_type.id,
            Application.status.notin_([
                Config.APPLICATION_STATUS['REJECTED'],
                Config.APPLICATION_STATUS['CANCELLED']
            ])
        ).all()
        
        if len(applications) >= max_count:
            eligible = False
            issues.append(f"该奖助金类型最多可申请{max_count}次，当前已申请{len(applications)}次")
        
        return {"eligible": eligible, "issues": issues, "current_count": len(applications)}
    
    def _check_previous_awards(self, student: Student, scholarship_type: ScholarshipType) -> Dict:
        issues = []
        eligible = True
        
        if scholarship_type.type != Config.SCHOLARSHIP_TYPES['GRANT']:
            return {"eligible": True, "issues": []}
        
        current_year = datetime.utcnow().year
        
        previous_awards = self.db.query(Application).filter(
            Application.student_id == student.id,
            Application.scholarship_type_id == scholarship_type.id,
            Application.status.in_([
                Config.APPLICATION_STATUS['DISBURSED'],
                Config.APPLICATION_STATUS['VERIFIED']
            ])
        ).all()
        
        return {"eligible": eligible, "issues": issues, "previous_awards_count": len(previous_awards)}
    
    def generate_eligibility_report(self, student_id: int, scholarship_type_id: int) -> Dict:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {"error": "学生不存在"}
        
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        if not scholarship_type:
            return {"error": "奖助金类型不存在"}
        
        eligibility_result = self.check_eligibility(student_id, scholarship_type_id)
        
        grades = self.db.query(Grade).filter(Grade.student_id == student_id).all()
        gpa_info = self._check_gpa_requirement(student, scholarship_type)
        
        applications = self.db.query(Application).filter(
            Application.student_id == student_id,
            Application.scholarship_type_id == scholarship_type_id
        ).all()
        
        report = {
            "student_info": {
                "id": student.id,
                "student_id": student.student_id,
                "name": student.name,
                "department": student.department.name if student.department else None,
                "major": student.major,
                "grade": student.grade,
                "status": student.status
            },
            "scholarship_info": {
                "id": scholarship_type.id,
                "name": scholarship_type.name,
                "type": scholarship_type.type,
                "amount": scholarship_type.amount,
                "min_gpa": scholarship_type.min_gpa,
                "application_period": {
                    "start": scholarship_type.application_start_date,
                    "end": scholarship_type.application_end_date
                }
            },
            "eligibility_check": eligibility_result,
            "academic_performance": {
                "gpa": gpa_info.get('gpa'),
                "total_grades": len(grades),
                "grades": [
                    {
                        "semester": g.semester,
                        "course_name": g.course_name,
                        "credit": g.credit,
                        "score": g.score
                    } for g in grades
                ]
            },
            "application_history": [
                {
                    "id": app.id,
                    "application_date": app.application_date,
                    "status": app.status,
                    "reason": app.reason
                } for app in applications
            ],
            "report_generated_at": datetime.utcnow()
        }
        
        return report
    
    def get_eligibility_statistics(self, scholarship_type_id: int) -> Dict:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()
        if not scholarship_type:
            return {"error": "奖助金类型不存在"}
        
        applications = self.db.query(Application).filter(
            Application.scholarship_type_id == scholarship_type_id
        ).all()
        
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
            if result['eligible']:
                eligible_students += 1
            else:
                ineligible_students += 1
        
        return {
            "scholarship_type": scholarship_type.name,
            "statistics": {
                "total_applications": total_applications,
                "approved": approved,
                "rejected": rejected,
                "pending": pending,
                "eligible_students": eligible_students,
                "ineligible_students": ineligible_students,
                "approval_rate": round(approved / total_applications * 100, 2) if total_applications > 0 else 0,
                "eligibility_rate": round(eligible_students / total_applications * 100, 2) if total_applications > 0 else 0
            }
        }
