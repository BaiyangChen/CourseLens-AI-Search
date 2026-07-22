from email.mime import text
import json
from typing import List, Dict, Any, Literal, Optional
import logging
from pathlib import Path
import ollama
from course_analyzer.frame import Frame
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
class FrameEvidence(BaseModel):
    
    frame_type: Literal[
        "code",
        "slide",
        "diagram",
        "exercise",
        "teacher_talking",
        "whiteboard",
        "terminal",
        "mixed",
        "blank",
        "unknown"
    ] = Field(description="Main visible type of this keyframe.")

    # teaching behaviour
    teaching_activity: Literal[
        "theory_explanation",
        "live_coding",
        "worked_example",
        "exercise_or_quiz",
        "project_demo",
        "teacher_talking",
        "transition",
        "unknown"
    ] = Field(description="Teaching activity supported by this frame.")

    visual_elements: List[
        Literal[
            "teacher",
            "slide",
            "code",
            "terminal",
            "diagram",
            "exercise",
            "whiteboard",
            "software_interface",
            "subtitle",
            "blank",
            "unknown"
        ]
    ] = Field(description="Visible educational elements in the frame.")

    topics_observed: List[str] = Field(
        description=(
            "Topics visibly supported by this frame. "
            "Do not invent topics that are not visible."
        )
    )

    # These score are for matching student preference
    theory_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How strongly this frame suggests theory explanation."
    )

    hands_on_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How strongly this frame suggests hands-on demo, coding, or tool usage."
    )

    exercise_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How strongly this frame suggests practice, quiz, or assignment."
    )

    project_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How strongly this frame suggests project-based learning."
    )

    visible_text_summary: Optional[str] = Field(
        default=None,
        description="Short summary of important readable text."
    )

    evidence_summary: str = Field(
        description=(
            "One short sentence explaining what this frame proves "
            "about the teaching style or learning experience."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence of this frame analysis."
    )

class VideoAnalyzer:
    def __init__(self, model: str = "qwen3-vl:4b", system_prompt: str="", temperature: float = 0.2, user_prompt: str="", outdir: Optional[str] = None):
        self.model = model
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.user_prompt = user_prompt
        self.previous_analyses = []
        self.outdir = Path(outdir) if outdir else Path("output/analysis")
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.frame_prompt = self._load_prompt("frame_analysis.txt")
        self.frame_analyses: List[Dict[str, Any]] = []

    def _format_previous_analyses(self) -> str:
        """Format previous frame analyses for inclusion in prompt."""
        if not self.previous_analyses:
            return ""
            
        formatted_analyses = []
        for i, analysis in enumerate(self.previous_analyses):
            formatted_analysis = (
                f"Frame {i}\n"
                f"{analysis.get('visible_text_summary', 'No analysis available')}\n"
            )
            formatted_analyses.append(formatted_analysis)
            
        return "\n".join(formatted_analyses)
    
    def _load_prompt(self, prompt_name: str) -> str:
        prompt_path = Path(__file__).parent / "prompt" / prompt_name

        return prompt_path.read_text(encoding="utf-8")
    
    def _save_frame_analyses(self) -> None:
        output_path = self.outdir / "frame_analyses.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.frame_analyses, f, ensure_ascii=False, indent=2)

    def _safe_json_loads(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Model response is not valid JSON")
            return {
                "frame_type": "unknown",
                "teaching_activity": "unknown",
                "visual_elements": ["unknown"],
                "topics_observed": [],
                "theory_score": 0.0,
                "hands_on_score": 0.0,
                "exercise_score": 0.0,
                "project_score": 0.0,
                "visible_text_summary": None,
                "evidence_summary": "Failed to parse model response.",
                "confidence": 0.0,
                "error": "Failed to parse JSON",
                "raw_response": text
            }
    
    def analyze_frame(self, frame: Frame) -> Dict[str, Any]:
        prompt = self.frame_prompt
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': "You are an educational video keyframe analyzer.Return only valid JSON that follows the schema."},
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [str(frame.path)]
                    }
                ],
                think=False,
                stream = False,
                format=FrameEvidence.model_json_schema(),
                options={
                    "temperature": self.temperature
                }
            )
            raw_content = response["message"]["content"]
            analysis = self._safe_json_loads(raw_content)
        except Exception as e:
            logger.exception("Failed to analyze frame %s", frame.number)
            analysis = {
                "frame_type": "unknown",
                "teaching_activity": "unknown",
                "visual_elements": ["unknown"],
                "topics_observed": [],
                "theory_score": 0.0,
                "hands_on_score": 0.0,
                "exercise_score": 0.0,
                "project_score": 0.0,
                "visible_text_summary": None,
                "evidence_summary": "Frame analysis failed.",
                "confidence": 0.0,
                "error": str(e)
            }

        analysis["frame_number"] = frame.number
        analysis["timestamp"] = frame.timestamp
        analysis["frame_path"] = str(frame.path)
        analysis["frame_score"] = frame.score
        analysis["content_score"] = getattr(frame, "content_score", None)

        self.frame_analyses.append(analysis)
        self.previous_analyses.append(analysis)
        self._save_frame_analyses()

        return analysis