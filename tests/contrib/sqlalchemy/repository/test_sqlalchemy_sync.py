"""Unit tests for the SQLAlchemy Repository implementation."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, call
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import MappedColumn, Session

from litestar.contrib.repository.exceptions import ConflictError, RepositoryError
from litestar.contrib.repository.filters import (
    BeforeAfter,
    CollectionFilter,
    LimitOffset,
)
from litestar.contrib.sqlalchemy import base
from litestar.contrib.sqlalchemy.repository import (
    SQLAlchemySyncRepository,
    wrap_sqlalchemy_exception,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


@pytest.fixture()
def mock_repo() -> SQLAlchemySyncRepository:
    """SQLAlchemy repository with a mock model type."""

    class Repo(SQLAlchemySyncRepository[MagicMock]):
        """Repo with mocked out stuff."""

        model_type = MagicMock()  # pyright:ignore[reportGeneralTypeIssues]

    return Repo(session=MagicMock(spec=Session, bind=MagicMock()), statement=MagicMock())


def test_sqlalchemy_tablename(monkeypatch: MonkeyPatch) -> None:
    """Test the snake case conversion for table names."""

    class BigModel(base.UUIDAuditBase):
        """Inheriting from UUIDAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    class TESTModel(base.UUIDAuditBase):
        """Inheriting from UUIDAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    class BigIntModel(base.BigIntAuditBase):
        """Inheriting from BigIntAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    assert BigModel.__tablename__ == "big_model"
    assert TESTModel.__tablename__ == "test_model"
    assert BigIntModel.__tablename__ == "big_int_model"


def test_sqlalchemy_sentinel(monkeypatch: MonkeyPatch) -> None:
    """Test the sqlalchemy sentinel column only exists on `UUIDPrimaryKey` models."""

    class AnotherModel(base.UUIDAuditBase):
        """Inheriting from UUIDAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    class TheTestModel(base.UUIDBase):
        """Inheriting from DeclarativeBase gives the model 'id'  columns."""

        ...

    class TheBigIntModel(base.BigIntBase):
        """Inheriting from DeclarativeBase gives the model 'id'  columns."""

        ...

    assert isinstance(AnotherModel._sentinel, MappedColumn)
    assert isinstance(TheTestModel._sentinel, MappedColumn)
    assert isinstance(TheBigIntModel._sentinel, MappedColumn)
    model1, model2, model3 = AnotherModel(), TheTestModel(), TheBigIntModel()
    assert "created" not in model1.to_dict(exclude={"created"}).keys()
    assert "_sentinel" not in model1.to_dict().keys()
    assert "_sentinel" not in model2.to_dict().keys()
    assert "_sentinel" not in model3.to_dict().keys()


def test_wrap_sqlalchemy_integrity_error() -> None:
    """Test to ensure we wrap IntegrityError."""
    with pytest.raises(ConflictError), wrap_sqlalchemy_exception():
        raise IntegrityError(None, None, Exception())


def test_wrap_sqlalchemy_generic_error() -> None:
    """Test to ensure we wrap generic SQLAlchemy exceptions."""
    with pytest.raises(RepositoryError), wrap_sqlalchemy_exception():
        raise SQLAlchemyError


def test_sqlalchemy_repo_add(mock_repo: SQLAlchemySyncRepository) -> None:
    """Test expected method calls for add operation."""
    mock_instance = MagicMock()
    instance = mock_repo.add(mock_instance)
    assert instance is mock_instance
    mock_repo.session.add.assert_called_once_with(mock_instance)
    mock_repo.session.flush.assert_called_once()
    mock_repo.session.refresh.assert_called_once_with(mock_instance)
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_add_many(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for add many operation."""

    class UUIDModel(base.UUIDAuditBase):
        """Inheriting from UUIDAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    class BigIntModel(base.BigIntAuditBase):
        """Inheriting from BigIntAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    mock_instances = [MagicMock(), MagicMock(), MagicMock()]
    monkeypatch.setattr(mock_repo, "model_type", UUIDModel)
    monkeypatch.setattr(mock_repo.session, "scalars", MagicMock(return_value=mock_instances))
    monkeypatch.setattr(mock_repo, "model_type", BigIntModel)
    monkeypatch.setattr(mock_repo.session, "scalars", MagicMock(return_value=mock_instances))
    instances = mock_repo.add_many(mock_instances)
    assert len(instances) == 3
    for row in instances:
        assert row.id is not None
    mock_repo.session.expunge.assert_called()
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_update_many(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for update many operation."""

    class UUIDModel(base.UUIDAuditBase):
        """Inheriting from UUIDAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    class BigIntModel(base.BigIntAuditBase):
        """Inheriting from BigIntAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    mock_instances = [MagicMock(), MagicMock(), MagicMock()]

    monkeypatch.setattr(mock_repo, "model_type", UUIDModel)
    monkeypatch.setattr(mock_repo.session, "scalars", Mock(return_value=mock_instances))
    monkeypatch.setattr(mock_repo, "model_type", BigIntModel)
    monkeypatch.setattr(mock_repo.session, "scalars", MagicMock(return_value=mock_instances))
    instances = mock_repo.update_many(mock_instances)

    assert len(instances) == 3
    for row in instances:
        assert row.id is not None

    mock_repo.session.flush.assert_called_once()
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_delete(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for delete operation."""
    mock_instance = MagicMock()
    monkeypatch.setattr(mock_repo, "get", MagicMock(return_value=mock_instance))
    instance = mock_repo.delete("instance-id")
    assert instance is mock_instance
    mock_repo.session.delete.assert_called_once_with(mock_instance)
    mock_repo.session.flush.assert_called_once()
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_delete_many(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for delete operation."""

    class UUIDModel(base.UUIDAuditBase):
        """Inheriting from UUIDAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    class BigIntModel(base.BigIntAuditBase):
        """Inheriting from BigIntAuditBase gives the model 'created' and 'updated'
        columns."""

        ...

    mock_instances = [MagicMock(), MagicMock(id=uuid4())]
    monkeypatch.setattr(mock_repo.session, "scalars", MagicMock(return_value=mock_instances))
    monkeypatch.setattr(mock_repo, "model_type", UUIDModel)
    monkeypatch.setattr(mock_repo.session, "execute", MagicMock(return_value=mock_instances))
    monkeypatch.setattr(mock_repo, "model_type", BigIntModel)
    monkeypatch.setattr(mock_repo.session, "execute", MagicMock(return_value=mock_instances))
    monkeypatch.setattr(mock_repo, "list", MagicMock(return_value=mock_instances))
    added_instances = mock_repo.add_many(mock_instances)
    instances = mock_repo.delete_many([obj.id for obj in added_instances])
    assert len(instances) == len(mock_instances)
    mock_repo.session.flush.assert_called()
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_get_member(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for member get operation."""
    mock_instance = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=mock_instance)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instance = mock_repo.get("instance-id")
    assert instance is mock_instance
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_get_one_member(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for member get one operation."""
    mock_instance = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=mock_instance)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instance = mock_repo.get_one(id="instance-id")
    assert instance is mock_instance
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_get_or_create_member_existing(
    mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch
) -> None:
    """Test expected method calls for member get or create operation (existing)."""
    mock_instance = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=mock_instance)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instance, created = mock_repo.get_or_create(id="instance-id")
    assert instance is mock_instance
    assert created is False
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.add.assert_not_called()


def test_sqlalchemy_repo_get_or_create_member_created(
    mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch
) -> None:
    """Test expected method calls for member get or create operation (created)."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instance, created = mock_repo.get_or_create(id="new-id")
    assert instance is not None
    assert created is True
    mock_repo.session.expunge.assert_called_once_with(instance)
    mock_repo.session.add.assert_called_once_with(instance)


def test_sqlalchemy_repo_get_one_or_none_member(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for member get one or none operation (found)."""
    mock_instance = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=mock_instance)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instance = mock_repo.get_one_or_none(id="instance-id")
    assert instance is mock_instance
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_get_one_or_none_not_found(
    mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch
) -> None:
    """Test expected method calls for member get one or none operation (Not found)."""

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instance = mock_repo.get_one_or_none(id="instance-id")
    assert instance is None
    mock_repo.session.expunge.assert_not_called()
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_list(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for list operation."""
    mock_instances = [MagicMock(), MagicMock()]
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=mock_instances)
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instances = mock_repo.list()
    assert instances == mock_instances
    mock_repo.session.expunge.assert_has_calls(*mock_instances)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_list_and_count(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for list operation."""
    mock_instances = [MagicMock(), MagicMock()]
    mock_count = len(mock_instances)
    execute_mock = MagicMock(return_value=iter([(mock, mock_count) for mock in mock_instances]))
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    instances, instance_count = mock_repo.list_and_count()
    assert instances == mock_instances
    assert instance_count == mock_count
    mock_repo.session.expunge.assert_has_calls(*mock_instances)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_exists(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for exists operation."""
    result_mock = MagicMock()
    count_mock = MagicMock()
    execute_mock = MagicMock(return_value=result_mock)
    execute_count_mock = MagicMock(return_value=count_mock)
    monkeypatch.setattr(mock_repo, "count", execute_count_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    mock_repo.count.return_value = 1
    exists = mock_repo.exists(id="my-id")
    assert exists
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_count(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test expected method calls for list operation."""
    result_mock = MagicMock()
    count_mock = MagicMock()
    execute_mock = MagicMock(return_value=result_mock)
    execute_count_mock = MagicMock(return_value=count_mock)
    monkeypatch.setattr(mock_repo, "count", execute_count_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    mock_repo.count.return_value = 1
    count = mock_repo.count()
    assert count == 1
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_list_with_pagination(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test list operation with pagination."""
    result_mock = MagicMock()
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    mock_repo.statement.limit.return_value = mock_repo.statement
    mock_repo.statement.offset.return_value = mock_repo.statement
    mock_repo.list(LimitOffset(2, 3))
    mock_repo.statement.limit.assert_called_once_with(2)
    mock_repo.statement.limit().offset.assert_called_once_with(3)  # type:ignore[call-arg]


def test_sqlalchemy_repo_list_with_before_after_filter(
    mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch
) -> None:
    """Test list operation with BeforeAfter filter."""
    field_name = "updated"
    # model has to support comparison with the datetimes
    getattr(mock_repo.model_type, field_name).__lt__ = lambda self, compare: "lt"
    getattr(mock_repo.model_type, field_name).__gt__ = lambda self, compare: "gt"
    result_mock = MagicMock()
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    mock_repo.statement.where.return_value = mock_repo.statement
    mock_repo.list(BeforeAfter(field_name, datetime.max, datetime.min))
    assert mock_repo.statement.where.call_count == 2
    assert mock_repo.statement.where.has_calls([call("gt"), call("lt")])


def test_sqlalchemy_repo_list_with_collection_filter(
    mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch
) -> None:
    """Test behavior of list operation given CollectionFilter."""
    field_name = "id"
    result_mock = MagicMock()
    execute_mock = MagicMock(return_value=result_mock)
    monkeypatch.setattr(mock_repo, "_execute", execute_mock)
    mock_repo.statement.where.return_value = mock_repo.statement
    values = [1, 2, 3]
    mock_repo.list(CollectionFilter(field_name, values))
    mock_repo.statement.where.assert_called_once()
    getattr(mock_repo.model_type, field_name).in_.assert_called_once_with(values)


def test_sqlalchemy_repo_unknown_filter_type_raises(mock_repo: SQLAlchemySyncRepository) -> None:
    """Test that repo raises exception if list receives unknown filter type."""
    with pytest.raises(RepositoryError):
        mock_repo.list("not a filter")  # type:ignore[arg-type]


def test_sqlalchemy_repo_update(mock_repo: SQLAlchemySyncRepository, monkeypatch: MonkeyPatch) -> None:
    """Test the sequence of repo calls for update operation."""
    id_ = 3
    mock_instance = MagicMock()
    get_id_value_mock = MagicMock(return_value=id_)
    monkeypatch.setattr(mock_repo, "get_id_attribute_value", get_id_value_mock)
    get_mock = MagicMock()
    monkeypatch.setattr(mock_repo, "get", get_mock)
    mock_repo.session.merge.return_value = mock_instance
    instance = mock_repo.update(mock_instance)
    assert instance is mock_instance
    mock_repo.session.merge.assert_called_once_with(mock_instance)
    mock_repo.session.flush.assert_called_once()
    mock_repo.session.refresh.assert_called_once_with(mock_instance)
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_sqlalchemy_repo_upsert(mock_repo: SQLAlchemySyncRepository) -> None:
    """Test the sequence of repo calls for upsert operation."""
    mock_instance = MagicMock()
    mock_repo.session.merge.return_value = mock_instance
    instance = mock_repo.upsert(mock_instance)
    assert instance is mock_instance
    mock_repo.session.merge.assert_called_once_with(mock_instance)
    mock_repo.session.flush.assert_called_once()
    mock_repo.session.refresh.assert_called_once_with(mock_instance)
    mock_repo.session.expunge.assert_called_once_with(mock_instance)
    mock_repo.session.commit.assert_not_called()


def test_attach_to_session_unexpected_strategy_raises_valueerror(
    mock_repo: SQLAlchemySyncRepository,
) -> None:
    """Test to hit the error condition in SQLAlchemy._attach_to_session()."""
    with pytest.raises(ValueError):
        mock_repo._attach_to_session(MagicMock(), strategy="t-rex")  # type:ignore[arg-type]


def testexecute(mock_repo: SQLAlchemySyncRepository) -> None:
    """Simple test of the abstraction over `Session.execute()`"""
    _ = mock_repo._execute(mock_repo.statement)
    mock_repo.session.execute.assert_called_once_with(mock_repo.statement)


def test_filter_in_collection_noop_if_collection_empty(mock_repo: SQLAlchemySyncRepository) -> None:
    """Ensures we don't filter on an empty collection."""
    mock_repo._filter_in_collection("id", [], statement=mock_repo.statement)
    mock_repo.statement.where.assert_not_called()


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (datetime.max, datetime.min),
        (None, datetime.min),
        (datetime.max, None),
    ],
)
def test__filter_on_datetime_field(before: datetime, after: datetime, mock_repo: SQLAlchemySyncRepository) -> None:
    """Test through branches of _filter_on_datetime_field()"""
    field_mock = MagicMock()
    field_mock.__gt__ = field_mock.__lt__ = lambda self, other: True
    mock_repo.model_type.updated = field_mock
    mock_repo._filter_on_datetime_field("updated", before, after, statement=mock_repo.statement)


def test_filter_collection_by_kwargs(mock_repo: SQLAlchemySyncRepository) -> None:
    """Test `filter_by()` called with kwargs."""
    _ = mock_repo.filter_collection_by_kwargs(mock_repo.statement, a=1, b=2)
    mock_repo.statement.filter_by.assert_called_once_with(a=1, b=2)


def test_filter_collection_by_kwargs_raises_repository_exception_for_attribute_error(
    mock_repo: SQLAlchemySyncRepository,
) -> None:
    """Test that we raise a repository exception if an attribute name is
    incorrect."""
    mock_repo.statement.filter_by = MagicMock(  # type:ignore[method-assign]
        side_effect=InvalidRequestError,
    )
    with pytest.raises(RepositoryError):
        _ = mock_repo.filter_collection_by_kwargs(mock_repo.statement, a=1)
