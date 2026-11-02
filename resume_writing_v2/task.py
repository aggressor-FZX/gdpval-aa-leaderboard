"""Task definition: the JD, the verified candidate profile, the system prompt.

Separated from the runner so the prompt can be versioned and diffed. The
profile is the ONLY set of facts a model may use — gates.py enforces this
against the same lists.
"""
from __future__ import annotations

JD_TEXT = """Data Scientist (Data Science) - Boeing Defense, Space & Security

Position Responsibilities:
- Develop and deploy Generative AI and large language model solutions for
  defense analytics, including retrieval-augmented generation and fine-tuning.
- Build and maintain data pipelines and ETL processes in Python and SQL.
- Design evaluation frameworks for model performance, bias, and fairness in
  regulated environments.
- Work with distributed training and GPU infrastructure (H100 clusters).
- Containerize and orchestrate workloads with Docker and Kubernetes.
- Collaborate cross-functionally with engineering teams; support MLOps,
  monitoring, and CI/CD for production models.
- Ensure governance, compliance, and audit readiness for regulated defense data.

Required skills: Python, PyTorch, SQL, Docker, Kubernetes, AWS, LangChain.
"""

CANDIDATE_PROFILE = """VERIFIED CANDIDATE FACTS — DO NOT INVENT ANYTHING OUTSIDE THIS PROFILE:

Name: Jeff Calderon
Location: Marysville, WA
Citizenship: U.S. Citizen
Contractor entity: Cogito Metric (C2C)

EDUCATION
- B.S. Data Analytics, Washington State University
- B.S. Physics, Washington State University
- A.A.S. Computer Science

CERTIFICATIONS
- CompTIA Security+ (Network Security+)
- Cybersecurity Analyst (ECC)
- Data Analytics certificate

EXPERIENCE (reverse chronological)
1. Cogito Metric (2024 - present) — built an NLP resume platform; 263 resumes
   processed; 500K in funding supported; 40% reduction in processing time;
   handles 30 requests per week; 13 production pipelines; 10+ TB of data.
2. NOAA — data engineering and analytics; weather and oceanographic datasets.
3. Naval Research Laboratory (NRL) — research computing support.
4. Capstone project — GPU cluster work, H100 exposure.

SKILLS
Python, PyTorch, TensorFlow, SQL, Docker, Kubernetes, AWS, LangChain, Pinecone,
Hadoop, Spark, Airflow.

DO NOT claim: a Master's degree, PhD, security clearance, or employment at
Google, Microsoft, Amazon, Meta, Apple, Netflix, OpenAI, or Anthropic.
"""

SYSTEM_PROMPT = """You are an expert ATS-optimized resume writer for data science
and machine learning roles in the defense industry.

Rules:
1. Output ONLY the resume text. No preamble, no explanation, no markdown code
   fences, no commentary before or after.
2. Use ONLY facts present in the verified candidate profile. Invent nothing.
3. Plain text with clear section headings. Do NOT use markdown tables or
   multi-column layouts — ATS parsers cannot read them.
4. Bullets start with a strong action verb and include a quantified result
   where the profile provides one. No first-person pronouns in bullets.
5. Target 400-600 words.
"""


def build_prompt(jd_text: str = JD_TEXT,
                 profile: str = CANDIDATE_PROFILE) -> str:
    return (f"JOB DESCRIPTION:\n{jd_text}\n\n"
            f"{profile}\n\n"
            "Write the tailored resume now.")
