import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchPreference(BaseModel):
    """
    Represents what the student is looking for in this search.

    This is not a permanent student profile. It is only the preference for the
    current search request.

    Use values from 0.0 to 1.0:
    - 1.0 means the student strongly wants that feature.
    - 0.0 means the student explicitly wants little or none of that feature.
    - None means the student does not care about that feature.

    Example:
        SearchPreference(
            query="python loops",
            theory=1.0,
            hands_on=None,
            exercise=0.0,
            project=0.0,
        )
    """

    query: str = Field(
        default="",
        description="Topic or keyword query, such as 'python loops'.",
    )

    theory: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Desired amount of theory or lecture explanation.",
    )
    hands_on: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Desired amount of hands-on coding or demo.",
    )
    exercise: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Desired amount of exercises, quizzes, or practice tasks.",
    )
    project: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Desired amount of project-based learning.",
    )

    teacher_led: Optional[bool] = Field(
        default=None,
        description=(
            "Whether the student prefers teacher-led lecture style. "
            "None means no preference."
        ),
    )


class RecommendationResult(BaseModel):
    """Result returned by the recommender for one course/tutorial."""

    match_score: float = Field(description="Final score from 0.0 to 1.0.")
    match_level: str = Field(description="Readable match level label.")

    topic_score: float = Field(description="How well the query matches course topics.")
    preference_score: float = Field(
        description="How well the course style matches selected preferences."
    )

    matched_topics: List[str] = Field(description="Course topics matched by query.")
    reasons: List[str] = Field(description="Positive explanations for the match.")
    warnings: List[str] = Field(description="Potential mismatches.")


class CourseRecommender:
    """
    Matches a course_profile.json against a student's current search preference.

    This class does not call an LLM. It is intentionally rule-based so the
    recommendation is easy to explain in a school project demo.
    """

    def recommend(
        self,
        course_profile: Dict[str, Any],
        preference: SearchPreference,
        selected_topics: Optional[List[str]] = None,
    ) -> RecommendationResult:
        """
        Return a recommendation result for one course.

        The final score combines:
        - topic_score: does the query match top_topics?
        - preference_score: do theory/hands_on/exercise/project scores match?
        """
        # Keyword matching
        topic_score, matched_topics = self._score_topic_match(
            course_profile=course_profile,
            query=preference.query,
            selected_topics=selected_topics
        )
        preference_score = self._score_preference_match(
            course_profile=course_profile,
            preference=preference,
        )

        # If the student provides no query, preference becomes more important.
        # If the student provides a query, topic and preference are both useful.
        if preference.query.strip():
            final_score = (0.45 * topic_score) + (0.55 * preference_score)
        else:
            final_score = preference_score

        final_score = round(max(0.0, min(1.0, final_score)), 3)

        reasons = self._build_reasons(
            course_profile=course_profile,
            preference=preference,
            matched_topics=matched_topics,
            topic_score=topic_score,
        )
        warnings = self._build_warnings(
            course_profile=course_profile,
            preference=preference,
            matched_topics=matched_topics,
            topic_score=topic_score,
        )

        return RecommendationResult(
            match_score=final_score,
            match_level=self._match_level(final_score),
            topic_score=round(topic_score, 3),
            preference_score=round(preference_score, 3),
            matched_topics=matched_topics,
            reasons=reasons,
            warnings=warnings,
        )

    def _score_topic_match(
        self,
        course_profile: Dict[str, Any],
        query: str,
        selected_topics: Optional[List[str]] = None,
    ) -> tuple[float, List[str]]:
        """
        Score whether the search query matches the course's top topics.

        This is simple keyword matching, not embedding search. It works well for
        a first version and keeps the result explainable.
        """
        if not query and not selected_topics:
            return 1.0, []
        
        query = query.strip()

        topic_items = course_profile.get("top_topics", []) or []
        topic_names = [str(item.get("topic", "")).strip().lower() for item in topic_items if str(item.get("topic", "")).strip()]

        if selected_topics:
            selected_topic_set = {
                str(topic).strip().lower()
                for topic in selected_topics
                if str(topic).strip()
            }

            matched_topics = [
                topic
                for topic in topic_names
                if topic.strip().lower() in selected_topic_set
            ]
            
            topic_score = len(matched_topics) / len(selected_topic_set)
            return topic_score, matched_topics
        
        matched_topics = []
        query_terms = self._normalize_terms(query)

        for topic in topic_names:
            topic_lower = topic.lower()
            topic_terms = self._normalize_terms(topic)

            full_query_match = query.lower() in topic_lower
            term_overlap = query_terms.intersection(topic_terms)

            if full_query_match or term_overlap:
                matched_topics.append(topic)

        if not matched_topics:
            return 0.0, []

        topic_score = 0.5 + min(0.5, 0.1 * len(matched_topics))
        return round(topic_score, 3), matched_topics

    def _score_preference_match(
        self,
        course_profile: Dict[str, Any],
        preference: SearchPreference,
    ) -> float:
        """
        Compare desired learning-style scores with course profile scores.

        The score is:
            1.0 - average absolute difference

        Example:
            student wants theory=1.0
            course theory_score=0.72
            difference=0.28
            contribution=0.72
        """

        comparisons = []

        self._add_score_comparison(
            comparisons,
            desired=preference.theory,
            actual=self._float_field(course_profile, "theory_score"),
        )
        self._add_score_comparison(
            comparisons,
            desired=preference.hands_on,
            actual=self._float_field(course_profile, "hands_on_score"),
        )
        self._add_score_comparison(
            comparisons,
            desired=preference.exercise,
            actual=self._float_field(course_profile, "exercise_score"),
        )
        self._add_score_comparison(
            comparisons,
            desired=preference.project,
            actual=self._float_field(course_profile, "project_score"),
        )

        teacher_led_score = self._teacher_led_score(course_profile)

        if preference.teacher_led is True:
            comparisons.append(teacher_led_score)
        elif preference.teacher_led is False:
            comparisons.append(1.0 - teacher_led_score)

        if not comparisons:
            # No explicit preferences means any course style is acceptable.
            return 1.0

        return sum(comparisons) / len(comparisons)

    def _add_score_comparison(
        self,
        comparisons: List[float],
        desired: Optional[float],
        actual: float,
    ) -> None:
        """Append a 0-1 similarity score when the user cares about this field."""

        if desired is None:
            return

        similarity = 1.0 - abs(desired - actual)
        comparisons.append(max(0.0, min(1.0, similarity)))

    def _build_reasons(
        self,
        course_profile: Dict[str, Any],
        preference: SearchPreference,
        matched_topics: List[str],
        topic_score: float,
        selected_topics: Optional[List[str]] = None,
    ) -> List[str]:
        """Build positive explanations for why this course matches."""

        reasons = []

        if matched_topics:
            reasons.append(
                "The course covers topics related to: "
                + ", ".join(matched_topics[:3])
                + "."
            )
        elif preference.query.strip() and topic_score == 0.0:
            # No positive reason here; the warning function will explain it.
            pass

        theory_score = self._float_field(course_profile, "theory_score")
        hands_on_score = self._float_field(course_profile, "hands_on_score")
        exercise_score = self._float_field(course_profile, "exercise_score")
        project_score = self._float_field(course_profile, "project_score")

        if preference.theory is not None and theory_score >= 0.6:
            reasons.append("The course is strong in theory or lecture explanation.")

        if preference.hands_on is not None and hands_on_score >= 0.5:
            reasons.append("The course includes strong hands-on coding or demo evidence.")

        if preference.exercise is not None and exercise_score >= 0.4:
            reasons.append("The course includes visible exercise or practice evidence.")

        if preference.project is not None and project_score >= 0.4:
            reasons.append("The course appears to include project-based learning.")

        if preference.teacher_led is True and self._teacher_led_score(course_profile) >= 0.5:
            reasons.append("The course has a strong teacher-led lecture style.")

        if not reasons:
            dominant_style = course_profile.get("dominant_learning_style", "unknown")
            reasons.append(f"The course style is classified as {dominant_style}.")

        return reasons

    def _build_warnings(
        self,
        course_profile: Dict[str, Any],
        preference: SearchPreference,
        matched_topics: List[str],
        topic_score: float,
    ) -> List[str]:
        """Build explanations for possible mismatches."""

        warnings = []

        if preference.query.strip() and topic_score == 0.0:
            warnings.append("The query does not clearly match the course's top topics.")

        theory_score = self._float_field(course_profile, "theory_score")
        hands_on_score = self._float_field(course_profile, "hands_on_score")
        exercise_score = self._float_field(course_profile, "exercise_score")
        project_score = self._float_field(course_profile, "project_score")

        if preference.theory is not None and preference.theory >= 0.7 and theory_score < 0.4:
            warnings.append("The course may not have enough theory explanation.")

        if preference.hands_on is not None and preference.hands_on >= 0.7 and hands_on_score < 0.4:
            warnings.append("The course may not have enough hands-on coding or demo work.")

        if preference.exercise is not None and preference.exercise >= 0.7 and exercise_score < 0.4:
            warnings.append("The course has little visible exercise or quiz evidence.")

        if preference.project is not None and preference.project >= 0.7 and project_score < 0.4:
            warnings.append("The course does not appear to be project-based.")

        if preference.teacher_led is False and self._teacher_led_score(course_profile) >= 0.6:
            warnings.append("The course is strongly teacher-led, which may not match this preference.")

        return warnings

    def _teacher_led_score(self, course_profile: Dict[str, Any]) -> float:
        """
        Estimate teacher-led style from frame_type_distribution.

        The aggregator currently does not output teacher_led_score directly, so
        this function derives it from the number of teacher_talking frames.
        """

        frame_distribution = course_profile.get("frame_type_distribution", {}) or {}
        useful_frames = float(course_profile.get("useful_frames", 0) or 0)

        if useful_frames <= 0:
            return 0.0

        teacher_frames = float(frame_distribution.get("teacher_talking", 0) or 0)
        return max(0.0, min(1.0, teacher_frames / useful_frames))

    def _normalize_terms(self, text: str) -> set[str]:
        """
        Normalize text into searchable terms.

        Example:
            "Python loops!" -> {"python", "loops"}
        """

        return {
            term
            for term in re.split(r"[^a-zA-Z0-9]+", text.lower())
            if term
        }

    def _float_field(self, data: Dict[str, Any], field_name: str) -> float:
        """Read a numeric field safely from course_profile.json."""

        return float(data.get(field_name, 0.0) or 0.0)

    def _match_level(self, score: float) -> str:
        """Convert numeric score into a simple label."""

        if score >= 0.85:
            return "strong_match"
        if score >= 0.65:
            return "good_match"
        if score >= 0.45:
            return "partial_match"
        return "weak_match"


def load_course_profile(path: Path) -> Dict[str, Any]:
    """
    Load one course profile.

    Older code expects course_profile.json to contain one JSON object.
    Now the file may contain a list of profiles for search demos, so this
    function returns the first profile when it sees a list.
    """

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        if isinstance(data, list) and data:
            first_profile = data[0]

            if not isinstance(first_profile, dict):
                raise ValueError("course_profile.json list must contain JSON objects.")

            return first_profile

        raise ValueError("course_profile.json must contain one JSON object or a list of objects.")

    return data


def load_course_profiles(path: Path) -> List[Dict[str, Any]]:
    """
    Load all course profiles.

    Use this when the search API needs to rank multiple tutorials.
    """

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return [data]

    if isinstance(data, list):
        profiles = []

        for item in data:
            if not isinstance(item, dict):
                raise ValueError("course_profile.json list must contain JSON objects.")
            profiles.append(item)

        return profiles

    raise ValueError("course_profile.json must contain one JSON object or a list of objects.")


def recommend_course(
    course_profile_path: Path,
    preference: SearchPreference,
) -> RecommendationResult:
    """
    Convenience function for matching one course profile against one preference.

    Example:
        result = recommend_course(
            Path("output/analysis/course_profile.json"),
            SearchPreference(query="python loops", theory=1.0),
        )
    """

    course_profile = load_course_profile(course_profile_path)
    recommender = CourseRecommender()
    return recommender.recommend(course_profile, preference)
