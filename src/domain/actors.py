from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


ACTOR_SCHEMA_VERSION = "1.0"
AbilityName = Literal[
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus_for_level(level: int) -> int:
    if not 1 <= level <= 20:
        raise ValueError("level must be between 1 and 20")
    return 2 + (level - 1) // 4


def proficiency_bonus_for_cr(challenge_rating: float) -> int:
    if not 0 <= challenge_rating <= 30:
        raise ValueError("challenge rating must be between 0 and 30")
    if challenge_rating < 5:
        return 2
    return 3 + int((challenge_rating - 5) // 4)


class AbilityScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strength: int = Field(ge=1, le=30)
    dexterity: int = Field(ge=1, le=30)
    constitution: int = Field(ge=1, le=30)
    intelligence: int = Field(ge=1, le=30)
    wisdom: int = Field(ge=1, le=30)
    charisma: int = Field(ge=1, le=30)

    def modifier(self, ability: AbilityName) -> int:
        return ability_modifier(getattr(self, ability))


class CharacterSheet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = ACTOR_SCHEMA_VERSION
    kind: Literal["character"] = "character"
    name: str = Field(min_length=1, max_length=100)
    ancestry: str = Field(min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=100)
    level: int = Field(ge=1, le=20)
    armor_class: int = Field(ge=1, le=40)
    hit_point_max: int = Field(ge=1, le=1000)
    perception_proficient: bool = False
    abilities: AbilityScores
    notes: str = Field(default="", max_length=4000)

    @field_validator("name", "ancestry", "class_name")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @computed_field
    @property
    def proficiency_bonus(self) -> int:
        return proficiency_bonus_for_level(self.level)

    @computed_field
    @property
    def passive_perception(self) -> int:
        bonus = self.abilities.modifier("wisdom")
        if self.perception_proficient:
            bonus += self.proficiency_bonus
        return 10 + bonus


class MonsterSheet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = ACTOR_SCHEMA_VERSION
    kind: Literal["monster"] = "monster"
    name: str = Field(min_length=1, max_length=100)
    size: Literal["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]
    creature_type: str = Field(min_length=1, max_length=100)
    challenge_rating: float = Field(ge=0, le=30)
    armor_class: int = Field(ge=1, le=40)
    hit_point_max: int = Field(ge=1, le=5000)
    speed: str = Field(min_length=1, max_length=200)
    primary_ability: AbilityName
    abilities: AbilityScores
    traits: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    notes: str = Field(default="", max_length=4000)

    @field_validator("name", "creature_type", "speed")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @computed_field
    @property
    def proficiency_bonus(self) -> int:
        return proficiency_bonus_for_cr(self.challenge_rating)

    @computed_field
    @property
    def attack_bonus(self) -> int:
        return self.proficiency_bonus + self.abilities.modifier(self.primary_ability)

    @computed_field
    @property
    def save_dc(self) -> int:
        return 8 + self.attack_bonus
