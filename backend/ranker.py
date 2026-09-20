"""
ranker.py
Core scoring engine: sentence embeddings + cosine similarity, plus
keyword-based skill extraction for explainability.
"""

import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
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
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, text_lower):
            found.add(skill)
    return found


def score_resume(job_description: str, resume_text: str) -> dict:
    """
    Score a single resume against a single job description.
    Returns: {score, matched_skills, missing_skills}
    """
    model = get_model()
    embeddings = model.encode([job_description, resume_text])
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    score = round(float(similarity) * 100, 2)

    jd_skills = extract_skills(job_description)
    resume_skills = extract_skills(resume_text)
    matched = sorted(jd_skills & resume_skills)
    missing = sorted(jd_skills - resume_skills)

    return {"score": score, "matched_skills": matched, "missing_skills": missing}


def rank_resumes(job_description: str, resumes: list[dict]) -> list[dict]:
    """
    Batch version: resumes = [{"id":..., "filename":..., "text":...}, ...]
    Returns the list augmented with score/matched/missing, sorted by score desc.
    """
    model = get_model()
    jd_embedding = model.encode([job_description])
    resume_texts = [r["text"] for r in resumes]
    resume_embeddings = model.encode(resume_texts)
    similarities = cosine_similarity(jd_embedding, resume_embeddings)[0]
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

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
