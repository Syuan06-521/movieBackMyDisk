"""
tasks.py - 转存任务 API 路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from storage.repositories import TaskRepository, OperationLogRepository, CatalogRepository
from storage.database import CatalogDBv2
from storage.sync_history import SyncHistory
from core.database import get_db

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    """获取任务列表"""
    db = next(get_db())
    try:
        repo = TaskRepository(db)
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        status = request.args.get('status')

        tasks = repo.get_all(skip=skip, limit=limit, status=status)
        total = repo.count(status=status)

        return jsonify({
            'tasks': [task.to_dict() for task in tasks],
            'total': total
        }), 200

    finally:
        db.close()


@tasks_bp.route('/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """获取任务详情"""
    db = next(get_db())
    try:
        repo = TaskRepository(db)
        task = repo.get_by_id(task_id)

        if not task:
            return jsonify({
                'error': 'not_found',
                'message': 'Task not found'
            }), 404

        return jsonify({
            'task': task.to_dict()
        }), 200

    finally:
        db.close()


@tasks_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_task_stats():
    """获取任务统计信息"""
    db = next(get_db())
    try:
        repo = TaskRepository(db)
        stats = repo.get_stats()

        return jsonify({
            'stats': stats
        }), 200

    finally:
        db.close()


@tasks_bp.route('/status', methods=['GET'])
@jwt_required()
def get_tasks_by_status():
    """根据状态获取任务"""
    db = next(get_db())
    try:
        repo = TaskRepository(db)
        status = request.args.get('status', 'pending')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)

        tasks = repo.get_by_status(status, skip=skip, limit=limit)
        total = repo.count(status=status)

        return jsonify({
            'tasks': [task.to_dict() for task in tasks],
            'total': total
        }), 200

    finally:
        db.close()


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    """更新任务状态"""
    data = request.get_json()

    db = next(get_db())
    try:
        repo = TaskRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        task = repo.get_by_id(task_id)
        if not task:
            return jsonify({
                'error': 'not_found',
                'message': 'Task not found'
            }), 404

        # 更新字段
        update_data = {}
        if 'status' in data:
            update_data['status'] = data['status']
        if 'resource_name' in data:
            update_data['resource_name'] = data['resource_name']
        if 'resource_url' in data:
            update_data['resource_url'] = data['resource_url']
        if 'quark_save_path' in data:
            update_data['quark_save_path'] = data['quark_save_path']
        if 'error_msg' in data:
            update_data['error_msg'] = data['error_msg']

        if update_data:
            repo.update(task_id, **update_data)

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='update_task',
            resource_type='task',
            resource_id=str(task_id),
            status='success'
        )

        return jsonify({
            'message': 'Task updated successfully',
            'task': repo.get_by_id(task_id).to_dict()
        }), 200

    finally:
        db.close()


@tasks_bp.route('/batch', methods=['POST'])
@jwt_required()
def batch_update_tasks():
    """批量更新任务状态"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    status = data.get('status')
    action = data.get('action')

    if not task_ids or not status:
        return jsonify({
            'error': 'invalid_request',
            'message': 'task_ids and status are required'
        }), 400

    db = next(get_db())
    try:
        repo = TaskRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        updated_count = 0
        for task_id in task_ids:
            task = repo.get_by_id(task_id)
            if task:
                if action == 'retry' and status in ['pending', 'failed']:
                    # 重试：重置状态
                    repo.update(task_id, status='pending', error_msg=None)
                else:
                    repo.update(task_id, status=status)
                updated_count += 1

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='batch_update_tasks',
            details={'task_ids': task_ids, 'status': status, 'action': action},
            status='success'
        )

        return jsonify({
            'message': f'{updated_count} tasks updated',
            'updated_count': updated_count
        }), 200

    finally:
        db.close()


@tasks_bp.route('/batch/delete', methods=['POST'])
@jwt_required()
def batch_delete_tasks():
    """批量删除待手动任务"""
    from sqlalchemy import delete
    from models.catalog import TransferTask

    data = request.get_json()
    task_ids = data.get('task_ids', [])
    delete_all_pending_manual = data.get('delete_all', False)

    db = next(get_db())
    try:
        repo = TaskRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        if delete_all_pending_manual:
            # 删除所有 pending_manual 状态的任务
            db.query(TransferTask).filter(
                TransferTask.status == 'pending_manual'
            ).delete()
            deleted_count = db.query(TransferTask).filter(
                TransferTask.status == 'pending_manual'
            ).count()
        else:
            # 删除指定的任务
            deleted_count = 0
            for task_id in task_ids:
                task = repo.get_by_id(task_id)
                if task:
                    db.delete(task)
                    deleted_count += 1

        db.commit()

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='batch_delete_tasks',
            details={'task_ids': task_ids, 'delete_all': delete_all_pending_manual},
            status='success'
        )

        return jsonify({
            'message': f'{deleted_count} tasks deleted',
            'deleted_count': deleted_count
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({
            'error': 'delete_failed',
            'message': str(e)
        }), 500
    finally:
        db.close()


@tasks_bp.route('/batch/mark-synced', methods=['POST'])
@jwt_required()
def batch_mark_synced():
    """批量标记待手动任务为已同步"""
    from storage.database import CatalogDBv2

    data = request.get_json()
    task_ids = data.get('task_ids', [])
    mark_all = data.get('mark_all', False)

    db = next(get_db())
    try:
        repo = TaskRepository(db)
        log_repo = OperationLogRepository(db)
        sync_history = SyncHistory()
        current_user_id = get_jwt_identity()

        if mark_all:
            # 标记所有 pending_manual 状态的任务
            pending_manual_tasks = db.query(TransferTask).filter(
                TransferTask.status == 'pending_manual'
            ).all()
            task_ids = [task.task_id for task in pending_manual_tasks]

        marked_count = 0
        for task_id in task_ids:
            task = repo.get_by_id(task_id)
            if task and task.status == 'pending_manual':
                # 获取 catalog 信息
                catalog_repo = CatalogRepository(db)
                catalog_item = catalog_repo.get_by_id(task.catalog_item_id, task.addon_name)

                if catalog_item:
                    # 记录到 catalog_items 表（已同步完成的项目）
                    catalog_db = CatalogDBv2()
                    try:
                        item_data = {
                            'id': catalog_item.id,
                            'name': catalog_item.name,
                            'type': catalog_item.item_type,
                            'year': catalog_item.year,
                            'imdbId': catalog_item.imdb_id,
                            'poster': catalog_item.poster,
                        }
                        catalog_db.insert(item_data, task.addon_name)
                    finally:
                        catalog_db.close()

                    # 记录同步历史
                    sync_history.record_sync(
                        item_id=catalog_item.id,
                        addon_name=task.addon_name,
                        item_name=catalog_item.name,
                        item_type=catalog_item.item_type,
                        resource_title=task.resource_name or '',
                        resource_url=task.resource_url or '',
                        save_path=task.quark_save_path or '',
                        status='saved',
                        resolution=task.resolution,
                        size_gb=task.size_gb,
                        codec=task.codec,
                    )

                # 更新任务状态为 done
                repo.update(task_id, status='done')
                marked_count += 1

        db.commit()

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='batch_mark_synced',
            details={'task_ids': task_ids, 'mark_all': mark_all},
            status='success'
        )

        return jsonify({
            'message': f'{marked_count} tasks marked as synced',
            'marked_count': marked_count
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({
            'error': 'mark_failed',
            'message': str(e)
        }), 500
    finally:
        db.close()


@tasks_bp.route('/batch/retry', methods=['POST'])
@jwt_required()
def batch_retry():
    """批量重试失败任务"""
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    retry_all = data.get('retry_all', False)

    db = next(get_db())
    try:
        repo = TaskRepository(db)
        log_repo = OperationLogRepository(db)
        current_user_id = get_jwt_identity()

        if retry_all:
            # 重试所有 failed 状态的任务
            failed_tasks = db.query(TransferTask).filter(
                TransferTask.status == 'failed'
            ).all()
            task_ids = [task.task_id for task in failed_tasks]

        retried_count = 0
        for task_id in task_ids:
            task = repo.get_by_id(task_id)
            if task and task.status == 'failed':
                # 重置任务状态为 pending，清空错误信息
                repo.update(task_id, status='pending', error_msg=None)
                retried_count += 1

        db.commit()

        # 记录操作日志
        log_repo.create(
            user_id=current_user_id,
            action='batch_retry',
            details={'task_ids': task_ids, 'retry_all': retry_all},
            status='success'
        )

        return jsonify({
            'message': f'{retried_count} tasks retried',
            'retried_count': retried_count
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({
            'error': 'retry_failed',
            'message': str(e)
        }), 500
    finally:
        db.close()
