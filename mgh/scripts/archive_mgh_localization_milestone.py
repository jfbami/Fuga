import json
import sys
from pathlib import Path

workspace = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace / 'outputs'))
import MGH_Master_tools as archive_tools


def payload(connection, kind, key):
    row = connection.execute('SELECT payload_json FROM current_records WHERE kind=? AND record_key=?', (kind, key)).fetchone()
    if row is None:
        raise ValueError(f'Missing {kind}:{key}')
    return json.loads(row['payload_json'])


def main():
    directory = workspace / 'outputs/MGH_Project'
    manifest = json.loads((directory / 'localization/visual_map_v1/manifest.json').read_text())
    evaluation = json.loads((directory / 'localization/evaluation_v1/results.json').read_text())
    provenance = json.loads((directory / 'localization/environment_provenance.json').read_text())
    connection = archive_tools.connect(workspace / 'outputs/MGH_Master.sqlite')
    original_checksums_before = dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'"))
    if connection.execute("SELECT 1 FROM current_records WHERE kind='validation' AND record_key='b9dca4993d:learned_localization_v1'").fetchone():
        raise RuntimeError('This milestone has already been archived; inspect before making another revision.')
    with archive_tools.revision(connection, 'Create MGH working folder and living history/decisions log; archive DISK-LightGlue reference map, withheld-image evaluation, source/weight provenance, and independent-phone capture protocol.') as revision_id:
        count = 0
        for path in sorted(directory.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            relative = path.relative_to(directory).as_posix()
            role = 'processing_script' if path.suffix == '.py' else 'project_documentation' if path.suffix in {'.md', '.csv'} else 'analysis'
            state = 'draft' if path.suffix in {'.md', '.csv'} else 'research_only'
            archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/{relative}', role, state,
                manifest['scan_id'] if relative.startswith('localization/') else None)
            count += 1
        for path, logical in [(directory / 'PROJECT_LOG.md', 'project/PROJECT_LOG.md'),
                (workspace / 'AGENTS.md', 'project/AGENTS.md'), (workspace / 'outputs/MGH_Master_README.md', 'project/README.md')]:
            archive_tools.add_asset(connection, revision_id, path, logical, 'project_documentation', 'draft')
        for script in [Path(__file__).resolve(), workspace / 'work/prepare_mgh_localization_provenance.py', workspace / 'work/report_mgh_localization.py']:
            archive_tools.add_asset(connection, revision_id, script, f'project/MGH_Project/scripts/{script.name}', 'processing_script', 'research_only')
        for weight in provenance['weights']:
            path = workspace / 'work/mgh_model_weights/checkpoints' / weight['filename']
            archive_tools.add_asset(connection, revision_id, path, f'project/MGH_Project/localization/models/{path.name}', 'pretrained_model_weight', 'research_only')
        print(f'Embedded {count} project exports plus model weights and continuity documents', flush=True)
        put = lambda kind, key, value, state='draft', evidence=(): archive_tools.put_record(connection, revision_id, kind, key, value, state, evidence)
        manifest_asset = 'project/MGH_Project/localization/visual_map_v1/manifest.json'
        evaluation_asset = 'project/MGH_Project/localization/evaluation_v1/results.json'
        project = payload(connection, 'project', 'MGH')
        project.update(project_log_asset='project/PROJECT_LOG.md', organized_working_folder='outputs/MGH_Project',
            decision_log_policy='Append actual results and user/implementation decisions; retain superseded decisions and embed revisions transactionally.',
            current_milestone='Experimental single-scan reference map built; full pose test not passed; retrieval/depth consistency, independent phone photos, and doorway anchors pending',
            independent_phone_localization_validated=False, enabled_navigation=False)
        put('project', 'MGH', project, 'verified', ['project/PROJECT_LOG.md'])
        scan = payload(connection, 'scan', manifest['scan_id'])
        scan.update(visual_reference_map_asset=manifest_asset, visual_reference_state='experimental', ordinary_phone_localization_validated=False)
        put('scan', manifest['scan_id'], scan, 'draft', [manifest_asset, evaluation_asset])
        put('validation', f'{manifest["scan_id"]}:learned_localization_v1',
            {**{key: value for key, value in evaluation.items() if key != 'results'}, 'status': 'not_passed'}, 'research_only',
            [evaluation_asset, manifest_asset, 'project/MGH_Project/localization/implementation_checks.json',
                'project/MGH_Project/localization/environment_provenance.json'])
        put('task', 'build_visual_reference_map', dict(status='prototype_complete', scan_id=manifest['scan_id'],
            feature_extractor='pretrained DISK', matcher='pretrained LightGlue disk', reference_views=manifest['reference_count'],
            confident_3d_features=manifest['total_confident_3d_features'], training_performed=False,
            geometry_merge_performed=False, navigation_ready=False), 'research_only', [manifest_asset])
        put('task', 'validate_localization', dict(status='open',
            description='Evaluate independently captured original regular-phone photos with appropriate calibration, held out from mapping; measure false accepts and location/orientation error with independent reference locations.',
            current_internal_test_asset=evaluation_asset, independent_phone_test_passed=False), 'pending',
            ['project/MGH_Project/capture/REGULAR_PHONE_TEST.md', evaluation_asset])
        put('task', 'verify_416_entrance_for_demo', dict(status='open', room_key='MGH:4:416',
            description='Review actual entrance threshold and floor-plan correspondence before building/enabling a small route.',
            doorway_anchor=None, enabled_navigation=False), 'pending', ['project/MGH_Project/localization/doorway_review_queue.csv'])
        put('task', 'maintain_project_history', dict(status='ongoing', log_asset='project/PROJECT_LOG.md',
            update_trigger='Meaningful work or actual user/implementation decision while an agent is running',
            background_monitor_created=False), 'draft', ['project/PROJECT_LOG.md'])
        original_checksums_after = dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'"))
        if original_checksums_after != original_checksums_before:
            raise RuntimeError('Original scan assets changed unexpectedly; rolling back.')
    print('Transaction committed. Verifying all embedded checksums, integrity, and evidence links...', flush=True)
    verification = archive_tools.verify(connection)
    inventory = archive_tools.summary(connection)
    connection.close()
    receipt = dict(revision=revision_id, verification=verification, inventory=inventory,
        original_scan_checksums_unchanged=True, database_bytes=(workspace / 'outputs/MGH_Master.sqlite').stat().st_size)
    (workspace / 'outputs/MGH_Master_localization_update.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2), flush=True)
    if not verification['passed']:
        raise RuntimeError('Archive verification did not pass; inspect the receipt.')


if __name__ == '__main__':
    main()
