import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base, get_session
from app.main import app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'goals.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    def override():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


def user(client, email='goal@example.org'):
    return client.post('/users', json={'name': 'Goal user', 'email': email, 'monthly_income': '5000'}).json()['id']


def goal(**changes):
    return dict(name=' Course fees ', target_amount='6000', saved_amount='0', target_date='2027-09-24', priority='medium', **changes) if not changes else {**goal(), **changes}


def test_goal_lifecycle_and_owner_scope(client):
    owner, other = user(client), user(client, 'other@example.org')
    path = f'/users/{owner}/goals'
    created = client.post(path, json=goal())
    assert created.status_code == 201
    record = created.json()
    assert record['name'] == 'Course fees'
    assert record['archived'] is False
    item = f"{path}/{record['id']}"
    assert client.put(f"/users/{other}/goals/{record['id']}", json=goal()).status_code == 404
    assert client.patch(f"/users/{other}/goals/{record['id']}", json={'archived': True}).status_code == 404
    assert client.get(f'/users/{other}/goals').json() == []
    for _ in range(2):
        assert client.patch(item, json={'archived': True}).json()['archived'] is True
    assert client.get(path).json() == []
    assert len(client.get(path, params={'include_archived': True}).json()) == 1
    edited = client.put(item, json=goal(saved_amount='7000', target_date='2020-01-01'))
    assert edited.status_code == 200
    assert edited.json()['archived'] is True
    assert edited.json()['saved_amount'] == '7000.00'
    assert client.patch(item, json={'archived': False}).json()['archived'] is False
    assert len(client.get(path).json()) == 1
    assert client.get('/users/999/goals').status_code == 404
    assert client.post('/users/999/goals', json=goal()).status_code == 404
    assert client.put(f'{path}/999', json=goal()).status_code == 404


@pytest.mark.parametrize('changes', [
    {'name': ' '}, {'name': 'a' * 101}, {'target_amount': '0'}, {'target_amount': '-1'},
    {'saved_amount': '-1'}, {'saved_amount': '0.001'}, {'target_amount': '10000000000'},
    {'priority': 'urgent'}, {'target_date': 'bad-date'},
])
def test_goal_validation(client, changes):
    path = f'/users/{user(client)}/goals'
    assert client.post(path, json=goal(**changes)).status_code == 422
    assert client.get(path).json() == []


def test_goal_overfunding_and_overdue_are_valid(client):
    path = f'/users/{user(client)}/goals'
    assert client.post(path, json=goal(saved_amount='7000', target_date='2020-01-01')).status_code == 201


def test_archive_preflight_is_allowed(client):
    response = client.options('/users/1/goals/1', headers={
        'Origin': 'http://127.0.0.1:5173', 'Access-Control-Request-Method': 'PATCH',
    })
    assert response.status_code == 200
