import os
import time
import sys
from typing import List, Dict, Any, Optional
import requests
import trafilatura
from bs4 import BeautifulSoup
from datetime import datetime
from utils import sanitize_filename, create_markdown_file, log_error
from research_templates import RESEARCH_TEMPLATE, SUMMARY_TEMPLATE
from llm_interface import LLMInterface, DummyLLM

class ResearchAgent:
    def __init__(self, llm: Optional[LLMInterface] = None, max_depth: int = 3, delay: float = 1.0):
        self.llm = llm or DummyLLM()
        self.max_depth = max_depth
        self.delay = delay
        self.results = []
        self.visited_urls = set()

    def _get_search_urls(self, query: str) -> List[str]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://duckduckgo.com/'
            }
            response = requests.get("https://html.duckduckgo.com/html/", headers=headers, params={'q': query, 'kl': 'us-en'})
            if response.status_code != 200:
                log_error(f"Search request failed with status {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            selectors = ['a.result__url', 'a.result__snippet', 'a[href^="http"]']
            blocked = ['.pdf', '.doc', 'javascript:', 'mailto:']

            urls = [url for selector in selectors 
                   for result in soup.select(selector)
                   if (url := result.get('href')) and url.startswith('http') and not any(b in url for b in blocked)][:5]

            print(f"Found {len(urls)} unique URLs")
            return urls

        except Exception as e:
            log_error(f"Error getting search URLs: {str(e)}")
            return []

    def research(self, query: str, depth: int = 0) -> Dict[str, Any]:
        if depth >= self.max_depth:
            return {"query": query, "content": [], "sub_queries": []}

        print(f"\nResearching: {query} (Depth: {depth})")

        try:
            urls = self._get_search_urls(query)
            content = []

            for url in urls[:3]:
                if url in self.visited_urls:
                    continue

                self.visited_urls.add(url)
                text = self._extract_content(url)
                if text:
                    content.append({"source": url, "content": self.llm.filter_content(text)})
                time.sleep(self.delay)

            if not content:
                return {"query": query, "content": [], "sub_queries": []}

            sub_queries = self.llm.generate_sub_queries(query, content)
            sub_results = [self.research(sq, depth + 1) for sq in sub_queries[:2]]

            result = {"query": query, "content": content, "sub_queries": sub_results}
            self.results.append(result)
            return result

        except Exception as e:
            log_error(f"Error researching query '{query}': {str(e)}")
            return {"query": query, "content": [], "sub_queries": []}

    def _extract_content(self, url: str) -> str:
        try:
            downloaded = trafilatura.fetch_url(url)
            return trafilatura.extract(downloaded) or ""
        except Exception as e:
            log_error(f"Error extracting content from {url}: {str(e)}")
            return ""

    def save_results(self, output_dir: str = "research_results") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"{output_dir}_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        summary = self.llm.summarize_results(self.results)

        for result in self.results:
            filename = sanitize_filename(result["query"])
            content = RESEARCH_TEMPLATE.format(
                query=result["query"],
                content="\n\n".join(f"### Source: {item['source']}\n{item['content']}" for item in result["content"]),
                sub_queries="\n".join(f"- {sq['query']}" for sq in result["sub_queries"])
            )
            create_markdown_file(os.path.join(output_dir, f"{filename}.md"), content)

        summary_content = SUMMARY_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_queries=len(self.results),
            queries=summary
        )
        create_markdown_file(os.path.join(output_dir, "summary.md"), summary_content)
        return output_dir

def run_test_query(query: str):
    print(f"\nRunning test query: {query}")
    agent = ResearchAgent(max_depth=2)
    agent.research(query)
    return agent.save_results()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        if len(sys.argv) > 2:
            output_dir = run_test_query(sys.argv[2])
            print(f"\nTest completed. Results saved in: {output_dir}")
            return
        else:
            print("Error: Test query required")
            sys.exit(1)

    agent = ResearchAgent()
    while True:
        query = input("\nEnter research query (or 'quit' to exit): ").strip()
        if query.lower() == 'quit':
            break
        agent.research(query)
        agent.save_results()

if __name__ == "__main__":
    main()