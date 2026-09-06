"""Central RBAC and ABAC policy for the DocFlow application."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.schema import SensitivityLevel, UserContext

MEMBER = "member"
REVIEWER = "reviewer"
ADMIN = "admin"
TEAM_LEAD = "team_lead"
VALID_ROLES = {MEMBER, REVIEWER, ADMIN, TEAM_LEAD}


def role_for_project(user: UserContext, project_id: str) -> str | None:
    """Resolve the strongest role the user has for a project."""
    if user.is_org_admin:
        return ADMIN
    role = user.project_roles.get(project_id)
    if role == REVIEWER:
        return ADMIN
    return role if role in VALID_ROLES else None


def require_tenant(user: UserContext, tenant_id: str) -> None:
    if user.tenant_id != tenant_id:
        raise PermissionError("Resource belongs to another organization")


def can_create_project(user: UserContext) -> bool:
    """Only organization admins may create projects."""
    return bool(user.user_id and user.tenant_id and user.is_org_admin)


def require_project(user: UserContext, project_id: str, allowed_roles: Iterable[str] = VALID_ROLES) -> str:
    role = role_for_project(user, project_id)
    if role not in set(allowed_roles):
        raise PermissionError("You do not have access to this project")
    return role


def require_action(user: UserContext, project_id: str, action: str) -> str:
    """Authorize a project action using role plus project scope."""
    role = require_project(user, project_id)
    allowed = {
        "view": {MEMBER, REVIEWER, ADMIN, TEAM_LEAD},
        "upload": {MEMBER, REVIEWER, ADMIN, TEAM_LEAD},
        "draft": {MEMBER, REVIEWER, ADMIN, TEAM_LEAD},
        "submit": {MEMBER, REVIEWER, ADMIN, TEAM_LEAD},
        "approve": {REVIEWER, ADMIN, TEAM_LEAD},
        "reject": {REVIEWER, ADMIN, TEAM_LEAD},
        "pending": {REVIEWER, ADMIN, TEAM_LEAD},
        "manage_roles": {ADMIN, TEAM_LEAD},
        "audit": {ADMIN},
    }
    if role not in allowed.get(action, set()):
        raise PermissionError(f"Role '{role}' cannot perform '{action}'")
    return role


def can_view_document(
    user: UserContext,
    *,
    project_id: str,
    sensitivity_level: int,
    visible_to_teams: Iterable[str] = (),
    workflow_state: str = "draft",
    uploaded_by: str | None = None,
) -> bool:
    """Evaluate project, clearance, team, and workflow attributes."""
    role = role_for_project(user, project_id)
    if role is None and uploaded_by != user.user_id:
        return False
    if role == ADMIN:
        return True
    if sensitivity_level > user.sensitivity_clearance:
        return False
    if visible_to_teams:
        user_teams = set(user.team_memberships.get(project_id, []))
        if not user_teams.intersection(visible_to_teams):
            return False
    return True


def require_document_action(user: UserContext, document: dict, action: str) -> str:
    """Authorize a document action after enforcing tenant and attributes."""
    require_tenant(user, document["tenant_id"])
    role = require_action(user, document["project_id"], action)
    if role != ADMIN and document.get("sensitivity_level", SensitivityLevel.INTERNAL) > user.sensitivity_clearance:
        raise PermissionError("Your sensitivity clearance is insufficient for this document")
    return role