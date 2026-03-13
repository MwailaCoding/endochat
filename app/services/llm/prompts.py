"""Prompt templates for LLM interactions."""

from typing import List, Dict, Any


class PromptTemplates:
    """Centralized prompt management for EndoChat."""

    SYSTEM_PROMPT = """You are EndoChat, a compassionate and knowledgeable AI assistant specializing in endometriosis information. Your role is to provide accurate, evidence-based information while being supportive and understanding.

Key guidelines:
- Use ONLY the provided context to answer questions
- Always cite sources using [1], [2] format when referencing information
- Be empathetic - endometriosis significantly impacts quality of life
- If information is not in the context, clearly state that
- Never provide medical diagnoses or treatment recommendations
- Encourage users to consult healthcare providers for personal medical decisions
- Use clear, accessible language while being medically accurate"""

    def detailed_answer(self, question: str, context: str) -> str:
        """Generate a detailed answer prompt."""
        return f"""Based on the following trusted medical sources, provide a comprehensive answer to the user's question about endometriosis.

CONTEXT FROM TRUSTED SOURCES:
{context}

USER QUESTION: {question}

INSTRUCTIONS:
1. Answer based ONLY on the provided context - do not add information from other sources
2. Cite sources using [1], [2], [3] format matching the context numbers
3. Be thorough but clear and well-organized
4. If the context doesn't fully answer the question, acknowledge what information is available and what is missing
5. Be supportive and empathetic in tone
6. Include relevant details that help the user understand the topic

Provide your answer:"""

    def simple_answer(self, question: str, context: str) -> str:
        """Generate a simplified answer prompt."""
        return f"""Using the information below, provide a simple, easy-to-understand answer to this question about endometriosis. Write as if explaining to someone with no medical background.

INFORMATION FROM TRUSTED SOURCES:
{context}

QUESTION: {question}

INSTRUCTIONS:
1. Use simple, everyday language - avoid medical jargon
2. Keep sentences short and clear
3. Answer in 2-3 paragraphs maximum
4. Still cite sources with [1], [2] where relevant
5. Focus on the most important points

Simple answer:"""

    def suggestions(
        self,
        question: str,
        answer: str,
        count: int = 3,
    ) -> str:
        """Generate follow-up question suggestions."""
        return f"""Based on this conversation about endometriosis, suggest {count} natural follow-up questions the user might want to ask next.

ORIGINAL QUESTION: {question}

ANSWER PROVIDED: {answer}

INSTRUCTIONS:
- Questions should be specific and actionable
- They should logically follow from the conversation
- Make them relevant to someone learning about or managing endometriosis
- Each question should explore a different aspect
- Format as a simple list, one question per line
- Do not number them or use bullets

Suggested follow-up questions:"""

    def simplify(self, complex_text: str) -> str:
        """Simplify medical text for patients."""
        return f"""Rewrite this medical text in simple, clear language that any patient can understand. Remove jargon and explain concepts in everyday terms.

ORIGINAL TEXT:
{complex_text}

SIMPLIFIED VERSION:"""

    def summarize_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Summarize multiple sources into key points."""
        source_text = "\n\n".join([
            f"Source {i+1} ({s.get('source', 'Unknown')}):\n{s.get('content', '')[:500]}"
            for i, s in enumerate(sources)
        ])

        return f"""Summarize the key points from these sources about endometriosis into a concise overview.

SOURCES:
{source_text}

INSTRUCTIONS:
- Extract 3-5 main points
- Note any consensus or conflicting information
- Keep each point brief but informative

Key points:"""

    def format_context(self, sources: List[Dict[str, Any]]) -> str:
        """Format sources into context string for prompts."""
        context_parts = []

        for i, source in enumerate(sources, 1):
            source_type = source.get("source", "source")
            org = source.get("organization", source_type.upper())
            title = source.get("title", "")
            content = source.get("content", "")[:600]

            context_parts.append(
                f"[{i}] {org} - {title}\n{content}"
            )

        return "\n\n".join(context_parts)

    def classify_question(self, question: str) -> str:
        """Classify question into category."""
        return f"""Classify this endometriosis-related question into ONE of these categories:
- symptoms
- treatment
- diagnosis
- causes
- fertility
- lifestyle
- support
- general

QUESTION: {question}

Respond with only the category name, nothing else:"""
