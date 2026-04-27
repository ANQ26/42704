from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from models import ScholarshipType, Student, Application, Grade

class PolicyService:
    def __init__(self, db: Session):
        self.db = db

    def create_scholarship_type(self, data: dict) -> dict:
        existing = self.db.query(ScholarshipType).filter(
            or_(
                ScholarshipType.code == data.get('code'),
                ScholarshipType.name == data.get('name')
            )
        ).first()

        if existing:
            return {'success': False, 'error': '奖助金类型代码或名称已存在'}

        scholarship_type = ScholarshipType(
            name=data['name'],
            code=data['code'],
            type=data.get('type', 'scholarship'),
            description=data.get('description'),
            application_start_date=data.get('application_start_date'),
            application_end_date=data.get('application_end_date'),
            review_start_date=data.get('review_start_date'),
            review_end_date=data.get('review_end_date'),
            disbursement_date=data.get('disbursement_date'),
            amount=data.get('amount', 0),
            min_gpa=data.get('min_gpa'),
            max_application_count=data.get('max_application_count')
        )

        self.db.add(scholarship_type)
        self.db.commit()

        return {'success': True, 'id': scholarship_type.id}

    def update_scholarship_type(self, scholarship_type_id: int, data: dict) -> dict:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()

        if not scholarship_type:
            return {'success': False, 'error': '奖助金类型不存在'}

        if 'name' in data:
            scholarship_type.name = data['name']
        if 'code' in data:
            scholarship_type.code = data['code']
        if 'type' in data:
            scholarship_type.type = data['type']
        if 'description' in data:
            scholarship_type.description = data['description']
        if 'application_start_date' in data:
            scholarship_type.application_start_date = data['application_start_date']
        if 'application_end_date' in data:
            scholarship_type.application_end_date = data['application_end_date']
        if 'review_start_date' in data:
            scholarship_type.review_start_date = data['review_start_date']
        if 'review_end_date' in data:
            scholarship_type.review_end_date = data['review_end_date']
        if 'disbursement_date' in data:
            scholarship_type.disbursement_date = data['disbursement_date']
        if 'amount' in data:
            scholarship_type.amount = data['amount']
        if 'min_gpa' in data:
            scholarship_type.min_gpa = data['min_gpa']
        if 'max_application_count' in data:
            scholarship_type.max_application_count = data['max_application_count']

        scholarship_type.updated_at = datetime.utcnow()
        self.db.commit()

        return {'success': True}

    def configure_policy_rules(self, scholarship_type_id: int, rules: dict) -> dict:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()

        if not scholarship_type:
            return {'success': False, 'error': '奖助金类型不存在'}

        if 'min_gpa' in rules:
            scholarship_type.min_gpa = rules['min_gpa']
        if 'max_application_count' in rules:
            scholarship_type.max_application_count = rules['max_application_count']
        if 'application_period' in rules:
            start, end = rules['application_period'].split(',')
            scholarship_type.application_start_date = datetime.strptime(start.strip(), '%Y-%m-%d').date()
            scholarship_type.application_end_date = datetime.strptime(end.strip(), '%Y-%m-%d').date()
        if 'review_period' in rules:
            start, end = rules['review_period'].split(',')
            scholarship_type.review_start_date = datetime.strptime(start.strip(), '%Y-%m-%d').date()
            scholarship_type.review_end_date = datetime.strptime(end.strip(), '%Y-%m-%d').date()
        if 'disbursement_date' in rules:
            scholarship_type.disbursement_date = datetime.strptime(rules['disbursement_date'], '%Y-%m-%d').date()
        if 'amount' in rules:
            scholarship_type.amount = rules['amount']

        scholarship_type.updated_at = datetime.utcnow()
        self.db.commit()

        return {'success': True}

    def get_policy_summary(self, scholarship_type_id: int) -> dict:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()

        if not scholarship_type:
            return None

        today = date.today()
        application_open = False
        if scholarship_type.application_start_date and scholarship_type.application_end_date:
            application_open = scholarship_type.application_start_date <= today <= scholarship_type.application_end_date

        review_open = False
        if scholarship_type.review_start_date and scholarship_type.review_end_date:
            review_open = scholarship_type.review_start_date <= today <= scholarship_type.review_end_date

        return {
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
                'end': scholarship_type.application_end_date,
                'open': application_open
            },
            'review_period': {
                'start': scholarship_type.review_start_date,
                'end': scholarship_type.review_end_date,
                'open': review_open
            },
            'disbursement_date': scholarship_type.disbursement_date
        }

    def match_student_to_scholarships(self, student_id: int) -> list:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return []

        all_types = self.db.query(ScholarshipType).all()
        today = date.today()

        matched = []
        for st in all_types:
            if st.application_start_date and st.application_end_date:
                if not (st.application_start_date <= today <= st.application_end_date):
                    continue

            if st.min_gpa:
                grades = self.db.query(Grade).filter(Grade.student_id == student_id).all()
                if grades:
                    total_score = sum(g.score * g.credit for g in grades)
                    total_credit = sum(g.credit for g in grades)
                    gpa = total_score / total_credit if total_credit > 0 else 0
                    if gpa < st.min_gpa:
                        continue

            existing = self.db.query(Application).filter(
                Application.student_id == student_id,
                Application.scholarship_type_id == st.id,
                Application.status.in_(['submitted', 'reviewed', 'approved', '公示中', '已发放'])
            ).first()
            if existing:
                continue

            matched.append({
                'id': st.id,
                'name': st.name,
                'type': st.type,
                'amount': st.amount,
                'min_gpa': st.min_gpa
            })

        return matched

    def auto_apply_policy(self, scholarship_type_id: int, student_ids: list = None) -> dict:
        scholarship_type = self.db.query(ScholarshipType).filter(
            ScholarshipType.id == scholarship_type_id
        ).first()

        if not scholarship_type:
            return {'success': False, 'error': '奖助金类型不存在'}

        query = self.db.query(Student).filter(Student.status == 'active')
        if student_ids:
            query = query.filter(Student.id.in_(student_ids))

        students = query.all()

        applied_count = 0
        skipped_count = 0
        results = []

        for student in students:
            if scholarship_type.min_gpa:
                grades = self.db.query(Grade).filter(Grade.student_id == student.id).all()
                if grades:
                    total_score = sum(g.score * g.credit for g in grades)
                    total_credit = sum(g.credit for g in grades)
                    gpa = total_score / total_credit if total_credit > 0 else 0
                    if gpa < scholarship_type.min_gpa:
                        skipped_count += 1
                        results.append({
                            'student_id': student.id,
                            'student_name': student.name,
                            'status': 'skipped',
                            'reason': f'GPA不满足: {gpa:.2f} < {scholarship_type.min_gpa}'
                        })
                        continue

            existing = self.db.query(Application).filter(
                Application.student_id == student.id,
                Application.scholarship_type_id == scholarship_type_id
            ).first()

            if existing:
                skipped_count += 1
                results.append({
                    'student_id': student.id,
                    'student_name': student.name,
                    'status': 'skipped',
                    'reason': '已存在申请'
                })
                continue

            application = Application(
                student_id=student.id,
                scholarship_type_id=scholarship_type_id,
                application_date=datetime.utcnow(),
                status='submitted',
                reason='系统自动匹配推荐'
            )
            self.db.add(application)
            applied_count += 1
            results.append({
                'student_id': student.id,
                'student_name': student.name,
                'status': 'applied'
            })

        self.db.commit()

        return {
            'success': True,
            'applied_count': applied_count,
            'skipped_count': skipped_count,
            'details': results
        }

    def get_active_scholarship_types(self, type_filter: str = None) -> list:
        query = self.db.query(ScholarshipType)
        if type_filter:
            query = query.filter(ScholarshipType.type == type_filter)
        return query.all()