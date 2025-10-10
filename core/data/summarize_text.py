from nltk.tokenize import sent_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from core.data.finance_hints import FINANCE_HINTS

def split_into_paragraphs(text: str):
    return [p.strip() for p in text.split("\n") if len(p.strip()) > 100]

def score_paragraphs_tfidf(paragraphs, finance_tokens):
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(paragraphs)
    scores = np.asarray(X.sum(axis=1)).ravel()

    # Boost paragraphs mentioning key finance words
    for i, p in enumerate(paragraphs):
        if any(tok.lower() in p.lower() for tok in finance_tokens):
            scores[i] *= 1.3
    return scores

def summarize_article(text: str, ticker: str):
    paras = split_into_paragraphs(text)
    if not paras:
        return None
    tokens = FINANCE_HINTS.get(ticker, FINANCE_HINTS["*"])
    scores = score_paragraphs_tfidf(paras, tokens)
    ranked = [p for _, p in sorted(zip(scores, paras), reverse=True)]
    # Take top 1–2 paragraphs
    summary = "\n\n".join(ranked[:2])
    return summary.strip()
