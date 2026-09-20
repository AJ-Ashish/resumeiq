"""
ranker.py
Core scoring engine: sentence embeddings + cosine similarity, plus
keyword-based skill extraction for explainability.

Render-friendly version:
- Uses a smaller sentence-transformer model
- CPU-only inference
- No gradient tracking
- No sklearn runtime import
- Smaller max sequence length
"""

import os
import re

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/paraphrase-MiniLM-L3-v2"

torch.set_num_threads(1)

_model = None


def get_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(
            MODEL_NAME,
            device="cpu",
        )
        _model.max_seq_length = 256
        _model.eval()

    return _model


COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "sql", "nosql",
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "aws", "azure", "gcp", "docker", "kubernetes", "git", "linux",
    "html", "css", "rest api", "graphql", "mongodb", "postgresql", "mysql",
    "data analysis", "data visualization", "excel", "power bi", "tableau",
    "communication", "leadership", "project management", "agile", "scrum",
]


def extract_skills(text: str) -> set:
    text_lower = text.lower()
    found = set()

    for skill in COMMON_SKILLS:
        pattern = (
            r"(?<![a-zA-Z0-9])"
            + re.escape(skill)
            + r"(?![a-zA-Z0-9])"
        )

        if re.search(pattern, text_lower):
            found.add(skill)

    return found


def _encode(texts: list[str]):
    """Generate normalized embeddings with minimal inference overhead."""
    model = get_model()

    with torch.inference_mode():
        embeddings = model.encode(
            texts,
            batch_size=1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    return embeddings


def score_resume(job_description: str, resume_text: str) -> dict:
    """
    Score a single resume against a single job description.

    Returns:
        {
            "score": float,
            "matched_skills": list[str],
            "missing_skills": list[str]
        }
    """
    embeddings = _encode([
        job_description,
        resume_text,
    ])

    # With normalized embeddings, cosine similarity equals dot product.
    similarity = float(embeddings[0] @ embeddings[1])
    score = round(similarity * 100, 2)

    jd_skills = extract_skills(job_description)
    resume_skills = extract_skills(resume_text)

    matched = sorted(jd_skills & resume_skills)
    missing = sorted(jd_skills - resume_skills)

    return {
        "score": score,
        "matched_skills": matched,
        "missing_skills": missing,
    }


def rank_resumes(
    job_description: str,
    resumes: list[dict],
) -> list[dict]:
    """
    Batch version.

    resumes = [
        {"id": ..., "filename": ..., "text": ...},
        ...
    ]

    Returns resumes augmented with score/matched/missing,
    sorted by score descending.
    """
    if not resumes:
        return []

    jd_embedding = _encode([job_description])[0]

    resume_texts = [r["text"] for r in resumes]
    resume_embeddings = _encode(resume_texts)

    # Normalized vectors -> dot product = cosine similarity.
    similarities = resume_embeddings @ jd_embedding

    jd_skills = extract_skills(job_description)

    results = []

    for i, resume in enumerate(resumes):
        resume_skills = extract_skills(resume["text"])
        matched = jd_skills & resume_skills
        missing = jd_skills - resume_skills

        score = round(float(similarities[i]) * 100, 2)

        results.append({
            **resume,
            "score": score,
            "matched_skills": sorted(matched),
            "missing_skills": sorted(missing),
        })

    results.sort(
        key=lambda r: r["score"],
        reverse=True,
    )

    return results
