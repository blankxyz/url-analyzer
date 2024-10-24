# README.md

-------------------------------------------
# Part A: URL Analyzer Service

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
-------------------------------
# PART B : URL Shortener Service
url_grouping.py

这个的目的是希望给url去个重，特别注意###的key是没有层级的，就是说，它不含后半截内容。
#### 特别提醒 我没有做过多的数据清洗处理，因此，如果你的数据中包含一些奇怪的符号，你将会在error里发现。

特别要注意path_analysis.json
```code
  "baijiahao.baidu.com": {
    "total_urls": 38,
    "unique_paths": 1,
    "depth_distribution": {
      "1": 38
    },
    "avg_depth": 1.0
  },
```

  "total_urls": 较大 即
  "unique_paths": 非常小
  
    total_urls/unique_paths值很大的，需要确认一下这组数据是不是由参数构成的页面访问。
  depth_distribution: 1
如果由可能的话，尽量确认所有unique_paths为1的链接

  

### 输出文件

1. 输出目录为 ./url_analysis


2. 输出格式为
unique_paths.json
```bash
  "share.hntv.tv": [
    "/news/0/1840550138165264385",
    "/news/0/1840561551229718529"
  ],
  "3g.china.com": [
    "/act/news/10000169/20240930/47303402.html",
    "/act/news/10000169/20240930/47303806.html",
    "/act/news/10000169/20240930/47303896.html"
  ],
  "browser.qq.com": [
    "/mobile/news"
  ],
```


3. path_analysis.json
```bash
  "www.iesdouyin.com": {
    "total_urls": 7890,
    "unique_paths": 130,
    "depth_distribution": {
      "3": 7890
    },
    "avg_depth": 3.0
  },
```