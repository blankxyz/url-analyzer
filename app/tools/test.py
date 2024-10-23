from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum
import asyncio
from playwright.async_api import async_playwright
import urllib.parse
from itertools import combinations
import logging
from datetime import datetime
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
import re

@dataclass
class URLAnalysisResult:
    """URL分析结果"""
    original_url: str
    minimal_url: str
    required_params: List[str]
    all_params: Dict[str, str]
    analysis_time: datetime
    status: str
    similarity: float = 0.0
    error_message: Optional[str] = None

@dataclass
class URLValidationResult:
    """URL验证结果"""
    url: str
    is_valid: bool
    status_code: Optional[int]
    content_similarity: float = 0.0
    error_message: Optional[str] = None
    response_time: float = 0.0

class AnalysisStatus(Enum):
    """分析状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"

class ContentSimilarityChecker:
    """内容相似度检查器"""
    
    @staticmethod
    def _extract_main_content(html: str) -> str:
        """提取页面主要内容，去除导航、页脚等干扰元素"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # 移除script、style标签
        for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
            
        # 获取文本内容
        text = soup.get_text()
        
        # 清理文本
        text = re.sub(r'\s+', ' ', text).strip()  # 移除多余空白
        text = re.sub(r'[\n\r\t]', ' ', text)     # 替换换行符等
        return text

    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        return SequenceMatcher(None, text1, text2).ratio()

class URLAnalyzerService:
    """URL分析服务类"""
    
    def __init__(self, 
                 timeout: int = 30000,
                 max_retries: int = 3,
                 concurrent_limit: int = 5,
                 similarity_threshold: float = 0.95):
        self.timeout = timeout
        self.max_retries = max_retries
        self.concurrent_limit = concurrent_limit
        self.similarity_threshold = similarity_threshold
        self.logger = self._setup_logger()
        self.content_checker = ContentSimilarityChecker()

    def _setup_logger(self) -> logging.Logger:
        """配置日志记录器"""
        logger = logging.getLogger('URLAnalyzerService')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    @staticmethod
    def _extract_params(url: str) -> Dict[str, str]:
        """提取URL参数"""
        parsed = urllib.parse.urlparse(url)
        return dict(urllib.parse.parse_qsl(parsed.query))

    @staticmethod
    def _build_url(base_url: str, params: Dict[str, str]) -> str:
        """构建URL"""
        parsed = urllib.parse.urlparse(base_url)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urllib.parse.urlencode(params),
            parsed.fragment
        ))

    async def _get_page_content(self, page, url: str) -> Tuple[str, int]:
        """获取页面内容和状态码"""
        response = await page.goto(url, wait_until='domcontentloaded')
        if not response:
            return "", 0
        
        # 等待页面稳定
        # await page.wait_for_timeout(1000)
        
        content = await page.content()
        return content, response.status

    async def _validate_url(self, page, test_url: str, original_content: str) -> URLValidationResult:
        """验证URL是否可访问并比较内容相似度"""
        start_time = datetime.now()
        try:
            test_content, status_code = await self._get_page_content(page, test_url)
            if not test_content:
                return URLValidationResult(
                    url=test_url,
                    is_valid=False,
                    status_code=None,
                    error_message="No content received"
                )

            # 提取和比较主要内容
            original_main_content = self.content_checker._extract_main_content(original_content)
            test_main_content = self.content_checker._extract_main_content(test_content)
            similarity = self.content_checker.calculate_similarity(
                original_main_content, 
                test_main_content
            )

            is_valid = (status_code == 200 and similarity >= self.similarity_threshold)
            
            return URLValidationResult(
                url=test_url,
                is_valid=is_valid,
                status_code=status_code,
                content_similarity=similarity,
                response_time=(datetime.now() - start_time).total_seconds()
            )

        except Exception as e:
            return URLValidationResult(
                url=test_url,
                is_valid=False,
                status_code=None,
                error_message=str(e),
                response_time=(datetime.now() - start_time).total_seconds()
            )

    async def find_minimal_url(self, url: str) -> URLAnalysisResult:
        """
        查找具有相似内容的最短URL
        """
        start_time = datetime.now()
        self.logger.info(f"开始分析URL: {url}")

        try:
            params = self._extract_params(url)
            base_url = self._build_url(url, {})
            param_names = list(params.keys())

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                context = await browser.new_context()
                page = await context.new_page()
                # await page.set_default_timeout(self.timeout)

                # 获取原始页面内容
                original_content, _ = await self._get_page_content(page, url)
                if not original_content:
                    raise Exception("无法获取原始页面内容")

                # 测试无参数的URL
                no_params_result = await self._validate_url(page, base_url, original_content)
                if no_params_result.is_valid:
                    await browser.close()
                    return URLAnalysisResult(
                        original_url=url,
                        minimal_url=base_url,
                        required_params=[],
                        all_params=params,
                        analysis_time=datetime.now(),
                        status=AnalysisStatus.SUCCESS.value,
                        similarity=no_params_result.content_similarity
                    )

                # 测试参数组合
                for r in range(1, len(param_names) + 1):
                    for param_combo in combinations(param_names, r):
                        test_params = {k: params[k] for k in param_combo}
                        test_url = self._build_url(base_url, test_params)
                        
                        validation_result = await self._validate_url(
                            page, 
                            test_url, 
                            original_content
                        )
                        
                        if validation_result.is_valid:
                            await browser.close()
                            return URLAnalysisResult(
                                original_url=url,
                                minimal_url=test_url,
                                required_params=list(param_combo),
                                all_params=params,
                                analysis_time=datetime.now(),
                                status=AnalysisStatus.SUCCESS.value,
                                similarity=validation_result.content_similarity
                            )

                await browser.close()

            # 如果没有找到有效的较短URL，返回原始URL
            return URLAnalysisResult(
                original_url=url,
                minimal_url=url,
                required_params=list(params.keys()),
                all_params=params,
                analysis_time=datetime.now(),
                status=AnalysisStatus.SUCCESS.value,
                similarity=1.0  # 原始URL与自身比较相似度为1
            )

        except Exception as e:
            self.logger.error(f"分析URL时发生错误: {str(e)}")
            return URLAnalysisResult(
                original_url=url,
                minimal_url=url,
                required_params=[],
                all_params=params,
                analysis_time=datetime.now(),
                status=AnalysisStatus.FAILED.value,
                error_message=str(e)
            )

# 使用示例
async def demo():
    service = URLAnalyzerService(
        timeout=30000,
        max_retries=3,
        concurrent_limit=5,
        similarity_threshold=0.95  # 设置相似度阈值
    )
    
    url = "https://www.bilibili.com/video/BV1ZdmVYfEKU/?spm_id_from=333.1007.tianma.1-1-1.click&vd_source=d028083f0c8178792dd457f6b955605b"
    result = await service.find_minimal_url(url)
    
    print(f"原始URL: {result.original_url}")
    print(f"最短URL: {result.minimal_url}")
    print(f"必需参数: {result.required_params}")
    print(f"内容相似度: {result.similarity:.2%}")
    print(f"分析状态: {result.status}")
    if result.error_message:
        print(f"错误信息: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(demo())