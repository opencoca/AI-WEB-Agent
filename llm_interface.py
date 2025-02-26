"""Abstract interface for LLM integration"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re

class LLMInterface(ABC):
    @abstractmethod
    def filter_content(self, content: str) -> str:
        """Filter and clean content using LLM"""
        pass

    @abstractmethod
    def generate_sub_queries(self, query: str, content: List[Dict[str, str]]) -> List[str]:
        """Generate relevant sub-queries using LLM"""
        pass

    @abstractmethod
    def summarize_results(self, results: List[Dict[str, Any]]) -> str:
        """Summarize research results using LLM"""
        pass

class DummyLLM(LLMInterface):
    """Dummy LLM implementation for testing"""
    def filter_content(self, content: str) -> str:
        return ' '.join(content.split())[:1000]  

    def generate_sub_queries(self, query: str, content: List[Dict[str, str]]) -> List[str]:
        print("\nProcessing content for sub-queries:")
        combined_text = " ".join(item["content"] for item in content)
        text = re.sub(r'["\'\s]+', ' ', combined_text)
        sentences = [s.strip() for s in text.replace('\n', '. ').split('. ') if s.strip()]
        print(f"Found {len(sentences)} potential sentences")

        key_phrases = ['what is', 'how to', 'why does', 'explain', 'difference between', 'compare', 'define']
        query_words = query.lower().split()

        relevant_sentences = {s for s in sentences 
                            if 4 <= len(s.split()) <= 20 and 
                            (any(p in s.lower() for p in key_phrases) or 
                             any(w in s.lower() for w in query_words))}

        question_words = ['what', 'how', 'why', 'when', 'where', 'who']
        final_queries = [(s if any(s.lower().startswith(w) for w in question_words) else f"What is meant by: {s}")
                        for s in list(relevant_sentences)[:5]]

        print(f"Generated {len(final_queries)} sub-queries")
        return final_queries

    def summarize_results(self, results: List[Dict[str, Any]]) -> str:
        return "\n\n".join(f"## {result['query']}\n" + "\n".join(f"- {item['content'][:200]}..." 
                          for item in result.get("content", [])) for result in results)