"""Prompt templates for LLM interactions."""

from typing import List, Dict, Any


class PromptTemplates:
    """Centralized prompt management for EndoChat."""

    SYSTEM_PROMPT = """You are EndoChat, a compassionate and highly knowledgeable AI assistant dedicated exclusively to endometriosis. You receive context from multiple source types: trusted medical APIs (e.g. WHO, PubMed, OpenFDA, DrugBank) and, when available, web search results. Your role is to synthesize all provided sources into one coherent, premium-quality answer—never give a basic or one-line reply.

SCOPE:
- Answer ONLY questions clearly about endometriosis or directly related (e.g. "pain with periods", "fertility and endo", "laparoscopy for endo"). If off-topic, respond briefly: "I'm here to help with endometriosis-related questions only. Is there something about endometriosis you'd like to know?"
- Stay strictly within the provided context; do not add facts from outside the sources.

PREMIUM ANSWER STYLE:
- Synthesize across all source types into a single, well-structured answer. Prioritize authoritative medical sources (WHO, PubMed, etc.) but incorporate relevant web content when it adds value.
- Use clear structure where appropriate: a short intro, key points or sections, and clear citations [1], [2], [3] matching the context numbers. End with a brief line encouraging the user to consult a healthcare provider for personal decisions.
- Be thorough, specific, and accurate—not generic. Use clear, accessible language while remaining medically accurate.
- Be empathetic and supportive; endometriosis significantly impacts quality of life.

SAFETY:
- Never give personal medical diagnoses or treatment recommendations. Cite only the provided context. If the context is insufficient, say so and suggest rephrasing or a related question."""

    def detailed_answer(self, question: str, context: str) -> str:
        """Generate a detailed, premium answer prompt (medical + web sources)."""
        return f"""Using the following context from trusted medical sources and web search (when present), provide a comprehensive, premium-quality answer to the user's question about endometriosis. Do not give a basic or generic answer—synthesize the context into a specific, accurate, and helpful response.

CONTEXT (medical APIs and/or web; each [N] is one source):
{context}

USER QUESTION: {question}

INSTRUCTIONS:
1. Answer based ONLY on the provided context. Combine information from medical and web sources into one coherent answer. Prioritize authoritative sources (WHO, PubMed, etc.) but use web content when relevant.
2. Cite sources with [1], [2], [3] matching the context numbers.
3. Be thorough and well-organized: use a short intro, key points or sections, and a closing line encouraging consultation with a healthcare provider.
4. If the context doesn't fully answer the question, state what is available and what is missing; do not speculate.
5. Be supportive and empathetic. Do not diagnose or recommend treatments.

Provide your answer:"""

    def simple_answer(self, question: str, context: str) -> str:
        """Generate a simplified but premium answer prompt (medical + web sources)."""
        return f"""Using the context below (from medical sources and/or web search), provide a simple, easy-to-understand answer to this question about endometriosis. Do not give a basic or generic answer—use the provided context to give a specific, accurate, and helpful response in plain language.

CONTEXT:
{context}

QUESTION: {question}

INSTRUCTIONS:
1. Synthesize the context (medical + web when present) into 2-3 clear paragraphs. Use simple, everyday language—avoid jargon.
2. Cite sources with [1], [2] where relevant.
3. Focus on the most important points for someone learning about or living with endometriosis. End with a brief line about consulting a healthcare provider.

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
        """Format sources into context string for prompts (medical APIs + web)."""
        context_parts = []
        source_labels = {"who": "WHO", "pubmed": "PubMed", "openfda": "OpenFDA", "drugbank": "DrugBank", "medlineplus": "MedlinePlus", "web": "Web"}

        for i, source in enumerate(sources, 1):
            source_type = source.get("source", "source")
            org = source.get("organization", source_labels.get(source_type, source_type.upper()))
            title = source.get("title", "")
            content = (source.get("content") or source.get("snippet") or "")[:600]

            context_parts.append(
                f"[{i}] ({org}) {title}\n{content}"
            )

        return "\n\n".join(context_parts)

    def classify_question(self, question: str) -> str:
        """Classify question into category."""
        return f"""Classify this question. If it is clearly about endometriosis (or directly related, e.g. period pain, fertility and endo), use ONE category below. If it is NOT about endometriosis, respond with: off-topic

Categories: symptoms, treatment, diagnosis, causes, fertility, lifestyle, support, general

QUESTION: {question}

Respond with only the category name or "off-topic", nothing else:"""
