"""
users.py - 用户管理 API 路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from core.security import hash_password, verify_password
from storage.repositories import UserRepository, OperationLogRepository
from core.database import get_db
from app import role_required

users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@jwt_required()
def get_users():
    """获取用户列表（管理员权限）"""
    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        role = request.args.get('role')
        status = request.args.get('status')

        users = user_repo.get_all(skip=skip, limit=limit, role=role, status=status)

        return jsonify({
            'users': [user.to_dict() for user in users],
            'total': len(users)
        }), 200

    finally:
        db.close()


@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """获取指定用户详情"""
    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)

        if not user:
            return jsonify({
                'error': 'not_found',
                'message': 'User not found'
            }), 404

        return jsonify({
            'user': user.to_dict()
        }), 200

    finally:
        db.close()


@users_bp.route('', methods=['POST'])
@jwt_required()
@role_required('admin')
def create_user():
    """创建新用户（仅管理员）"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({
            'error': 'invalid_request',
            'message': 'Username and password are required'
        }), 400

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        # 检查用户名是否存在
        existing = user_repo.get_by_username(username)
        if existing:
            return jsonify({
                'error': 'username_exists',
                'message': 'Username already exists'
            }), 409

        # 创建用户
        password_hash = hash_password(password)
        user = user_repo.create(
            username=username,
            password_hash=password_hash,
            email=email,
            role=role
        )

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='create_user',
            resource_type='user',
            resource_id=str(user.id),
            details={'username': username},
            status='success'
        )

        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict()
        }), 201

    finally:
        db.close()


@users_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
@role_required('admin')
def update_user(user_id):
    """更新用户信息（仅管理员）"""
    data = request.get_json()

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        user = user_repo.get_by_id(user_id)
        if not user:
            return jsonify({
                'error': 'not_found',
                'message': 'User not found'
            }), 404

        # 更新字段
        update_data = {}
        if 'email' in data:
            update_data['email'] = data['email']
        if 'role' in data:
            update_data['role'] = data['role']
        if 'status' in data:
            update_data['status'] = data['status']
        if 'password' in data and data['password']:
            update_data['password_hash'] = hash_password(data['password'])

        if update_data:
            user_repo.update(user_id, **update_data)

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_user',
            resource_type='user',
            resource_id=str(user_id),
            status='success'
        )

        return jsonify({
            'message': 'User updated successfully',
            'user': user_repo.get_by_id(user_id).to_dict()
        }), 200

    finally:
        db.close()


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin')
def delete_user(user_id):
    """删除用户（仅管理员）"""
    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        user = user_repo.get_by_id(user_id)
        if not user:
            return jsonify({
                'error': 'not_found',
                'message': 'User not found'
            }), 404

        # 不能删除自己
        if user_id == current_user_id:
            return jsonify({
                'error': 'invalid_operation',
                'message': 'Cannot delete yourself'
            }), 400

        user_repo.delete(user_id)

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='delete_user',
            resource_type='user',
            resource_id=str(user_id),
            status='success'
        )

        return jsonify({
            'message': 'User deleted successfully'
        }), 200

    finally:
        db.close()


@users_bp.route('/<int:user_id>/password', methods=['PUT'])
@jwt_required()
def update_password(user_id):
    """更新密码"""
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({
            'error': 'invalid_request',
            'message': 'Current password and new password are required'
        }), 400

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        # 只能修改自己的密码
        if user_id != current_user_id:
            return jsonify({
                'error': 'forbidden',
                'message': 'Can only update your own password'
            }), 403

        user = user_repo.get_by_id(user_id)
        if not user:
            return jsonify({
                'error': 'not_found',
                'message': 'User not found'
            }), 404

        # 验证当前密码
        if not verify_password(current_password, user.password_hash):
            return jsonify({
                'error': 'invalid_password',
                'message': 'Current password is incorrect'
            }), 400

        # 更新密码
        user_repo.update(user_id, password_hash=hash_password(new_password))

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_password',
            status='success'
        )

        return jsonify({
            'message': 'Password updated successfully'
        }), 200

    finally:
        db.close()
