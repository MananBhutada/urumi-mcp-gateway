import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/gateway"))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.session import Base
from app.models.tables import User
from app.api.admin import InviteIn, AcceptInviteIn, create_invitation, accept_invitation


def test_invitation_is_one_time_and_returns_member_key():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin = User(email="admin@example.com", name="Admin", role="ADMIN")
        db.add(admin)
        db.commit()
        db.refresh(admin)

        invite = create_invitation(InviteIn(email="New.Member@example.com"), db, admin)
        assert invite["email"] == "new.member@example.com"
        assert invite["role"] == "MEMBER"
        assert invite["invite_token"]
        assert invite["expires_at"] > 0

        accepted = accept_invitation(AcceptInviteIn(token=invite["invite_token"], name="New Member"), db)
        assert accepted["user"]["email"] == "new.member@example.com"
        assert accepted["user"]["role"] == "MEMBER"
        assert accepted["api_key"].startswith("urumi_live_")

        try:
            accept_invitation(AcceptInviteIn(token=invite["invite_token"]), db)
            assert False, "an invitation must not be reusable"
        except HTTPException as exc:
            assert exc.status_code == 400
