import json
from pathlib import Path

from course_analyzer.aggregator import build_course_profile
from course_analyzer.analyzer import VideoAnalyzer
from course_analyzer.frame import VideoProcessor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
ANALYSIS_DIR = OUTPUT_DIR / "analysis"
COURSE_PROFILE_PATH = ANALYSIS_DIR / "course_profile2.json"

FRAMES_PER_MINUTE = 6
MODEL = "qwen3-vl:4b"

COURSES = [
    {
        "title": "Branching Iteration",
        "video_path": DATA_DIR / "Branching_Iteration.mp4",
        "frames_dir": OUTPUT_DIR / "frame1",
        "analysis_dir": ANALYSIS_DIR / "frame1",
    },
    {
        "title": "Chinese History",
        "video_path": DATA_DIR / "Chinese_Hinstory.mp4",
        "frames_dir": OUTPUT_DIR / "frame2",
        "analysis_dir": ANALYSIS_DIR / "frame2",
    },
]


def process_course(course: dict) -> dict:
    print(f"\nProcessing: {course['title']}")
    print(f"Video: {course['video_path']}")

    processor = VideoProcessor(
        video_path=course["video_path"],
        output_dir=course["frames_dir"],
    )
    frames = processor.extract_keyframe(frames_per_minute=FRAMES_PER_MINUTE)

    print(f"Extracted frames: {len(frames)}")
    if not frames:
        raise RuntimeError(f"No frames extracted for {course['title']}")

    analyzer = VideoAnalyzer(
        model=MODEL,
        temperature=0.2,
        outdir=str(course["analysis_dir"]),
    )

    for index, frame in enumerate(frames, start=1):
        print(f"Analyzing frame {index}/{len(frames)}")
        analyzer.analyze_frame(frame)

    frame_analyses_path = course["analysis_dir"] / "frame_analyses.json"
    profile = build_course_profile(
        input_path=frame_analyses_path,
        min_confidence=0.4,
        title=course["title"],
    )

    print(f"Profile ready: {profile.summary}")
    return profile.model_dump()


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    profiles = []
    for course in COURSES:
        profiles.append(process_course(course))

    with open(COURSE_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)

    print(f"\nSaved course profiles to: {COURSE_PROFILE_PATH}")


if __name__ == "__main__":
    main()
