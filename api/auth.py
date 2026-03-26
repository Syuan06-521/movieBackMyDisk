"""
auth.py - 认证相关 API 路由
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from datetime import datetime

from core.security import hash_password, verify_password
from storage.repositories import UserRepository, OperationLogRepository
from core.database import get_db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录
    ---
    Request:
        username: str
        password: str
    Response:
        access_token: str
        refresh_token: str
        user: User object
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({
            'error': 'invalid_request',
            'message': 'Username and password are required'
        }), 400

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        log_repo = OperationLogRepository(db)

        user = user_repo.get_by_username(username)

        if not user:
            log_repo.create(
                user_id=None,
                action='login',
                details={'username': username},
                status='failure'
            )
            return jsonify({
                'error': 'invalid_credentials',
                'message': 'Invalid username or password'
            }), 401

        if not verify_password(password, user.password_hash):
            log_repo.create(
                user_id=user.id,
                action='login',
                details={'username': username},
                status='failure'
            )
            return jsonify({
                'error': 'invalid_credentials',
                'message': 'Invalid username or password'
            }), 401

        if not user.is_active:
            return jsonify({
                'error': 'account_inactive',
                'message': 'Your account is inactive'
            }), 403

        # 生成 Token（注意：Flask-JWT-Extended v4.7+ 要求 identity 为字符串）
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        # 更新最后登录时间
        user_repo.update_last_login(user.id)

        # 记录操作日志
        log_repo.create(
            user_id=user.id,
            action='login',
            details={'username': username},
            status='success'
        )

        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200

    finally:
        db.close()


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """刷新访问 Token"""
    current_user_id = get_jwt_identity()

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(current_user_id)

        if not user or not user.is_active:
            return jsonify({
                'error': 'invalid_user',
                'message': 'User not found or inactive'
            }), 401

        access_token = create_access_token(identity=current_user_id)

        return jsonify({
            'access_token': access_token
        }), 200

    finally:
        db.close()


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """获取当前登录用户信息"""
    current_user_id = get_jwt_identity()

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(current_user_id)

        if not user:
            return jsonify({
                'error': 'user_not_found',
                'message': 'User not found'
            }), 404

        return jsonify({
            'user': user.to_dict()
        }), 200

    finally:
        db.close()


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户登出"""
    current_user_id = get_jwt_identity()

    db = next(get_db())
    try:
        log_repo = OperationLogRepository(db)
        log_repo.create(
            user_id=current_user_id,
            action='logout',
            status='success'
        )

        return jsonify({
            'message': 'Logged out successfully'
        }), 200

    finally:
        db.close()


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册（仅管理员或开放注册时使用）
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    if not username or not password:
        return jsonify({
            'error': 'invalid_request',
            'message': 'Username and password are required'
        }), 400

    db = next(get_db())
    try:
        user_repo = UserRepository(db)
        log_repo = OperationLogRepository(db)

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
            role='user'
        )

        # 记录操作日志
        log_repo.create(
            user_id=user.id,
            action='register',
            details={'username': username},
            status='success'
        )

        return jsonify({
            'message': 'User registered successfully',
            'user': user.to_dict()
        }), 201

    finally:
        db.close()
