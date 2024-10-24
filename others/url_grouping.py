from urllib.parse import urlparse
from collections import defaultdict
from typing import List, Dict, Set, Tuple
import tqdm
from concurrent.futures import ThreadPoolExecutor
import threading
import json
from pathlib import Path

class URLGrouper:
    def __init__(self):
        self.domain_groups = defaultdict(lambda: defaultdict(list))
        self.unique_paths = defaultdict(set)
        # 修复: 正确初始化嵌套的defaultdict
        self.path_statistics = defaultdict(lambda: {
            'depth_distribution': defaultdict(int),
            'total_urls': 0
        })
        self._lock = threading.Lock()
    
    def _parse_url(self, url: str) -> tuple:
        """解析单个URL，返回域名和路径层级"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # 移除空路径段并分割路径，同时处理特殊字符
            path_segments = [seg for seg in parsed.path.split('/') if seg]
            
            # 处理查询参数
            if parsed.query:
                # 可以选择是否将查询参数作为路径的一部分
                # 这里选择忽略查询参数，但保留在原始URL中
                pass
                
            return domain, path_segments
        except Exception as e:
            raise ValueError(f"URL解析错误 {url}: {str(e)}")
    
    def _process_single_url(self, url: str) -> None:
        """处理单个URL并添加到相应的组中"""
        try:
            domain, path_segments = self._parse_url(url)
            if url == 'http://qq78.com/\n':
                print('here')
            # 使用锁确保线程安全
            with self._lock:
                # 按路径层级存储
                current_path = ""
                for segment in path_segments:
                    current_path = f"{current_path}/{segment}"
                if len(current_path) < 1:
                    self.unique_paths[domain].add("###")
                    self.domain_groups[domain]["###"].append(url)
                else:
                    self.domain_groups[domain][current_path].append(url)
                    self.unique_paths[domain].add(current_path)
                
                # 更新路径深度统计
                path_depth = len(path_segments)
                self.path_statistics[domain]['depth_distribution'][path_depth] += 1
                self.path_statistics[domain]['total_urls'] += 1
                
        except Exception as e:
            print(f"处理URL时出错 {url}: {str(e)}")
            # 继续处理其他URL，但记录错误
            with self._lock:
                if 'errors' not in self.path_statistics:
                    self.path_statistics['errors'] = []
                self.path_statistics['errors'].append({
                    'url': url,
                    'error': str(e)
                })

    def process_urls(self, urls: List[str], max_workers: int = 10) -> Dict:
        """并行处理URL列表"""
        # 确保输入是URL列表
        if not isinstance(urls, list):
            urls = [urls]
            
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(tqdm.tqdm(executor.map(self._process_single_url, urls), 
                          total=len(urls), 
                          desc="处理URL"))
        return self.get_grouped_results()
    
    def get_grouped_results(self) -> Dict:
        """返回分组结果"""
        return dict(self.domain_groups)
    
    def get_unique_paths(self) -> Dict[str, Set[str]]:
        """获取每个域名的唯一路径"""
        return {domain: sorted(paths) for domain, paths in self.unique_paths.items()}
    
    def get_path_analysis(self) -> Dict:
        """获取路径分析结果"""
        analysis = {}
        for domain, stats in self.path_statistics.items():
            if domain == 'errors':  # 跳过错误记录
                continue
            try:
                total_urls = stats['total_urls']
                if total_urls > 0:  # 防止除零错误
                    depth_distribution = stats['depth_distribution']
                    weighted_sum = sum(depth * count for depth, count in depth_distribution.items())
                    analysis[domain] = {
                        'total_urls': total_urls,
                        'unique_paths': len(self.unique_paths[domain]),
                        'depth_distribution': dict(depth_distribution),
                        'avg_depth': weighted_sum / total_urls
                    }
            except Exception as e:
                print(f"分析域名 {domain} 时出错: {str(e)}")
                continue
        return analysis
    
    def save_results(self, output_dir: str = 'url_analysis') -> None:
        """保存分析结果到文件"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 保存域名和对应的唯一路径
        paths_file = output_path / 'unique_paths.json'
        with paths_file.open('w', encoding='utf-8') as f:
            json.dump(self.get_unique_paths(), f, indent=2, ensure_ascii=False)
        
        # 保存路径分析结果
        analysis_file = output_path / 'path_analysis.json'
        with analysis_file.open('w', encoding='utf-8') as f:
            json.dump(self.get_path_analysis(), f, indent=2, ensure_ascii=False)
        
        # 保存错误日志（如果有）
        if 'errors' in self.path_statistics:
            errors_file = output_path / 'errors.json'
            with errors_file.open('w', encoding='utf-8') as f:
                json.dump(self.path_statistics['errors'], f, indent=2, ensure_ascii=False)
        
        print(f"分析结果已保存到目录: {output_dir}")
    
    def get_domain_summary(self) -> List[Tuple[str, int, int]]:
        """获取域名摘要信息"""
        return [
            (domain, len(paths), self.path_statistics[domain]['total_urls'])
            for domain, paths in self.unique_paths.items()
        ]

def process_url_batch(urls: List[str], output_dir: str = None) -> Dict:
    """便捷的批处理函数"""
    grouper = URLGrouper()
    results = grouper.process_urls(urls)
    
    if output_dir:
        grouper.save_results(output_dir)
    
    return {
        'grouped_results': results,
        'unique_paths': grouper.get_unique_paths(),
        'path_analysis': grouper.get_path_analysis()
    }

# 使用示例
if __name__ == "__main__":
    with open(r'E:\git_repo\url-analyzer\others\x1.csv', 'r',  errors='replace') as file:
        lines = file.readlines()

    sample_urls = lines
    
    # 创建分组器实例
    grouper = URLGrouper()
    
    # 处理URL
    results = grouper.process_urls(sample_urls)
    
    # 保存分析结果
    grouper.save_results('url_analysis')
    
    # 打印域名摘要
    print("\n域名摘要:")
    for domain, unique_paths_count, total_urls in grouper.get_domain_summary():
        print(f"{domain}: {unique_paths_count} 个唯一路径, {total_urls} 个URL")

