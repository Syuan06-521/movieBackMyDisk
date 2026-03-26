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
