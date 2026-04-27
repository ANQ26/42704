from datetime import datetime, date
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from models import (
    Department, Student, ScholarshipType, Application, ApprovalRecord, 
    Disbursement, DepartmentQuota, User, Notification, Grade, StudentStatus
)
from database import get_db_session, init_db
from services import (
    ApplicationService, ApprovalService, DisbursementService,
    QuotaService, ValidationService, ScholarshipTypeService, NotificationService
)

def create_sample_departments(db: Session) -> List[Department]:
    departments = [
        Department(name="计算机科学与技术学院", code="CS"),
        Department(name="电子信息工程学院", code="EE"),
        Department(name="经济管理学院", code="EM"),
        Department(name="外国语学院", code="FL")
    ]
    
    for dept in departments:
        existing = db.query(Department).filter(Department.code == dept.code).first()
        if not existing:
            db.add(dept)
    
    db.commit()
    return db.query(Department).all()

def create_sample_users(db: Session, departments: List[Department]) -> List[User]:
    users = [
        User(
            username="admin",
            password="admin123",
            name="系统管理员",
            role="admin",
            department_id=None
        ),
        User(
            username="cs_admin",
            password="cs123",
            name="计算机学院管理员",
            role="department_admin",
            department_id=departments[0].id
        ),
        User(
            username="school_admin",
            password="school123",
            name="学校管理员",
            role="school_admin",
            department_id=None
        ),
        User(
            username="financial_admin",
            password="financial123",
            name="财务管理员",
            role="financial_admin",
            department_id=None
        )
    ]
    
    for user in users:
        existing = db.query(User).filter(User.username == user.username).first()
        if not existing:
            db.add(user)
    
    db.commit()
    return db.query(User).all()

def create_sample_students(db: Session, departments: List[Department]) -> List[Student]:
    students = [
        Student(
            student_id="2021001",
            name="张三",
            gender="男",
            birthdate=date(2000, 1, 15),
            department_id=departments[0].id,
            major="计算机科学与技术",
            grade="2021级",
            class_name="计科2101班",
            status="active"
        ),
        Student(
            student_id="2021002",
            name="李四",
            gender="女",
            birthdate=date(2000, 3, 20),
            department_id=departments[0].id,
            major="软件工程",
            grade="2021级",
            class_name="软工2101班",
            status="active"
        ),
        Student(
            student_id="2021003",
            name="王五",
            gender="男",
            birthdate=date(2000, 5, 10),
            department_id=departments[1].id,
            major="电子信息工程",
            grade="2021级",
            class_name="电信2101班",
            status="active"
        ),
        Student(
            student_id="2021004",
            name="赵六",
            gender="女",
            birthdate=date(2000, 7, 25),
            department_id=departments[2].id,
            major="经济学",
            grade="2021级",
            class_name="经济2101班",
            status="active"
        )
    ]
    
    for student in students:
        existing = db.query(Student).filter(Student.student_id == student.student_id).first()
        if not existing:
            db.add(student)
    
    db.commit()
    return db.query(Student).all()

def create_sample_scholarship_types(db: Session) -> List[ScholarshipType]:
    today = datetime.now().date()
    
    scholarship_types = [
        ScholarshipType(
            name="国家奖学金",
            code="NATIONAL_SCHOLARSHIP",
            type="scholarship",
            description="用于奖励特别优秀的全日制普通本科学生",
            application_start_date=date(today.year, 9, 1),
            application_end_date=date(today.year, 9, 30),
            review_start_date=date(today.year, 10, 1),
            review_end_date=date(today.year, 10, 15),
            disbursement_date=date(today.year, 11, 1),
            amount=8000.0,
            min_gpa=3.8,
            max_application_count=1
        ),
        ScholarshipType(
            name="国家励志奖学金",
            code="NATIONAL_ENCOURAGEMENT",
            type="scholarship",
            description="用于奖励资助品学兼优的家庭经济困难全日制普通本科学生",
            application_start_date=date(today.year, 9, 1),
            application_end_date=date(today.year, 9, 30),
            review_start_date=date(today.year, 10, 1),
            review_end_date=date(today.year, 10, 15),
            disbursement_date=date(today.year, 11, 1),
            amount=5000.0,
            min_gpa=3.0,
            max_application_count=1
        ),
        ScholarshipType(
            name="国家助学金",
            code="NATIONAL_GRANT",
            type="grant",
            description="用于资助家庭经济困难的全日制普通本科学生",
            application_start_date=date(today.year, 9, 1),
            application_end_date=date(today.year, 9, 30),
            review_start_date=date(today.year, 10, 1),
            review_end_date=date(today.year, 10, 15),
            disbursement_date=date(today.year, 11, 1),
            amount=3000.0,
            min_gpa=None,
            max_application_count=1
        ),
        ScholarshipType(
            name="校级一等奖学金",
            code="SCHOOL_FIRST_CLASS",
            type="scholarship",
            description="学校设立的一等奖学金",
            application_start_date=date(today.year, 9, 15),
            application_end_date=date(today.year, 10, 15),
            review_start_date=date(today.year, 10, 16),
            review_end_date=date(today.year, 10, 31),
            disbursement_date=date(today.year, 11, 15),
            amount=2000.0,
            min_gpa=3.5,
            max_application_count=1
        )
    ]
    
    for st in scholarship_types:
        existing = db.query(ScholarshipType).filter(ScholarshipType.code == st.code).first()
        if not existing:
            db.add(st)
    
    db.commit()
    return db.query(ScholarshipType).all()

def create_sample_department_quotas(db: Session, departments: List[Department], 
                                      scholarship_types: List[ScholarshipType]) -> List[DepartmentQuota]:
    current_year = datetime.now().year
    quotas = []
    
    for dept in departments:
        for st in scholarship_types:
            quota = DepartmentQuota(
                department_id=dept.id,
                scholarship_type_id=st.id,
                year=current_year,
                quota=5 if dept.code == "CS" else 3,
                budget=st.amount * (5 if dept.code == "CS" else 3),
                used_quota=0,
                used_budget=0.0
            )
            quotas.append(quota)
    
    for quota in quotas:
        existing = db.query(DepartmentQuota).filter(
            DepartmentQuota.department_id == quota.department_id,
            DepartmentQuota.scholarship_type_id == quota.scholarship_type_id,
            DepartmentQuota.year == quota.year
        ).first()
        if not existing:
            db.add(quota)
    
    db.commit()
    return db.query(DepartmentQuota).all()

def create_sample_grades(db: Session, students: List[Student]) -> List[Grade]:
    courses = [
        {"name": "高等数学", "credit": 4.0},
        {"name": "大学英语", "credit": 3.0},
        {"name": "程序设计基础", "credit": 3.0},
        {"name": "数据结构", "credit": 4.0},
        {"name": "计算机组成原理", "credit": 3.0}
    ]
    
    grades = []
    for student in students[:2]:
        for i, course in enumerate(courses):
            score = 90 - i * 2 if student.name == "张三" else 85 - i * 2
            grade = Grade(
                student_id=student.id,
                semester="2023-2024学年第一学期",
                course_name=course["name"],
                credit=course["credit"],
                score=score
            )
            grades.append(grade)
    
    for grade in grades:
        db.add(grade)
    
    db.commit()
    return grades

def create_sample_student_statuses(db: Session, students: List[Student]) -> List[StudentStatus]:
    statuses = []
    for student in students:
        status = StudentStatus(
            student_id=student.id,
            status="active",
            effective_date=date(2021, 9, 1),
            expiry_date=None
        )
        statuses.append(status)
        db.add(status)
    
    db.commit()
    return statuses

def populate_sample_data() -> Dict[str, Any]:
    init_db()
    
    with get_db_session() as db:
        departments = create_sample_departments(db)
        users = create_sample_users(db, departments)
        students = create_sample_students(db, departments)
        scholarship_types = create_sample_scholarship_types(db)
        quotas = create_sample_department_quotas(db, departments, scholarship_types)
        grades = create_sample_grades(db, students)
        student_statuses = create_sample_student_statuses(db, students)
        
        return {
            "departments": departments,
            "users": users,
            "students": students,
            "scholarship_types": scholarship_types,
            "quotas": quotas,
            "grades": grades,
            "student_statuses": student_statuses
        }

if __name__ == "__main__":
    print("正在填充示例数据...")
    data = populate_sample_data()
    print(f"示例数据填充完成！")
    print(f"- 院系: {len(data['departments'])} 个")
    print(f"- 用户: {len(data['users'])} 个")
    print(f"- 学生: {len(data['students'])} 个")
    print(f"- 奖学金类型: {len(data['scholarship_types'])} 个")
    print(f"- 院系额度: {len(data['quotas'])} 个")
    print(f"- 成绩记录: {len(data['grades'])} 条")
    print(f"- 学生状态: {len(data['student_statuses'])} 条")
