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
        """Simple content filtering"""
        # Remove extra whitespace and normalize
        content = ' '.join(content.split())
        return content[:1000]  # Simple truncation

    def generate_sub_queries(self, query: str, content: List[Dict[str, str]]) -> List[str]:
        """Generate sub-queries using simple text analysis"""
        print("\nProcessing content for sub-queries:")
        sub_queries = set()  # Use set to avoid duplicates

        # Combine all content
        combined_text = " ".join(item["content"] for item in content)
        print(f"Combined text length: {len(combined_text)}")

        # Clean up text
        text = re.sub(r'\s+', ' ', combined_text)
        text = re.sub(r'["\']', '', text)  # Remove quotes that might break sentences

        # Split into sentences using multiple delimiters
        sentences = []
        for delimiter in ['. ', '? ', '! ', '\n']:
            parts = text.split(delimiter)
            sentences.extend(parts)

        print(f"Found {len(sentences)} potential sentences")

        # Process each sentence
        for sentence in sentences:
            # Clean the sentence
            sentence = sentence.strip()
            words = sentence.split()

            # More flexible length requirements
            if 4 <= len(words) <= 20:  # Accept shorter and longer sentences
                # Check if sentence seems to be a question or contains key phrases
                lower_sentence = sentence.lower()
                if any(phrase in lower_sentence for phrase in 
                      ['what is', 'how to', 'why does', 'explain', 
                       'difference between', 'compare', 'define']):
                    sub_queries.add(sentence)
                elif any(word in lower_sentence for word in 
                        query.lower().split()):  # Related to original query
                    sub_queries.add(sentence)

        # Convert relevant sentences to questions if needed
        final_queries = []
        for sentence in list(sub_queries)[:5]:  # Limit to top 5
            if not any(sentence.lower().startswith(w) for w in 
                      ['what', 'how', 'why', 'when', 'where', 'who']):
                # Convert statement to question if it's not already one
                question = f"What is meant by: {sentence}"
                final_queries.append(question)
            else:
                final_queries.append(sentence)

        print(f"Generated {len(final_queries)} sub-queries")
        return final_queries

    def summarize_results(self, results: List[Dict[str, Any]]) -> str:
        """Create a readable summary of research results"""
        summary = []
        for result in results:
            content_summary = []
            for item in result.get("content", []):
                text = item.get("content", "")[:200]
                content_summary.append(f"- {text}...")

            summary.append(f"## {result['query']}\n" + "\n".join(content_summary))

        return "\n\n".join(summary)