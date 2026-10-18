"""Append evaluation artifacts and current records to the sole canonical archive."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'outputs'))
import MGH_Master_tools as archive


def main():
    base = ROOT / 'outputs/MGH_Project'
    local = base / 'localization'
    comparison = json.loads((local / 'evaluation_v3_v4_comparison/summary.json').read_text())
    phone_summary = json.loads((local / 'evaluation_independent_phone_430_440/summary.json').read_text())
    phone_manifest = json.loads((base / 'capture/independent_phone_20261017/manifest.json').read_text())
    connection = archive.connect(ROOT / 'outputs/MGH_Master.sqlite')

    def current(kind, key):
        row = connection.execute('SELECT payload_json FROM current_records WHERE kind=? AND record_key=?', (kind, key)).fetchone()
        return json.loads(row['payload_json']) if row else {}

    if connection.execute('SELECT MAX(id) FROM revisions').fetchone()[0] != 7:
        raise RuntimeError('Expected revision 7; inspect concurrent archive edits before proceeding.')
    originals = dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'"))
    before = dict(connection.execute('SELECT kind,COUNT(*) FROM records GROUP BY kind'))
    with archive.revision(connection, 'Evaluate v3 A/B and low-rotation v4 B; preserve two independent iPhone 14 originals and diagnostics; add existing-app localization backend; embed D016-D019/current records with routing disabled and original checksums intact.') as revision:
        def add(source, logical, role='analysis', state='research_only', scan='b9dca4993d'):
            return archive.add_asset(connection, revision, source, logical, role, state, scan)

        for relative in ['PROJECT_LOG.md', 'localization/README.md', 'localization/PHONE_APP_INTERFACE.md',
                         'localization/phone_localizer.py', 'localization/serve_phone_localizer.py']:
            add(base / relative, f'project/MGH_Project/{relative}', 'processing_script' if relative.endswith('.py') else 'project_documentation')
        for path, logical in [(base / 'PROJECT_LOG.md', 'project/PROJECT_LOG.md'),
                              (ROOT / 'AGENTS.md', 'project/AGENTS.md'),
                              (ROOT / 'outputs/MGH_Master_README.md', 'project/MGH_Master_README.md')]:
            add(path, logical, 'project_documentation', 'draft', None)
        for folder in ['evaluation_v3_setA', 'evaluation_v3_setB', 'visual_map_v4_low_rotation', 'evaluation_v4_setB', 'evaluation_v3_v4_comparison', 'evaluation_independent_phone_430_440']:
            for path in sorted((local / folder).rglob('*')):
                if path.is_file():
                    add(path, f'project/MGH_Project/localization/{path.relative_to(local).as_posix()}')
        for path in sorted((base / 'capture/independent_phone_20261017').rglob('*')):
            if path.is_file():
                if path.suffix.lower() == '.heic':
                    expected = next(p['sha256'] for p in phone_manifest['photos'] if p['original_filename'] == path.name)
                    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                        raise RuntimeError('Independent original checksum mismatch.')
                add(path, f'project/MGH_Project/{path.relative_to(base).as_posix()}',
                    'original_validation_photo' if path.suffix.lower() == '.heic' else 'validation_photo_derivative', scan=None)
        for name in ['run_mgh_declared_evaluations.py', 'report_mgh_v3_v4.py', 'archive_mgh_v3_v4.py', 'prepare_mgh_v3_v4_handoff.py',
                     'evaluate_v3_setA.log', 'evaluate_v3_setB.log', 'build_v4_low_rotation.log', 'evaluate_v4_low_rotation_setB.log',
                     'prepare_mgh_phone_photos.py', 'evaluate_mgh_phone_photos.py', 'evaluate_mgh_phone_v4.py',
                     'diagnose_mgh_phone_440_exhaustive.py', 'inspect_mgh_440_reference_coverage.py', 'report_mgh_phone_photos.py',
                     'test_mgh_phone_localizer.py', 'test_mgh_phone_service.py', 'smoke_mgh_phone_http.py',
                     'evaluate_independent_phone_430_440.log', 'evaluate_mgh_phone_v4.log', 'diagnose_mgh_phone_440_exhaustive.log',
                     'test_mgh_phone_localizer.log', 'test_mgh_phone_service.log', 'smoke_mgh_phone_http.log']:
            add(ROOT / 'work' / name, f'project/MGH_Project/scripts/{name}', 'processing_script' if name.endswith('.py') else 'processing_log')
        add(ROOT / 'work/440_scan_coverage.jpg', 'project/MGH_Project/localization/evaluation_independent_phone_430_440/440_scan_coverage.jpg')
        add(ROOT / 'work/IMG_5385_reference_check.jpg', 'project/MGH_Project/localization/evaluation_independent_phone_430_440/IMG_5385_reference_check.jpg')

        report = 'project/MGH_Project/localization/evaluation_v3_v4_comparison/EVALUATION_REPORT.md'
        summary = 'project/MGH_Project/localization/evaluation_v3_v4_comparison/summary.json'

        def put(kind, key, value, state='draft', evidence=(report, summary)):
            archive.put_record(connection, revision, kind, key, value, state, evidence)

        for run in comparison['runs']:
            key = f"b9dca4993d:localization_{run['map_variant']}_set{run['query_set_label']}"
            put('validation', key, dict(run, status='complete_same_recording_research', acceptance_thresholds_changed=False,
                use_as_surveyed_accuracy_evidence=False), 'research_only', [report, 'project/MGH_Project/localization/' + run['results_asset']])
        put('validation', 'b9dca4993d:v3_v4_evaluation_protocol', comparison, 'research_only')
        phone_report = 'project/MGH_Project/localization/evaluation_independent_phone_430_440/PHONE_REPORT.md'
        put('validation', 'MGH:independent_phone_430_440', phone_summary, 'research_only', [phone_report,
            'project/MGH_Project/localization/evaluation_independent_phone_430_440/summary.json'])
        for photo, number in zip(phone_manifest['photos'], ['430', '440']):
            original = 'project/MGH_Project/capture/independent_phone_20261017/originals/' + photo['original_filename']
            observation = dict(room_key=f'MGH:4:{number}', source_photo_asset=original,
                source_sha256=photo['sha256'], location_description=photo['user_location'],
                source='user location statement plus visual signed-doorway review',
                camera_position_scan_m=None, facing_direction=None, doorway_anchor_verified=False,
                mapping_reference=False, camera_calibration_verified=False)
            put('observation', f'independent_phone:{Path(photo["original_filename"]).stem}:{number}', observation, evidence=[original, phone_report])
            room = current('room', f'MGH:4:{number}')
            room.update(independent_phone_doorway_context_asset=original, doorway_anchor_verified=False,
                routing_enabled=False)
            if number == '440':
                room.update(label='440 Team & Quiet Labs', observed_sign_text='440 Team & Quiet Labs')
                room['voice_aliases'] = list(dict.fromkeys(room.get('voice_aliases', []) + ['Team & Quiet Labs', 'Team and Quiet Labs']))
            put('room', f'MGH:4:{number}', room, evidence=[original, phone_report])
        project = current('project', 'MGH')
        project.update(current_milestone='v3 A/B and v4 B evaluated; two independent iPhone 14 photos diagnosed (430 hypothesis, 440 unresolved); existing-app backend added; calibrated live guidance pending',
            enabled_navigation=False, independent_phone_localization_validated=False,
            team_handoff=dict(repository='jfbami/Fuga', branch='mgh-localization', pull_request='https://github.com/jfbami/Fuga/pull/1',
                              excluded=['canonical master', 'original scan ZIPs', 'floor plans']),
            latest_evaluation_summary_asset=summary,
            independent_photo_diagnostics_asset=phone_report,
            app_goal='Destination arrow follows corridor path; vibration signals reduction in remaining path distance.',
            external_navigation_branch=dict(ref='nav/route-guidance', inspected_commit='d7229ac',
                frame='plan meters and separate ARWorldMap', registered_to_staircase_scan=False),
            offered_new_floor_data=dict(floors=[2,3], received=False, floor_plans_publication_allowed=False))
        put('project', 'MGH', project, 'verified')
        scan = current('scan', 'b9dca4993d')
        scan.update(visual_reference_state='v3_and_v4_evaluated_same_recording_only',
            ordinary_phone_localization_validated=False, latest_evaluation_summary_asset=summary,
            visual_reference_variant_asset='project/MGH_Project/localization/visual_map_v4_low_rotation/manifest.json')
        put('scan', 'b9dca4993d', scan)
        build = current('task', 'build_visual_reference_map')
        build.update(current_reference_map_asset='project/MGH_Project/localization/visual_map_v3/manifest.json',
            reference_views=125, confident_3d_features=65708, status='prototype_evaluated', navigation_ready=False,
            variant_map_asset='project/MGH_Project/localization/visual_map_v4_low_rotation/manifest.json')
        put('task', 'build_visual_reference_map', build, 'research_only')
        task = current('task', 'validate_localization')
        task.update(paused_by_user=False, status='open', predeclared_v3_v4_evaluation_complete=True,
            independent_phone_test_passed=False, independent_photo_count_received=2, query_set_B_consumed=True,
            description='v3 A/B and v4 B complete; two iPhone 14 photos diagnosed, 430 numerical hypothesis and 440 unresolved. Verified query calibration, known positions, stable live tracking and wrong-floor/out-of-map tests remain pending. Later tuned variants require fresh held-out photos; routing disabled.')
        put('task', 'validate_localization', task, 'pending')
        put('task', 'receive_floor2_floor3_data', dict(status='awaiting_user_files', floors=[2,3],
            description='User offered floor-2/3 plans and scan originals. Add to the sole master with provenance/separate scan frames when received; keep floor plans private.'), 'pending')
        # Correct a stale current summary without erasing the earlier historical record.
        initial = current('validation', 'MGH:4:camera_localization_initial')
        initial.update(status='historical_same_recording_one_frame_offset_not_rerun',
            video_association_note='iLounge decoded ordinal i corresponds to depth/pose row i+1; original SIFT run used row i.',
            use_as_accuracy_evidence=False, historical_numbers_retained=True)
        put('validation', 'MGH:4:camera_localization_initial', initial, 'diagnostic')
        if originals != dict(connection.execute("SELECT logical_path,sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE role='original_scan_zip'")):
            raise RuntimeError('Original scan checksums changed; rollback required.')
        if any(json.loads(p).get('enabled') for (p,) in connection.execute("SELECT payload_json FROM current_records WHERE kind='navigation_edge'")):
            raise RuntimeError('Unexpected enabled routing edge.')
    verification = archive.verify(connection)
    receipt = dict(revision=revision, verification=verification, inventory=archive.summary(connection),
        original_scan_checksums_unchanged=True, original_scan_checksums=originals,
        previous_record_version_counts=before, results=comparison, independent_phone_diagnostics=phone_summary)
    connection.close()
    (ROOT / 'outputs/MGH_Master_v3_v4_update.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(dict(revision=revision, verification=verification), indent=2))
    if not verification['passed']:
        raise RuntimeError('Post-commit archive verification failed; do not publish a passing claim.')


if __name__ == '__main__':
    main()
