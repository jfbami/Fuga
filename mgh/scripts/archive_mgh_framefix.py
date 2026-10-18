import json
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace / 'outputs'))
import MGH_Master_tools as archive_tools


def current(connection, kind, key):
    row = connection.execute('SELECT payload_json FROM current_records WHERE kind=? AND record_key=?', (kind, key)).fetchone()
    if row is None:
        raise ValueError(f'Missing record {kind}:{key}')
    return json.loads(row['payload_json'])


def main():
    base = workspace / 'outputs/MGH_Project'
    directory = base / 'localization'
    diagnostic = json.loads((directory / 'frame_index_diagnostic/results.json').read_text())
    manifest = json.loads((directory / 'visual_map_v2/manifest.json').read_text())
    evaluation = json.loads((directory / 'evaluation_v2_framefix/results.json').read_text())
    corrections = {row['requested_frame']: row['matching_actual_ordinals'][0] for row in diagnostic['results'] if len(row['matching_actual_ordinals']) == 1}
    connection = archive_tools.connect(workspace / 'outputs/MGH_Master.sqlite')
    if connection.execute("SELECT 1 FROM current_records WHERE kind='validation' AND record_key='b9dca4993d:localization_v2_framefix'").fetchone():
        raise RuntimeError('Frame-fix milestone already archived; preserve prior revisions.')
    originals = dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'"))
    with archive_tools.revision(connection, 'Fix RGB-depth-pose association using sequential decoding; invalidate random-seek localization/registration diagnostics, correct sign-frame provenance, preserve baseline history, and archive corrected evaluation.') as revision_id:
        for path in [base / 'PROJECT_LOG.md', directory / 'README.md', directory / 'mgh_localizer.py']:
            archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/{path.relative_to(base).as_posix()}',
                'processing_script' if path.suffix == '.py' else 'project_documentation', 'research_only', 'b9dca4993d')
        for folder in ['visual_map_v2', 'evaluation_v2_framefix', 'frame_index_diagnostic']:
            for path in sorted((directory / folder).rglob('*')):
                if path.is_file():
                    archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/localization/{path.relative_to(directory).as_posix()}',
                        'analysis', 'research_only' if folder != 'frame_index_diagnostic' else 'diagnostic', 'b9dca4993d')
        for folder in ['visual_map_v1', 'evaluation_v1']:
            for path in sorted((directory / folder).rglob('*')):
                if path.is_file():
                    logical = f'project/MGH_Project/localization/{path.relative_to(directory).as_posix()}'
                    asset = connection.execute('SELECT role FROM current_assets WHERE logical_path=?', (logical,)).fetchone()
                    archive_tools.add_asset(connection, revision_id, path, logical, asset['role'] if asset else 'analysis', 'diagnostic', 'b9dca4993d')
        for path, logical in [(base / 'PROJECT_LOG.md', 'project/PROJECT_LOG.md'),
                (workspace / 'AGENTS.md', 'project/AGENTS.md'), (workspace / 'outputs/MGH_Master_README.md', 'project/README.md'),
                (workspace / 'outputs/mgh_staircase_review/REVIEW.md', 'scans/b9dca4993d/analysis/review/REVIEW.md')]:
            archive_tools.add_asset(connection, revision_id, path, logical, 'project_documentation', 'draft')
        for name in ['diagnose_mgh_frame_index.py', 'report_mgh_framefix.py', 'archive_mgh_framefix.py']:
            path = workspace / 'work' / name
            archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/scripts/{name}', 'processing_script', 'research_only')
        put = lambda kind, key, payload, state='draft', evidence=(): archive_tools.put_record(connection, revision_id, kind, key, payload, state, evidence)
        diagnostic_asset = 'project/MGH_Project/localization/frame_index_diagnostic/results.json'
        report_asset = 'project/MGH_Project/localization/evaluation_v2_framefix/FRAME_FIX_REPORT.md'
        evaluation_asset = 'project/MGH_Project/localization/evaluation_v2_framefix/results.json'
        manifest_asset = 'project/MGH_Project/localization/visual_map_v2/manifest.json'
        for key in ['b9dca4993d:learned_localization_v1', 'b9dca4993d:registration_attempt']:
            old = current(connection, 'validation', key)
            old.update(status='invalidated_frame_association_bug', reason='Random video seeking paired incorrect RGB frames with requested-index depth/calibration/poses.',
                use_as_accuracy_evidence=False, superseding_evaluation=evaluation_asset if key.endswith('learned_localization_v1') else None,
                historical_numbers_retained=True)
            put('validation', key, old, 'diagnostic', [diagnostic_asset, report_asset])
        put('validation', 'b9dca4993d:localization_v2_framefix', {**{key: value for key, value in evaluation.items() if key != 'results'},
            'status': 'internal_only_not_phone_validated', 'frame_association_corrected': True}, 'research_only', [evaluation_asset, manifest_asset, diagnostic_asset, report_asset])
        put('validation', 'b9dca4993d:frame_index_audit', {key: value for key, value in diagnostic.items() if key != 'results'}, 'diagnostic', [diagnostic_asset])
        observations = connection.execute("SELECT record_key,payload_json FROM current_records WHERE kind='observation' AND record_key LIKE 'b9dca4993d:%'").fetchall()
        for observation in observations:
            value = json.loads(observation['payload_json'])
            requested = value.get('source_frame')
            if requested is None:
                continue
            actual = corrections.get(requested)
            value.update(legacy_seek_request_frame=requested, source_frame=actual,
                source_frame_association_verified=actual is not None,
                provenance_correction='Legacy seek label replaced with exact pixel-hash-matched sequential ordinal; unresolved source indices stay unknown.',
                doorway_anchor=None)
            evidence = [diagnostic_asset]
            if actual is not None:
                evidence.append(f'project/MGH_Project/localization/frame_index_diagnostic/corrected_requested_{requested:06d}_actual_{actual:06d}.jpg')
            put('observation', observation['record_key'], value, 'draft', evidence)
        stair = current(connection, 'floor_connection', 'MGH:STAIR1:3_4')
        stair.update(sign_source_frame_ordinals=dict(lower=corrections[610], upper=corrections[2565]),
            frame_provenance='Corrected by exact pixel hashes; old 610/2565 were random-seek request labels.', routing_enabled=False)
        put('floor_connection', 'MGH:STAIR1:3_4', stair, 'draft', [diagnostic_asset, report_asset])
        alignment = current(connection, 'alignment', 'MGH:b9dca4993d_to_b43779c138')
        alignment.update(status='pending_correctly_indexed_registration', diagnostic_summary='Prior random-seek registration trial invalidated due to RGB/pose/depth association; rerun needed.',
            usable_for_geometry_merge=False, matrix=None)
        put('alignment', 'MGH:b9dca4993d_to_b43779c138', alignment, 'pending', [diagnostic_asset, report_asset])
        scan = current(connection, 'scan', 'b9dca4993d')
        scan.update(visual_reference_map_asset=manifest_asset, visual_reference_state='experimental_sequential_index_corrected')
        put('scan', 'b9dca4993d', scan, 'draft', [manifest_asset, evaluation_asset])
        project = current(connection, 'project', 'MGH')
        project.update(current_milestone='Frame-association bug corrected; reference map v2 and same-recording results saved; independent-phone localization and navigation still pending',
            independent_phone_localization_validated=False, enabled_navigation=False)
        put('project', 'MGH', project, 'verified', ['project/PROJECT_LOG.md', report_asset])
        put('task', 'build_visual_reference_map', dict(status='prototype_complete', scan_id='b9dca4993d',
            current_reference_map_asset=manifest_asset, reference_views=manifest['reference_count'], confident_3d_features=manifest['total_confident_3d_features'],
            sequential_indexing=True, navigation_ready=False), 'research_only', [manifest_asset])
        put('task', 'register_staircase_scan', dict(status='open', description='Rerun cross-scan registration with sequentially selected RGB and correctly indexed depth/poses; old diagnostic invalidated. No merge until distributed overlap reviewed.'), 'pending', [report_asset])
        put('task', 'validate_localization', dict(status='open', description='Investigate remaining retrieval/multiview rejections; evaluate fresh ordinary-phone photos with correct calibration and independent reference locations; include wrong-floor/out-of-map failures.',
            current_internal_test_asset=evaluation_asset, independent_phone_test_passed=False), 'pending', [evaluation_asset, report_asset])
        after = dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'"))
        if originals != after:
            raise RuntimeError('Original scan checksum registry changed; rolling back.')
    print('Corrected records committed. Verifying all archive checksums and integrity...', flush=True)
    verification = archive_tools.verify(connection)
    summary = archive_tools.summary(connection)
    connection.close()
    receipt = dict(revision=revision_id, verification=verification, inventory=summary, original_scan_checksums_unchanged=True)
    (workspace / 'outputs/MGH_Master_framefix_update.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2), flush=True)
    if not verification['passed']:
        raise RuntimeError('Archive verification failed; inspect receipt.')


if __name__ == '__main__':
    main()
