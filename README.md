# PDF Scan Quality Checker - POC System

A comprehensive proof-of-concept system for analyzing PDF document quality using computer vision and machine learning techniques. The system consists of a FastAPI backend for processing and analysis, and a React frontend for user interaction and visualization.

## 🏗️ Architecture Overview

```
┌──────────────────────────┐
│ Frontend                 │
│ (React / Bootstrap UI)   │
├──────────────────────────┤
│ - PDF Upload Form        │
│ - Processing Status View │
│ - Dashboard (Reports)    │
│ - Page Viewer & Flags    │
│ - Review/Approve Buttons │
│ - Confidence Indicator   │
│ - API Integration Layer  │
└────────────┬─────────────┘
             │ REST API Calls (JSON)
             ▼
┌──────────────────────────┐
│ Backend                  │
│ (Python + FastAPI)       │
├──────────────────────────┤
│ 1. API Endpoints         │
│ - /upload                │
│ - /status/{job_id}       │
│ - /results/{job_id}      │
│ - /page/{job_id}/{no}    │
│ - /review/{job_id}       │
│                          │
│ 2. Processing Pipeline   │
│ - PDF to Images          │
│ - Blur Detection         │
│ - Orientation Check      │
│ - Cropping Detection     │
│ - Color Consistency      │
│                          │
│ 3. ML / Rule Engine      │
│ - Heuristic + RF ML      │
│ - PyTorch CNN (DL)       │
│ - OCR readability        │
│ - Ensemble confidence    │
│   score (0–100%)         │
│                          │
│ 4. Data Layer            │
│ - Store PDFs, images,    │
│   metrics (JSON)         │
│ - Thumbnails for UI      │
│                          │
│ 5. Report Generator      │
│ - Aggregate results      │
│ - Provide JSON/CSV       │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Storage                  │
│ (Local / S3 / Database)  │
│ - Original PDFs          │
│ - Extracted images       │
│ - Results JSON & reports │
└──────────────────────────┘
```

## 🚀 Features

### Backend Features
- **PDF Processing**: Convert PDF pages to high-quality images
- **Quality Analysis**: Multiple quality checks including:
  - Blur detection using Laplacian variance
  - Orientation analysis using Hough line detection
  - Cropping detection (content vs whitespace ratio)
  - Color consistency analysis across image regions
  - DPI (Dots Per Inch) analysis for print quality assessment
- **Confidence Scoring**: Ensemble of heuristic checks, Random Forest ML, a small PyTorch CNN, OCR readability, and optional OpenAI Vision LLM (when DL &lt; 70%)
- **OCR Analysis**: RapidOCR (ONNX) with optional Tesseract fallback; flags poor text readability
- **Deep Learning**: Lightweight QualityCNN trained on synthetic degraded scans
- **Vision LLM**: OpenAI Vision review for low DL-confidence pages with score + summary
- **Auto-Approval**: Documents with ≥80% confidence are auto-approved
- **Manual Review**: Documents with ≤20% confidence require manual review
- **Batch & SharePoint**: Multi-file upload and Microsoft Graph library crawl
- **Report Generation**: Export results in JSON or CSV format
- **RESTful API**: Complete API for frontend integration

### Frontend Features
- **Modern UI**: Bootstrap-based responsive interface
- **Drag & Drop Upload**: Easy PDF file upload with validation
- **Real-time Status**: Live processing status updates
- **Interactive Dashboard**: Comprehensive results visualization
- **Page Viewer**: Detailed page-by-page analysis with zoom
- **Quality Flags**: Visual indicators for detected issues
- **Review Workflow**: Manual approval/rejection system
- **Job History**: Track all processed documents
- **Export Reports**: Download analysis results

## 📋 Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn
- poppler-utils (for PDF processing)

### Install poppler-utils

**Ubuntu/Debian:**
```bash
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

**Windows:**
Download from [poppler-windows](https://github.com/oschwartz10612/poppler-windows) and add to PATH.

## 🛠️ Installation & Setup

### 1. Clone and Setup Backend

```bash
cd /home/candi/POC/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Frontend

```bash
cd /home/candi/POC/frontend

# Install dependencies
npm install
```

### 3. Start the Application

**Terminal 1 - Backend:**
```bash
cd /home/candi/POC/backend
source venv/bin/activate
python -m app.main
```

**Terminal 2 - Frontend:**
```bash
cd /home/candi/POC/frontend
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 📖 Usage Guide

### 1. Upload PDF
- Navigate to the Upload tab
- Drag and drop a PDF file or click to select
- Maximum file size: 50MB
- Supported format: PDF only

### 2. Monitor Processing
- Switch to the Status tab to monitor processing
- View real-time progress and page count
- Processing typically takes 10-30 seconds per page

### 3. Review Results
- Once complete, switch to the Results tab
- View overall confidence score and auto-approval status
- Examine individual page analysis with quality metrics
- Click "View Pages" for detailed page-by-page review

### 4. Manual Review (if needed)
- Documents with low confidence require manual review
- Use the Page Viewer to inspect flagged pages
- Approve or reject based on visual inspection
- Add comments if necessary

### 5. Export Reports
- Download analysis results in JSON or CSV format
- Reports include all quality metrics and flags
- Use for further analysis or record keeping

## 🔧 API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload` | Upload PDF for analysis |
| GET | `/api/v1/status/{job_id}` | Get processing status |
| GET | `/api/v1/results/{job_id}` | Get analysis results |
| GET | `/api/v1/page/{job_id}/{page_number}` | Get page details |
| POST | `/api/v1/review/{job_id}` | Submit manual review |
| POST | `/api/v1/reports/{job_id}` | Generate report |
| GET | `/api/v1/jobs` | List all jobs |

### File Serving

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/images/{job_id}/{page_number}` | Serve page image |
| GET | `/api/v1/thumbnails/{job_id}/{page_number}` | Serve thumbnail |
| GET | `/api/v1/download/{job_id}/{filename}` | Download report |

## 🧪 Quality Analysis Details

### Blur Detection
- Uses Laplacian variance to measure image sharpness
- Higher variance = sharper image
- Threshold: <50 = poor, >100 = good

### Orientation Analysis
- Detects text orientation using Hough line detection
- Identifies horizontal (0-15°) and vertical (75-90°) text
- Calculates percentage of properly oriented lines

### Cropping Detection
- Analyzes content-to-whitespace ratio
- Identifies excessive margins or poor cropping
- Good cropping: >30% content area

### Color Consistency
- Divides image into quadrants
- Compares mean colors across regions
- Lower variance = better consistency

### DPI Analysis
- Extracts DPI from image metadata
- Estimates DPI based on image dimensions if not specified
- Quality standards:
  - 300+ DPI: Professional print quality (100% score)
  - 200-299 DPI: Good quality (80% score)
  - 150-199 DPI: Acceptable (60% score)
  - 100-149 DPI: Poor (40% score)
  - <100 DPI: Very poor (20% score)

### Confidence Scoring
- Weighted combination of all metrics:
  - Blur: 30% (most important)
  - DPI: 25% (very important for print quality)
  - Orientation: 15%
  - Cropping: 15%
  - Color: 15%
- Final score: 0-100%

## 📊 Data Flow

1. **Upload**: Frontend sends PDF to `/upload` endpoint
2. **Processing**: Backend converts PDF to images and runs quality checks
3. **Analysis**: Heuristic + ML + DL + OCR ensemble produces confidence scores for each page
4. **Classification**: 
   - ≥80% confidence → Auto-approved
   - ≤20% confidence → Manual review required
   - 20-80% → Flagged for review
5. **Storage**: Results stored with metadata and images
6. **Display**: Frontend polls for results and displays analysis
7. **Review**: Manual inspection for low-confidence documents
8. **Export**: Generate reports in JSON/CSV format

## 🔍 Troubleshooting

### Common Issues

**Backend won't start:**
- Ensure poppler-utils is installed
- Check Python version (3.8+)
- Verify all dependencies are installed

**PDF processing fails:**
- Check file size (max 50MB)
- Ensure PDF is not password-protected
- Verify poppler-utils installation

**Frontend can't connect to backend:**
- Ensure backend is running on port 8000
- Check CORS settings in backend config
- Verify API_BASE_URL in frontend

**Images not loading:**
- Check file permissions in uploads/processed directories
- Ensure backend is serving static files correctly
- Verify image paths in API responses

### Logs and Debugging

**Backend logs:**
```bash
cd /home/candi/POC/backend
tail -f logs/app.log  # If logging is configured
```

**Frontend logs:**
- Open browser developer tools
- Check Network tab for API calls
- Review Console for JavaScript errors

## 🚀 Production Considerations

### Security
- Add authentication and authorization
- Implement rate limiting
- Validate file uploads more strictly
- Use HTTPS in production

### Performance
- Implement database for job storage
- Add Redis for job queue management
- Use CDN for image serving
- Implement caching strategies

### Scalability
- Add horizontal scaling support
- Implement load balancing
- Use cloud storage (S3, GCS)
- Add monitoring and alerting

### Data Management
- Implement data retention policies
- Add backup and recovery procedures
- Consider data encryption at rest
- Implement audit logging

## 📝 License

This is a proof-of-concept system for demonstration purposes.

## 🤝 Contributing

This is a POC system. For production use, consider:
- Adding comprehensive tests
- Implementing proper error handling
- Adding configuration management
- Improving security measures
- Adding monitoring and logging
