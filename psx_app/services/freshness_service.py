"""Refresh clean warm workers from the canonical cloud snapshot, never pending ones."""
from psx_app.services.cloud_sync_service import CloudSyncService


def check_cloud_freshness(db_path, cloud=None):
    cloud = cloud or CloudSyncService(db_path)
    if not cloud.is_configured():
        return {'status': 'LOCAL', 'changed': False, 'snapshot_id': None}
    base = cloud.base_state()
    if base.get('pending'):
        return {'status': 'PENDING', 'changed': False, 'snapshot_id': base.get('blob'),
                'message': 'Unsynced local changes are preserved. Download a snapshot and resolve cloud save before reloading.'}
    try:
        _head, _tree, remote_blob = cloud._remote_head()
        same_scope = base.get('repo') == cloud.repo and base.get('branch') == cloud.branch
        if base.get('initialized') and same_scope and base.get('blob') == remote_blob:
            return {'status': 'CURRENT', 'changed': False, 'snapshot_id': remote_blob}
        result = cloud.pull_latest_db_on_startup()
        updated = cloud.base_state()
        if result.get('error') or not updated.get('initialized') or updated.get('pending'):
            raise RuntimeError(result.get('error') or result.get('reason') or 'Snapshot refresh was not verified.')
        # Missing/invalid remote snapshots must not be treated as successful hydration.
        if remote_blob and not result.get('pulled'):
            raise RuntimeError(result.get('reason') or 'Remote snapshot was not restored.')
        return {'status': 'CURRENT', 'changed': True, 'snapshot_id': updated.get('blob')}
    except Exception as exc:
        return {'status': 'UNVERIFIED', 'changed': False, 'snapshot_id': base.get('blob'),
                'message': 'Cloud freshness could not be verified; local data was retained. ' + str(exc)}
