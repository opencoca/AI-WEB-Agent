import os
import time
import sys
import random
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils import sanitize_filename, create_markdown_file, log_error
from research_templates import RESEARCH_TEMPLATE, SUMMARY_TEMPLATE
from llm_interface import LLMInterface, DummyLLM
import trafilatura

class ResearchAgent:
    def __init__(self, llm: Optional[LLMInterface] = None, max_depth: int = 3, delay: float = 1.0, proxy_handler=None):
        self.llm = llm or DummyLLM()
        self.max_depth = max_depth
        self.delay = delay
        self.results = []
        self.visited_urls = set()
        self.proxy_handler = proxy_handler # Added proxy_handler
        self._init_headers()

    def _init_headers(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        self.languages = ["en-US,en;q=0.9", "en-GB,en;q=0.8", "en;q=0.7"]
        self.referrers = [
            "https://www.google.com/",
            "https://www.bing.com/",
            "https://search.yahoo.com/",
            "https://duckduckgo.com/"
        ]

    def _get_random_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": random.choice(self.languages),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Referer": random.choice(self.referrers)
        }

    def _get_search_urls(self, query: str, max_retries: int = 3) -> List[str]:
        search_urls = [
            f"https://duckduckgo.com/html/?q={query}",
            f"https://html.duckduckgo.com/html/?q={query}",
            f"https://lite.duckduckgo.com/lite?q={query}"
        ]

        for attempt in range(max_retries):
            try:
                response = self.proxy_handler.make_request( # Use proxy handler
                    random.choice(search_urls),
                    headers=self._get_random_headers(),
                )

                if not response:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                urls = [link['href'] for link in soup.find_all('a', {'class': ['result__a', 'result__url']}, href=True)
                       if link['href'].startswith('http') and not any(b in link['href'] for b in ['.pdf', '.doc', 'javascript:', 'mailto:'])][:5]

                if urls:
                    print(f"Found {len(urls)} URLs")
                    return urls

                if "Transitional" in response.text[:500]:
                    print("Anti-bot protection detected, using fallback URLs")
                    return self._get_fallback_urls()

                time.sleep(2 ** attempt + random.uniform(0.1, 0.5))

            except Exception as e:
                log_error(f"Search attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2 ** attempt + random.uniform(0.1, 0.5))

        print("Using fallback URLs after failed attempts")
        return self._get_fallback_urls()

    def _get_fallback_urls(self) -> List[str]:
        default_urls = [
            "https://www.ibm.com/topics/quantum-computing",
            "https://www.explainthatstuff.com/quantum-computing.html",
            "https://www.geeksforgeeks.org/introduction-quantum-computing/",
            "https://en.wikipedia.org/wiki/Quantum_computing"
        ]
        return default_urls  # Return all URLs since they're pre-validated


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
                time.sleep(self.delay + random.uniform(0.1, 0.5))

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
        """
        Extract content from a given URL using trafilatura

        Args:
            url: URL to extract content from

        Returns:
            Extracted text content or empty string if extraction fails
        """
        try:
            print(f"\nExtracting content from: {url}")
            if downloaded := trafilatura.fetch_url(url):
                if content := trafilatura.extract(downloaded):
                    preview = content[:200].replace('\n', ' ').strip()
                    print(f"Successfully extracted content. Preview: {preview}...")
                    return content
                print(f"No content extracted from {url}")
            else:
                print(f"Failed to download content from {url}")
            return ""
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
                sub_queries="\n".join(f"- {sq['query']}" for sq in result["sub_queries"]),
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

    print("\nTesting fallback URLs extraction:")
    for url in agent._get_fallback_urls():
        content = agent._extract_content(url)
        if content:
            print(f"Successfully extracted content from fallback URL: {url}")
        else:
            print(f"Failed to extract content from fallback URL: {url}")

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