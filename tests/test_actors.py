from fastapi.testclient import TestClient

from src.domain.actors import (
    AbilityScores,
    CharacterSheet,
    MonsterSheet,
    ability_modifier,
    proficiency_bonus_for_cr,
    proficiency_bonus_for_level,
)
from src.web import db
from src.web.app import app


def _isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(db, "db_path", lambda: tmp_path / "app.db")
    db.init_db()


def test_deterministic_actor_calculations():
    assert ability_modifier(9) == -1
    assert ability_modifier(10) == 0
    assert ability_modifier(18) == 4
    assert proficiency_bonus_for_level(1) == 2
    assert proficiency_bonus_for_level(9) == 4
    assert proficiency_bonus_for_cr(0.125) == 2
    assert proficiency_bonus_for_cr(5) == 3
    assert proficiency_bonus_for_cr(21) == 7

    abilities = AbilityScores(
        strength=18,
        dexterity=14,
        constitution=16,
        intelligence=8,
        wisdom=12,
        charisma=10,
    )
    character = CharacterSheet(
        name="Aria",
        ancestry="Human",
        class_name="Fighter",
        level=5,
        armor_class=18,
        hit_point_max=44,
        perception_proficient=True,
        abilities=abilities,
    )
    assert character.proficiency_bonus == 3
    assert character.passive_perception == 14

    monster = MonsterSheet(
        name="Ash Drake",
        size="Large",
        creature_type="dragon",
        challenge_rating=5,
        armor_class=17,
        hit_point_max=95,
        speed="40 ft., fly 60 ft.",
        primary_ability="strength",
        abilities=abilities,
        actions=("Bite", "Cinder Breath"),
    )
    assert monster.proficiency_bonus == 3
    assert monster.attack_bonus == 7
    assert monster.save_dc == 15


def test_actor_persistence_and_json_export(monkeypatch, tmp_path):
    _isolated_db(monkeypatch, tmp_path)
    campaign = db.create_campaign("Actors")
    client = TestClient(app)

    character_response = client.post(
        f"/campaigns/{campaign.id}/characters",
        data={
            "name": "Aria",
            "ancestry": "Human",
            "class_name": "Fighter",
            "level": 5,
            "armor_class": 18,
            "hit_point_max": 44,
            "strength": 18,
            "dexterity": 14,
            "constitution": 16,
            "intelligence": 8,
            "wisdom": 12,
            "charisma": 10,
            "perception_proficient": "true",
        },
    )
    assert character_response.status_code == 200
    assert "Passive Perception 14" in character_response.text

    monster_response = client.post(
        f"/campaigns/{campaign.id}/monsters",
        data={
            "name": "Ash Drake",
            "size": "Large",
            "creature_type": "dragon",
            "challenge_rating": 5,
            "armor_class": 17,
            "hit_point_max": 95,
            "speed": "40 ft., fly 60 ft.",
            "primary_ability": "strength",
            "strength": 18,
            "dexterity": 14,
            "constitution": 16,
            "intelligence": 8,
            "wisdom": 12,
            "charisma": 10,
            "traits": "Heated Body",
            "actions": "Bite\nCinder Breath",
        },
    )
    assert monster_response.status_code == 200
    assert "Attack +7" in monster_response.text
    assert "Cinder Breath" in monster_response.text

    actors = db.list_actors(campaign.id)
    assert [actor.name for actor in actors] == ["Aria", "Ash Drake"]
    exported = client.get(f"/actors/{actors[0].id}.json")
    assert exported.status_code == 200
    assert exported.json()["schema_version"] == "1.0"
    assert exported.json()["proficiency_bonus"] == 3


def test_invalid_actor_form_returns_validation_details(monkeypatch, tmp_path):
    _isolated_db(monkeypatch, tmp_path)
    campaign = db.create_campaign("Validation")

    response = TestClient(app).post(
        f"/campaigns/{campaign.id}/characters",
        data={
            "name": " ",
            "ancestry": "Human",
            "class_name": "Fighter",
            "level": 1,
            "armor_class": 10,
            "hit_point_max": 10,
            "strength": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["name"]
