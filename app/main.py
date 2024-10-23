from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import asyncio
from analyzer import URLAnalyzerService

app = FastAPI(
    title="URL Analyzer API",
    description="分析URL参数并找出最短可用URL的服务",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class URLAnalysisRequest(BaseModel):
    url: HttpUrl
    timeout: Optional[int] = 30000

# 响应模型
class URLAnalysisResponse(BaseModel):
    original_url: str
    minimal_url: str
    required_params: List[str]
    status: str
    error_message: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "URL Analyzer Service is running"}

@app.post("/analyze", response_model=URLAnalysisResponse)
async def analyze_url(request: URLAnalysisRequest):
    try:
        service = URLAnalyzerService(timeout=request.timeout)
        result = await service.find_minimal_url(str(request.url))
        
        return URLAnalysisResponse(
            original_url=result.original_url,
            minimal_url=result.minimal_url,
            required_params=result.required_params,
            status=result.status,
            error_message=result.error_message
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-batch")
async def analyze_urls(urls: List[HttpUrl]):
    try:
        service = URLAnalyzerService()
        tasks = [service.find_minimal_url(str(url)) for url in urls]
        results = await asyncio.gather(*tasks)
        
        return [
            URLAnalysisResponse(
                original_url=result.original_url,
                minimal_url=result.minimal_url,
                required_params=result.required_params,
                status=result.status,
                error_message=result.error_message
            )
            for result in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy"}