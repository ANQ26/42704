#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, date
from database import init_db, get_session, Session
from models import Department, Student, ScholarshipType, User, Grade, StudentStatus
from services import (
    get_application_service,
    get_quota_service,
    get_eligibility_service,
    get_policy_service,
    get_notification_service
)
from config import Config
from utils.helpers import Helpers
import sys


def initialize_database():
    print("正在初始化数据库...")
    init_db()
    print("数据库初始化完成！")


def create_sample_data():
    print("正在创建示例数据...")
    
    with get_session() as session:
        print("1. 创建院系数据...")
        departments = [
            Department(name="计算机科学与技术学院", code="CS"),
            Department(name="电子工程学院", code="EE"),
            Department(name="经济管理学院", code="EM"),
            Department(name="外国语学院", code="FL")
        ]
        for dept in departments:
            session.add(dept)
        session.flush()
        
        cs_dept = departments[0]
        ee_dept = departments[1]
        
        print("2. 创建用户(管理员)数据...")
        admins = [
            User(
                username="admin",
                password=Helpers.hash_password("admin123"),
                name="系统管理员",
                role=Config.USER_ROLES['ADMIN']
            ),
            User(
                username="cs_admin",
                password=Helpers.hash_password("cs123"),
                name="计算机学院管理员",
                role=Config.USER_ROLES['DEPARTMENT_ADMIN'],
                department_id=cs_dept.id
            ),
            User(
                username="financial",
                password=Helpers.hash_password("fin123"),
                name="财务管理员",
                role=Config.USER_ROLES['FINANCIAL_ADMIN']
            )
        ]
        for admin in admins:
            session.add(admin)
        
        print("3. 创建学生数据...")
        students = [
            Student(
                student_id="2024001",
                name="张三",
                gender="男",
                birthdate=date(2002, 5, 15),
                department_id=cs_dept.id,
                major="计算机科学与技术",
                grade="2024级",
                class_name="计科2401班",
                status=Config.STUDENT_STATUS['ACTIVE']
            ),
            Student(
                student_id="2024002",
                name="李四",
                gender="女",
                birthdate=date(2002, 8, 20),
                department_id=cs_dept.id,
                major="软件工程",
                grade="2024级",
                class_name="软工2401班",
                status=Config.STUDENT_STATUS['ACTIVE']
            ),
            Student(
                student_id="2024003",
                name="王五",
                gender="男",
                birthdate=date(2002, 3, 10),
                department_id=ee_dept.id,
                major="电子信息工程",
                grade="2024级",
                class_name="电信2401班",
                status=Config.STUDENT_STATUS['ACTIVE']
            )
        ]
        for student in students:
            session.add(student)
        session.flush()
        
        print("4. 创建学生学籍状态...")
        for student in students:
            status = StudentStatus(
                student_id=student.id,
                status=Config.STUDENT_STATUS['ACTIVE'],
                effective_date=date(2024, 9, 1)
            )
            session.add(status)
        
        print("5. 创建学生成绩数据...")
        grades_data = [
            {"semester": "2024-2025-1", "course_name": "高等数学", "credit": 4.0, "score": 88},
            {"semester": "2024-2025-1", "course_name": "大学英语", "credit": 3.0, "score": 85},
            {"semester": "2024-2025-1", "course_name": "程序设计基础", "credit": 3.0, "score": 92},
            {"semester": "2024-2025-1", "course_name": "线性代数", "credit": 3.0, "score": 78},
            {"semester": "2024-2025-1", "course_name": "大学物理", "credit": 4.0, "score": 82}
        ]
        
        for student in students:
            for grade_data in grades_data:
                grade = Grade(
                    student_id=student.id,
                    semester=grade_data["semester"],
                    course_name=grade_data["course_name"],
                    credit=grade_data["credit"],
                    score=grade_data["score"]
                )
                session.add(grade)
        
        print("6. 创建奖助金政策...")
        today = date.today()
        scholarship_types = [
            ScholarshipType(
                name="国家奖学金",
                code="NATIONAL_SCHOLARSHIP",
                type=Config.SCHOLARSHIP_TYPES['SCHOLARSHIP'],
                description="国家奖学金用于奖励特别优秀的全日制普通高校本专科（含高职、第二学士学位）在校生",
                amount=8000.0,
                min_gpa=3.5,
                max_application_count=1,
                application_start_date=today,
                application_end_date=date(today.year + 1, today.month, today.day),
                review_start_date=date(today.year + 1, today.month + 1, 1),
                review_end_date=date(today.year + 1, today.month + 1, 15),
                disbursement_date=date(today.year + 1, today.month + 2, 1)
            ),
            ScholarshipType(
                name="国家励志奖学金",
                code="NATIONAL_ENCOURAGE",
                type=Config.SCHOLARSHIP_TYPES['SCHOLARSHIP'],
                description="国家励志奖学金用于奖励资助品学兼优的家庭经济困难全日制普通高校本专科（含高职、第二学士学位）在校生",
                amount=5000.0,
                min_gpa=3.0,
                max_application_count=1,
                application_start_date=today,
                application_end_date=date(today.year + 1, today.month, today.day),
                review_start_date=date(today.year + 1, today.month + 1, 1),
                review_end_date=date(today.year + 1, today.month + 1, 15),
                disbursement_date=date(today.year + 1, today.month + 2, 1)
            ),
            ScholarshipType(
                name="国家助学金",
                code="NATIONAL_GRANT",
                type=Config.SCHOLARSHIP_TYPES['GRANT'],
                description="国家助学金用于资助家庭经济困难的全日制普通高校本专科（含高职、第二学士学位）在校生",
                amount=3000.0,
                min_gpa=2.0,
                max_application_count=2,
                application_start_date=today,
                application_end_date=date(today.year + 1, today.month, today.day),
                review_start_date=date(today.year + 1, today.month + 1, 1),
                review_end_date=date(today.year + 1, today.month + 1, 15),
                disbursement_date=date(today.year + 1, today.month + 2, 1)
            ),
            ScholarshipType(
                name="校级一等奖学金",
                code="SCHOOL_LEVEL_1",
                type=Config.SCHOLARSHIP_TYPES['SCHOLARSHIP'],
                description="校级一等奖学金用于奖励在校期间学习成绩优异的学生",
                amount=2000.0,
                min_gpa=3.8,
                max_application_count=1,
                application_start_date=today,
                application_end_date=date(today.year + 1, today.month, today.day),
                review_start_date=date(today.year + 1, today.month + 1, 1),
                review_end_date=date(today.year + 1, today.month + 1, 15),
                disbursement_date=date(today.year + 1, today.month + 2, 1)
            )
        ]
        for st in scholarship_types:
            session.add(st)
        session.flush()
        
        national_scholarship = scholarship_types[0]
        national_grant = scholarship_types[2]
        
        print("7. 创建院系额度配置...")
        from models import DepartmentQuota
        quotas = [
            DepartmentQuota(
                department_id=cs_dept.id,
                scholarship_type_id=national_scholarship.id,
                year=today.year,
                quota=10,
                budget=80000.0,
                used_quota=0,
                used_budget=0.0
            ),
            DepartmentQuota(
                department_id=cs_dept.id,
                scholarship_type_id=national_grant.id,
                year=today.year,
                quota=50,
                budget=150000.0,
                used_quota=0,
                used_budget=0.0
            ),
            DepartmentQuota(
                department_id=ee_dept.id,
                scholarship_type_id=national_scholarship.id,
                year=today.year,
                quota=8,
                budget=64000.0,
                used_quota=0,
                used_budget=0.0
            ),
            DepartmentQuota(
                department_id=ee_dept.id,
                scholarship_type_id=national_grant.id,
                year=today.year,
                quota=40,
                budget=120000.0,
                used_quota=0,
                used_budget=0.0
            )
        ]
        for quota in quotas:
            session.add(quota)
        
        print("示例数据创建完成！")
        print("\n" + "="*50)
        print("示例数据摘要:")
        print("="*50)
        print(f"院系数量: {len(departments)}")
        print(f"学生数量: {len(students)}")
        print(f"奖助金类型数量: {len(scholarship_types)}")
        print(f"管理员数量: {len(admins)}")
        print("\n登录信息:")
        print("  系统管理员: admin / admin123")
        print("  计算机学院管理员: cs_admin / cs123")
        print("  财务管理员: financial / fin123")
        print("="*50)


def demonstrate_workflow():
    print("\n" + "="*60)
    print("演示：奖助金申请全流程")
    print("="*60)
    
    with get_session() as session:
        app_service = get_application_service(session)
        quota_service = get_quota_service(session)
        eligibility_service = get_eligibility_service(session)
        policy_service = get_policy_service(session)
        notification_service = get_notification_service(session)
        
        print("\n[步骤1] 查看可用的奖助金政策...")
        active_policies = policy_service.get_active_policies()
        print(f"当前可用奖助金政策: {len(active_policies)} 个")
        for policy in active_policies:
            print(f"  - {policy['name']} (金额: {policy['amount']}元)")
        
        student = session.query(Student).filter(Student.student_id == "2024001").first()
        national_scholarship = session.query(ScholarshipType).filter(
            ScholarshipType.code == "NATIONAL_SCHOLARSHIP"
        ).first()
        
        if not student or not national_scholarship:
            print("错误：找不到示例数据，请先运行 --seed 参数")
            return
        
        print(f"\n[步骤2] 学生 {student.name} 申请 {national_scholarship.name}...")
        
        print("\n[步骤3] 资格校验...")
        eligibility_result = eligibility_service.check_eligibility(
            student.id, national_scholarship.id
        )
        print(f"  资格校验结果: {'通过' if eligibility_result['eligible'] else '不通过'}")
        if eligibility_result['issues']:
            for issue in eligibility_result['issues']:
                print(f"    - {issue}")
        
        print("\n[步骤4] 检查院系额度...")
        quota_check = quota_service.check_quota_availability(
            student.department_id, national_scholarship.id
        )
        print(f"  额度状态: {'可用' if quota_check['available'] else '不足'}")
        print(f"  总名额: {quota_check.get('quota', '未设置')}, 已使用: {quota_check['used_quota']}")
        print(f"  总预算: {quota_check.get('budget', '未设置')}元, 已使用: {quota_check['used_budget']}元")
        
        print("\n[步骤5] 提交申请...")
        submit_result = app_service.submit_application(
            student_id=student.id,
            scholarship_type_id=national_scholarship.id,
            reason="本人在校期间表现优异，学习成绩名列前茅，积极参与各项活动，特申请国家奖学金。",
            attachments=""
        )
        print(f"  申请结果: {'成功' if submit_result['success'] else '失败'}")
        if submit_result['success']:
            print(f"  申请ID: {submit_result['application_id']}")
        
        print("\n[步骤6] 查看待审核申请...")
        pending_approvals = app_service.get_pending_approvals(level=Config.APPROVAL_LEVELS['DEPARTMENT'])
        print(f"  待院系审核的申请: {len(pending_approvals)} 个")
        for app in pending_approvals:
            print(f"    - 申请ID: {app['application_id']}, 学生: {app['student_name']}, 奖助金: {app['scholarship_type']}")
        
        admin = session.query(User).filter(User.username == "cs_admin").first()
        if admin and submit_result['success']:
            print("\n[步骤7] 院系审核通过...")
            review_result = app_service.review_application(
                application_id=submit_result['application_id'],
                reviewer_id=admin.id,
                approval_status='approved',
                comments="同意推荐",
                level=Config.APPROVAL_LEVELS['DEPARTMENT']
            )
            print(f"  审核结果: {'成功' if review_result['success'] else '失败'}")
            if review_result['success']:
                print(f"  申请状态: {review_result['application_status']}")
        
        financial_admin = session.query(User).filter(User.username == "financial").first()
        if financial_admin and submit_result['success']:
            print("\n[步骤8] 学校审核通过...")
            review_result2 = app_service.review_application(
                application_id=submit_result['application_id'],
                reviewer_id=financial_admin.id,
                approval_status='approved',
                comments="同意",
                level=Config.APPROVAL_LEVELS['SCHOOL']
            )
            print(f"  审核结果: {'成功' if review_result2['success'] else '失败'}")
            
            print("\n[步骤9] 财务审核通过...")
            review_result3 = app_service.review_application(
                application_id=submit_result['application_id'],
                reviewer_id=financial_admin.id,
                approval_status='approved',
                comments="财务审核通过",
                level=Config.APPROVAL_LEVELS['FINANCIAL']
            )
            print(f"  审核结果: {'成功' if review_result3['success'] else '失败'}")
        
        if submit_result['success']:
            print("\n[步骤10] 开始公示...")
            notice_result = app_service.start_public_notice(submit_result['application_id'])
            print(f"  公示结果: {'成功' if notice_result['success'] else '失败'}")
            
            print("\n[步骤11] 发放资金...")
            disburse_result = app_service.disburse_application(
                application_id=submit_result['application_id'],
                bank_account="6222021234567890123",
                amount=national_scholarship.amount
            )
            print(f"  发放结果: {'成功' if disburse_result['success'] else '失败'}")
            if disburse_result['success']:
                print(f"  发放金额: {disburse_result['amount']}元")
            
            print("\n[步骤12] 资金核销...")
            if disburse_result['success']:
                verify_result = app_service.verify_disbursement(
                    disbursement_id=disburse_result['disbursement_id'],
                    verifier_id=financial_admin.id,
                    transaction_id="TXN202404270001"
                )
                print(f"  核销结果: {'成功' if verify_result['success'] else '失败'}")
        
        print("\n[步骤13] 查看学生通知...")
        notifications = notification_service.get_notifications_by_student(student.id)
        print(f"  收到的通知: {len(notifications)} 条")
        for notification in notifications[:5]:
            print(f"    - [{Helpers.format_datetime(notification['created_at'])}] {notification['title']}")
        
        print("\n" + "="*60)
        print("流程演示完成！")
        print("="*60)


def show_statistics():
    print("\n" + "="*60)
    print("系统统计信息")
    print("="*60)
    
    with get_session() as session:
        from models import Application, Disbursement
        
        total_applications = session.query(Application).count()
        total_disbursements = session.query(Disbursement).filter(
            Disbursement.status == 'verified'
        ).count()
        total_amount = session.query(Disbursement).filter(
            Disbursement.status == 'verified'
        ).with_entities(
            __import__('sqlalchemy').func.sum(Disbursement.amount)
        ).scalar() or 0
        
        print(f"\n申请统计:")
        print(f"  总申请数: {total_applications}")
        print(f"  已发放数: {total_disbursements}")
        print(f"  发放总金额: {Helpers.format_currency(total_amount)}")
        
        policy_service = get_policy_service(session)
        policies = policy_service.get_all_policies()
        print(f"\n奖助金政策统计:")
        for policy in policies:
            stats = policy_service.get_policy_statistics(policy['id'])
            if 'statistics' in stats:
                print(f"\n  {policy['name']}:")
                print(f"    总名额: {stats['statistics']['total_quota']}")
                print(f"    已使用: {stats['statistics']['total_used_quota']}")
                print(f"    名额使用率: {stats['statistics']['quota_utilization']}%")
        
        notification_service = get_notification_service(session)
        notify_stats = notification_service.get_notification_statistics()
        print(f"\n通知统计:")
        print(f"  总通知数: {notify_stats['total_notifications']}")
        print(f"  未读通知数: {notify_stats['unread_notifications']}")
        print(f"  阅读率: {notify_stats['read_rate']}%")
        
        print("="*60)


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--init':
            initialize_database()
        elif command == '--seed':
            initialize_database()
            create_sample_data()
        elif command == '--demo':
            demonstrate_workflow()
        elif command == '--stats':
            show_statistics()
        elif command == '--help':
            print("="*60)
            print("学生奖助学金管理系统")
            print("="*60)
            print("\n使用方法:")
            print("  python main.py --init      初始化数据库")
            print("  python main.py --seed      初始化数据库并创建示例数据")
            print("  python main.py --demo      演示奖助金申请全流程")
            print("  python main.py --stats     查看系统统计信息")
            print("  python main.py --help      显示帮助信息")
            print("\n功能模块:")
            print("  1. 奖助金全流程闭环管理")
            print("  2. 院系额度与名额管控")
            print("  3. 数据校验与资格追踪")
            print("  4. 政策规则动态配置")
            print("  5. 关键节点消息通知")
            print("="*60)
        else:
            print(f"未知命令: {command}")
            print("使用 --help 查看帮助信息")
    else:
        print("="*60)
        print("学生奖助学金管理系统")
        print("="*60)
        print("\n请使用以下命令之一:")
        print("  python main.py --init      初始化数据库")
        print("  python main.py --seed      初始化数据库并创建示例数据")
        print("  python main.py --demo      演示奖助金申请全流程")
        print("  python main.py --stats     查看系统统计信息")
        print("  python main.py --help      显示帮助信息")
        print("="*60)


if __name__ == "__main__":
    main()
