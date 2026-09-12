"""Calendar events follow immutable task identity across exports and edits."""

from icalendar import Calendar


def _event(client):
    response = client.get('/api/exports/tasks.ics')
    assert response.status_code == 200
    events = Calendar.from_ical(response.content).walk('VEVENT')
    assert len(events) == 1
    return events[0]


def test_calendar_identity_survives_edit_and_sequence_advances(client):
    task = client.post('/api/tasks', json={
        'name': '报告', 'due_at': '2099-09-12T18:30:00',
    }).json()
    first = _event(client)
    repeated = _event(client)
    assert first['uid'] == repeated['uid']
    assert first['sequence'] == repeated['sequence'] == 0
    assert first.decoded('last-modified') == repeated.decoded('last-modified')
    edited = client.patch(f"/api/tasks/{task['id']}", json={
        'name': '修订报告', 'due_at': '2099-09-13T20:00:00',
    }, headers={'If-Match': f'"{task["navigation_key"]}:{task["revision"]}"'})
    assert edited.status_code == 200, edited.text
    changed = _event(client)
    assert changed['uid'] == first['uid']
    assert changed['sequence'] > first['sequence']
    assert changed.decoded('last-modified') >= first.decoded('last-modified')
    assert str(changed['summary']) == '[DDL] 修订报告'
    assert changed.decoded('dtstart').isoformat() == '2099-09-13T20:00:00+08:00'


def test_reused_numeric_task_id_does_not_reuse_calendar_uid(client):
    original = client.post('/api/tasks', json={
        'name': '原报告', 'due_at': '2099-09-12T18:30:00',
    }).json()
    old_uid = str(_event(client)['uid'])
    assert client.delete(f"/api/tasks/{original['id']}").status_code == 204
    replacement = client.post('/api/tasks', json={
        'name': '另一份报告', 'due_at': '2099-09-12T18:30:00',
    }).json()
    assert replacement['id'] == original['id']  # SQLite exercises actual reuse.
    assert str(_event(client)['uid']) != old_uid
