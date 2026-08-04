"""Repository 베이스 — 테이블별 CRUD 캡슐화 (backend-design §1.2).

service는 이 계층을 통해서만 DB에 접근한다. 트랜잭션(commit)은 service가 잡는다.
"""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session):
        self.session = session

    def get(self, pk) -> ModelT | None:
        return self.session.get(self.model, pk)

    def list(self, *, limit: int | None = None, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
        self.session.flush()
