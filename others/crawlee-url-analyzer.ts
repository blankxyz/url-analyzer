import {
    PlaywrightCrawler,
    Dataset,
    KeyValueStore,
    RequestQueue,
    createPlaywrightRouter,
    Request,
    Configuration,
} from 'crawlee';
import { URL } from 'url';
import * as similarity from 'string-similarity';
import { load } from 'cheerio';

// 类型定义
interface URLParams {
    [key: string]: string;
}

interface URLPattern {
    domain: string;
    path: string;
    paramNames: string[];
}

interface AnalysisResult {
    originalUrl: string;
    minimalUrl: string;
    requiredParams: string[];
    allParams: URLParams;
    similarity: number;
    status: 'success' | 'failed';
    errorMessage?: string;
    timestamp: string;
}

interface PageContent {
    url: string;
    content: string;
    status: number;
}

// 配置选项
interface AnalyzerOptions {
    similarityThreshold: number;
    maxRequestsPerDomain: number;
    maxConcurrency: number;
    requestTimeout: number;
    maxRequestRetries: number;
}

class URLAnalyzer {
    private crawler: PlaywrightCrawler;
    private requestQueue: RequestQueue;
    private dataset: Dataset;
    private store: KeyValueStore;
    private options: AnalyzerOptions;
    private urlPatterns: Map<string, Set<string>> = new Map();
    private originalContents: Map<string, string> = new Map();

    constructor(options: Partial<AnalyzerOptions> = {}) {
        this.options = {
            similarityThreshold: 0.95,
            maxRequestsPerDomain: 2,
            maxConcurrency: 10,
            requestTimeout: 30000,
            maxRequestRetries: 3,
            ...options,
        };
    }

    private getUrlPattern(url: string): URLPattern {
        const parsedUrl = new URL(url);
        const params = new URLSearchParams(parsedUrl.search);
        return {
            domain: parsedUrl.hostname,
            path: parsedUrl.pathname,
            paramNames: Array.from(params.keys()),
        };
    }

    private buildUrl(baseUrl: string, params: URLParams): string {
        const url = new URL(baseUrl);
        Object.entries(params).forEach(([key, value]) => {
            url.searchParams.set(key, value);
        });
        return url.toString();
    }

    private extractMainContent(html: string): string {
        const $ = load(html);
        // 移除不相关的元素
        $('script, style, nav, footer, header, iframe').remove();
        // 获取主要内容
        const content = $('body').text();
        // 清理文本
        return content
            .replace(/\s+/g, ' ')
            .replace(/[\n\r\t]/g, ' ')
            .trim();
    }

    private calculateSimilarity(content1: string, content2: string): number {
        return similarity.compareTwoStrings(content1, content2);
    }

    private async createCrawler(): Promise<PlaywrightCrawler> {
        const router = createPlaywrightRouter();

        // 处理原始URL
        router.addHandler('ORIGINAL', async ({ request, page, log }) => {
            const url = request.url;
            const pattern = this.getUrlPattern(url);
            
            try {
                const response = await page.goto(url, {
                    timeout: this.options.requestTimeout,
                    waitUntil: 'networkidle',
                });
                const content = await page.content();
                const mainContent = this.extractMainContent(content);
                
                // 存储原始内容
                this.originalContents.set(url, mainContent);

                // 生成参数组合
                const paramCombinations = this.generateParamCombinations(pattern.paramNames);
                
                // 将测试URL添加到队列
                for (const params of paramCombinations) {
                    const testUrl = this.buildUrl(url.split('?')[0], params);
                    await this.requestQueue.addRequest({
                        url: testUrl,
                        userData: {
                            originalUrl: url,
                            params,
                            label: 'TEST',
                        },
                    });
                }
            } catch (error) {
                log.error(`Error processing original URL ${url}:`, error);
                await this.saveResult({
                    originalUrl: url,
                    minimalUrl: url,
                    requiredParams: [],
                    allParams: {},
                    similarity: 0,
                    status: 'failed',
                    errorMessage: error.message,
                    timestamp: new Date().toISOString(),
                });
            }
        });

        // 处理测试URL
        router.addHandler('TEST', async ({ request, page, log }) => {
            const { originalUrl, params } = request.userData;
            const testUrl = request.url;

            try {
                const response = await page.goto(testUrl, {
                    timeout: this.options.requestTimeout,
                    waitUntil: 'networkidle',
                });
                const content = await page.content();
                const mainContent = this.extractMainContent(content);
                
                const originalContent = this.originalContents.get(originalUrl);
                const similarity = this.calculateSimilarity(originalContent, mainContent);

                if (similarity >= this.options.similarityThreshold) {
                    await this.saveResult({
                        originalUrl,
                        minimalUrl: testUrl,
                        requiredParams: Object.keys(params),
                        allParams: params,
                        similarity,
                        status: 'success',
                        timestamp: new Date().toISOString(),
                    });
                }
            } catch (error) {
                log.error(`Error testing URL ${testUrl}:`, error);
            }
        });

        // 创建爬虫实例
        return new PlaywrightCrawler({
            requestQueue: this.requestQueue,
            maxRequestsPerMinute: this.options.maxRequestsPerDomain * 60,
            maxConcurrency: this.options.maxConcurrency,
            requestHandler: router,
            maxRequestRetries: this.options.maxRequestRetries,
            sessionPoolOptions: {
                maxPoolSize: this.options.maxConcurrency,
            },
        });
    }

    private generateParamCombinations(params: string[]): URLParams[] {
        const combinations: URLParams[] = [];
        for (let i = 1; i <= params.length; i++) {
            this.getCombinations(params, i).forEach(combo => {
                const paramObj: URLParams = {};
                combo.forEach(param => {
                    paramObj[param] = ''; // 使用原始值
                });
                combinations.push(paramObj);
            });
        }
        return combinations;
    }

    private getCombinations(arr: string[], size: number): string[][] {
        if (size === 0) return [[]];
        if (arr.length === 0) return [];

        const first = arr[0];
        const rest = arr.slice(1);
        const combosWithoutFirst = this.getCombinations(rest, size);
        const combosWithFirst = this.getCombinations(rest, size - 1)
            .map(combo => [first, ...combo]);

        return [...combosWithoutFirst, ...combosWithFirst];
    }

    private async saveResult(result: AnalysisResult): Promise<void> {
        await this.dataset.pushData(result);
    }

    public async initialize(): Promise<void> {
        this.requestQueue = await RequestQueue.open();
        this.dataset = await Dataset.open('url-analysis-results');
        this.store = await KeyValueStore.open('url-analysis-store');
        this.crawler = await this.createCrawler();
    }

    public async analyzeUrls(urls: string[]): Promise<void> {
        await this.initialize();

        // 将原始URL添加到队列
        for (const url of urls) {
            await this.requestQueue.addRequest({
                url,
                userData: {
                    label: 'ORIGINAL',
                },
            });
        }

        // 开始爬取
        await this.crawler.run();

        // 保存最终结果
        await this.dataset.exportToJSON('url-analysis-results');
    }
}

// 使用示例
async function main() {
    const analyzer = new URLAnalyzer({
        similarityThreshold: 0.95,
        maxRequestsPerDomain: 2,
        maxConcurrency: 10,
        requestTimeout: 30000,
        maxRequestRetries: 3,
    });

    const urls = [
        'https://example.com/page?id=123&utm_source=google&lang=en',
        'https://example.com/page?id=124&utm_source=facebook&lang=es',
        'https://another-site.com/product?pid=456&ref=email',
    ];

    try {
        await analyzer.analyzeUrls(urls);
        console.log('Analysis completed. Results saved to url-analysis-results.json');
    } catch (error) {
        console.error('Error during analysis:', error);
    }
}

// 运行分析器
if (require.main === module) {
    main().catch(console.error);
}

export { URLAnalyzer, AnalyzerOptions };
