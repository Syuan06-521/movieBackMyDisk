"""
settings.py - 系统设置 API 路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from storage.repositories import SettingRepository, OperationLogRepository
from core.database import get_db

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('', methods=['GET'])
@jwt_required()
def get_settings():
    """获取所有系统设置"""
    db = next(get_db())
    try:
        repo = SettingRepository(db)
        settings = repo.get_as_dict()

        return jsonify({
            'settings': settings
        }), 200

    finally:
        db.close()


@settings_bp.route('/<key>', methods=['GET'])
@jwt_required()
def get_setting(key):
    """获取指定设置项"""
    db = next(get_db())
    try:
        repo = SettingRepository(db)
        value = repo.get_value(key)

        if value is None:
            return jsonify({
                'error': 'not_found',
                'message': f'Setting "{key}" not found'
            }), 404

        return jsonify({
            'key': key,
            'value': value
        }), 200

    finally:
        db.close()


@settings_bp.route('', methods=['PUT'])
@jwt_required()
def update_settings():
    """批量更新系统设置"""
    data = request.get_json()

    db = next(get_db())
    try:
        repo = SettingRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        updated = []
        for key, value in data.items():
            repo.set_value(key, value)
            updated.append(key)

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_settings',
            details={'updated_keys': updated},
            status='success'
        )

        return jsonify({
            'message': f'{len(updated)} settings updated',
            'updated_keys': updated
        }), 200

    finally:
        db.close()


@settings_bp.route('/<key>', methods=['PUT'])
@jwt_required()
def update_setting(key):
    """更新指定设置项"""
    data = request.get_json()
    value = data.get('value')
    setting_type = data.get('type', 'string')
    description = data.get('description')

    if value is None:
        return jsonify({
            'error': 'invalid_request',
            'message': 'Value is required'
        }), 400

    db = next(get_db())
    try:
        repo = SettingRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        repo.set_value(key, value, setting_type, description)

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_setting',
            resource_type='setting',
            resource_id=key,
            status='success'
        )

        return jsonify({
            'message': 'Setting updated successfully',
            'key': key,
            'value': repo.get_value(key)
        }), 200

    finally:
        db.close()


@settings_bp.route('/quark', methods=['GET'])
@jwt_required()
def get_quark_settings():
    """获取夸克网盘相关设置"""
    db = next(get_db())
    try:
        repo = SettingRepository(db)

        settings = {
            'cookie': repo.get_value('quark_cookie', ''),
            'save_folders': repo.get_value('save_folders', ['filmTransfer']),
            'auto_create_folder': repo.get_value('auto_create_folder', True),
        }

        return jsonify({
            'settings': settings
        }), 200

    finally:
        db.close()


@settings_bp.route('/quark', methods=['PUT'])
@jwt_required()
def update_quark_settings():
    """更新夸克网盘设置"""
    data = request.get_json()

    db = next(get_db())
    try:
        repo = SettingRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        if 'cookie' in data:
            repo.set_value('quark_cookie', data['cookie'])
        if 'save_folders' in data:
            import json
            repo.set_value('save_folders', json.dumps(data['save_folders']), 'json')
        if 'auto_create_folder' in data:
            repo.set_value('auto_create_folder', str(data['auto_create_folder']), 'boolean')

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_quark_settings',
            status='success'
        )

        return jsonify({
            'message': 'Quark settings updated successfully'
        }), 200

    finally:
        db.close()


@settings_bp.route('/filter', methods=['GET'])
@jwt_required()
def get_filter_settings():
    """获取资源过滤相关设置"""
    db = next(get_db())
    try:
        repo = SettingRepository(db)

        settings = {
            'preferred_resolutions': repo.get_value('preferred_resolutions', []),
            'min_resolution': repo.get_value('min_resolution', '720p'),
            'min_size_gb': repo.get_value('min_size_gb', 0.5),
            'max_size_gb': repo.get_value('max_size_gb', 60),
            'preferred_codecs': repo.get_value('preferred_codecs', []),
        }

        return jsonify({
            'settings': settings
        }), 200

    finally:
        db.close()


@settings_bp.route('/filter', methods=['PUT'])
@jwt_required()
def update_filter_settings():
    """更新资源过滤设置"""
    data = request.get_json()

    db = next(get_db())
    try:
        repo = SettingRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        if 'preferred_resolutions' in data:
            import json
            repo.set_value('preferred_resolutions', json.dumps(data['preferred_resolutions']), 'json')
        if 'min_resolution' in data:
            repo.set_value('min_resolution', data['min_resolution'])
        if 'min_size_gb' in data:
            repo.set_value('min_size_gb', str(data['min_size_gb']), 'number')
        if 'max_size_gb' in data:
            repo.set_value('max_size_gb', str(data['max_size_gb']), 'number')
        if 'preferred_codecs' in data:
            import json
            repo.set_value('preferred_codecs', json.dumps(data['preferred_codecs']), 'json')

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_filter_settings',
            status='success'
        )

        return jsonify({
            'message': 'Filter settings updated successfully'
        }), 200

    finally:
        db.close()


@settings_bp.route('/notification', methods=['GET'])
@jwt_required()
def get_notification_settings():
    """获取通知相关设置"""
    db = next(get_db())
    try:
        repo = SettingRepository(db)

        # 直接获取原始 setting 对象来调试
        enabled_setting = repo.get_by_key('notification_enabled')
        enabled_value = False
        if enabled_setting:
            enabled_value = enabled_setting.get_typed_value()

        settings = {
            'enabled': enabled_value,
            'type': repo.get_value('notification_type', 'bark'),
            'bark_key': repo.get_value('notification_bark_key', ''),
            'telegram_bot_token': repo.get_value('notification_telegram_bot_token', ''),
            'telegram_chat_id': repo.get_value('notification_telegram_chat_id', ''),
        }

        return jsonify({
            'settings': settings
        }), 200

    finally:
        db.close()


@settings_bp.route('/notification', methods=['PUT'])
@jwt_required()
def update_notification_settings():
    """更新通知设置"""
    data = request.get_json()

    db = next(get_db())
    try:
        repo = SettingRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        if 'enabled' in data:
            # 确保保存为小写的 'true' 或 'false'
            bool_value = bool(data['enabled'])
            repo.set_value('notification_enabled', 'true' if bool_value else 'false', 'boolean')
        if 'type' in data:
            repo.set_value('notification_type', data['type'])
        if 'bark_key' in data:
            repo.set_value('notification_bark_key', data['bark_key'])
        if 'telegram_bot_token' in data:
            repo.set_value('notification_telegram_bot_token', data['telegram_bot_token'])
        if 'telegram_chat_id' in data:
            repo.set_value('notification_telegram_chat_id', data['telegram_chat_id'])

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_notification_settings',
            status='success'
        )

        return jsonify({
            'message': 'Notification settings updated successfully'
        }), 200

    finally:
        db.close()


@settings_bp.route('/notification/test', methods=['POST'])
@jwt_required()
def test_notification():
    """测试通知发送"""
    db = next(get_db())
    try:
        repo = SettingRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        # 获取通知配置
        notif_type = repo.get_value('notification_type', 'bark')
        notif_enabled = repo.get_value('notification_enabled', False)

        if not notif_enabled:
            return jsonify({
                'error': 'notification_disabled',
                'message': '请先启用通知功能'
            }), 400

        # 构建配置
        config = {
            'notification': {
                'enabled': True,
                'type': notif_type,
                'bark_key': repo.get_value('notification_bark_key', ''),
                'telegram_bot_token': repo.get_value('notification_telegram_bot_token', ''),
                'telegram_chat_id': repo.get_value('notification_telegram_chat_id', ''),
            }
        }

        # 导入并使用 pipeline 的通知功能
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from pipeline import TransferPipeline

        # 创建一个临时的 pipeline 实例来发送通知
        class MockPipeline:
            def __init__(self, config):
                self.config = config
            def _notify(self, msg):
                TransferPipeline._notify(self, msg)
            def _notify_bark(self, msg, key):
                TransferPipeline._notify_bark(self, msg, key)
            def _notify_telegram(self, msg, token, chat_id):
                TransferPipeline._notify_telegram(self, msg, token, chat_id)

        try:
            pipeline = MockPipeline(config)
            pipeline._notify("🎬 小兔纸: 测试通知 - 如果收到此消息，说明通知配置正确！")

            # 记录操作日志
            log_repo.create(
                user_id=current_user_id,
                action='test_notification',
                status='success'
            )

            return jsonify({
                'message': 'Test notification sent successfully'
            }), 200

        except Exception as e:
            log_repo.create(
                user_id=current_user_id,
                action='test_notification',
                status='failure',
                details={'error': str(e)}
            )
            return jsonify({
                'error': 'notification_failed',
                'message': f'发送测试通知失败: {str(e)}'
            }), 500

    finally:
        db.close()
