import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CourseProfile(BaseModel):
    """Final course-level profile built from frame-level evidence."""

    title: str = Field(description="Course title.")

    total_frames: int = Field(description="Number of frame analyses loaded.")
    useful_frames: int = Field(description="Number of frames used for aggregation.")

    theory_score: float = Field(description="Course-level theory preference score.")
    hands_on_score: float = Field(description="Course-level hands-on preference score.")
    exercise_score: float = Field(description="Course-level exercise preference score.")
    project_score: float = Field(description="Course-level project preference score.")

    dominant_learning_style: str = Field(
        description="Human-readable label for the strongest learning style."
    )

    frame_type_distribution: Dict[str, int] = Field(
        description="Counts of frame_type values among useful frames."
    )
    teaching_activity_distribution: Dict[str, int] = Field(
        description="Counts of teaching_activity values among useful frames."
    )
    top_topics: List[Dict[str, Any]] = Field(
        description="Most frequently observed topics."
    )

    best_for_students_who_prefer: List[str] = Field(
        description="Student preferences that likely match this course."
    )
    less_suitable_for: List[str] = Field(
        description="Student preferences that may not match this course."
    )

    summary: str = Field(description="Short explanation of the course profile.")
    evidence: List[str] = Field(description="Representative frame evidence.")


class EvidenceAggregator:
    """
    Aggregates frame-level analysis into a course-level profile.

    Important design idea:
    - analyzer.py decides what each keyframe shows.
    - aggregator.py does not call an LLM.
    - aggregator.py only turns those frame-level signals into stable numbers.
    """

    def __init__(self, min_confidence: float = 0.4):
        # Low-confidence frames are often unclear images or failed model outputs.
        # Filtering them prevents one bad frame from influencing the course profile.
        self.min_confidence = min_confidence

    def aggregate(self, frame_analyses: List[Dict[str, Any]]) -> CourseProfile:
        """Build a CourseProfile from a list of frame analysis dictionaries."""

        useful_frames = self._filter_useful_frames(frame_analyses)

        if not useful_frames:
            return CourseProfile(
                total_frames=len(frame_analyses),
                useful_frames=0,
                theory_score=0.0,
                hands_on_score=0.0,
                exercise_score=0.0,
                project_score=0.0,
                dominant_learning_style="unknown",
                frame_type_distribution={},
                teaching_activity_distribution={},
                top_topics=[],
                best_for_students_who_prefer=[],
                less_suitable_for=[],
                summary="Not enough reliable frame evidence was found.",
                evidence=[],
            )

        theory_score = self._weighted_average(useful_frames, "theory_score")
        hands_on_score = self._weighted_average(useful_frames, "hands_on_score")
        exercise_score = self._weighted_average(useful_frames, "exercise_score")
        project_score = self._weighted_average(useful_frames, "project_score")

        frame_type_distribution = self._count_field(useful_frames, "frame_type")
        teaching_activity_distribution = self._count_field(
            useful_frames,
            "teaching_activity",
        )

        top_topics = self._get_top_topics(useful_frames)
        dominant_learning_style = self._decide_dominant_learning_style(
            theory_score=theory_score,
            hands_on_score=hands_on_score,
            exercise_score=exercise_score,
            project_score=project_score,
        )

        best_for = self._build_best_for(
            theory_score=theory_score,
            hands_on_score=hands_on_score,
            exercise_score=exercise_score,
            project_score=project_score,
            teaching_activity_distribution=teaching_activity_distribution,
        )
        less_suitable_for = self._build_less_suitable_for(
            theory_score=theory_score,
            hands_on_score=hands_on_score,
            exercise_score=exercise_score,
            project_score=project_score,
        )

        evidence = self._select_representative_evidence(useful_frames)
        summary = self._build_summary(
            dominant_learning_style=dominant_learning_style,
            theory_score=theory_score,
            hands_on_score=hands_on_score,
            exercise_score=exercise_score,
            project_score=project_score,
            top_topics=top_topics,
        )

        return CourseProfile(
            total_frames=len(frame_analyses),
            useful_frames=len(useful_frames),
            theory_score=theory_score,
            hands_on_score=hands_on_score,
            exercise_score=exercise_score,
            project_score=project_score,
            dominant_learning_style=dominant_learning_style,
            frame_type_distribution=frame_type_distribution,
            teaching_activity_distribution=teaching_activity_distribution,
            top_topics=top_topics,
            best_for_students_who_prefer=best_for,
            less_suitable_for=less_suitable_for,
            summary=summary,
            evidence=evidence,
        )

    def _filter_useful_frames(
        self,
        frame_analyses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Keep frames that are reliable enough for course-level aggregation."""

        useful_frames = []

        for frame in frame_analyses:
            frame_type = frame.get("frame_type", "unknown")
            confidence = float(frame.get("confidence", 0.0) or 0.0)

            # Failed JSON parsing or model failures usually include error.
            if frame.get("error"):
                continue

            # Blank and unknown frames do not tell us much about course style.
            if frame_type in {"blank", "unknown"}:
                continue

            if confidence < self.min_confidence:
                continue

            useful_frames.append(frame)

        return useful_frames

    def _weighted_average(
        self,
        frames: List[Dict[str, Any]],
        score_key: str,
    ) -> float:
        """
        Average a score using confidence as weight.

        A high-confidence frame should influence the final profile more than
        a low-confidence frame.
        """

        weighted_sum = 0.0
        weight_sum = 0.0

        for frame in frames:
            score = float(frame.get(score_key, 0.0) or 0.0)
            confidence = float(frame.get("confidence", 0.0) or 0.0)

            weighted_sum += score * confidence
            weight_sum += confidence

        if weight_sum == 0.0:
            return 0.0

        return round(weighted_sum / weight_sum, 3)

    def _count_field(
        self,
        frames: List[Dict[str, Any]],
        field_name: str,
    ) -> Dict[str, int]:
        """Count values such as frame_type or teaching_activity."""

        counter = Counter()

        for frame in frames:
            value = frame.get(field_name)
            if value:
                counter[str(value)] += 1

        return dict(counter.most_common())

    def _get_top_topics(
        self,
        frames: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Count visible topics extracted by analyzer.py."""

        counter = Counter()

        for frame in frames:
            for topic in frame.get("topics_observed", []) or []:
                normalized_topic = str(topic).strip().lower()
                if normalized_topic:
                    counter[normalized_topic] += 1

        return [
            {"topic": topic, "count": count}
            for topic, count in counter.most_common(limit)
        ]

    def _decide_dominant_learning_style(
        self,
        theory_score: float,
        hands_on_score: float,
        exercise_score: float,
        project_score: float,
    ) -> str:
        """
        Convert numeric scores into one readable course style label.

        The thresholds are intentionally simple for the first version.
        Later, you can tune them after looking at more courses.
        """

        if project_score >= 0.55:
            return "project_based"

        if exercise_score >= 0.55:
            return "exercise_based"

        if theory_score >= 0.55 and hands_on_score >= 0.45:
            return "theory_plus_hands_on_examples"

        if hands_on_score >= 0.55:
            return "mostly_hands_on"

        if theory_score >= 0.55:
            return "mostly_theory"

        if max(theory_score, hands_on_score, exercise_score, project_score) < 0.25:
            return "low_visible_learning_signal"

        return "mixed"

    def _build_best_for(
        self,
        theory_score: float,
        hands_on_score: float,
        exercise_score: float,
        project_score: float,
        teaching_activity_distribution: Dict[str, int],
    ) -> List[str]:
        """Generate recommendation-friendly preference labels."""

        best_for = []

        if theory_score >= 0.5:
            best_for.append("students who prefer concept explanations and slides")

        if hands_on_score >= 0.5:
            best_for.append("students who prefer hands-on demonstrations")

        if exercise_score >= 0.45:
            best_for.append("students who want visible exercises or practice tasks")

        if project_score >= 0.45:
            best_for.append("students who prefer project-based learning")

        if teaching_activity_distribution.get("teacher_talking", 0) >= 2:
            best_for.append("students who are comfortable with teacher-led lectures")

        if not best_for:
            best_for.append("students who want a mixed or lightly structured lesson")

        return best_for

    def _build_less_suitable_for(
        self,
        theory_score: float,
        hands_on_score: float,
        exercise_score: float,
        project_score: float,
    ) -> List[str]:
        """Generate labels for preferences that this course may not satisfy."""

        less_suitable_for = []

        if hands_on_score < 0.35:
            less_suitable_for.append(
                "students looking for frequent hands-on demonstrations"
            )

        if exercise_score < 0.3:
            less_suitable_for.append(
                "students looking for many exercises, quizzes, or assignments"
            )

        if project_score < 0.3:
            less_suitable_for.append(
                "students looking for a full project-based tutorial"
            )

        if theory_score < 0.3:
            less_suitable_for.append(
                "students looking for detailed theory or concept explanations"
            )

        return less_suitable_for

    def _select_representative_evidence(
        self,
        frames: List[Dict[str, Any]],
        limit: int = 8,
    ) -> List[str]:
        """
        Pick short evidence summaries for the final profile.

        We sort by confidence so the most reliable observations appear first.
        """

        sorted_frames = sorted(
            frames,
            key=lambda frame: float(frame.get("confidence", 0.0) or 0.0),
            reverse=True,
        )

        evidence = []
        seen = set()

        for frame in sorted_frames:
            summary = str(frame.get("evidence_summary", "")).strip()

            if not summary or summary in seen:
                continue

            frame_number = frame.get("frame_number", "unknown")
            evidence.append(f"Frame {frame_number}: {summary}")
            seen.add(summary)

            if len(evidence) >= limit:
                break

        return evidence

    def _build_summary(
        self,
        dominant_learning_style: str,
        theory_score: float,
        hands_on_score: float,
        exercise_score: float,
        project_score: float,
        top_topics: List[Dict[str, Any]],
    ) -> str:
        """Build a compact human-readable summary."""

        topic_names = [item["topic"] for item in top_topics[:5]]
        topic_text = ", ".join(topic_names) if topic_names else "no clear repeated topics"

        return (
            f"The course appears to be {dominant_learning_style}. "
            f"Scores: theory={theory_score:.2f}, hands_on={hands_on_score:.2f}, "
            f"exercise={exercise_score:.2f}, project={project_score:.2f}. "
            f"Common visible topics include: {topic_text}."
        )


def load_frame_analyses(input_path: Path) -> List[Dict[str, Any]]:
    """Load analyzer.py output from frame_analyses.json."""

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("frame_analyses.json must contain a list of frame results.")

    return data


def save_course_profile(profile: CourseProfile, output_path: Path) -> None:
    """Save the final course profile as readable JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)


def build_course_profile(
    input_path: Path,
    output_path: Optional[Path] = None,
    min_confidence: float = 0.4,
) -> CourseProfile:
    """
    Convenience function for scripts or CLI usage.

    Example:
        profile = build_course_profile(
            Path("output/analysis/frame_analyses.json"),
            Path("output/analysis/course_profile.json"),
        )
    """

    frame_analyses = load_frame_analyses(input_path)
    aggregator = EvidenceAggregator(min_confidence=min_confidence)
    profile = aggregator.aggregate(frame_analyses)

    if output_path is not None:
        save_course_profile(profile, output_path)

    return profile