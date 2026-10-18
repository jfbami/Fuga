import json
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace / 'outputs'))
import MGH_Master_tools as archive_tools


def current(connection, kind, key):
    row = connection.execute('SELECT payload_json FROM current_records WHERE kind=? AND record_key=?', (kind, key)).fetchone()
    return json.loads(row['payload_json']) if row else {}


def main():
    base = workspace / 'outputs/MGH_Project'
    directory = base / 'localization'
    audit = json.loads((directory / 'audit_v2_retrieval_correspondence/results.json').read_text())
    connection = archive_tools.connect(workspace / 'outputs/MGH_Master.sqlite')
    if connection.execute("SELECT 1 FROM current_records WHERE kind='validation' AND record_key='b9dca4993d:retrieval_correspondence_audit'").fetchone():
        raise RuntimeError('Audit already archived.')
    originals = dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'"))
    with archive_tools.revision(connection, 'Audit v2 retrieval and cross-view 3D correspondences; confirm one-frame video/odometry offset; fix localizer association; build map v3 (not yet evaluated); preserve interrupted partial builds; paused at user request.') as revision_id:
        for path in [base / 'PROJECT_LOG.md', directory / 'README.md', directory / 'mgh_localizer.py', directory / 'doorway_review_queue.csv', directory / 'EVALUATION_PLAN_v3_v4.json']:
            archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/{path.relative_to(base).as_posix()}',
                'processing_script' if path.suffix == '.py' else 'project_documentation', 'research_only', 'b9dca4993d')
        for folder, state in [('audit_v2_retrieval_correspondence', 'diagnostic'), ('visual_map_v3', 'research_only'),
                ('visual_map_v3_interrupted_partial', 'diagnostic'), ('visual_map_v4_low_rotation_stopped_partial', 'diagnostic')]:
            for path in sorted((directory / folder).rglob('*')):
                if path.is_file():
                    archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/localization/{path.relative_to(directory).as_posix()}', 'analysis', state, 'b9dca4993d')
        for path, logical in [(base / 'PROJECT_LOG.md', 'project/PROJECT_LOG.md'), (workspace / 'AGENTS.md', 'project/AGENTS.md')]:
            archive_tools.add_asset(connection, revision_id, path, logical, 'project_documentation', 'draft')
        for name in ['audit_mgh_retrieval_correspondence.py', 'audit_mgh_crossview_geometry.py', 'probe_audit_source.py', 'probe_audit_timestamps.py',
                'probe_audit_turning.py', 'archive_mgh_retrieval_audit.py', 'audit_run.log', 'audit_run_attempt1_failed_refpair_indexing.log',
                'audit_crossview.log', 'build_v3_interrupted_session_end.log', 'build_v3_complete_v4_stopped.log']:
            archive_tools.add_asset(connection, revision_id, workspace / 'work' / name, f'project/MGH_Project/scripts/{name}', 'processing_script', 'diagnostic')

        def put(kind, key, payload, state='draft', evidence=()):
            archive_tools.put_record(connection, revision_id, kind, key, payload, state, evidence)

        report = 'project/MGH_Project/localization/audit_v2_retrieval_correspondence/AUDIT_REPORT.md'
        results = 'project/MGH_Project/localization/audit_v2_retrieval_correspondence/results.json'
        put('validation', 'b9dca4993d:retrieval_correspondence_audit', dict(status='diagnostic_complete', primary_row_minus_ordinal=audit['primary_row_minus_ordinal'],
            association_shift_test=audit['association_shift_test'], decisions=audit['decisions'], retrieval_summary=audit['retrieval_summary'],
            per_view_wrong_place_rejected_by_two_view_rule=True, acceptance_rules_changed=False, independent_phone_test_passed=False), 'diagnostic', [report, results])
        old = current(connection, 'validation', 'b9dca4993d:localization_v2_framefix')
        old.update(status='superseded_one_frame_offset', use_as_accuracy_evidence=False, historical_numbers_retained=True)
        put('validation', 'b9dca4993d:localization_v2_framefix', old, 'diagnostic', [report])
        timestamp = {item['scan_id']: item for item in audit['timestamp_alignment']}
        for scan_id in ['b9dca4993d', 'b43779c138', 'e1a70b754b']:
            scan = current(connection, 'scan', scan_id)
            item = timestamp[scan_id]
            scan.update(video_row_minus_decoded_ordinal=item['best_row_minus_ordinal'], video_association_conclusive=item['conclusive'],
                video_association_method='timestamp-gap fingerprint' + (' + geometric reprojection test' if scan_id == 'b9dca4993d' else ''))
            if scan_id == 'b9dca4993d':
                scan.update(visual_reference_map_asset='project/MGH_Project/localization/visual_map_v3/manifest.json', visual_reference_state='v3_association_fixed_not_yet_evaluated')
            put('scan', scan_id, scan, 'draft', [results])
        for row in connection.execute("SELECT record_key,payload_json FROM current_records WHERE kind='observation' AND record_key LIKE 'b9dca4993d:%'").fetchall():
            value = json.loads(row['payload_json'])
            if value.get('source_frame') is not None:
                value.update(source_decoded_video_ordinal=value['source_frame'], source_odometry_row=value['source_frame'] + 1,
                    association_note='source_frame is a decoded video ordinal; depth/pose row is ordinal + 1 (2026-10-17 audit).')
                put('observation', row['record_key'], value, 'draft', [report])
        stair = current(connection, 'floor_connection', 'MGH:STAIR1:3_4')
        stair.update(sign_source_odometry_rows=dict(lower=649, upper=2729), routing_enabled=False)
        put('floor_connection', 'MGH:STAIR1:3_4', stair, 'draft', [report])
        put('task', 'validate_localization', dict(status='open', paused_by_user=True,
            description='Evaluate visual_map_v3 on query sets A and B per EVALUATION_PLAN_v3_v4.json; optionally rebuild/evaluate low-rotation v4 on B. Then independent ordinary-phone photos with correct calibration; wrong-floor/out-of-map tests.',
            independent_phone_test_passed=False), 'pending', [report])
        if originals != dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'")):
            raise RuntimeError('Original scan checksums changed; rolling back.')
    verification = archive_tools.verify(connection)
    receipt = dict(revision=revision_id, verification=verification, inventory=archive_tools.summary(connection), original_scan_checksums_unchanged=True)
    connection.close()
    (workspace / 'outputs/MGH_Master_retrieval_audit_update.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(dict(revision=revision_id, verification=verification), indent=2))


if __name__ == '__main__':
    main()
