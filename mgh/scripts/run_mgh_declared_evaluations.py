"""Run the remaining predeclared experiments without tuning on their results."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'outputs/MGH_Project/localization'
PLAN = json.loads((LOCAL / 'EVALUATION_PLAN_v3_v4.json').read_text())
TOOL = LOCAL / 'mgh_localizer.py'


def run(name, *args):
    command = [sys.executable, '-u', str(TOOL), *map(str, args)]
    print(json.dumps(dict(run=name, command=command)), flush=True)
    with (ROOT / 'work' / (name + '.log')).open('x', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end='', flush=True)
        if process.wait():
            raise RuntimeError(f'{name} failed; preserve its partial artifacts/log.')


def evaluate(map_name, label):
    run(f'evaluate_{map_name.removeprefix("visual_map_")}_set{label}', 'evaluate',
        '--map', LOCAL / map_name, '--output', LOCAL / f'evaluation_{map_name.removeprefix("visual_map_").replace("_low_rotation", "")}_set{label}',
        '--query-ordinals', ','.join(map(str, PLAN['query_sets'][label]['ordinals'])),
        '--query-set-label', label)


if __name__ == '__main__':
    evaluate('visual_map_v3', 'B')
    run('build_v4_low_rotation', 'build', '--map', LOCAL / 'visual_map_v4_low_rotation',
        '--selection', 'low_rotation')
    evaluate('visual_map_v4_low_rotation', 'B')
