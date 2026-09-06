import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, UploadCloud } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { projectsApi, documentsApi } from '../lib/api';
import { STAGES } from '../constants/stages';
import { DOC_TYPES, SENSITIVITY_LEVELS } from '../constants/docTypes';
import Input from '../components/ui/Input';
import Dropdown from '../components/ui/Dropdown';
import Button from '../components/ui/Button';
import Textarea from '../components/ui/Textarea';

const stageOptions = STAGES.map((s) => ({ label: s, value: s }));
const docTypeOptions = DOC_TYPES.map((t) => ({ label: t, value: t }));
const teamOptions = ['Engineering', 'Design', 'Product', 'QA'].map((team) => ({ label: team, value: team }));
const sensitivityOptions = SENSITIVITY_LEVELS.map((s) => ({ label: s.label, value: String(s.value) }));
const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024;

const UploadDocumentPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [documentName, setDocumentName] = useState('');
  const [stage, setStage] = useState('');
  const [docType, setDocType] = useState('');
  const [files, setFiles] = useState([]);

  const [description, setDescription] = useState('');
  const [teamVisibility, setTeamVisibility] = useState('');
  const [sensitivity, setSensitivity] = useState('1');

  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  const availableTeamOptions = [{ label: 'Visible to all teams', value: '' }, ...teamOptions];

  const handleFileDrop = (e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer?.files || []);
    if (droppedFiles.length > 0) setSelectedFiles(droppedFiles);
  };

  const handleFileSelect = (e) => {
    setSelectedFiles(Array.from(e.target.files || []));
  };

  const setSelectedFiles = (selectedFiles) => {
    setFiles(selectedFiles.slice(0, 100));
    if (!documentName && selectedFiles[0]) setDocumentName(selectedFiles[0].name);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const newErrors = {};
    if (!documentName.trim()) newErrors.documentName = 'Document Name is required.';
    if (!stage) newErrors.stage = 'Stage is required.';
    if (!docType) newErrors.docType = 'Document type is required.';
    if (files.length === 0) newErrors.file = 'At least one file is required.';
    if (files.some((selectedFile) => selectedFile.size > MAX_UPLOAD_SIZE_BYTES)) newErrors.file = 'Every file must be 10 MB or smaller.';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSubmitting(true);
    setSubmitError('');
    try {
      // Look up (or fall back to) the human-readable project name for the ingestion header.
      let projectName = projectId;
      try {
        const projects = await projectsApi.list();
        projectName = projects.find((p) => p.project_id === projectId)?.project_name || projectId;
      } catch {
        // non-fatal — fall back to the id
      }

      const formData = new FormData();
      files.forEach((selectedFile) => formData.append('files', selectedFile, selectedFile.name));
      formData.append('project_id', projectId);
      formData.append('project_name', projectName);
      formData.append('stage', stage);
      formData.append('doc_type', docType);
      formData.append('visible_to_teams', teamVisibility || '');
      formData.append('sensitivity_level', sensitivity);

      if (files.length === 1) {
        formData.delete('files');
        formData.append('file', files[0], documentName || files[0].name);
        await documentsApi.upload(formData);
      } else {
        await documentsApi.uploadBatch(formData);
      }
      navigate(`/projects/${projectId}`);
    } catch (err) {
      setSubmitError(err.message || 'Upload failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-background">
      <div className="h-14 border-b border-border bg-background px-6 flex items-center shrink-0">
        <Link to={`/projects/${projectId}`} className="text-gray-400 hover:text-gray-200 transition-colors flex items-center gap-1 text-sm">
          <ArrowLeft size={16} />
          Back to Project
        </Link>
      </div>

      <div className="max-w-3xl mx-auto w-full p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-100">Upload Document</h1>
          <p className="text-gray-400 mt-1">Add a new document to this project's sources. It will be chunked and indexed for the AI assistant.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleFileDrop}
            className={`w-full border-2 border-dashed rounded-xl p-12 flex flex-col items-center justify-center text-center transition-colors
              {errors.file ? 'border-red-500 bg-red-500/5' : 'border-border hover:border-primary/50 hover:bg-surface-hover/50 bg-surface'}
            `}
          >
            <UploadCloud size={48} className={errors.file ? 'text-red-400' : 'text-primary mb-4'} />
              {files.length > 0 ? (
              <div>
                  <p className="text-gray-200 font-medium mb-1">{files.length} file{files.length === 1 ? '' : 's'} selected</p>
                  <div className="text-gray-500 text-sm space-y-1 max-w-md">
                    {files.slice(0, 4).map((selectedFile) => <p key={`${selectedFile.name}-${selectedFile.size}`} className="truncate">{selectedFile.name} · {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>)}
                    {files.length > 4 && <p>+ {files.length - 4} more</p>}
                  </div>
                  <Button type="button" variant="ghost" size="sm" className="mt-4" onClick={() => setFiles([])}>
                  Remove file
                </Button>
              </div>
            ) : (
              <div>
                <p className="text-gray-300 font-medium mb-1">Drag and drop your file here</p>
                <p className="text-gray-500 text-sm mb-4">Supported: PDF, DOCX, DOC, PPTX, PPT, TXT, MD, JSON · 10 MB maximum</p>
                <label className="cursor-pointer">
                  <span className="bg-primary text-white hover:bg-primary-dark shadow-sm inline-flex items-center justify-center font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 h-10 px-4 py-2 text-sm">
                    Browse Files
                  </span>
                  <input
                    type="file"
                    className="hidden"
                    onChange={handleFileSelect}
                    multiple
                    accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.md,.json"
                  />
                </label>
              </div>
            )}
            {errors.file && <p className="text-red-400 text-sm mt-4">{errors.file}</p>}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-200 border-b border-border pb-2">Required Details</h3>
              <Input
                label="Document Name"
                placeholder="e.g. Q3 Financial Report.pdf"
                required
                value={documentName}
                onChange={(e) => { setDocumentName(e.target.value); if (errors.documentName) setErrors({ ...errors, documentName: null }); }}
                error={errors.documentName}
              />
              <Dropdown
                label="Stage"
                placeholder="Select a stage"
                options={stageOptions}
                value={stage}
                onChange={(val) => { setStage(val); if (errors.stage) setErrors({ ...errors, stage: null }); }}
                error={errors.stage}
              />
              <Dropdown
                label="Document Type"
                placeholder="Select a document type"
                options={docTypeOptions}
                value={docType}
                onChange={(val) => { setDocType(val); if (errors.docType) setErrors({ ...errors, docType: null }); }}
                error={errors.docType}
              />
            </div>

            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-200 border-b border-border pb-2">Access Control</h3>
              <Dropdown
                label="Team Visibility"
                placeholder="Visible to all teams"
                options={availableTeamOptions}
                value={teamVisibility}
                onChange={setTeamVisibility}
              />
              <Dropdown
                label="Sensitivity Level"
                options={sensitivityOptions}
                value={sensitivity}
                onChange={setSensitivity}
              />
            </div>
          </div>

          <Textarea
            label="Description (optional, not stored yet — for your own notes)"
            placeholder="Provide context about this document..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="bg-surface p-4 rounded-lg border border-border flex gap-8">
            <div>
              <p className="text-xs text-gray-500 uppercase font-medium mb-1">Uploaded By</p>
              <p className="text-sm text-gray-200">{user?.full_name || user?.username}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase font-medium mb-1">Upload Date</p>
              <p className="text-sm text-gray-200">{new Date().toLocaleDateString()}</p>
            </div>
          </div>

          {submitError && <p className="text-red-400 text-sm">{submitError}</p>}

          <div className="flex justify-end gap-4 pt-6 border-t border-border">
            <Button variant="ghost" type="button" onClick={() => navigate(`/projects/${projectId}`)}>Cancel</Button>
            <Button type="submit" loading={submitting}>Upload Document</Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UploadDocumentPage;
