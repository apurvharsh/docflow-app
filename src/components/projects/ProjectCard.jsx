import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Folder } from 'lucide-react';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

const formatDate = (isoString) => {
  if (!isoString) return '';
  const date = new Date(isoString);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('en-IN', { dateStyle: 'medium' });
};

const ROLE_LABELS = {
  org_admin: 'Organization Admin',
  admin: 'Project Admin',
  team_lead: 'Team Lead',
  reviewer: 'Reviewer',
  member: 'Member',
};

const ProjectCard = ({ project, role, teamName }) => {
  const navigate = useNavigate();
  const roleLabel = ROLE_LABELS[role] || 'Role not assigned';
  const accessTeam = role === 'org_admin' ? 'All teams' : (teamName || 'Team not assigned');
  const canManageAccess = ['org_admin', 'admin', 'team_lead'].includes(role);
  return (
    <Card
      title={(
        <Link
          to={`/projects/${encodeURIComponent(project.project_id)}`}
          onClick={(event) => event.stopPropagation()}
          className="hover:text-primary transition-colors"
          aria-label={`Open ${project.project_name} as ${roleLabel}`}
        >
          {project.project_name}
        </Link>
      )}
      description={project.description || 'No description yet.'}
      icon={Folder}
      className="h-full min-h-[220px]"
      hoverable
      onClick={() => navigate(`/projects/${project.project_id}`)}
      footer={
        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <Badge variant="active">{project.document_count} doc{project.document_count === 1 ? '' : 's'}</Badge>
            <Badge variant="neutral">{roleLabel}</Badge>
          </div>
          <div className="space-y-1 text-xs text-gray-500">
            <p>Access: <span className="text-gray-300">{roleLabel}</span></p>
            <p>Team: <span className="text-gray-300">{accessTeam}</span></p>
            {project.assigned_teams?.length > 0 && (
              <p>Assigned team: {project.assigned_teams.join(', ')}</p>
            )}
            <p>Start date: {formatDate(project.created_at) || formatDate(project.updated_at) || 'Not available'}</p>
            {canManageAccess && (
              <Link
                to={`/admin?project_id=${encodeURIComponent(project.project_id)}`}
                onClick={(event) => event.stopPropagation()}
                className="inline-flex pt-1 text-primary-light hover:text-primary underline underline-offset-2"
              >
                {role === 'team_lead' ? 'Manage team access' : 'Manage project access'}
              </Link>
            )}
          </div>
        </div>
      }
    />
  );
};

export default ProjectCard;
