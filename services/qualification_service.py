from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from models import Student, Application, Grade, StudentStatus, ScholarshipType, Disbursement

class QualificationService:
    def __init__(self, db: Session):
        self.db = db

    def check_student_eligibility(self, student_id: int, scholarship_type_id: int) -> dict:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {'eligible': False, 'reason': '学生不存在'}

        scholarship_type = self.db.query(ScholarshipType).filter(ScholarshipType.id == scholarship_type_id).first()
        if not scholarship_type:
            return {'eligible': False, 'reason': '奖助学金类型不存在'}

        reasons = []
        eligible = True

        if student.status != 'active':
            reasons.append(f'学生状态异常: {student.status}')
            eligible = False

        current_status = self.db.query(StudentStatus).filter(
            StudentStatus.student_id == student_id
        ).order_by(StudentStatus.effective_date.desc()).first()

        if current_status and current_status.status != 'active':
            reasons.append(f'学籍状态: {current_status.status}')
            eligible = False

        if scholarship_type.min_gpa:
            grades = self.db.query(Grade).filter(Grade.student_id == student_id).all()
            if grades:
                total_score = sum(g.score * g.credit for g in grades)
                total_credit = sum(g.credit for g in grades)
                gpa = total_score / total_credit if total_credit > 0 else 0
                if gpa < scholarship_type.min_gpa:
                    reasons.append(f'GPA不满足要求: {gpa:.2f} < {scholarship_type.min_gpa}')
                    eligible = False

        existing_application = self.db.query(Application).filter(
            Application.student_id == student_id,
            Application.scholarship_type_id == scholarship_type_id,
            Application.status.in_(['submitted', 'reviewed', 'approved', '公示中', '已发放'])
        ).first()
        if existing_application:
            reasons.append('已有正在处理中的申请')
            eligible = False

        if scholarship_type.max_application_count:
            past_count = self.db.query(Application).filter(
                Application.student_id == student_id,
                Application.scholarship_type_id == scholarship_type_id
            ).count()
            if past_count >= scholarship_type.max_application_count:
                reasons.append(f'已超过最大申请次数: {past_count}/{scholarship_type.max_application_count}')
                eligible = False

        return {
            'eligible': eligible,
            'reasons': reasons,
            'student_id': student_id,
            'student_name': student.name,
            'scholarship_type': scholarship_type.name
        }

    def generate_qualification_report(self, scholarship_type_id: int = None, department_id: int = None) -> dict:
        query = self.db.query(Student)

        if department_id:
            query = query.filter(Student.department_id == department_id)

        students = query.all()

        results = []
        for student in students:
            if scholarship_type_id:
                eligibility = self.check_student_eligibility(student.id, scholarship_type_id)
                results.append(eligibility)
            else:
                scholarship_types = self.db.query(ScholarshipType).all()
                for st in scholarship_types:
                    eligibility = self.check_student_eligibility(student.id, st.id)
                    results.append(eligibility)

        eligible_count = sum(1 for r in results if r['eligible'])
        ineligible_count = len(results) - eligible_count

        return {
            'total_students': len(students),
            'evaluated_applications': len(results),
            'eligible_count': eligible_count,
            'ineligible_count': ineligible_count,
            'eligibility_rate': eligible_count / len(results) if results else 0,
            'details': results
        }

    def generate_disbursement_report(self, year: int = None, department_id: int = None, scholarship_type_id: int = None) -> dict:
        if year is None:
            year = datetime.now().year

        query = self.db.query(Disbursement).join(Application)

        if year:
            query = query.filter(func.strftime('%Y', Disbursement.disbursement_date) == str(year))
        if department_id:
            query = query.filter(Application.student_id.in_(
                self.db.query(Student.id).filter(Student.department_id == department_id)
            ))
        if scholarship_type_id:
            query = query.filter(Application.scholarship_type_id == scholarship_type_id)

        disbursements = query.all()

        total_amount = sum(d.amount for d in disbursements)
        by_status = {}
        for d in disbursements:
            status = d.status
            by_status[status] = by_status.get(status, 0) + 1

        return {
            'year': year,
            'total_disbursements': len(disbursements),
            'total_amount': total_amount,
            'average_amount': total_amount / len(disbursements) if disbursements else 0,
            'by_status': by_status
        }

    def get_student_assistance_history(self, student_id: int) -> dict:
        applications = self.db.query(Application).filter(
            Application.student_id == student_id
        ).order_by(Application.application_date.desc()).all()

        total_received = 0
        history = []
        for app in applications:
            if app.status == '已核销' and app.disbursement:
                total_received += app.disbursement.amount
            history.append({
                'year': app.application_date.year,
                'scholarship_name': app.scholarship_type.name,
                'scholarship_type': app.scholarship_type.type,
                'amount': app.disbursement.amount if app.disbursement else 0,
                'status': app.status,
                'application_date': app.application_date
            })

        return {
            'student_id': student_id,
            'student_name': self.db.query(Student).filter(Student.id == student_id).first().name,
            'total_received': total_received,
            'total_applications': len(applications),
            'history': history
        }

    def validate_student_data(self, student_id: int) -> dict:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {'valid': False, 'errors': ['学生不存在']}

        errors = []
        warnings = []

        if not student.name or len(student.name) < 2:
            errors.append('姓名无效')

        if not student.student_id or len(student.student_id) < 6:
            errors.append('学号无效')

        if not student.department_id:
            errors.append('未分配院系')

        if student.birthdate:
            age = (date.today() - student.birthdate).days / 365
            if age < 16 or age > 40:
                warnings.append(f'年龄异常: {int(age)}岁')

        grades = self.db.query(Grade).filter(Grade.student_id == student_id).count()
        if grades == 0:
            warnings.append('无成绩记录')

        current_status = self.db.query(StudentStatus).filter(
            StudentStatus.student_id == student_id
        ).order_by(StudentStatus.effective_date.desc()).first()

        if not current_status:
            warnings.append('无学籍状态记录')
        elif current_status.status not in ['active', 'graduated']:
            errors.append(f'学籍状态异常: {current_status.status}')

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'student_id': student_id
        }

    def get_grade_statistics(self, student_id: int) -> dict:
        grades = self.db.query(Grade).filter(Grade.student_id == student_id).all()

        if not grades:
            return {
                'has_grades': False,
                'student_id': student_id
            }

        total_credit = sum(g.credit for g in grades)
        weighted_sum = sum(g.score * g.credit for g in grades)
        gpa = weighted_sum / total_credit if total_credit > 0 else 0

        by_semester = {}
        for g in grades:
            if g.semester not in by_semester:
                by_semester[g.semester] = {'credits': 0, 'total_score': 0, 'courses': []}
            by_semester[g.semester]['credits'] += g.credit
            by_semester[g.semester]['total_score'] += g.score * g.credit
            by_semester[g.semester]['courses'].append({
                'course_name': g.course_name,
                'credit': g.credit,
                'score': g.score
            })

        semester_gpas = {}
        for semester, data in by_semester.items():
            semester_gpas[semester] = data['total_score'] / data['credits'] if data['credits'] > 0 else 0

        return {
            'has_grades': True,
            'student_id': student_id,
            'total_credits': total_credit,
            'overall_gpa': gpa,
            'semester_gpas': semester_gpas,
            'total_courses': len(grades)
        }