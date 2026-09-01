"""On-ramp application database — ORM models (W5).

This is the "designated database" (``docs/website_production_overview.md`` §3): on-ramp-private
storage for accounts, restaurants, sessions, and staged uploads. It is **not** the seam — never
imported by ``forecasting/``, never written through ``schemas/``, never placed under ``data/``
(the seam directory owned by neither peer; see ``engine.py`` for where the file actually lives).

Six tables landed in W5, matching the schema sketch in ``website_production_overview.md`` §3:
``restaurants`` · ``users`` · ``memberships`` (user<->restaurant, role) · ``credentials`` (argon2
hash + a single pending reset token) · ``sessions`` (revocable, DB-listed) · ``staged_uploads``
(payload/kind/expiry, replacing W1-W4's hidden-base64-form-field round trip). ``audit_log`` is
in that sketch too but deliberately not built here — nothing in this phase writes or reads one
yet; see ``docs/phase_decisions/W5.md`` Explicitly Deferred.

W6 adds a seventh: ``dishes`` (the operator-maintained menu-price catalog — see ``Dish`` below).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _new_id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    """Naive datetime representing the current UTC instant — deliberately not tz-aware.
    SQLite (this app DB's engine today) has no native timezone type: SQLAlchemy's plain
    ``DateTime`` column round-trips a tz-aware value back as *naive* on read, so an aware
    ``_utcnow()`` compared against a value freshly read from the DB raises ``TypeError: can't
    compare offset-naive and offset-aware datetimes``. Every stored/compared timestamp in this
    module uses this same naive-but-UTC convention, so comparisons are always apples to apples."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Restaurant(Base):
    """A tenant. W5 gives the app DB real multi-row tenancy; the seam (``data/raw/``) stays a
    flat, unpartitioned directory regardless — physically partitioning it is W9's job, gated on
    a second real tenant (``docs/website_production_overview.md`` §4)."""

    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="restaurant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    credential: Mapped["Credential | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base):
    """A user's role at a restaurant — one row per (user, restaurant) pair. W5 only ever
    creates one membership per account (the invite-only CLI bootstraps one restaurant + one
    owner in a single transaction); the table exists so W10's "team access + roles" has
    somewhere to add rows without a schema change."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "restaurant_id", name="uq_membership_user_restaurant"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    role: Mapped[str] = mapped_column(nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    restaurant: Mapped["Restaurant"] = relationship(back_populates="memberships")


class Credential(Base):
    """One row per user: the argon2id password hash plus, at most, one live password-reset
    token. ``reset_token_hash`` stores a SHA-256 hash of the token, never the raw value — the
    same "hash what you store" discipline as ``Session.token_hash`` below, so a DB read/backup
    never hands out a directly usable reset link."""

    __tablename__ = "credentials"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    reset_token_hash: Mapped[str | None] = mapped_column(default=None)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(default=None)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="credential")


class Session(Base):
    """A revocable login session — the production answer to W2's ephemeral, unlistable,
    itsdangerous-signed cookie. The cookie carries only the opaque random token
    (``src/auth/credentials.py::generate_token``); ``token_hash`` (SHA-256) is what's stored,
    so a DB read never yields a live, directly usable session token. ``restaurant_id`` is the
    session's tenant context (identity/audit only in W5 — ``data/raw/`` reads stay global until
    W9 partitions the seam)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class Dish(Base):
    """The operator-maintained menu-price catalog (W6) -- the one seam input the PoC never
    asked for. ``data/raw/bom.parquet`` has quantities/units and
    ``data/raw/price_observations.parquet`` has ingredient unit prices, but no dish's *menu
    price* crosses the seam anywhere (``data/CONTRACT.md``'s "Co provenance" forward note). Menu
    price is *user/operational* catalog data under the two-store laws
    (``docs/website_production_overview.md`` §3) -- it lives here, app-DB-only, and never
    crosses into ``data/raw/``; only the *derived* food-cost this phase also introduces does that
    (``src/costing/tenant_grid.py::FoodCostRow``).

    Keyed by ``(restaurant_id, dish_name)`` rather than the seam's own ``dish_id``: that id is
    itself just ``normalize_name(dish_name)`` (``schemas/seam.py::BomRow``), so storing the
    display name here and normalizing at join time (``src/costing/menu_prices.py``) reuses that
    one canonical function instead of persisting a second, parallel id. ``id`` is still a real
    UUID primary key -- the "stable item_id introduced app-side" production overview §6 asks
    for; carrying it into the seam schemas themselves is W9's job.
    """

    __tablename__ = "dishes"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "dish_name", name="uq_dish_restaurant_name"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    dish_name: Mapped[str] = mapped_column(nullable=False)
    menu_price: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)


class StagedUpload(Base):
    """A confirmed-pending upload payload, replacing W1-W4's hidden-base64-form-field round
    trip: ``/upload`` and ``/invoice/upload`` now stage the parsed bytes here and hand the
    client back only this row's opaque ``id``; ``/confirm``/``/invoice/confirm`` fetch, re-
    validate, and consume it. ``payload`` holds the base64-encoded file contents keyed by the
    same field names the old hidden inputs used (``sales_csv_b64``/``bom_csv_b64`` for
    ``kind="bom_sales"``, ``invoice_csv_b64`` for ``kind="invoice"``) so the parse/validate call
    sites barely change shape. ``consumed_at`` makes a staged upload single-use."""

    __tablename__ = "staged_uploads"

    id: Mapped[str] = mapped_column(primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id"), nullable=False)
    kind: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(default=None)
