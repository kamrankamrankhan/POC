import React, { useRef, useState } from 'react';
import { Alert, Button, Form, Nav, ProgressBar, Spinner, Table } from 'react-bootstrap';
import { apiService } from '../services/api';
import { BatchUploadResponse, SharePointPreviewFile, UploadResponse } from '../types';

const ACCEPTED_TYPES = '.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.gif';
const MAX_FILE_BYTES = 50 * 1024 * 1024;

interface UploadFormProps {
  onUploadSuccess: (response: UploadResponse) => void;
  onBatchStarted: (response: BatchUploadResponse) => void;
}

const isPdfFile = (file: File) =>
  file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

const isSupportedFile = (file: File) => {
  const name = file.name.toLowerCase();
  return (
    isPdfFile(file) ||
    file.type.startsWith('image/') ||
    ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp', '.gif'].some((ext) =>
      name.endsWith(ext)
    )
  );
};

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const fileIcon = (filename: string) =>
  filename.toLowerCase().endsWith('.pdf') ? 'fas fa-file-pdf text-danger' : 'fas fa-file-image text-info';

const UploadForm: React.FC<UploadFormProps> = ({ onUploadSuccess, onBatchStarted }) => {
  const [sourceTab, setSourceTab] = useState<'local' | 'sharepoint'>('local');
  const [files, setFiles] = useState<File[]>([]);
  const [password, setPassword] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [sharepointUrl, setSharepointUrl] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [previewing, setPreviewing] = useState(false);
  const [previewFiles, setPreviewFiles] = useState<SharePointPreviewFile[]>([]);

  const hasPdf = files.some(isPdfFile);

  const addFiles = (incoming: FileList | File[]) => {
    const next: File[] = [];
    const rejected: string[] = [];
    Array.from(incoming).forEach((file) => {
      if (file.size > MAX_FILE_BYTES) {
        rejected.push(`${file.name} is larger than 50MB`);
        return;
      }
      if (!isSupportedFile(file)) {
        rejected.push(`${file.name} is not a PDF, scan, or photo`);
        return;
      }
      next.push(file);
    });
    if (rejected.length) {
      setError(rejected[0]);
    } else {
      setError(null);
    }
    if (next.length) {
      setFiles((current) => {
        const names = new Set(current.map((file) => `${file.name}:${file.size}`));
        const merged = [...current];
        next.forEach((file) => {
          const key = `${file.name}:${file.size}`;
          if (!names.has(key)) {
            merged.push(file);
          }
        });
        return merged;
      });
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      addFiles(event.target.files);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    if (event.dataTransfer.files?.length) {
      addFiles(event.dataTransfer.files);
    }
  };

  const removeFile = (index: number) => {
    setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const sharepointPayload = () => ({
    url: sharepointUrl.trim(),
    tenant_id: tenantId.trim() || undefined,
    client_id: clientId.trim() || undefined,
    client_secret: clientSecret.trim() || undefined,
    access_token: accessToken.trim() || undefined,
  });

  const handleLocalSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!files.length) return;

    setUploading(true);
    setUploadProgress(15);
    setError(null);

    try {
      if (files.length === 1) {
        const response = await apiService.uploadPDF(files[0], password);
        setUploadProgress(100);
        onUploadSuccess(response);
      } else {
        const response = await apiService.uploadBatch(files, password);
        setUploadProgress(100);
        onBatchStarted(response);
      }
      setFiles([]);
      setPassword('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handlePreviewSharePoint = async () => {
    if (!sharepointUrl.trim()) {
      setError('Enter a SharePoint document library URL.');
      return;
    }
    setPreviewing(true);
    setError(null);
    try {
      const preview = await apiService.previewSharePoint(sharepointPayload());
      setPreviewFiles(preview.files);
    } catch (err: any) {
      setPreviewFiles([]);
      setError(err.response?.data?.detail || 'Could not read the SharePoint library.');
    } finally {
      setPreviewing(false);
    }
  };

  const handleProcessSharePoint = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!sharepointUrl.trim()) {
      setError('Enter a SharePoint document library URL.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const response = await apiService.processSharePoint(sharepointPayload());
      onBatchStarted(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not start SharePoint processing.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-form-card">
      <Nav variant="pills" className="mb-3">
        <Nav.Item>
          <Nav.Link active={sourceTab === 'local'} onClick={() => setSourceTab('local')}>
            <i className="fas fa-folder-open me-2"></i>
            This computer
          </Nav.Link>
        </Nav.Item>
        <Nav.Item>
          <Nav.Link active={sourceTab === 'sharepoint'} onClick={() => setSourceTab('sharepoint')}>
            <i className="fas fa-cloud me-2"></i>
            SharePoint library
          </Nav.Link>
        </Nav.Item>
      </Nav>

      {sourceTab === 'local' ? (
        <Form onSubmit={handleLocalSubmit}>
          <div
            className={`upload-drop-zone ${files.length ? 'file-selected' : ''}`}
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleDrop}
            style={{ minHeight: '150px' }}
          >
            {files.length ? (
              <div className="selected-file-info">
                <i className="fas fa-layer-group upload-icon file-selected"></i>
                <h6 className="mb-2">{files.length} file{files.length === 1 ? '' : 's'} ready</h6>
                <p className="text-muted mb-0">PDFs, scanned images, and photos can be mixed in one batch.</p>
              </div>
            ) : (
              <div>
                <i className="fas fa-cloud-upload-alt upload-icon"></i>
                <p className="upload-text">Drag and drop files here, or choose them below</p>
                <small className="upload-subtext">
                  PDF, PNG, JPG, TIFF, BMP, WebP, GIF · up to 50MB each · multiple files allowed
                </small>
              </div>
            )}
          </div>

          <Form.Group className="mt-3">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_TYPES}
              multiple
              onChange={handleFileChange}
              disabled={uploading}
              className="custom-file-input"
              id="quality-file-input"
            />
            <label htmlFor="quality-file-input" className="custom-file-label">
              <i className="fas fa-folder-open me-2"></i>
              {uploading ? 'Processing...' : 'Choose PDFs, scans, or photos'}
              <span className="file-input-subtitle">Click to browse or drag & drop several files</span>
            </label>
          </Form.Group>

          {files.length > 0 && (
            <Table size="sm" hover className="mt-3 mb-0">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {files.map((file, index) => (
                  <tr key={`${file.name}-${index}`}>
                    <td>
                      <i className={`${fileIcon(file.name)} me-2`}></i>
                      {file.name}
                    </td>
                    <td>{isPdfFile(file) ? 'PDF' : 'Image'}</td>
                    <td>{formatSize(file.size)}</td>
                    <td className="text-end">
                      <Button variant="link" size="sm" onClick={() => removeFile(index)} disabled={uploading}>
                        Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}

          {hasPdf && (
            <Form.Group className="mt-3">
              <Form.Label htmlFor="pdf-password">
                PDF password <span className="text-muted">(if any selected PDF needs one)</span>
              </Form.Label>
              <Form.Control
                id="pdf-password"
                type="password"
                autoComplete="off"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={uploading}
                placeholder="Enter password for encrypted PDFs"
              />
            </Form.Group>
          )}

          {error && <Alert variant="danger" className="mt-3">{error}</Alert>}

          {uploading && (
            <div className="mt-3">
              <ProgressBar now={Math.max(uploadProgress, 20)} animated />
              <small className="text-muted mt-1 d-block">Uploading and starting analysis...</small>
            </div>
          )}

          <Button type="submit" variant="primary" size="lg" className="mt-3 w-100" disabled={!files.length || uploading}>
            {uploading
              ? 'Processing...'
              : files.length > 1
                ? `Analyze ${files.length} files`
                : 'Upload & Analyze'}
          </Button>
        </Form>
      ) : (
        <Form onSubmit={handleProcessSharePoint}>
          <p className="text-muted">
            Paste a SharePoint site or document library URL. The checker walks every folder and
            analyzes each PDF, scanned image, and photo.
          </p>
          <Form.Group className="mb-3">
            <Form.Label>SharePoint URL</Form.Label>
            <Form.Control
              value={sharepointUrl}
              onChange={(event) => setSharepointUrl(event.target.value)}
              placeholder="https://contoso.sharepoint.com/sites/HR/Shared Documents"
              disabled={uploading}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Tenant ID</Form.Label>
            <Form.Control
              value={tenantId}
              onChange={(event) => setTenantId(event.target.value)}
              placeholder="Azure AD tenant ID"
              disabled={uploading}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Client ID</Form.Label>
            <Form.Control
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              placeholder="Azure AD app client ID"
              disabled={uploading}
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Client secret</Form.Label>
            <Form.Control
              type="password"
              value={clientSecret}
              onChange={(event) => setClientSecret(event.target.value)}
              placeholder="App registration secret"
              disabled={uploading}
              autoComplete="off"
            />
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label>Access token <span className="text-muted">(optional)</span></Form.Label>
            <Form.Control
              as="textarea"
              rows={2}
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              placeholder="Paste a Graph token if you already have one"
              disabled={uploading}
            />
            <Form.Text>
              The Azure AD app needs <code>Sites.Read.All</code>. You can also set
              GRAPH_TENANT_ID, GRAPH_CLIENT_ID, and GRAPH_CLIENT_SECRET on the server.
            </Form.Text>
          </Form.Group>

          {error && <Alert variant="danger">{error}</Alert>}

          <div className="d-flex gap-2 mb-3">
            <Button variant="outline-primary" type="button" onClick={handlePreviewSharePoint} disabled={previewing || uploading}>
              {previewing ? <Spinner size="sm" animation="border" className="me-2" /> : <i className="fas fa-search me-2"></i>}
              Find files
            </Button>
            <Button variant="primary" type="submit" disabled={uploading || !sharepointUrl.trim()}>
              {uploading ? 'Starting...' : 'Analyze entire library'}
            </Button>
          </div>

          {previewFiles.length > 0 && (
            <>
              <h6>{previewFiles.length} supported file{previewFiles.length === 1 ? '' : 's'} found</h6>
              <div className="table-responsive" style={{ maxHeight: 280 }}>
                <Table size="sm" hover>
                  <thead>
                    <tr>
                      <th>Path</th>
                      <th>Type</th>
                      <th>Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewFiles.map((file) => (
                      <tr key={file.relative_path}>
                        <td>
                          <i className={`${fileIcon(file.name)} me-2`}></i>
                          {file.relative_path}
                        </td>
                        <td>{file.file_type === 'pdf' ? 'PDF' : 'Image'}</td>
                        <td>{formatSize(file.size)}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            </>
          )}
        </Form>
      )}
    </div>
  );
};

export default UploadForm;
