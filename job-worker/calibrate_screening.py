"""Six bounded OpenAI fit checks. Reads professional facts only; never applies to jobs."""
import argparse
import json
import os
import time
from pathlib import Path

from job_matching import screen
from openai_screening import MODEL, configuration_error

CASES = [
    ('core-linux', True, 'Linux Administrator', 'Maintain Linux servers, DNS, backups, monitoring and patching. Troubleshoot production incidents and document recovery. Linux operations experience is required; any bachelor degree is acceptable.'),
    ('basic-cloud-support', True, 'Systems Engineer', 'Monitor Linux servers, maintain backups, troubleshoot incidents and DNS. Assist with basic Azure administration under supervision. Cloud lab exposure is sufficient.'),
    ('unverified-ai', False, 'AI Automation & DevOps Engineer', 'Maintain Linux servers and backups. Requirements: strong Node.js backend development and prior AI/LLM API integration into production systems. Docker and monitoring required.'),
    ('production-cloud-tenure', False, 'DevOps Engineer', 'Maintain Linux servers and backups. Mandatory: 5 years of production Azure architecture, Azure DevOps and Ansible experience. Personal labs are insufficient.'),
    ('nationality-restriction', False, 'Linux Engineer', 'Emirati nationals only. Maintain Linux servers, DNS, backups and incident response.'),
    ('conflicting-location', False, 'Infrastructure Engineer', 'Listing header says Dubai, UAE. Mandatory full-time on-site residence and employment in Pakistan; this is not a UAE role. Maintain Linux servers, DNS, backups and incident response.'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=Path('/data/user_config.json'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('JOB_SCREENING_MODE') != 'openai':
        raise ValueError('Explicit OpenAI mode is required for calibration')
    error = configuration_error()
    if error:
        raise ValueError(error)
    config = json.loads(args.profile.read_text())
    os.umask(0o077)
    results = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for name, expected, title, description in CASES:
        started = time.monotonic()
        result = screen(config, {'title': title, 'company': 'Synthetic calibration company', 'head': title + '\nDubai, UAE', 'description': description})
        row = {'case': name, 'expected': expected, 'decision': result, 'seconds': round(time.monotonic() - started, 2), 'passed': result['eligible'] is expected}
        results.append(row)
        args.out.write_text(json.dumps({'model': MODEL, 'submitted_applications': 0, 'results': results}, indent=2))
        args.out.chmod(0o600)
        print(json.dumps({'case': name, 'passed': row['passed'], 'seconds': row['seconds']}), flush=True)
    if not all(row['passed'] for row in results):
        raise ValueError('Calibration failed; leave the current screening mode active')


if __name__ == '__main__':
    main()
