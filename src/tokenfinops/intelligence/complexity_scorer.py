import logging

logger = logging.getLogger(__name__)

class PromptComplexityScorer:
    """Estimates the reasoning complexity of a prompt to inform routing choices."""

    def score_complexity(self, prompt_text: str) -> float:
        # Initial score
        score = 0.2
        prompt_lower = prompt_text.lower()
        word_count = len(prompt_text.split())

        # 1. Size adjustments
        if word_count > 300:
            score += 0.3
        elif word_count > 100:
            score += 0.15

        # 2. Syntax / code markers indicating engineering requests
        code_markers = ["def ", "class ", "import ", "const ", "function ", "<html>", "sql", "git", "docker"]
        if any(marker in prompt_lower for marker in code_markers):
            score += 0.35

        # 3. Instruction terms indicating reasoning / analysis
        reasoning_keywords = [
            "explain", "solve", "prove", "analyze", "why", "comprehensive", 
            "step-by-step", "calculate", "optimize", "compare", "evaluate"
        ]
        keyword_hits = sum(1 for kw in reasoning_keywords if kw in prompt_lower)
        score += min(keyword_hits * 0.08, 0.3)

        # 4. Cap score between 0.0 and 1.0
        final_score = max(min(score, 1.0), 0.0)
        logger.debug(f"Prompt complexity score: {final_score:.2f} (words: {word_count})")
        return final_score
