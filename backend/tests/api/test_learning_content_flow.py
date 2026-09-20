"""End-to-end boundaries between material recognition and review scheduling."""
import json
from datetime import timedelta

import pytest

from app.time import as_local, utc_now


def _material(client, course_id, filename, text):
    response = client.post('/api/materials', json={'course_id': course_id, 'original_filename': filename, 'extracted_text': text})
    assert response.status_code == 201
    material = response.json()
    result = client.post(f"/api/materials/{material['id']}/extract", json={'provider': 'local-rules'})
    assert result.status_code == 200
    return material, result.json()


def _ref(source):
    return {key: source[key] for key in ('source_id', 'navigation_key', 'revision')}


def _generate(client, course, materials, tasks):
    return client.post('/api/study-plans/generate', json={
        'course_id': course['id'], 'exam_date': (as_local(utc_now()).date() + timedelta(days=5)).isoformat(),
        'daily_minutes': 60, 'material_sources': [_ref(item) for item in materials], 'task_sources': [_ref(item) for item in tasks],
    })


@pytest.mark.parametrize('filename,text,kind', [
    ('高数复习资料.txt', '课程：高等数学\n知识点：极限与连续\n复习期末考试重点：微积分\n自测：完成第一章练习题', 'study_material'),
    ('高数复习计划.txt', '复习计划\n9月15日复习第一章\n9月16日完成练习题，自测考试重点\n9月17日梳理错题', 'review_outline'),
])
def test_learning_content_saves_without_creating_tasks_and_keeps_course(client, filename, text, kind):
    course = client.post('/api/courses', json={'name': '高等数学'}).json()
    material, result = _material(client, None, filename, text)
    assert result['content_kind'] == kind
    assert result['tasks'] == []
    assert not result['needs_review']
    assert result['learning_points']
    assert all(point in text for point in result['learning_points'])
    response = client.post(f"/api/materials/{material['id']}/extraction/confirm", json={'course_id': course['id'], 'tasks': []})
    assert response.status_code == 200
    assert response.json()['confirmed_task_ids'] == []
    stored = next(item for item in client.get('/api/materials').json() if item['id'] == material['id'])
    assert stored['course_id'] == course['id']
    assert stored['extraction_status'] == 'confirmed'
    assert client.get('/api/tasks').json() == []
    assert client.post(f"/api/materials/{material['id']}/extraction/confirm", json={'tasks': []}).status_code == 409


def test_mixed_document_preserves_obligation_and_does_not_schedule_it_twice(client):
    course = client.post('/api/courses', json={'name': '算法'}).json()
    material, result = _material(client, course['id'], '算法复习资料.txt',
        '知识点：动态规划与最短路径\n9月15日复习考试重点\n请于2026年10月20日18:00前提交算法作业。')
    assert result['content_kind'] == 'mixed'
    assert len(result['tasks']) == 1
    assert '提交算法作业' in result['tasks'][0]['source_quote']
    assert not any('提交' in point for point in result['learning_points'])
    assert client.post(f"/api/materials/{material['id']}/extraction/confirm", json={'tasks': result['tasks']}).status_code == 200
    sources = client.get('/api/study-plans/sources', params={'course_id': course['id']}).json()
    plan = _generate(client, course, sources['materials'], []).json()
    assert plan['task_count'] == 0 and plan['material_count'] == 1
    assert all(not item['source_task_ids'] for item in plan['items'])
    assert all('提交算法作业' not in item['content'] for item in plan['items'])


def test_discarding_task_candidates_requires_explicit_material_only_choice(client):
    material, result = _material(client, None, '作业通知.txt', '请于2026年10月20日18:00前提交算法作业。')
    assert result['tasks']
    url = f"/api/materials/{material['id']}/extraction/confirm"
    assert client.post(url, json={'tasks': []}).status_code == 400
    saved = client.post(url, json={'tasks': [], 'material_only': True})
    assert saved.status_code == 200
    assert saved.json()['confirmed_task_ids'] == []
    assert client.get('/api/tasks').json() == []


def test_revision_homework_with_explicit_obligation_is_still_a_task(client):
    course = client.post('/api/courses', json={'name': '复习作业边界'}).json()
    _, result = _material(client, course['id'], '复习作业.txt', '请于2026年10月20日前完成复习作业。')
    assert len(result['tasks']) == 1
    assert result['tasks'][0]['due_at']
    assert result['content_kind'] == 'task_notice'
    assert result['material_type'] == '作业要求'
    sources = client.get('/api/study-plans/sources', params={'course_id': course['id']}).json()
    assert not sources['materials'][0]['recommended']


def test_source_defaults_exclude_notices_schedules_and_empty_materials(client):
    course = client.post('/api/courses', json={'name': '测试课程'}).json()
    for name, text in [('复习资料.txt', '知识点：导数与积分'), ('课程通知.txt', '请于2026年10月20日前提交作业。'), ('复习计划.txt', '复习计划\n9月20日梳理错题')]:
        _material(client, course['id'], name, text)
    client.post('/api/materials', json={'course_id': course['id'], 'original_filename': '空白.txt'})
    sources = client.get('/api/study-plans/sources', params={'course_id': course['id']}).json()
    recommended = [item['label'] for item in sources['materials'] if item['recommended']]
    assert recommended == ['复习资料.txt']
    empty = next(item for item in sources['materials'] if item['label'] == '空白.txt')
    assert not empty['available']
    assert _generate(client, course, [empty], []).status_code == 422


def test_explicit_sources_do_not_expand_and_reject_stale_or_cross_course_selection(client):
    course = client.post('/api/courses', json={'name': '范围课程'}).json()
    other = client.post('/api/courses', json={'name': '另一课程'}).json()
    material, _ = _material(client, course['id'], '讲义.txt', '知识点：二叉树遍历')
    _material(client, other['id'], '其他讲义.txt', '知识点：傅里叶变换')
    task = client.post('/api/tasks', json={'course_id': course['id'], 'name': '待完成作业'}).json()
    sources = client.get('/api/study-plans/sources', params={'course_id': course['id']}).json()
    response = _generate(client, course, sources['materials'], [])
    assert response.status_code == 201
    plan = response.json()
    assert plan['material_count'] == 1 and plan['task_count'] == 0
    assert _generate(client, course, [], []).status_code == 422
    assert _generate(client, other, sources['materials'], []).status_code == 409
    wrong_key = {**sources['materials'][0], 'navigation_key': '0' * 32}
    assert _generate(client, course, [wrong_key], []).status_code == 409
    client.patch(f"/api/materials/{material['id']}", json={'summary': '修改后的知识点'})
    assert _generate(client, course, sources['materials'], []).status_code == 409
    # Optional tasks really are selected and scheduled when explicitly requested.
    task_plan = _generate(client, course, [], sources['tasks'])
    assert task_plan.status_code == 201
    assert task_plan.json()['task_count'] == 1 and task_plan.json()['material_count'] == 0
    assert any(task['id'] in item['source_task_ids'] for item in task_plan.json()['items'])
    # Manual plan edits retain the chosen scope for later agent suggestions.
    updated = client.patch(f"/api/study-plans/{plan['id']}", json={'items': plan['items']}).json()
    assert json.loads(updated['plan_content'])['agent']['source_selection']['tasks'] == []


def test_external_provider_cannot_turn_verbatim_review_activity_into_ddl(client, monkeypatch):
    from app.services import extraction
    class Provider:
        name = 'openai-compatible'
        def extract(self, text, filename):
            return {'tasks': [{'name': '期末复习', 'source_quote': text, 'due_at': '2026-10-20', 'confidence': .9}], 'learning_points': ['虚构知识点']}
    monkeypatch.setattr(extraction, 'get_provider', lambda *_: Provider())
    _, result = _material(client, None, '复习计划.txt', '10月20日复习期末考试重点')
    assert result['tasks'] == []
    assert '虚构知识点' not in result['learning_points']


def test_unselected_task_events_do_not_change_a_material_only_plan(client):
    from app.database import get_db
    from app.services.agent_feedback import _candidate_changes
    from app.models.study_plan import StudyPlan
    from app.models.task import Task
    course = client.post('/api/courses', json={'name': '独立复习'}).json()
    _material(client, course['id'], '复习资料.txt', '知识点：递归与分治')
    sources = client.get('/api/study-plans/sources', params={'course_id': course['id']}).json()
    plan = _generate(client, course, sources['materials'], []).json()
    task = client.post('/api/tasks', json={'course_id': course['id'], 'name': '新作业'}).json()
    generator = client.app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        assert _candidate_changes(db.get(StudyPlan, plan['id']), db.get(Task, task['id']), 'task_created') == []
    finally:
        generator.close()
