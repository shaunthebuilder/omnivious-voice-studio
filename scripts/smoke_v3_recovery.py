from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / 'data'
PREFERRED_PERSONAS = ['Scarlett Normal', 'Trump Speech', 'Trump Speech 2']


def _get_json(url: str) -> dict | list:
    with request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def _wait_for_ready(base_url: str, timeout_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = 'health did not become ready'
    while time.time() < deadline:
        try:
            payload = _get_json(f'{base_url}/api/health')
            if isinstance(payload, dict):
                state = str(payload.get('startup_state', ''))
                if state == 'ready' and bool(payload.get('model_ready')):
                    return payload
                last_error = str(payload.get('startup_error') or f'startup_state={state}')
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(last_error)


def _pick_persona(base_url: str) -> dict:
    payload = _get_json(f'{base_url}/api/personas')
    if not isinstance(payload, list):
        raise RuntimeError('Unexpected personas payload')
    certified = [row for row in payload if isinstance(row, dict) and row.get('certification_status') == 'certified']
    if not certified:
        raise RuntimeError('No certified personas available for smoke test')
    for name in PREFERRED_PERSONAS:
        for persona in certified:
            if persona.get('name') == name:
                return persona
    return certified[0]


def _poll_job(base_url: str, job_id: int, timeout_seconds: float) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = _get_json(f'{base_url}/api/jobs/{job_id}')
        if not isinstance(payload, dict):
            raise RuntimeError('Unexpected job payload')
        status = str(payload.get('status', ''))
        if status == 'completed':
            return payload
        if status == 'failed':
            raise RuntimeError(str(payload.get('error') or 'job failed'))
        time.sleep(2)
    raise RuntimeError(f'Job {job_id} did not finish before timeout')


def _assert_output_file_exists(audio_path: str | None) -> None:
    if not audio_path:
        raise RuntimeError('Generation completed without audio_path')
    if not audio_path.startswith('/media/'):
        raise RuntimeError(f'Unexpected media path: {audio_path}')
    disk_path = DATA_DIR / audio_path.removeprefix('/media/')
    if not disk_path.exists():
        raise RuntimeError(f'Generated audio file missing on disk: {disk_path}')


def _run_generation(base_url: str, persona_id: int, render_mode: str, text: str) -> dict:
    response = _post_json(
        f'{base_url}/api/generate',
        {
            'persona_id': persona_id,
            'text': text,
            'style': 'natural',
            'speed': 1.0,
            'render_mode': render_mode,
        },
    )
    generation_id = int(response['generation_id'])
    job_id = int(response['job_id'])
    _poll_job(base_url, job_id, timeout_seconds=300 if render_mode == 'final' else 180)
    generation = _get_json(f'{base_url}/api/generations/{generation_id}')
    if not isinstance(generation, dict):
        raise RuntimeError('Unexpected generation payload')
    if generation.get('status') != 'completed':
        raise RuntimeError(f'Generation {generation_id} did not complete')
    _assert_output_file_exists(generation.get('audio_path'))
    return generation


def main() -> int:
    parser = argparse.ArgumentParser(description='Smoke-test Omnivious V3 preview/final generation.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8001')
    parser.add_argument(
        '--text',
        default='The storm has passed. Breathe in. Let your voice carry both relief and resolve.',
    )
    args = parser.parse_args()

    try:
        health = _wait_for_ready(args.base_url.rstrip('/'), timeout_seconds=240)
        persona = _pick_persona(args.base_url.rstrip('/'))
        print(f"health={health['startup_state']} persona={persona['name']}")
        preview = _run_generation(args.base_url.rstrip('/'), int(persona['id']), 'preview', args.text)
        print(f"preview_generation={preview['id']} duration={preview.get('duration_sec')} audio={preview.get('audio_path')}")
        final = _run_generation(args.base_url.rstrip('/'), int(persona['id']), 'final', args.text)
        print(f"final_generation={final['id']} duration={final.get('duration_sec')} audio={final.get('audio_path')}")
        return 0
    except error.HTTPError as exc:
        print(f'HTTP error: {exc.code} {exc.reason}', file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
