from collections import defaultdict

import rag
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER

SYSTEM_PROMPT = (
    "You are a competitive intelligence analyst. Answer the user's question using ONLY "
    "the provided context from competitor websites. If the context does not contain the "
    "answer, say so clearly. Always mention competitor names and cite their page URLs. "
    "Structure your answer as: 1) Short answer, 2) Comparison table in markdown, "
    "3) Strengths and weaknesses per competitor, 4) Gaps or opportunities."
)


def rank_competitors(query: str, per_competitor: int = 3) -> list:
    hits = rag.search(query, n_results=40)
    grouped = defaultdict(list)
    for hit in hits:
        grouped[hit["competitor"]].append(hit)

    ranked = []
    for name, items in grouped.items():
        items.sort(key=lambda h: h["similarity"], reverse=True)
        top = items[:per_competitor]
        score = sum(h["similarity"] for h in top) / len(top)
        ranked.append(
            {
                "competitor": name,
                "website": top[0]["website"],
                "score": round(score, 4),
                "evidence": [
                    {
                        "url": h["url"],
                        "title": h["title"],
                        "snippet": h["text"][:500],
                        "similarity": h["similarity"],
                    }
                    for h in top
                ],
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked


def _llm_enabled() -> bool:
    if LLM_PROVIDER in ("", "none"):
        return False
    if not LLM_MODEL:
        return False
    if LLM_PROVIDER != "ollama" and not LLM_API_KEY:
        return False
    return True


def _call_llm(user_prompt: str) -> str:
    if LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=LLM_API_KEY)
        response = client.messages.create(
            model=LLM_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(b.text for b in response.content if b.type == "text")

    # Groq, Gemini, OpenAI and Ollama all work through the OpenAI-compatible client.
    from openai import OpenAI

    client = OpenAI(api_key=LLM_API_KEY or "not-needed", base_url=LLM_BASE_URL)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


def generate_analysis(query: str, ranked: list) -> str | None:
    if not _llm_enabled() or not ranked:
        return None

    blocks = []
    for item in ranked:
        for ev in item["evidence"]:
            blocks.append(
                f"[Competitor: {item['competitor']}] [URL: {ev['url']}]\n{ev['snippet']}"
            )
    context = "\n\n---\n\n".join(blocks)

    prompt = f"Question: {query}\n\nContext from competitor websites:\n\n{context}"
    return _call_llm(prompt)