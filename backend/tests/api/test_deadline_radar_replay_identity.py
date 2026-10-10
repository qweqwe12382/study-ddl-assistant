"""A recorded DDL action must never resolve to a different incarnation of a task."""

import pytest


def _task(client, name):
    response = client.post('/api/tasks', json={'name': name, 'estimated_minutes': 30})
    assert response.status_code == 201
    return response.json()


def _payload(task):
    return {
        'task_id': task['id'],
        'task_navigation_key': task['navigation_key'],
        'task_revision': task['revision'],
        'notice_text': '本次报告任务取消，无需提交。',
        'reference_time': '2026-10-02T01:00:00Z',
        'idempotency_key': 'replay-original-report-cancellation',
    }


@pytest.mark.parametrize('use_replacement_identity', [False, True])
def test_replay_cannot_bind_old_receipt_to_a_reused_task_id(client, use_replacement_identity):
    original = _task(client, '旧报告')
    payload = _payload(original)
    applied = client.post('/api/deadline-radar/apply', json=payload)
    assert applied.status_code == 200
    saved = applied.json()['task']
    deleted = client.delete(f'/api/tasks/{saved["id"]}', headers={
        'If-Match': f'"{saved["navigation_key"]}:{saved["revision"]}"',
    })
    assert deleted.status_code == 204
    replacement = _task(client, '另一个报告')
    assert replacement['id'] == original['id']
    assert replacement['navigation_key'] != original['navigation_key']
    if use_replacement_identity:
        payload.update(task_navigation_key=replacement['navigation_key'], task_revision=replacement['revision'])

    replay = client.post('/api/deadline-radar/apply', json=payload)

    assert replay.status_code == 409
    assert replay.json()['error']['code'] in {'IDEMPOTENCY_KEY_CONFLICT', 'DEADLINE_CHANGE_RESULT_UNAVAILABLE'}
    assert client.get(f'/api/tasks/{replacement["id"]}').json() == replacement


def test_same_task_replay_accepts_original_revision_but_not_another_identity(client):
    original = _task(client, '正常报告')
    payload = _payload(original)
    applied = client.post('/api/deadline-radar/apply', json=payload)
    assert applied.status_code == 200
    replay = client.post('/api/deadline-radar/apply', json=payload)
    assert replay.status_code == 200
    assert replay.json() == applied.json()
    foreign_identity = 'f' * 32 if original['navigation_key'] != 'f' * 32 else 'e' * 32
    forged = client.post('/api/deadline-radar/apply', json={**payload, 'task_navigation_key': foreign_identity})
    assert forged.status_code == 409
    assert forged.json()['error']['code'] == 'IDEMPOTENCY_KEY_CONFLICT'
