import argparse
import csv
import hashlib
import io
import json
import mimetypes
import sqlite3
import sys
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


FORMAT_VERSION = 1
RECORD_KINDS = {'project', 'building', 'floor', 'scan', 'coordinate_frame', 'alignment', 'room', 'landmark', 'observation', 'area', 'navigation_node', 'navigation_edge', 'floor_connection', 'measurement', 'validation', 'task'}
REVIEW_STATES = {'draft', 'verified', 'unassigned', 'rejected', 'diagnostic', 'research_only', 'pending'}
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions(
    id INTEGER PRIMARY KEY, created_utc TEXT NOT NULL, actor TEXT NOT NULL,
    description TEXT NOT NULL, parent_id INTEGER REFERENCES revisions(id));
CREATE TABLE IF NOT EXISTS blobs(
    id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, byte_count INTEGER NOT NULL,
    content BLOB NOT NULL, CHECK(length(content)=byte_count));
CREATE TABLE IF NOT EXISTS assets(
    id INTEGER PRIMARY KEY, logical_path TEXT NOT NULL, revision_id INTEGER NOT NULL REFERENCES revisions(id),
    blob_id INTEGER NOT NULL REFERENCES blobs(id), media_type TEXT NOT NULL, source_path TEXT,
    role TEXT NOT NULL, review_state TEXT NOT NULL, scan_id TEXT,
    UNIQUE(logical_path, revision_id));
CREATE INDEX IF NOT EXISTS asset_path_revision ON assets(logical_path, revision_id);
CREATE TABLE IF NOT EXISTS records(
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, record_key TEXT NOT NULL,
    revision_id INTEGER NOT NULL REFERENCES revisions(id), review_state TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), UNIQUE(kind, record_key, revision_id));
CREATE INDEX IF NOT EXISTS record_key_revision ON records(kind, record_key, revision_id);
CREATE TABLE IF NOT EXISTS record_assets(
    record_id INTEGER NOT NULL REFERENCES records(id), asset_id INTEGER NOT NULL REFERENCES assets(id),
    role TEXT NOT NULL, PRIMARY KEY(record_id, asset_id, role));
CREATE VIEW IF NOT EXISTS current_assets AS
    SELECT asset.* FROM assets asset WHERE NOT EXISTS
    (SELECT 1 FROM assets newer WHERE newer.logical_path=asset.logical_path AND newer.revision_id>asset.revision_id);
CREATE VIEW IF NOT EXISTS current_records AS
    SELECT record.* FROM records record WHERE NOT EXISTS
    (SELECT 1 FROM records newer WHERE newer.kind=record.kind AND newer.record_key=record.record_key AND newer.revision_id>record.revision_id);
'''


def connect(path, readonly=False):
    path = Path(path).resolve()
    if readonly:
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    else:
        connection = sqlite3.connect(path)
        connection.execute('PRAGMA journal_mode=DELETE')
        connection.execute('PRAGMA synchronous=FULL')
    connection.execute('PRAGMA foreign_keys=ON')
    connection.row_factory = sqlite3.Row
    return connection


def initialize(connection):
    connection.executescript(SCHEMA)
    connection.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('format', 'MGH embedded building archive'))
    connection.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('format_version', str(FORMAT_VERSION)))
    connection.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('canonical_building', 'Mary Gates Hall'))
    connection.commit()


@contextmanager
def revision(connection, description, actor='Codex'):
    connection.execute('BEGIN IMMEDIATE')
    try:
        parent = connection.execute('SELECT MAX(id) FROM revisions').fetchone()[0]
        cursor = connection.execute('INSERT INTO revisions(created_utc,actor,description,parent_id) VALUES (?,?,?,?)',
            (datetime.now(timezone.utc).isoformat(), actor, description, parent))
        yield cursor.lastrowid
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def normalize_logical_path(value):
    normalized = value.replace('\\', '/')
    if not normalized or normalized.startswith('/') or ':' in normalized or any(part in {'', '.', '..'} for part in normalized.split('/')):
        raise ValueError('Archive paths must be relative and must not contain traversal components.')
    return normalized


def add_asset(connection, revision_id, source, logical_path, role, review_state='draft', scan_id=None):
    source = Path(source).resolve()
    logical_path = normalize_logical_path(logical_path)
    expected_size = source.stat().st_size
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    existing_blob = connection.execute('SELECT id,byte_count FROM blobs WHERE sha256=?', (digest,)).fetchone()
    if existing_blob:
        if existing_blob['byte_count'] != expected_size:
            raise RuntimeError('Checksum/size collision in embedded asset.')
        blob_id = existing_blob['id']
    else:
        cursor = connection.execute('INSERT INTO blobs(sha256,byte_count,content) VALUES (?,?,zeroblob(?))', (digest, expected_size, expected_size))
        blob_id = cursor.lastrowid
        written_digest = hashlib.sha256()
        with source.open('rb') as stream, connection.blobopen('blobs', 'content', blob_id) as blob:
            while chunk := stream.read(1024 * 1024):
                blob.write(chunk)
                written_digest.update(chunk)
        if written_digest.hexdigest() != digest or source.stat().st_size != expected_size:
            raise RuntimeError('Source changed while it was being imported; transaction rolled back.')
    previous = connection.execute('SELECT * FROM current_assets WHERE logical_path=?', (logical_path,)).fetchone()
    if previous and previous['blob_id'] == blob_id and previous['role'] == role and previous['review_state'] == review_state and previous['scan_id'] == scan_id:
        return previous['id']
    cursor = connection.execute('INSERT INTO assets(logical_path,revision_id,blob_id,media_type,source_path,role,review_state,scan_id) VALUES (?,?,?,?,?,?,?,?)',
        (logical_path, revision_id, blob_id, mimetypes.guess_type(source.name)[0] or 'application/octet-stream', str(source), role, review_state, scan_id))
    return cursor.lastrowid


def put_record(connection, revision_id, kind, key, payload, review_state='draft', evidence=()):
    if kind not in RECORD_KINDS or review_state not in REVIEW_STATES:
        raise ValueError('Unknown record kind or review state.')
    if not isinstance(payload, dict) or not key:
        raise ValueError('Records require a nonempty key and a JSON object.')
    if kind == 'navigation_edge' and payload.get('enabled') and review_state != 'verified':
        raise ValueError('Enabled navigation edges require verified review state.')
    if kind == 'alignment' and payload.get('usable_for_geometry_merge') and review_state != 'verified':
        raise ValueError('Geometry merge requires a verified alignment.')
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    cursor = connection.execute('INSERT INTO records(kind,record_key,revision_id,review_state,payload_json) VALUES (?,?,?,?,?)',
        (kind, key, revision_id, review_state, encoded))
    for logical_path in evidence:
        asset = connection.execute('SELECT id FROM current_assets WHERE logical_path=?', (normalize_logical_path(logical_path),)).fetchone()
        if not asset:
            raise ValueError(f'Missing evidence asset: {logical_path}')
        connection.execute('INSERT INTO record_assets VALUES (?,?,?)', (cursor.lastrowid, asset['id'], 'evidence'))
    return cursor.lastrowid


def export_asset(connection, logical_path, destination, revision_id=None):
    logical_path = normalize_logical_path(logical_path)
    if revision_id is None:
        asset = connection.execute('SELECT * FROM current_assets WHERE logical_path=?', (logical_path,)).fetchone()
    else:
        asset = connection.execute('SELECT * FROM assets WHERE logical_path=? AND revision_id<=? ORDER BY revision_id DESC LIMIT 1', (logical_path, revision_id)).fetchone()
    if not asset:
        raise ValueError(f'Unknown asset: {logical_path}')
    blob_info = connection.execute('SELECT sha256,byte_count FROM blobs WHERE id=?', (asset['blob_id'],)).fetchone()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with destination.open('xb') as stream, connection.blobopen('blobs', 'content', asset['blob_id'], readonly=True) as blob:
        while chunk := blob.read(1024 * 1024):
            stream.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != blob_info['sha256']:
        raise RuntimeError('Export checksum mismatch.')
    return {'destination': str(destination), 'sha256': digest.hexdigest()}


def verify(connection):
    integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
    foreign_keys = [tuple(row) for row in connection.execute('PRAGMA foreign_key_check')]
    errors = []
    checked_bytes = 0
    blobs = connection.execute('SELECT id,sha256,byte_count FROM blobs ORDER BY id').fetchall()
    for info in blobs:
        digest = hashlib.sha256()
        count = 0
        with connection.blobopen('blobs', 'content', info['id'], readonly=True) as blob:
            while chunk := blob.read(1024 * 1024):
                digest.update(chunk)
                count += len(chunk)
        checked_bytes += count
        if digest.hexdigest() != info['sha256'] or count != info['byte_count']:
            errors.append(info['id'])
    return {'integrity_check': integrity, 'foreign_key_errors': foreign_keys, 'blob_checksum_errors': errors,
        'blobs_verified': len(blobs), 'embedded_bytes_verified': checked_bytes,
        'passed': integrity == 'ok' and not foreign_keys and not errors}


def summary(connection):
    return {'format_version': FORMAT_VERSION,
        'latest_revision': connection.execute('SELECT MAX(id) FROM revisions').fetchone()[0],
        'assets_current': connection.execute('SELECT COUNT(*) FROM current_assets').fetchone()[0],
        'assets_historical_versions': connection.execute('SELECT COUNT(*) FROM assets').fetchone()[0],
        'embedded_unique_bytes': connection.execute('SELECT COALESCE(SUM(byte_count),0) FROM blobs').fetchone()[0],
        'records_by_kind': dict(connection.execute('SELECT kind,COUNT(*) FROM current_records GROUP BY kind')),
        'scans': [json.loads(row['payload_json']) for row in connection.execute("SELECT payload_json FROM current_records WHERE kind='scan' ORDER BY record_key")]}


def import_scan(connection, source, building='MGH', floor=None, area=None):
    source = Path(source).resolve()
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        pose_paths = [name for name in names if name.endswith('/odometry.csv')]
        if len(pose_paths) != 1:
            raise ValueError('Expected exactly one Stray Scanner odometry.csv; use add-asset for other formats or multi-scan ZIPs.')
        prefix = pose_paths[0].rsplit('/', 1)[0]
        scan_id = prefix.rsplit('/', 1)[-1]
        normalize_logical_path(scan_id)
        rows = list(csv.DictReader(io.StringIO(archive.read(pose_paths[0]).decode()), skipinitialspace=True))
        if not rows or [int(row['frame']) for row in rows] != list(range(len(rows))):
            raise ValueError('Invalid or noncontiguous pose frame IDs; original ZIP is unchanged.')
        if f'{prefix}/rgb.mp4' not in names:
            raise ValueError('Scan RGB video is missing.')
        modalities_complete = all(f'{prefix}/depth/{frame:06d}.png' in names and f'{prefix}/confidence/{frame:06d}.png' in names for frame in range(len(rows)))
        source_sha = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
        previous = connection.execute("SELECT payload_json FROM current_records WHERE kind='scan' AND record_key=?", (scan_id,)).fetchone()
        if previous:
            original = json.loads(previous['payload_json'])['original_asset']
            saved = connection.execute('SELECT blobs.sha256 FROM current_assets JOIN blobs ON blobs.id=current_assets.blob_id WHERE logical_path=?', (original,)).fetchone()
            if saved and saved['sha256'] == source_sha:
                return {'status': 'already_imported', 'scan_id': scan_id, 'changed': False}
            raise ValueError('That scan ID already exists with different original bytes. Preserve and review the conflict before registering another version.')
        logical_path = f'scans/{scan_id}/original/{source.name}'
        state = 'draft' if floor is not None else 'unassigned'
        with revision(connection, f'Import new scan {scan_id}; reconstruction and alignment pending') as revision_id:
            add_asset(connection, revision_id, source, logical_path, 'original_scan_zip', state, scan_id)
            payload = {'scan_id': scan_id, 'building_id': building, 'floor': floor, 'area_hint': area,
                'original_asset': logical_path, 'coordinate_frame_id': f'scan:{scan_id}', 'frame_count': len(rows),
                'capture_span_seconds': float(rows[-1]['timestamp']) - float(rows[0]['timestamp']),
                'depth_confidence_filename_coverage_complete': modalities_complete,
                'geometry_merge_verified': False, 'reconstruction_state': 'pending', 'location_source': 'import command context'}
            put_record(connection, revision_id, 'scan', scan_id, payload, state, [logical_path])
            put_record(connection, revision_id, 'coordinate_frame', f'scan:{scan_id}', {'units': 'meters', 'scan_id': scan_id,
                'building_from_scan_transform': None, 'registration_verified': False}, state)
            if floor is not None:
                floor_key = f'{building}:{floor}'
                previous_floor = connection.execute("SELECT payload_json FROM current_records WHERE kind='floor' AND record_key=?", (floor_key,)).fetchone()
                floor_payload = json.loads(previous_floor['payload_json']) if previous_floor else {'building_id': building, 'floor_number': floor, 'scan_ids': [], 'coverage_state': 'partial', 'navigation_graph_verified': False}
                floor_payload['scan_ids'] = sorted(set(floor_payload.get('scan_ids', [])) | {scan_id})
                put_record(connection, revision_id, 'floor', floor_key, floor_payload, 'draft')
        return {'status': 'imported', 'scan_id': scan_id, 'revision': revision_id, 'floor': floor, 'alignment': 'pending', 'depth_confidence_coverage_complete': modalities_complete}


def main():
    parser = argparse.ArgumentParser(description='Read and extend the single-file MGH building archive.')
    parser.add_argument('--db', default=str(Path(__file__).resolve().parent / 'MGH_Master.sqlite'))
    subparsers = parser.add_subparsers(dest='command', required=True)
    subparsers.add_parser('summary')
    subparsers.add_parser('verify')
    list_parser = subparsers.add_parser('list-assets')
    list_parser.add_argument('--scan')
    get_parser = subparsers.add_parser('get-record')
    get_parser.add_argument('kind')
    get_parser.add_argument('key')
    export_parser = subparsers.add_parser('export')
    export_parser.add_argument('logical_path')
    export_parser.add_argument('destination')
    export_parser.add_argument('--revision', type=int)
    asset_parser = subparsers.add_parser('add-asset')
    asset_parser.add_argument('source')
    asset_parser.add_argument('--path', required=True)
    asset_parser.add_argument('--role', default='uploaded_source')
    asset_parser.add_argument('--state', default='pending')
    asset_parser.add_argument('--scan')
    record_parser = subparsers.add_parser('put-record')
    record_parser.add_argument('kind', choices=sorted(RECORD_KINDS))
    record_parser.add_argument('key')
    record_parser.add_argument('json_file')
    record_parser.add_argument('--state', choices=sorted(REVIEW_STATES), default='draft')
    record_parser.add_argument('--evidence', action='append', default=[])
    record_parser.add_argument('--description', required=True)
    scan_parser = subparsers.add_parser('import-scan')
    scan_parser.add_argument('source')
    scan_parser.add_argument('--building', default='MGH')
    scan_parser.add_argument('--floor', type=int)
    scan_parser.add_argument('--area')
    arguments = parser.parse_args()
    if not Path(arguments.db).exists():
        raise FileNotFoundError('Master archive does not exist. Do not silently create a new empty project.')
    writable = arguments.command in {'add-asset', 'put-record', 'import-scan'}
    with connect(arguments.db, readonly=not writable) as connection:
        if arguments.command == 'summary':
            result = summary(connection)
        elif arguments.command == 'verify':
            result = verify(connection)
            if not result['passed']:
                print(json.dumps(result, indent=2))
                sys.exit(1)
        elif arguments.command == 'list-assets':
            query = 'SELECT logical_path,role,review_state,scan_id,revision_id FROM current_assets'
            parameters = ()
            if arguments.scan:
                query += ' WHERE scan_id=?'
                parameters = (arguments.scan,)
            result = [dict(row) for row in connection.execute(query + ' ORDER BY logical_path', parameters)]
        elif arguments.command == 'get-record':
            row = connection.execute('SELECT * FROM current_records WHERE kind=? AND record_key=?', (arguments.kind, arguments.key)).fetchone()
            if not row:
                raise ValueError('Record not found.')
            result = dict(row)
            result['payload'] = json.loads(result.pop('payload_json'))
        elif arguments.command == 'export':
            result = export_asset(connection, arguments.logical_path, arguments.destination, arguments.revision)
        elif arguments.command == 'add-asset':
            with revision(connection, f'Import asset {arguments.path}') as revision_id:
                asset_id = add_asset(connection, revision_id, arguments.source, arguments.path, arguments.role, arguments.state, arguments.scan)
            result = {'revision': revision_id, 'asset_id': asset_id}
        elif arguments.command == 'import-scan':
            result = import_scan(connection, arguments.source, arguments.building, arguments.floor, arguments.area)
        else:
            payload = json.loads(Path(arguments.json_file).read_text(encoding='utf-8'))
            with revision(connection, arguments.description) as revision_id:
                record_id = put_record(connection, revision_id, arguments.kind, arguments.key, payload, arguments.state, arguments.evidence)
            result = {'revision': revision_id, 'record_id': record_id}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
