from __future__ import annotations

import os

from ..models import Candidate

PROMPT_TEMPLATE = """Bạn là trợ lý trả lời câu hỏi dựa trên tài liệu.
Chỉ dùng thông tin trong phần NGỮ CẢNH. Trích dẫn nguồn bằng số trong ngoặc vuông, ví dụ [1].
Nếu ngữ cảnh không đủ để trả lời, hãy nói rõ là không đủ thông tin, không tự suy đoán.

NGỮ CẢNH:
{context}

CÂU HỎI: {question}

TRẢ LỜI:"""


def build_prompt(question: str, candidates: list[Candidate]) -> str:
    context = "\n\n".join(
        f"[{i}] ({c.file_name})\n{c.text}" for i, c in enumerate(candidates, start=1)
    )
    return PROMPT_TEMPLATE.format(context=context, question=question)


def build_llm(model: str):
    """Tao LLM cho LlamaIndex.

    - Co LLM_API_BASE: dung bat ky dich vu tuong thich OpenAI
      (Groq, Gemini, Mistral, OpenRouter, GitHub Models...).
    - Khong co LLM_API_BASE: dung OpenAI chinh hang (can OPENAI_API_KEY).
    """
    api_base = os.getenv("LLM_API_BASE", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()

    if api_base:
        if not api_key:
            raise RuntimeError("Thiếu LLM_API_KEY trong file .env")
        from llama_index.llms.openai_like import OpenAILike

        return OpenAILike(
            model=model,
            api_base=api_base,
            api_key=api_key,
            is_chat_model=True,
            context_window=32768,
            temperature=0.1,
            timeout=120,
        )

    from llama_index.llms.openai import OpenAI

    return OpenAI(model=model)


def generate_answer(llm, question: str, candidates: list[Candidate]) -> str:
    if not candidates:
        return "Không tìm thấy tài liệu phù hợp với câu hỏi và bộ lọc đã chọn."
    return llm.complete(build_prompt(question, candidates)).text.strip()
