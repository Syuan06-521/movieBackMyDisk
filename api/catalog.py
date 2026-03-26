"""
catalog.py - 影视目录 API 路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from storage.repositories import CatalogRepository, OperationLogRepository
from core.database import get_db
from flask_jwt_extended import get_jwt_identity

catalog_bp = Blueprint('catalog', __name__)


@catalog_bp.route('', methods=['GET'])
@jwt_required()
def get_catalog():
    """获取影视目录列表"""
    db = next(get_db())
    try:
        repo = CatalogRepository(db)
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        addon_name = request.args.get('addon_name')
        item_type = request.args.get('type')
        search = request.args.get('search')

        items = repo.get_all(
            skip=skip,
            limit=limit,
            addon_name=addon_name,
            item_type=item_type,
            search=search
        )

        return jsonify({
            'items': [item.to_dict() for item in items],
            'total': repo.count(addon_name=addon_name, item_type=item_type)
        }), 200

    finally:
        db.close()


@catalog_bp.route('/<item_id>', methods=['GET'])
@jwt_required()
def get_catalog_item(item_id):
    """获取影视详情"""
    addon_name = request.args.get('addon_name')

    if not addon_name:
        return jsonify({
            'error': 'invalid_request',
            'message': 'addon_name parameter is required'
        }), 400

    db = next(get_db())
    try:
        repo = CatalogRepository(db)
        item = repo.get_by_id(item_id, addon_name)

        if not item:
            return jsonify({
                'error': 'not_found',
                'message': 'Item not found'
            }), 404

        return jsonify({
            'item': item.to_dict()
        }), 200

    finally:
        db.close()


@catalog_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_catalog_stats():
    """获取目录统计信息"""
    db = next(get_db())
    try:
        repo = CatalogRepository(db)
        stats = repo.get_stats()

        return jsonify({
            'stats': stats
        }), 200

    finally:
        db.close()


@catalog_bp.route('/types', methods=['GET'])
@jwt_required()
def get_item_types():
    """获取影视类型列表"""
    db = next(get_db())
    try:
        repo = CatalogRepository(db)

        # 获取所有类型
        from models.catalog import CatalogItem
        from sqlalchemy import distinct
        types = db.query(distinct(CatalogItem.item_type)).all()

        return jsonify({
            'types': [t[0] for t in types]
        }), 200

    finally:
        db.close()
