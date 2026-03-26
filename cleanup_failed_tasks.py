"""清空所有失败状态的任务记录"""
from core.database import get_db_session
from models.catalog import TransferTask

db = get_db_session()
try:
    result = db.query(TransferTask).filter(TransferTask.status == 'failed').delete(synchronize_session=False)
    db.commit()
    print(f'已删除 {result} 条失败任务记录')
except Exception as e:
    db.rollback()
    print(f'删除失败：{e}')
finally:
    db.close()
