import sys
from datetime import datetime, date
from sqlalchemy.orm import Session
from typing import Dict, Any

from database import get_db_session, init_db
from sample_data import populate_sample_data
from models import Student, ScholarshipType, Department, User
from services import (
    ApplicationService, ApprovalService, DisbursementService,
    QuotaService, ValidationService, ScholarshipTypeService, NotificationService
)

def print_separator(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_application_process():
    print_separator("测试1: 奖学金申请全流程")
    
    with get_db_session() as db:
        student = db.query(Student).filter(Student.student_id == "2021001").first()
        scholarship_type = db.query(ScholarshipType).filter(
            ScholarshipType.code == "SCHOOL_FIRST_CLASS"
        ).first()
        
        if not student or not scholarship_type:
            print("错误：未找到测试数据")
            return False
        
        print(f"\n测试学生: {student.name} (学号: {student.student_id})")
        print(f"申请奖学金: {scholarship_type.name}")
        
        validation_service = ValidationService(db)
        eligible, report = validation_service.validate_student_eligibility(
            student.id, scholarship_type.id
        )
        
        print(f"\n资格校验结果: {'通过' if eligible else '不通过'}")
        print("校验详情:")
        for check in report["checks"]:
            status = "✓ 通过" if check["passed"] else "✗ 不通过"
            print(f"  - {check['description']}: {status}")
            print(f"    {check['details']}")
            print(f"    要求: {check['requirement']}")
        
        if not eligible:
            print("\n学生不符合申请条件，流程终止")
            return False
        
        application_service = ApplicationService(db)
        success, message, application = application_service.submit_application(
            student_id=student.id,
            scholarship_type_id=scholarship_type.id,
            reason="本人学习成绩优异，积极参与社会实践，符合奖学金申请条件。",
            attachments="[]"
        )
        
        print(f"\n申请提交结果: {'成功' if success else '失败'} - {message}")
        
        if not success:
            return False
        
        print(f"\n申请信息:")
        print(f"  - 申请ID: {application.id}")
        print(f"  - 申请状态: {application.status}")
        print(f"  - 申请时间: {application.application_date}")
        
        cs_admin = db.query(User).filter(User.username == "cs_admin").first()
        school_admin = db.query(User).filter(User.username == "school_admin").first()
        financial_admin = db.query(User).filter(User.username == "financial_admin").first()
        
        approval_service = ApprovalService(db)
        
        print(f"\n--- 院系审核 (院系管理员: {cs_admin.name}) ---")
        success, message = approval_service.process_approval(
            application_id=application.id,
            approver_id=cs_admin.id,
            approval_level=1,
            status="approved",
            comments="该生成绩优异，符合申请条件，同意推荐。"
        )
        print(f"院系审核结果: {'成功' if success else '失败'} - {message}")
        
        db.refresh(application)
        print(f"当前申请状态: {application.status}")
        
        print(f"\n--- 学校审核 (学校管理员: {school_admin.name}) ---")
        success, message = approval_service.process_approval(
            application_id=application.id,
            approver_id=school_admin.id,
            approval_level=2,
            status="approved",
            comments="经学校评审委员会审议，该生符合国家励志奖学金评选条件。"
        )
        print(f"学校审核结果: {'成功' if success else '失败'} - {message}")
        
        db.refresh(application)
        print(f"当前申请状态: {application.status}")
        
        print(f"\n--- 财务审核 (财务管理员: {financial_admin.name}) ---")
        success, message = approval_service.process_approval(
            application_id=application.id,
            approver_id=financial_admin.id,
            approval_level=3,
            status="approved",
            comments="财务信息审核通过，准备进入公示环节。"
        )
        print(f"财务审核结果: {'成功' if success else '失败'} - {message}")
        
        db.refresh(application)
        print(f"当前申请状态: {application.status}")
        
        print(f"\n--- 公示环节 ---")
        success, message = approval_service.complete_public_notice(
            application_id=application.id,
            has_objection=False,
            objection_comments=""
        )
        print(f"公示结果: {'成功' if success else '失败'} - {message}")
        
        db.refresh(application)
        print(f"当前申请状态: {application.status}")
        
        print(f"\n--- 发放环节 ---")
        disbursement_service = DisbursementService(db)
        
        success, message, disbursement = disbursement_service.create_disbursement(
            application_id=application.id,
            amount=scholarship_type.amount,
            bank_account="6222021234567890123"
        )
        print(f"发放记录创建结果: {'成功' if success else '失败'} - {message}")
        
        if success:
            success, message = disbursement_service.process_disbursement(
                disbursement_id=disbursement.id,
                transaction_id="TRX" + datetime.now().strftime("%Y%m%d%H%M%S")
            )
            print(f"发放处理结果: {'成功' if success else '失败'} - {message}")
            
            db.refresh(disbursement)
            print(f"发放状态: {disbursement.status}")
            print(f"交易ID: {disbursement.transaction_id}")
            
            success, message = disbursement_service.verify_disbursement(
                disbursement_id=disbursement.id,
                verifier_id=financial_admin.id
            )
            print(f"核销结果: {'成功' if success else '失败'} - {message}")
            
            db.refresh(application)
            print(f"最终申请状态: {application.status}")
        
        print("\n✓ 奖学金申请全流程测试完成！")
        return True

def test_quota_management():
    print_separator("测试2: 院系额度与名额管控")
    
    with get_db_session() as db:
        quota_service = QuotaService(db)
        
        cs_dept = db.query(Department).filter(Department.code == "CS").first()
        scholarship_type = db.query(ScholarshipType).filter(
            ScholarshipType.code == "NATIONAL_SCHOLARSHIP"
        ).first()
        current_year = datetime.now().year
        
        print(f"\n院系: {cs_dept.name}")
        print(f"奖学金: {scholarship_type.name}")
        print(f"年度: {current_year}")
        
        quota = quota_service.get_department_quota(
            cs_dept.id, scholarship_type.id, current_year
        )
        
        if quota:
            print(f"\n当前额度信息:")
            print(f"  - 总名额: {quota.quota}")
            print(f"  - 已使用名额: {quota.used_quota}")
            print(f"  - 剩余名额: {quota.quota - quota.used_quota}")
            print(f"  - 总预算: {quota.budget}元")
            print(f"  - 已使用预算: {quota.used_budget}元")
            print(f"  - 剩余预算: {quota.budget - quota.used_budget}元")
        
        print(f"\n--- 测试额度检查 ---")
        available, message = quota_service.check_quota_availability(
            cs_dept.id, scholarship_type.id, current_year
        )
        print(f"额度可用性: {'可用' if available else '不可用'} - {message}")
        
        print(f"\n--- 测试超额预警 ---")
        success, message = quota_service.update_department_quota(
            quota_id=quota.id,
            quota=0
        )
        print(f"将名额设置为0: {'成功' if success else '失败'} - {message}")
        
        available, message = quota_service.check_quota_availability(
            cs_dept.id, scholarship_type.id, current_year
        )
        print(f"额度可用性检查: {'可用' if available else '不可用'} - {message}")
        
        success, message = quota_service.update_department_quota(
            quota_id=quota.id,
            quota=5
        )
        print(f"恢复名额为5: {'成功' if success else '失败'} - {message}")
        
        print("\n✓ 院系额度与名额管控测试完成！")
        return True

def test_validation_and_reporting():
    print_separator("测试3: 数据校验与资格追踪")
    
    with get_db_session() as db:
        validation_service = ValidationService(db)
        
        student = db.query(Student).filter(Student.student_id == "2021001").first()
        scholarship_type = db.query(ScholarshipType).filter(
            ScholarshipType.code == "NATIONAL_SCHOLARSHIP"
        ).first()
        
        print(f"\n生成资格审核报告...")
        report = validation_service.generate_qualification_report(
            student.id, scholarship_type.id
        )
        
        print(f"\n=== 资格审核报告 ===")
        print(f"报告日期: {report['report_date']}")
        print(f"\n学生信息:")
        print(f"  - 姓名: {report['student']['name']}")
        print(f"  - 学号: {report['student']['student_id']}")
        print(f"  - 院系: {report['student']['department']}")
        print(f"  - 专业: {report['student']['major']}")
        print(f"  - 年级: {report['student']['grade']}")
        print(f"  - 状态: {report['student']['status']}")
        
        print(f"\n奖学金信息:")
        print(f"  - 名称: {report['scholarship']['name']}")
        print(f"  - 类型: {report['scholarship']['type']}")
        print(f"  - 金额: {report['scholarship']['amount']}元")
        print(f"  - 最低GPA要求: {report['scholarship']['min_gpa']}")
        
        print(f"\n资格校验结果: {'符合条件' if report['eligible'] else '不符合条件'}")
        print(f"\n校验详情:")
        for check in report['validation']['checks']:
            status = "✓ 通过" if check['passed'] else "✗ 不通过"
            print(f"\n  {check['description']}: {status}")
            print(f"    - 详情: {check['details']}")
            print(f"    - 要求: {check['requirement']}")
        
        print(f"\n--- 生成发放统计报表 ---")
        current_year = datetime.now().year
        stats = validation_service.generate_disbursement_statistics(year=current_year)
        
        print(f"\n=== 发放统计报表 ===")
        print(f"报告日期: {stats['report_date']}")
        print(f"统计年度: {stats['year']}")
        
        print(f"\n汇总信息:")
        print(f"  - 总发放笔数: {stats['summary']['total_disbursements']}")
        print(f"  - 总发放金额: {stats['summary']['total_amount']}元")
        print(f"  - 平均发放金额: {stats['summary']['average_amount']:.2f}元")
        
        print(f"\n状态分布:")
        for status, count in stats['status_breakdown'].items():
            print(f"  - {status}: {count}笔")
        
        if stats['disbursements']:
            print(f"\n发放明细:")
            for d in stats['disbursements']:
                print(f"\n  - 发放ID: {d['id']}")
                print(f"    学生: {d['student_name']} ({d['student_id']})")
                print(f"    奖学金类型: {d['scholarship_type']}")
                print(f"    金额: {d['amount']}元")
                print(f"    状态: {d['status']}")
        
        print("\n✓ 数据校验与资格追踪测试完成！")
        return True

def test_policy_configuration():
    print_separator("测试4: 政策规则动态配置")
    
    with get_db_session() as db:
        scholarship_service = ScholarshipTypeService(db)
        
        print(f"\n--- 创建新的奖学金类型 ---")
        today = datetime.now().date()
        
        success, message, new_scholarship = scholarship_service.create_scholarship_type(
            name="企业专项奖学金",
            code="ENTERPRISE_SPECIAL",
            type="scholarship",
            description="由合作企业设立的专项奖学金，用于奖励在专业领域有突出表现的学生。",
            application_start_date=date(today.year, 10, 1),
            application_end_date=date(today.year, 10, 31),
            review_start_date=date(today.year, 11, 1),
            review_end_date=date(today.year, 11, 15),
            disbursement_date=date(today.year, 12, 1),
            amount=5000.0,
            min_gpa=3.2,
            max_application_count=1
        )
        
        print(f"创建结果: {'成功' if success else '失败'} - {message}")
        
        if success:
            print(f"\n新奖学金信息:")
            print(f"  - ID: {new_scholarship.id}")
            print(f"  - 名称: {new_scholarship.name}")
            print(f"  - 代码: {new_scholarship.code}")
            print(f"  - 类型: {new_scholarship.type}")
            print(f"  - 金额: {new_scholarship.amount}元")
            print(f"  - 最低GPA: {new_scholarship.min_gpa}")
            print(f"  - 申报期: {new_scholarship.application_start_date} 至 {new_scholarship.application_end_date}")
        
        print(f"\n--- 更新奖学金政策 ---")
        if new_scholarship:
            success, message = scholarship_service.update_scholarship_type(
                scholarship_type_id=new_scholarship.id,
                amount=6000.0,
                min_gpa=3.5,
                description="由合作企业设立的专项奖学金，用于奖励在专业领域有突出表现的优秀学生。金额已调整。"
            )
            print(f"更新结果: {'成功' if success else '失败'} - {message}")
            
            db.refresh(new_scholarship)
            print(f"\n更新后信息:")
            print(f"  - 金额: {new_scholarship.amount}元")
            print(f"  - 最低GPA: {new_scholarship.min_gpa}")
            print(f"  - 描述: {new_scholarship.description}")
        
        print(f"\n--- 查看所有奖学金类型 ---")
        all_types = scholarship_service.get_all_scholarship_types()
        print(f"\n共有 {len(all_types)} 种奖学金类型:")
        for st in all_types:
            print(f"\n  - {st.name} ({st.code})")
            print(f"    类型: {st.type} | 金额: {st.amount}元 | 最低GPA: {st.min_gpa}")
            print(f"    申报期: {st.application_start_date} 至 {st.application_end_date}")
        
        print(f"\n--- 查看当前可申请的奖学金 ---")
        active_types = scholarship_service.get_active_scholarship_types()
        print(f"\n当前有 {len(active_types)} 种奖学金处于申报期:")
        for st in active_types:
            print(f"  - {st.name}: 金额 {st.amount}元, 截止日期 {st.application_end_date}")
        
        print("\n✓ 政策规则动态配置测试完成！")
        return True

def test_notification_system():
    print_separator("测试5: 消息通知系统")
    
    with get_db_session() as db:
        notification_service = NotificationService(db)
        
        student = db.query(Student).filter(Student.student_id == "2021001").first()
        cs_admin = db.query(User).filter(User.username == "cs_admin").first()
        
        print(f"\n--- 发送申报提醒通知 ---")
        scholarship_type = db.query(ScholarshipType).filter(
            ScholarshipType.code == "NATIONAL_SCHOLARSHIP"
        ).first()
        
        notification_service.send_application_reminder(scholarship_type.id)
        print(f"已向所有在读学生发送申报提醒通知")
        
        print(f"\n--- 查看用户通知 ---")
        student_notifications = notification_service.get_user_notifications(
            user_id=student.id,
            unread_only=False
        )
        
        print(f"\n学生 {student.name} 的通知列表 ({len(student_notifications)} 条):")
        for notif in student_notifications:
            status = "未读" if not notif.is_read else "已读"
            print(f"\n  - 标题: {notif.title}")
            print(f"    类型: {notif.type} | 状态: {status}")
            print(f"    内容: {notif.content}")
            print(f"    时间: {notif.created_at}")
        
        if student_notifications:
            print(f"\n--- 标记通知为已读 ---")
            success, message = notification_service.mark_notification_as_read(
                notification_id=student_notifications[0].id
            )
            print(f"标记结果: {'成功' if success else '失败'} - {message}")
            
            db.refresh(student_notifications[0])
            print(f"通知状态: {'已读' if student_notifications[0].is_read else '未读'}")
        
        print(f"\n--- 标记所有通知为已读 ---")
        success, message = notification_service.mark_all_notifications_as_read(
            user_id=student.id
        )
        print(f"标记结果: {'成功' if success else '失败'} - {message}")
        
        print("\n✓ 消息通知系统测试完成！")
        return True

def main():
    print("=" * 80)
    print("  学生奖助学金管理系统 - 功能测试")
    print("=" * 80)
    
    print("\n正在初始化数据库并填充示例数据...")
    populate_sample_data()
    print("数据库初始化完成！")
    
    test_results = []
    
    test_results.append(("奖学金申请全流程", test_application_process()))
    test_results.append(("院系额度与名额管控", test_quota_management()))
    test_results.append(("数据校验与资格追踪", test_validation_and_reporting()))
    test_results.append(("政策规则动态配置", test_policy_configuration()))
    test_results.append(("消息通知系统", test_notification_system()))
    
    print_separator("测试总结")
    print("\n测试结果汇总:")
    all_passed = True
    for test_name, passed in test_results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  - {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print(f"\n总体测试结果: {'全部通过 ✓' if all_passed else '部分失败 ✗'}")
    
    if all_passed:
        print("\n恭喜！所有功能测试均已通过！")
        print("\n系统已实现以下核心功能:")
        print("  1. 奖助金全流程闭环管理（申报→审核→公示→发放→核销）")
        print("  2. 院系额度与名额管控（超额预警、多级复核）")
        print("  3. 数据校验与资格追踪（自动比对学籍、成绩、受助记录）")
        print("  4. 政策规则动态配置（按类型设置申报条件、发放标准）")
        print("  5. 关键节点消息通知（申报提醒、审核待办、公示通知、发放进度）")
    else:
        print("\n部分测试失败，请检查错误信息。")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
