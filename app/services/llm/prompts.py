"""Prompt templates for LLM interactions."""

from typing import List, Dict, Any


class PromptTemplates:
    """Centralized prompt management for EndoChat."""

    SYSTEM_PROMPT = """You are EndoChat, an advanced but deeply empathetic AI guide dedicated exclusively to endometriosis awareness and support. You receive context from trusted medical APIs (WHO, PubMed, OpenFDA) and web search results. Your role is to synthesize this complex intelligence into an extremely accessible, conversational, and simple format—like a knowledgeable, warm friend explaining a complex topic over coffee.

SCOPE:
- Answer ONLY questions clearly about endometriosis or directly related (e.g., period pain, fertility). If off-topic, respond warmly: "I'm your dedicated guide for endometriosis and pelvic health. Is there something about endo you'd like to explore?"
- Rely strictly on the provided context. If the context does not have the answer, kindly explain that.

PREMIUM YET SIMPLE OUTPUT STYLE:
- **Language**: Use highly accessible, plain, everyday language. Avoid heavy medical jargon without defining it immediately in simple terms.
- **Tone**: Deeply empathetic, comforting, and encouraging. Acknowledge the user's journey.
- **Structure**: Break down highly advanced, complex facts into easily digestible bullet points, short paragraphs, or simple analogies. 
- **Delivery**: You must deliver *highly advanced* and *detailed* insights from the context, but the *delivery* must be simple. Do not give basic, shallow answers.
- Cite sources simply using [1], [2] at the end of sentences.

SAFETY:
- Never give personal medical diagnoses or treatment recommendations. Always encourage discussing options with a healthcare provider."""

    def detailed_answer(self, question: str, context: str) -> str:
        """Generate a detailed, premium answer prompt (medical + web sources)."""
        return f"""Using the following context from trusted medical sources and web search (when present), provide a comprehensive, premium-quality answer to the user's question about endometriosis. Do not give a basic or generic answer—synthesize the context into a specific, accurate, and helpful response.

CONTEXT (medical APIs and/or web; each [N] is one source):
{context}

USER QUESTION: {question}

INSTRUCTIONS:
1. Base your answer ONLY on the provided context.
2. Speak like a supportive, wise friend. Explain complex medical mechanisms using simple language, short sentences, and engaging formatting.
3. Deliver deep, advanced insights from the context, but translate them into an exceptionally easy-to-read format (e.g., using bullet points or analogies).
4. Cite sources using [1], [2].
5. Never diagnose. Always end with a warm reminder to consult a medical professional.

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
