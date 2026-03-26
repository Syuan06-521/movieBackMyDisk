"""
history.py - 同步历史 API 路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, date, timedelta

from storage.repositories import SyncHistoryRepository, OperationLogRepository
from core.database import get_db
from flask_jwt_extended import get_jwt_identity

history_bp = Blueprint('history', __name__)


@history_bp.route('', methods=['GET'])
@jwt_required()
def get_history():
    """获取同步历史记录"""
    db = next(get_db())
    try:
        repo = SyncHistoryRepository(db)

        # 日期范围
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        status_filter = request.args.get('status')

        if not start_date_str:
            # 默认最近 7 天
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = date.today()

        records = repo.get_history(start_date, end_date, skip=skip, limit=limit, status=status_filter)
        total = repo.count(start_date, end_date, status=status_filter)

        return jsonify({
            'records': [record.to_dict() for record in records],
            'total': total
        }), 200

    finally:
        db.close()


@history_bp.route('/today', methods=['GET'])
@jwt_required()
def get_today_history():
    """获取今日同步记录"""
    db = next(get_db())
    try:
        repo = SyncHistoryRepository(db)

        records = repo.get_today_records()
        failures = repo.get_today_failures()

        return jsonify({
            'records': [record.to_dict() for record in records],
            'failures': [record.to_dict() for record in failures],
            'total': len(records),
            'failed_count': len(failures)
        }), 200

    finally:
        db.close()


@history_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_history_stats():
    """获取同步历史统计"""
    db = next(get_db())
    try:
        repo = SyncHistoryRepository(db)
        stats = repo.get_stats()

        return jsonify({
            'stats': stats
        }), 200

    finally:
        db.close()


@history_bp.route('/failed', methods=['GET'])
@jwt_required()
def get_failed_history():
    """获取失败记录"""
    db = next(get_db())
    try:
        repo = SyncHistoryRepository(db)

        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)

        if not start_date_str:
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = date.today()

        # 获取失败记录
        records = repo.get_history(start_date, end_date, skip=skip, limit=limit)
        failed_records = [r for r in records if r.status == 'failed']

        return jsonify({
            'records': [record.to_dict() for record in failed_records],
            'total': len(failed_records)
        }), 200

    finally:
        db.close()


@history_bp.route('/export', methods=['GET'])
@jwt_required()
def export_history():
    """导出同步历史（CSV 格式）"""
    from io import StringIO
    import csv

    db = next(get_db())
    try:
        repo = SyncHistoryRepository(db)

        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        if not start_date_str:
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = date.today()

        records = repo.get_history(start_date, end_date, skip=0, limit=10000)

        # 生成 CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Item ID', 'Addon Name', 'Item Name', 'Item Type',
            'Resource Title', 'Resource URL', 'Save Path', 'Resolution',
            'Size (GB)', 'Codec', 'Status', 'Sync Date', 'Error Reason'
        ])

        for record in records:
            writer.writerow([
                record.id,
                record.item_id,
                record.addon_name,
                record.item_name,
                record.item_type,
                record.resource_title,
                record.resource_url,
                record.save_path,
                record.resolution,
                record.size_gb,
                record.codec,
                record.status,
                record.sync_date.isoformat() if record.sync_date else '',
                record.error_reason or ''
            ])

        csv_content = output.getvalue()

        return csv_content, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=sync_history_{start_date}_to_{end_date}.csv'
        }

    finally:
        db.close()
