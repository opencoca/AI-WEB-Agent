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
        """
        Initialize the research agent

        Args:
            llm: LLM interface for content processing
            max_depth: Maximum recursion depth for research
            delay: Delay between requests in seconds
        """
        self.llm = llm or DummyLLM()
        self.max_depth = max_depth
        self.delay = delay
        self.results = []
        self.visited_urls = set()

    def _get_search_urls(self, query: str) -> List[str]:
        """Get URLs from search results"""
        try:
            print(f"Searching DuckDuckGo for: {query}")
            # Updated search URL format
            search_url = f"https://html.duckduckgo.com/html/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://duckduckgo.com/'
            }
            params = {'q': query, 'kl': 'us-en'}

            response = requests.get(search_url, headers=headers, params=params)
            if response.status_code != 200:
                print(f"Warning: Search request failed with status {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            urls = []

            # Try multiple possible result selectors
            result_selectors = [
                'a.result__url',    # Primary selector
                'a.result__snippet',  # Alternative selector
                'a[href^="http"]'     # Fallback for any HTTP link
            ]

            for selector in result_selectors:
                results = soup.select(selector)
                for result in results:
                    url = result.get('href')
                    if url and url.startswith('http'):
                        if not any(blocked in url for blocked in ['.pdf', '.doc', 'javascript:', 'mailto:']):
                            urls.append(url)

                if urls:  # If we found URLs with this selector, stop trying others
                    break

            # Deduplicate URLs while preserving order
            urls = list(dict.fromkeys(urls))

            if not urls:
                print("Warning: No URLs found in search results")
                print("Response content preview:", response.text[:200])  # Debug info
            else:
                print(f"Found {len(urls)} unique URLs")

            return urls[:5]  # Return up to 5 unique URLs

        except Exception as e:
            log_error(f"Error getting search URLs: {str(e)}")
            return []

    def research(self, query: str, depth: int = 0) -> Dict[str, Any]:
        """
        Perform recursive research on a query

        Args:
            query: Research query
            depth: Current recursion depth

        Returns:
            Dictionary containing research results
        """
        if depth >= self.max_depth:
            return {"query": query, "content": [], "sub_queries": []}

        print(f"\nResearching: {query} (Depth: {depth})")

        try:
            # Get initial search results
            print(f"Searching for URLs related to: {query}")
            urls = self._get_search_urls(query)
            content = []

            for url in urls[:3]:  # Limit to top 3 results
                if url in self.visited_urls:
                    print(f"Skipping already visited URL: {url}")
                    continue

                self.visited_urls.add(url)
                print(f"Processing URL: {url}")

                # Extract and filter content using LLM
                text = self._extract_content(url)
                if text:
                    print(f"Filtering content from {url} (length: {len(text)})")
                    filtered_text = self.llm.filter_content(text)
                    content.append({
                        "source": url,
                        "content": filtered_text
                    })
                else:
                    print(f"No content extracted from {url}")

                time.sleep(self.delay)

            if not content:
                print("Warning: No content gathered from any URLs")
                return {"query": query, "content": [], "sub_queries": []}

            # Generate sub-queries using LLM
            print("\nGenerating sub-queries...")
            sub_queries = self.llm.generate_sub_queries(query, content)
            print(f"Generated {len(sub_queries)} sub-queries: {sub_queries}")

            # Recursive research on sub-queries
            sub_results = []
            for sub_query in sub_queries[:2]:  # Limit to 2 sub-queries
                print(f"\nExploring sub-query: {sub_query}")
                sub_result = self.research(sub_query, depth + 1)
                sub_results.append(sub_result)

            result = {
                "query": query,
                "content": content,
                "sub_queries": sub_results
            }

            self.results.append(result)
            return result

        except Exception as e:
            log_error(f"Error researching query '{query}': {str(e)}")
            return {"query": query, "content": [], "sub_queries": []}

    def _extract_content(self, url: str) -> str:
        """Extract main content from URL using trafilatura"""
        try:
            downloaded = trafilatura.fetch_url(url)
            return trafilatura.extract(downloaded) or ""
        except Exception as e:
            log_error(f"Error extracting content from {url}: {str(e)}")
            return ""

    def save_results(self, output_dir: str = "research_results") -> str:
        """
        Save research results to markdown files

        Returns:
            Path to the output directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"{output_dir}_{timestamp}"

        os.makedirs(output_dir, exist_ok=True)
        print(f"\nSaving results to: {output_dir}")

        # Generate summary using LLM
        print("Generating research summary...")
        summary = self.llm.summarize_results(self.results)

        for result in self.results:
            filename = sanitize_filename(result["query"])
            filepath = os.path.join(output_dir, f"{filename}.md")

            content = RESEARCH_TEMPLATE.format(
                query=result["query"],
                content="\n\n".join(f"### Source: {item['source']}\n{item['content']}"
                                  for item in result["content"]),
                sub_queries="\n".join(f"- {sq['query']}"
                                    for sq in result["sub_queries"])
            )

            create_markdown_file(filepath, content)
            print(f"Saved research results to: {filepath}")

        # Create summary file with LLM-generated summary
        summary_path = os.path.join(output_dir, "summary.md")
        summary_content = SUMMARY_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_queries=len(self.results),
            queries=summary
        )
        create_markdown_file(summary_path, summary_content)
        print(f"Saved research summary to: {summary_path}")

        return output_dir

def run_test_query(query: str):
    """Run a test query and return results directory"""
    print(f"\nRunning test query: {query}")
    agent = ResearchAgent(max_depth=2)  # Lower depth for testing
    agent.research(query)
    return agent.save_results()

def main():
    # Check if running in test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        if len(sys.argv) > 2:
            output_dir = run_test_query(sys.argv[2])
            print(f"\nTest completed. Results saved in: {output_dir}")
            return
        else:
            print("Error: Test query required")
            sys.exit(1)

    # Interactive mode
    agent = ResearchAgent(max_depth=3)

    while True:
        query = input("\nEnter research query (or 'quit' to exit): ").strip()
        if query.lower() == 'quit':
            break

        print("\nStarting research...")
        agent.research(query)
        agent.save_results()
        print("\nResearch completed!")

if __name__ == "__main__":
    main()