from flask import Blueprint, request, jsonify
from database import get_db
from services.application_service import ApplicationService
from services.quota_service import QuotaService
from services.qualification_service import QualificationService
from services.policy_service import PolicyService
from services.notification_service import NotificationService
from reports.report_generator import ReportGenerator
from utils.validators import Validator

api = Blueprint('api', __name__)

@api.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': '奖助学金管理系统运行正常'})

@api.route('/applications', methods=['POST'])
def submit_application():
    data = request.get_json()
    db = next(get_db())

    valid, errors = Validator.validate_application_data(data)
    if not valid:
        return jsonify({'success': False, 'errors': errors}), 400

    service = ApplicationService(db)
    result = service.submit_application(
        student_id=data['student_id'],
        scholarship_type_id=data['scholarship_type_id'],
        reason=data.get('reason'),
        attachments=data.get('attachments')
    )

    if result['success']:
        return jsonify(result), 201
    return jsonify(result), 400

@api.route('/applications/<int:application_id>', methods=['GET'])
def get_application(application_id):
    db = next(get_db())
    service = ApplicationService(db)
    result = service.get_application_flow(application_id)

    if result:
        return jsonify(result)
    return jsonify({'error': '申请不存在'}), 404

@api.route('/applications/<int:application_id>/review', methods=['POST'])
def review_application(application_id):
    data = request.get_json()
    db = next(get_db())

    service = ApplicationService(db)
    result = service.review_application(
        application_id=application_id,
        approver_id=data['approver_id'],
        status=data['status'],
        comments=data.get('comments'),
        level=data.get('level', 1)
    )

    return jsonify(result)

@api.route('/applications/<int:application_id>/publish', methods=['POST'])
def publish_application(application_id):
    db = next(get_db())
    service = ApplicationService(db)
    result = service.publish_application(application_id)

    return jsonify(result)

@api.route('/applications/<int:application_id>/disburse', methods=['POST'])
def disburse_application(application_id):
    data = request.get_json()
    db = next(get_db())

    service = ApplicationService(db)
    result = service.disburse_application(
        application_id=application_id,
        amount=data['amount'],
        bank_account=data.get('bank_account')
    )

    return jsonify(result)

@api.route('/applications/<int:application_id>/verify', methods=['POST'])
def verify_disbursement(application_id):
    data = request.get_json()
    db = next(get_db())

    service = ApplicationService(db)
    result = service.verify_disbursement(
        disbursement_id=application_id,
        verifier_id=data['verifier_id'],
        transaction_id=data.get('transaction_id')
    )

    return jsonify(result)

@api.route('/quotas', methods=['POST'])
def set_quota():
    data = request.get_json()
    db = next(get_db())

    valid, errors = Validator.validate_quota_data(data)
    if not valid:
        return jsonify({'success': False, 'errors': errors}), 400

    service = QuotaService(db)
    result = service.set_quota(
        department_id=data['department_id'],
        scholarship_type_id=data['scholarship_type_id'],
        year=data['year'],
        quota=data['quota'],
        budget=data['budget']
    )

    return jsonify(result)

@api.route('/quotas/<int:department_id>/<int:scholarship_type_id>/<int:year>', methods=['GET'])
def get_quota(department_id, scholarship_type_id, year):
    db = next(get_db())
    service = QuotaService(db)
    result = service.get_quota(department_id, scholarship_type_id, year)

    return jsonify(result)

@api.route('/quotas/overview', methods=['GET'])
def get_quotas_overview():
    year = request.args.get('year', type=int)
    db = next(get_db())
    service = QuotaService(db)
    result = service.get_all_quotas_overview(year)

    return jsonify(result)

@api.route('/qualification/check', methods=['POST'])
def check_qualification():
    data = request.get_json()
    db = next(get_db())

    service = QualificationService(db)
    result = service.check_student_eligibility(
        student_id=data['student_id'],
        scholarship_type_id=data['scholarship_type_id']
    )

    return jsonify(result)

@api.route('/qualification/report', methods=['GET'])
def get_qualification_report():
    scholarship_type_id = request.args.get('scholarship_type_id', type=int)
    department_id = request.args.get('department_id', type=int)
    db = next(get_db())

    service = QualificationService(db)
    result = service.generate_qualification_report(
        scholarship_type_id=scholarship_type_id,
        department_id=department_id
    )

    return jsonify(result)

@api.route('/disbursement/report', methods=['GET'])
def get_disbursement_report():
    year = request.args.get('year', type=int)
    department_id = request.args.get('department_id', type=int)
    scholarship_type_id = request.args.get('scholarship_type_id', type=int)
    db = next(get_db())

    service = QualificationService(db)
    result = service.generate_disbursement_report(
        year=year,
        department_id=department_id,
        scholarship_type_id=scholarship_type_id
    )

    return jsonify(result)

@api.route('/scholarship-types', methods=['POST'])
def create_scholarship_type():
    data = request.get_json()
    db = next(get_db())

    service = PolicyService(db)
    result = service.create_scholarship_type(data)

    if result['success']:
        return jsonify(result), 201
    return jsonify(result), 400

@api.route('/scholarship-types/<int:scholarship_type_id>', methods=['PUT'])
def update_scholarship_type(scholarship_type_id):
    data = request.get_json()
    db = next(get_db())

    service = PolicyService(db)
    result = service.update_scholarship_type(scholarship_type_id, data)

    return jsonify(result)

@api.route('/scholarship-types/<int:scholarship_type_id>/policy', methods=['PUT'])
def configure_policy(scholarship_type_id):
    data = request.get_json()
    db = next(get_db())

    service = PolicyService(db)
    result = service.configure_policy_rules(scholarship_type_id, data.get('rules', {}))

    return jsonify(result)

@api.route('/scholarship-types/<int:scholarship_type_id>', methods=['GET'])
def get_policy_summary(scholarship_type_id):
    db = next(get_db())
    service = PolicyService(db)
    result = service.get_policy_summary(scholarship_type_id)

    if result:
        return jsonify(result)
    return jsonify({'error': '奖助金类型不存在'}), 404

@api.route('/scholarship-types', methods=['GET'])
def get_active_scholarship_types():
    type_filter = request.args.get('type')
    db = next(get_db())
    service = PolicyService(db)
    result = service.get_active_scholarship_types(type_filter)

    return jsonify([{
        'id': st.id,
        'name': st.name,
        'code': st.code,
        'type': st.type,
        'amount': st.amount
    } for st in result])

@api.route('/students/<int:student_id>/match', methods=['GET'])
def match_student_scholarships(student_id):
    db = next(get_db())
    service = PolicyService(db)
    result = service.match_student_to_scholarships(student_id)

    return jsonify(result)

@api.route('/students/<int:student_id>/history', methods=['GET'])
def get_student_history(student_id):
    db = next(get_db())
    service = QualificationService(db)
    result = service.get_student_assistance_history(student_id)

    return jsonify(result)

@api.route('/reports/applications', methods=['GET'])
def get_application_statistics():
    year = request.args.get('year', type=int)
    department_id = request.args.get('department_id', type=int)
    db = next(get_db())

    generator = ReportGenerator(db)
    result = generator.generate_application_statistics(year, department_id)

    return jsonify(result)

@api.route('/reports/quota-usage', methods=['GET'])
def get_quota_usage_report():
    year = request.args.get('year', type=int)
    db = next(get_db())

    generator = ReportGenerator(db)
    result = generator.generate_quota_usage_report(year)

    return jsonify(result)

@api.route('/reports/disbursement', methods=['GET'])
def get_disbursement_report_v2():
    year = request.args.get('year', type=int)
    quarter = request.args.get('quarter', type=int)
    db = next(get_db())

    generator = ReportGenerator(db)
    result = generator.generate_disbursement_report(year, quarter)

    return jsonify(result)

@api.route('/reports/student/<int:student_id>', methods=['GET'])
def get_student_summary(student_id):
    db = next(get_db())
    generator = ReportGenerator(db)
    result = generator.generate_student_summary_report(student_id)

    return jsonify(result)

@api.route('/reports/department/<int:department_id>', methods=['GET'])
def get_department_summary(department_id):
    year = request.args.get('year', type=int)
    db = next(get_db())
    generator = ReportGenerator(db)
    result = generator.generate_department_summary_report(department_id, year)

    return jsonify(result)

@api.route('/notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    db = next(get_db())
    service = NotificationService(db)
    result = service.get_user_notifications(user_id, unread_only)

    return jsonify([{
        'id': n.id,
        'title': n.title,
        'content': n.content,
        'type': n.type,
        'is_read': n.is_read,
        'created_at': n.created_at
    } for n in result])

@api.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    db = next(get_db())
    service = NotificationService(db)
    result = service.mark_as_read(notification_id)

    return jsonify(result)