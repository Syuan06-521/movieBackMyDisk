"""
check.py - 执行检查 API 路由

提供触发影视资源检查和转存的 API 端点
支持两种模式：auto（全自动）和 semi-auto（半自动）

优化 (2026-03-25):
  - 增加进度回调支持
  - 增加执行日志记录
"""
import threading
import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from storage.repositories import OperationLogRepository
from core.database import get_db
from core.config import settings

check_bp = Blueprint('check', __name__)

# 全局任务状态（简单实现，生产环境建议使用 Redis 或数据库）
running_tasks = {}
task_logs = {}  # 存储每个任务的执行日志
task_stop_flags = {}  # 存储每个任务的停止标志

logger = logging.getLogger(__name__)


def _progress_callback(task_id: str, status: str, progress: int, message: str, current_item: str = ""):
    """进度回调函数"""
    # 检查是否有停止标志
    if task_id in task_stop_flags and task_stop_flags[task_id]:
        logger.info(f"Task {task_id} received stop signal")
        return

    if task_id in running_tasks:
        running_tasks[task_id].update({
            'status': status,
            'progress': progress,
            'message': message,
            'current_item': current_item,
        })
    # 记录日志
    log_entry = f"[{status}] {message}"
    if current_item:
        log_entry += f" - {current_item}"
    if task_id not in task_logs:
        task_logs[task_id] = []
    task_logs[task_id].append(log_entry)


def _should_stop(task_id: str) -> bool:
    """检查任务是否应该停止"""
    return task_stop_flags.get(task_id, False)


@check_bp.route('', methods=['POST'])
@jwt_required()
def run_check():
    """
    执行一次检查

    Request Body:
        {
            "mode": "auto" | "semi-auto",  // 运行模式
            "content_type": "movie" | "series" | null  // 内容类型过滤
        }

    Response:
        {
            "task_id": "xxx",
            "status": "started",
            "message": "检查任务已启动"
        }
    """
    from pipeline import TransferPipeline
    import uuid

    data = request.get_json() or {}
    mode = data.get('mode', settings.mode)  # 默认使用配置文件中的模式
    content_type = data.get('content_type')

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    db = next(get_db())
    try:
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        # 记录操作日志
        log_repo.create(
            user_id=int(current_user_id),
            action='run_check',
            details={
                'mode': mode,
                'content_type': content_type
            },
            status='success'
        )

        # 创建并启动任务
        def run_task():
            try:
                running_tasks[task_id] = {'status': 'running', 'progress': 0, 'message': '正在初始化...'}
                task_logs[task_id] = ['任务已启动']
                task_stop_flags[task_id] = False  # 初始化停止标志

                # 构建配置
                config = {
                    'mode': mode,
                    'quark': settings.quark,
                    'filter': settings.filter,
                    'search_sites': settings.search_sites,
                    'stremio_addons': settings.stremio_addons,
                    'logging': settings.logging,
                }

                # 如果指定了内容类型，过滤 addon
                if content_type:
                    for addon in config['stremio_addons']:
                        addon['watch_types'] = [content_type]

                # 设置进度回调
                from pipeline import set_progress_callback, _report_progress, set_should_stop_callback
                set_progress_callback(lambda status, progress, message, current_item="":
                    _progress_callback(task_id, status, progress, message, current_item))
                # 设置停止标志检查回调
                set_should_stop_callback(lambda: _should_stop(task_id))

                # 报告初始化完成
                _report_progress("running", 0, "正在执行检查...")

                # 执行检查
                pipeline = TransferPipeline(config)
                pipeline.run_once(content_type)

                # 检查是否被停止
                if task_stop_flags.get(task_id, False):
                    running_tasks[task_id] = {
                        'status': 'stopped',
                        'progress': running_tasks[task_id].get('progress', 0),
                        'message': '任务已被用户停止'
                    }
                    task_logs[task_id].append("任务已被用户停止")
                else:
                    running_tasks[task_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': '检查完成'
                    }
                    task_logs[task_id].append("检查完成")
            except Exception as e:
                running_tasks[task_id] = {
                    'status': 'failed',
                    'error': str(e)
                }
                logger.error(f'Check task failed: {e}', exc_info=True)
                if task_id in task_logs:
                    task_logs[task_id].append(f"错误：{str(e)}")
            finally:
                # 清理停止标志
                if task_id in task_stop_flags:
                    del task_stop_flags[task_id]

        # 在后台线程中运行
        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()

        running_tasks[task_id] = {'status': 'queued', 'progress': 0, 'message': '任务已排队'}

        return jsonify({
            'task_id': task_id,
            'status': 'started',
            'message': f'检查任务已启动（模式：{mode}）'
        }), 202

    finally:
        db.close()


@check_bp.route('/status/<task_id>', methods=['GET'])
@jwt_required()
def get_task_status(task_id):
    """获取任务执行状态"""
    task = running_tasks.get(task_id)

    if not task:
        return jsonify({
            'error': 'not_found',
            'message': '任务不存在或已完成清理'
        }), 404

    return jsonify({
        'task_id': task_id,
        'status': task.get('status'),
        'progress': task.get('progress'),
        'message': task.get('message'),
        'error': task.get('error')
    }), 200


@check_bp.route('/modes', methods=['GET'])
@jwt_required()
def get_run_modes():
    """获取可用的运行模式"""
    return jsonify({
        'modes': [
            {'value': 'auto', 'label': '全自动模式', 'description': '自动搜索并转存到夸克网盘'},
            {'value': 'semi-auto', 'label': '半自动模式', 'description': '搜索结果保存到 Excel，手动处理'}
        ],
        'current_mode': settings.mode
    }), 200


@check_bp.route('/stop/<task_id>', methods=['POST'])
@jwt_required()
def stop_task(task_id):
    """停止正在执行的任务"""
    from storage.repositories import OperationLogRepository
    from flask_jwt_extended import get_jwt_identity

    task = running_tasks.get(task_id)

    if not task:
        return jsonify({
            'error': 'not_found',
            'message': '任务不存在或已完成'
        }), 404

    if task.get('status') not in ['running', 'queued']:
        return jsonify({
            'error': 'invalid_status',
            'message': f'任务状态为 {task.get("status")}，无法停止'
        }), 400

    # 设置停止标志
    task_stop_flags[task_id] = True

    # 立即更新任务状态为 stopping，让前端可以显示停止中状态
    running_tasks[task_id]['status'] = 'stopping'
    running_tasks[task_id]['message'] = '正在停止任务，等待当前操作完成...'

    db = next(get_db())
    try:
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        # 记录操作日志
        log_repo.create(
            user_id=int(current_user_id),
            action='stop_task',
            details={'task_id': task_id},
            status='success'
        )
    finally:
        db.close()

    return jsonify({
        'message': '任务停止信号已发送，等待当前操作完成后退出...',
        'task_id': task_id
    }), 200


@check_bp.route('/logs/<task_id>', methods=['GET'])
@jwt_required()
def get_task_logs(task_id):
    """获取任务执行日志"""
    logs = task_logs.get(task_id, [])
    return jsonify({
        'task_id': task_id,
        'logs': logs
    }), 200
