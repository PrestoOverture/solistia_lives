import json
import re
from html import unescape
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from story_engine.web import create_app


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
        assert '<th scope="col">Private intent</th>' in html.text
        assert '<td>A private reason.</td>' in html.text
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
    overview = re.search(r'<table id="thread-overview">(.*?)</table>', html, re.S)[1]
    colgroup = re.search(r'<colgroup>(.*?)</colgroup>', overview, re.S)
    assert colgroup is not None
    columns = re.findall(r'<col\b[^>]*>', colgroup[1])
    assert len(columns) == 6
    headers = re.findall(r'<th\b[^>]*>(.*?)</th>', overview)
    summary_column = columns[headers.index('Summary')]
    width = re.search(r'width:\s*([\d.]+)%', summary_column)
    assert width is not None and float(width[1]) >= 50
    round_tables = re.findall(r'<table>(.*?)</table>', html, re.S)
    assert round_tables
    for table in round_tables:
        assert '<colgroup' not in table
        assert re.findall(r'<th\b[^>]*>(.*?)</th>', table) == ['Did / said', 'Private intent']
    rows = re.findall(r'<tr>(.*?)</tr>', overview.split('<tbody>')[1], re.S)
    assert len(rows) == len(data['threads']) == 2
    for row, thread in zip(rows, data['threads']):
        target = re.search(r'href="#([^"]+)"', row)[1]
        assert target == f"thread-{thread['id']}"
        assert f'<section id="{target}">' in html
        assert thread['kind'] in row and thread['summary'] in row
        assert 'Agnea Bristarni' in row
        assert f'<td>{len(thread["scenes"])}</td>' in row
    assert '<td>Start</td>' in rows[0]
    assert 'dropped · Day 1 afternoon · by the clock' in rows[0]
    assert '<td>Day 1 morning</td>' in rows[1]
    assert 'resolved · Day 1 afternoon' in rows[1]
    assert '2 of 4 scenes are in no thread' in html
    assert '<pre' not in html.lower()
    assert 'Day 1 afternoon · Scene 2 · status → resolved' in html
    assert 'situation · id → later · next → Changed' in html
    assert 'Cropdale / square' in html and 'cropdale / square' not in html
    scene = data['threads'][1]['scenes'][0]
    assert scene['place'] == 'cropdale' and scene['place_name'] == 'Cropdale'
    unthreaded = html.split('<section id="unthreaded">')[1].split('</section>')[0]
    assert re.search(r'<h3>Day 1</h3>.*Scene 3.*Scene 4', unthreaded, re.S)
    heading = re.search(r'<section id="thread-start">\s*<h2>(.*?)</h2>', html, re.S)[1]
    assert unescape(heading) == 'start · trouble'
    assert '<p>Opaque summary</p>' in html


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
    assert 'unknown_place / square' in html
    assert next(s for s in data['unthreaded'] if s['id'] == '3')['place_name'] == 'unknown_place'
    unthreaded = html.split('<section id="unthreaded">')[1].split('</section>')[0]
    assert re.search(r'<h3>Day 1</h3>.*Scene 4.*<h3>Day 2</h3>.*Scene 3', unthreaded, re.S)


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
    scene_html = re.search(r'<details>\s*<summary>Scene 1 .*?</details>', html, re.S)[0]
    first, second = scene_html.split('<h4>Round 2</h4>')
    assert first.count('A spoken line.') == 1
    assert first.index('A visible move.') < first.index('Leaves the square.') < first.index('Waits nearby.')
    assert '<td>Find a quiet place.</td>' in first
    assert 'World · Event 4' not in first and 'World · Event 4' in second
    assert 'World · Event 12' not in html and '<h4>Round 3</h4>' not in scene_html
    assert 'No floor move recorded' not in html
    elsewhere = html.split('<section id="elsewhere">')[1].split('</section>')[0]
    assert 'News from elsewhere.' in elsewhere
    assert '<details><summary>morning</summary>' in elsewhere
    assert 13 in [e['id'] for e in data['elsewhere']]
    assert 5 not in [e['id'] for e in data['elsewhere']]
    thread = data['threads'][0]
    assert [(e['status'], e['event_id'], e['by_clock']) for e in thread['status_history']] == [
        ('dropped', 7, True), ('resolved', 14, False)]
    sequence = 'dropped · Day 1 afternoon · by the clock → resolved · Day 1 evening'
    overview = html.split('<table id="thread-overview">')[1].split('</table>')[0]
    section = html.split('<section id="thread-start">')[1].split('</section>')[0]
    assert sequence in overview and sequence in section
    assert 'min-width: 1100px' in html and 'overflow-x: auto' in html
    assert '#thread-overview td { overflow-wrap: normal; word-break: normal;' in html


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
        assert 'succeeded · even' in client.get('/world/fixture/chronicle').text
