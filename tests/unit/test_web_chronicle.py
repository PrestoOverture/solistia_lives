import json
import re
from html import unescape
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from story_engine.web import _display_name, create_app
from story_engine.kb import TRAVELERS
from story_engine.web.chronicle import chronicle_data


@pytest.fixture
def world(tmp_path):
    directory = tmp_path / 'worlds' / 'fixture'
    shutil.copytree(Path(__file__).parents[1] / 'fixtures/worlds/player', directory)
    genesis = json.loads((directory / 'genesis.json').read_text())
    situation = dict(id='start', kind='trouble', summary='Opaque summary', touches=['agnea'],
                     people=['Mabel'], status='open', next='Opaque next', due=dict(day=2, part='night'))
    genesis['situations'] = [situation]
    (directory / 'genesis.json').write_text(json.dumps(genesis))

    def event(id, **fields):
        return dict(id=id, day=1, part='morning', place='cropdale', actor='world',
                    type='world', content='Opaque content', perceived_by=[], **fields)

    rows = [event(1, ops=[dict(op='open', situation=dict(situation, id='later', people=[]))]),
            event(2, scene='1', round=1, ops=[dict(op='situation', id='later', next='Changed')]),
            {**event(3, scene='1', round=1), 'actor': 'agnea', 'type': 'speech', 'move': 'act',
             'action': 'A visible move.', 'say': 'A spoken line.', 'intent': 'A private reason.'},
            event(4, scene='1', round=2, resolves=3, resolution='succeeded', odds='even'),
            {**event(5), 'actor': 'Mabel'},
            {**event(6), 'actor': 'Mabel', 'type': 'plan'},
            {**event(7), 'type': 'state_change', 'content': '', 'part': 'afternoon',
             'ops': [dict(op='situation', id='start', status='dropped', people=[])]},
            {**event(8), 'actor': 'Mabel', 'part': 'evening'},
            {**event(9), 'part': 'afternoon', 'ops': [dict(op='situation', id='later',
               status='resolved')], 'scene': '2', 'round': 1}]
    (directory / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    scenes = [dict(id=str(i), day=1, part=part, place='cropdale', spot='square',
                   participants=people, first_event_id=1, last_event_id=9, rounds=2, end='quiet')
              for i, part, people in [(1, 'morning', ['agnea']), (2, 'afternoon', ['Mabel']),
                                      (3, 'evening', ['Mabel']), (4, 'morning', ['throne'])]]
    (directory / 'scenes.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in scenes))
    return directory


def test_chronicle_threads_scenes_intent_and_read_only(world, tmp_path):
    before = {p: p.read_bytes() for p in world.rglob('*') if p.is_file()}
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        response = client.get('/world/fixture/chronicle.json')
        assert response.status_code == 200
        data = response.json()
        start, later = data['threads']
        assert start['id'] == 'start'
        assert start['opened'] == dict(day=1, part='morning', event_id=None, at_start=True)
        assert later['opened'] == dict(day=1, part='morning', event_id=1, at_start=False)
        assert later['updates'][0] == dict(day=1, part='morning', event_id=2,
                                          scene='1', changed_fields={'next': 'Changed'})
        assert later['next'] == 'Changed'
        assert start['closed'] == dict(day=1, part='afternoon', event_id=7, scene=None,
                                       round=None, content='', status='dropped', by_clock=True)
        assert start['people'] == []
        assert [s['id'] for s in start['scenes']] == ['2']  # historical people, inclusive closing tick
        assert [s['id'] for s in later['scenes']] == ['1', '2']  # ops even without shared people
        assert [s['id'] for s in data['unthreaded']] == ['3', '4']
        assert [e['id'] for e in start['off_scene']] == [5]
        assert later['closed']['status'] == 'resolved'
        scene = later['scenes'][0]
        move = scene['rounds'][0]['moves'][0]
        assert (move['action'], move['say'], move['intent']) == (
            'A visible move.', 'A spoken line.', 'A private reason.')
        assert any(e['resolves'] == move['id'] for e in scene['rounds'][1]['world'])
        assert scene['participants'] == ['Agnea Bristarni']
        assert scene['theater_link'] == '/world/fixture/theater#1'
        html = client.get('/world/fixture/chronicle')
        assert html.status_code == 200
        assert 'id="show-intents" type="checkbox"' in html.text
        assert 'class="private-intent metadata">Private intent: A private reason.</p>' in html.text
        assert '#show-intents:checked' in html.text
        assert 'A visible move.' in html.text and 'A spoken line.' in html.text
        assert '/world/fixture/theater#1' in html.text
        assert '/world/fixture/chronicle' in client.get('/worlds').text
        assert client.post('/world/fixture/chronicle').status_code == 405
    assert before == {p: p.read_bytes() for p in world.rglob('*') if p.is_file()}


@pytest.mark.parametrize('route', ['chronicle', 'chronicle.json'])
@pytest.mark.parametrize('world_id', ['unknown', 'bad%5Cid', 'fixture'])
def test_missing_genesis_and_unknown_world(world, tmp_path, route, world_id):
    (world / 'genesis.json').unlink()
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        assert client.get(f'/world/{world_id}/{route}').status_code == 404


def test_empty_world_has_open_thread(world, tmp_path):
    (world / 'events.jsonl').write_text('')
    (world / 'scenes.jsonl').write_text('')
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        data = client.get('/world/fixture/chronicle.json').json()
        assert data['threads'][0]['closed'] is None
        assert data['unthreaded'] == []
        assert client.get('/world/fixture/chronicle').status_code == 200


def test_chronicle_overview_and_readable_details(world, tmp_path):
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        data = client.get('/world/fixture/chronicle.json').json()
        html = client.get('/world/fixture/chronicle').text
    overview = html.split('<div id="thread-overview"')[1].split('</section>')[0]
    previews = re.findall(r'<a class="card thread-preview"(.*?)</a>', overview, re.S)
    assert len(previews) == len(data['threads']) == 2
    assert '<table' not in html
    assert 'grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr))' in html
    for preview, thread in zip(previews, data['threads']):
        target = re.search(r'href="#([^"]+)"', preview)[1]
        assert target == f"thread-{thread['id']}"
        assert f'<section id="{target}" class="card thread-card">' in html
        assert thread['kind'] in preview and thread['summary'] in preview
        assert f'title="{thread["summary"]}"' in preview
        assert '<h3 class="prose">' in preview
        assert 'Agnea Bristarni' in preview
        count = len(thread['scenes'])
        assert f' · {count} scene{"" if count == 1 else "s"}</p>' in preview
        assert f'class="pill-{thread["status"]}"' in preview
    assert ' · Start · ' in previews[0]
    assert ' · Day 1 morning · ' in previews[1]
    assert 'dropped</span><span class="metadata"> · Day 1 afternoon · by the clock' in html
    assert 'resolved</span><span class="metadata"> · Day 1 afternoon' in html
    assert '2 of 4 scenes are in no thread' in html
    assert '<pre' not in html.lower()
    assert 'Day 1 afternoon · Scene 2 · status → resolved' in html
    assert 'situation · id → later · next → Changed' in html
    assert 'Cropdale — square' in html and 'cropdale — square' not in html
    scene = data['threads'][1]['scenes'][0]
    assert scene['place'] == 'cropdale' and scene['place_name'] == 'Cropdale'
    unthreaded = html.split('<section id="unthreaded"')[1].split('</section>')[0]
    assert re.search(r'<summary>Day 1</summary>.*Scene 4.*Scene 3', unthreaded, re.S)
    section = html.split('<section id="thread-start"')[1].split('</section>')[0]
    heading = re.search(r'<h2 class="thread-summary">(.*?)</h2>', section, re.S)[1]
    assert unescape(heading) == 'Opaque summary'
    assert '<p class="metadata">start</p>' in section
    assert '<h3>Timeline</h3>' in section


def test_chronicle_formats_fields_and_groups_multiple_days(world, tmp_path):
    events = [json.loads(line) for line in (world / 'events.jsonl').read_text().splitlines()]
    events[1]['ops'][0].update(due=dict(day=2, part='morning'), people=['agnea'])
    (world / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    scenes = [json.loads(line) for line in (world / 'scenes.jsonl').read_text().splitlines()]
    scenes[2].update(day=2, place='unknown_place')
    (world / 'scenes.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in scenes))
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        html = client.get('/world/fixture/chronicle').text
        data = client.get('/world/fixture/chronicle.json').json()
    assert 'due → Day 2 morning · people → Agnea Bristarni' in html
    assert 'unknown_place — square' in html
    assert next(s for s in data['unthreaded'] if s['id'] == '3')['place_name'] == 'unknown_place'
    unthreaded = html.split('<section id="unthreaded"')[1].split('</section>')[0]
    assert re.search(r'<summary>Day 1</summary>.*Scene 4.*<summary>Day 2</summary>.*Scene 3', unthreaded, re.S)


def test_chronicle_display_defects(world, tmp_path):
    events = [json.loads(line) for line in (world / 'events.jsonl').read_text().splitlines()]
    events[2]['content'] = 'A visible move. “A spoken line.”'
    events.extend([
        dict(events[2], id=10, actor='throne', type='action', move='leave',
             action='Leaves the square.', say=None, content='Leaves the square.',
             intent='Find a quiet place.'),
        dict(events[2], id=11, type='action', move='wait', action=None, say=None,
             content='Waits nearby.', intent='Listen.'),
        dict(events[3], id=12, round=3, content='', resolves=None, resolution=None),
        dict(events[4], id=13, actor='world', content='News from elsewhere.'),
        dict(events[6], id=14, part='evening', content='Finally settled.',
             ops=[dict(op='situation', id='start', status='resolved')]),
    ])
    (world / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        data = client.get('/world/fixture/chronicle.json').json()
        html = client.get('/world/fixture/chronicle').text
    scene = next(s for t in data['threads'] for s in t['scenes'] if s['id'] == '1')
    assert [e['id'] for e in scene['rounds'][0]['moves']] == [3, 10, 11]
    assert scene['rounds'][0]['moves'][0]['content'] == events[2]['content']
    assert 4 not in [e['id'] for e in scene['rounds'][0]['world']]
    assert 4 in [e['id'] for e in scene['rounds'][1]['world']]
    assert 12 in [e['id'] for e in scene['rounds'][2]['world']]
    scene_html = re.search(r'<details class="scene-entry">\s*<summary><span class="scene-summary-text"><span class="scene-title">Scene 1 .*?</details>', html, re.S)[0]
    first, second = scene_html.split('<h4 class="round-divider">Round 2</h4>')
    assert first.count('A spoken line.') == 1
    assert first.index('A visible move.') < first.index('Leaves the square.') < first.index('Waits nearby.')
    assert 'Private intent: Find a quiet place.</p>' in first
    assert 'class="metadata outcome-event">Event 4</span>' not in first
    assert 'class="metadata outcome-event">Event 4</span>' in second
    assert 'class="metadata outcome-event">Event 12</span>' not in html and '<h4 class="round-divider">Round 3</h4>' not in scene_html
    assert 'No floor move recorded' not in html
    elsewhere = html.split('<section id="elsewhere"')[1].split('</section>')[0]
    assert 'News from elsewhere.' in elsewhere
    assert '<details class="day-group"><summary>Day 1</summary>' in elsewhere
    assert '<h3 class="eyebrow">morning</h3>' in elsewhere
    assert 13 in [e['id'] for e in data['elsewhere']]
    assert 5 not in [e['id'] for e in data['elsewhere']]
    thread = data['threads'][0]
    assert [(e['status'], e['event_id'], e['by_clock']) for e in thread['status_history']] == [
        ('dropped', 7, True), ('resolved', 14, False)]
    overview = html.split('<div id="thread-overview"')[1].split('</section>')[0]
    section = html.split('<section id="thread-start"')[1].split('</section>')[0]
    history = re.search(r'<div class="status-history">(.*?)</div>', section, re.S)[1]
    sequence = ' '.join(unescape(re.sub('<[^>]+>', '', history)).split())
    assert sequence == 'dropped · Day 1 afternoon · by the clock → resolved · Day 1 evening'
    assert 'pill-resolved' in overview
    assert 'min-width: 1100px' not in html
    assert 'class="thread-grid"' in html


def test_explicit_about_links_without_people_and_disables_people_guess(world, tmp_path):
    events = [json.loads(line) for line in (world / 'events.jsonl').read_text().splitlines()]
    events[3]['about'] = 'start'  # resolution in scene 1; Mabel is absent
    events.append(dict(id=10, day=1, part='evening', place='cropdale', actor='world',
                       type='world', content='Thread news.', perceived_by=[], about='start'))
    (world / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        data = client.get('/world/fixture/chronicle.json').json()
    start = data['threads'][0]
    assert [s['id'] for s in start['scenes']] == ['1']
    assert '3' in [s['id'] for s in data['unthreaded']]  # Mabel present, no op/about
    assert [e['id'] for e in start['off_scene']] == [10]
    assert 10 not in [e['id'] for e in data['elsewhere']]
    assert start['scenes'][0]['rounds'][1]['world'][0]['about'] == 'start'


def test_chronicle_odds(world, tmp_path):
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        data = client.get('/world/fixture/chronicle.json').json()
        outcome = data['threads'][1]['scenes'][0]['rounds'][1]['world'][0]
        assert outcome['odds'] == 'even'
        html = client.get('/world/fixture/chronicle').text
        assert 'class="pill-succeeded">succeeded</span>' in html
        assert 'class="chip">even</span>' in html


@pytest.mark.parametrize('asset_directory', ['assets/player', 'custom-art'])
def test_chronicle_timeline_catalog_names_and_unchanged_json(world, tmp_path, asset_directory):
    assets = tmp_path / asset_directory
    (assets / 'stages').mkdir(parents=True)
    (assets / 'stages/cropdale.yaml').write_text(
        'default: festival_square\nspots:\n- id: festival_square\n  name: Festival Square\n'
        '  stand: [{x: 0.5, y: 0.6, h: 0.1}]\n')
    # Event ids deliberately disagree with day/part order. The first off-scene
    # event and Scene 1 also share a tick, exercising the event-id tie breaker.
    def event(id, part, **fields):
        return dict(id=id, day=1, part=part, actor='world', place='cropdale',
                    type='world', content=f'Stored fact {id}.', perceived_by=[], **fields)

    events = [dict(event(1, 'morning', scene='2', round=1, about='start'), day=2),
              event(10, 'morning', about='start'),
              event(20, 'morning', scene='1', round=1, about='start'),
              event(5, 'afternoon', about='start'),
              event(4, 'night', ops=[dict(op='situation', id='start', next='Stored next.')]),
              dict(event(2, 'night', about='start', ops=[dict(op='situation', id='start',
                                                           status='resolved')]), day=2)]
    (world / 'events.jsonl').write_text(''.join(
        json.dumps(e) + '\n' for e in sorted(events, key=lambda e: e['id'])))
    scenes = [json.loads(line) for line in (world / 'scenes.jsonl').read_text().splitlines()]
    scenes[0].update(spot='festival_square', first_event_id=20, last_event_id=20)
    scenes[1].update(day=2, part='morning', first_event_id=1, last_event_id=1)
    (world / 'scenes.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in scenes))
    names = {slug: _display_name(Path('kb/characters') / slug / f'{slug}.md') for slug in TRAVELERS}
    expected = chronicle_data(world.parent, world.name, names, {'cropdale': 'Cropdale'})
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent,
                              player_assets_dir=assets)) as client:
        before = client.get('/world/fixture/chronicle.json')
        response = client.get('/world/fixture/chronicle')
        after = client.get('/world/fixture/chronicle.json')
    assert response.status_code == 200
    assert before.content == after.content
    assert after.json() == expected.model_dump(mode='json')
    html = response.text
    assert 'min-width: 1100px' not in html
    assert 'Cropdale — Festival Square' in html and 'festival_square' not in html
    assert 'Agnea Bristarni, Throné Anguis · Cropdale' in html
    section = html.split('<section id="thread-start"')[1].split('</section>')[0]
    timeline = re.search(r'<ol class="timeline"[^>]*>(.*?)</ol>', section, re.S)[1]
    assert re.findall(r'<li data-kind="([^"]+)" data-event-id="(\d+)">', timeline) == [
        ('opened', '0'), ('off-scene', '10'), ('scene', '20'), ('off-scene', '5'),
        ('update', '4'), ('scene', '1'), ('closing', '2')]
    assert timeline.count('Stored fact 2.') == 1  # the off-scene closing is shown once
    assert 'hx-boost="false" href="/world/fixture/theater#1"' in timeline
    assert '<details class="scene-entry" open' not in timeline


@pytest.mark.parametrize('count', [0, 1, 2])
def test_chronicle_singular_and_plural_counts(world, tmp_path, count):
    path = world / 'genesis.json'
    genesis = json.loads(path.read_text())
    genesis['situations'] = [dict(genesis['situations'][0], id=f'thread-{i}', people=[]) for i in range(count)]
    path.write_text(json.dumps(genesis))
    (world / 'events.jsonl').write_text('')
    scenes = [json.loads(line) for line in (world / 'scenes.jsonl').read_text().splitlines()][:count]
    for scene in scenes:
        scene['day'] = max(1, count)
    (world / 'scenes.jsonl').write_text(''.join(json.dumps(scene) + '\n' for scene in scenes))
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        html = client.get('/world/fixture/chronicle').text
    stats = re.search(r'<div class="stats">(.*?)</div>', html, re.S)[1]
    suffix = '' if count == 1 else 's'
    assert f'<strong>{count}</strong> thread{suffix}</span>' in stats
    assert f'<strong>{count}</strong> scene{suffix}</span>' in stats
    assert f'<strong>{max(1, count)}</strong> day{"s" if count > 1 else ""}</span>' in stats
    assert f'{count} of {count} scene{suffix} {"is" if count == 1 else "are"} in no thread' in html
    assert '1 scenes' not in html and '1 threads' not in html and '1 days' not in html


def test_chronicle_polished_headers_and_actor_labels(world, tmp_path):
    path = world / 'events.jsonl'
    events = [json.loads(line) for line in path.read_text().splitlines()]
    events.extend([dict(events[4], id=10, actor='world', about='start', content='Stored world fact.'),
                   dict(events[4], id=11, about='start', content='Stored person fact.')])
    path.write_text(''.join(json.dumps(event) + '\n' for event in events))
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=world.parent)) as client:
        html = client.get('/world/fixture/chronicle').text
    section = html.split('<section id="thread-start"')[1].split('</section>')[0]
    assert re.search(r'<div class="thread-heading"><span class="chip">trouble</span>\s*<div class="status-history">', section)
    assert '<strong class="small">World</strong>' not in section
    assert '<strong class="small">Mabel</strong>' in section
    assert 'Stored world fact.' in section and 'Stored person fact.' in section
    summary = re.search(r'<details class="scene-entry">\s*(<summary>.*?</summary>)', html, re.S)[1]
    assert 'class="scene-title"' in summary and 'class="scene-cast metadata"' in summary
    assert summary.index('class="scene-title"') < summary.index('class="scene-cast metadata"') < summary.index('Play ▶')
    assert re.search(r'<div class="outcome-header"><div class="actions">\s*'
                     r'<span class="pill-succeeded">succeeded</span>\s*'
                     r'<span class="chip">even</span></div>\s*'
                     r'<span class="metadata outcome-event">Event 4</span></div>', html)
    assert 'World · Event' not in html
