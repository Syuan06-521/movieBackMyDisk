"""
Flask 应用工厂
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from functools import wraps

from core.config import settings
from core.database import init_db, db_session, close_db
from models.user import User, UserRole


def create_app(config=None):
    """应用工厂函数"""
    app = Flask(__name__)

    # Flask 配置
    app.config['SECRET_KEY'] = settings.flask.secret_key
    app.config['JWT_SECRET_KEY'] = settings.jwt.secret_key
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = settings.jwt.access_token_expires
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = settings.jwt.refresh_token_expires
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'

    # 初始化扩展
    CORS(app, supports_credentials=True)
    jwt = JWTManager(app)

    # 初始化数据库
    init_db()

    # 注册请求钩子
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        close_db()

    # JWT 错误处理
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'token_expired',
            'message': 'Token has expired'
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': 'invalid_token',
            'message': 'Invalid token'
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': 'authorization_required',
            'message': 'Authorization token required'
        }), 401

    # 注册路由蓝图
    from api.auth import auth_bp
    from api.users import users_bp
    from api.catalog import catalog_bp
    from api.tasks import tasks_bp
    from api.history import history_bp
    from api.settings import settings_bp
    from api.check import check_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(catalog_bp, url_prefix='/api/catalog')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(history_bp, url_prefix='/api/history')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(check_bp, url_prefix='/api/check')

    # 根路径
    @app.route('/')
    def index():
        return jsonify({
            'name': 'Film Transfer API',
            'version': '2.0.0',
            'status': 'running'
        })

    # 404 错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'not_found',
            'message': 'API endpoint not found'
        }), 404

    # 通用错误处理
    @app.errorhandler(Exception)
    def handle_exception(error):
        return jsonify({
            'error': 'internal_error',
            'message': str(error)
        }), 500

    return app


# JWT 角色权限装饰器
def role_required(*roles):
    """要求用户具有指定角色之一"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()

            from storage.repositories import UserRepository
            db = next(get_db_generator())
            try:
                user_repo = UserRepository(db)
                user = user_repo.get_by_id(int(current_user_id))

                if not user or user.role.value not in roles:
                    return jsonify({
                        'error': 'forbidden',
                        'message': 'Insufficient permissions'
                    }), 403

                return fn(*args, **kwargs)
            finally:
                db.close()

        return wrapper
    return decorator


def get_db_generator():
    """获取数据库会话生成器"""
    from core.database import get_db
    return get_db()
