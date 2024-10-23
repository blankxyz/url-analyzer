# README.md

# URL Analyzer Service

This service analyzes URLs to find the minimal required parameters for accessing web pages.

## Quick Start

1. Build and run with Docker Compose:

   ```bash
   docker-compose up --build
   ```

2. Access the API at http://localhost:8000

3. API Endpoints:
   - POST /analyze - Analyze single URL
   - POST /analyze-batch - Analyze multiple URLs
   - GET /health - Health check

## API Usage

1. Analyze single URL:

```bash
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.bilibili.com/video/BV1ZdmVYfEKU/?spm_id_from=333.1007.tianma.1-1-1.click&vd_source=d028083f0c8178792dd457f6b955605b"}'
```

2. Analyze multiple URLs:

```bash
curl -X POST "http://localhost:8000/analyze-batch" \
     -H "Content-Type: application/json" \
     -d '["https://example.com/1?a=1", "https://example.com/2?b=2"]'
```
