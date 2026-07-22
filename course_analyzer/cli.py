from pathlib import Path

from course_analyzer.aggregator import build_course_profile
from course_analyzer.analyzer import VideoAnalyzer
from course_analyzer.frame import VideoProcessor


# Input video. The file in your data folder is named "Chinese_Hinstory.mp4".
VIDEO_PATH = Path(r"D:\INF5114\video_analysis_system\data\Chinese_Hinstory.mp4")

# Save the new Chinese History keyframes here.
FRAMES_DIR = Path(r"D:\INF5114\video_analysis_system\output\frames2")

# Save frame_analyses.json and course_profile.json here.
ANALYSIS_DIR = Path(r"D:\INF5114\video_analysis_system\output\analysis")
FRAME_ANALYSES_PATH = ANALYSIS_DIR / "frame_analyses.json"
COURSE_PROFILE_PATH = ANALYSIS_DIR / "course_profile.json"

# A small value keeps the number of frames manageable.
# Increase it if you want denser sampling.
FRAMES_PER_MINUTE = 6


def main() -> None:
    """
    Full pipeline for Chinese History:
    1. Cut keyframes from the video into output/frames2.
    2. Analyze each keyframe with analyzer.py.
    3. Aggregate frame_analyses.json into course_profile.json.
    """

    print("Starting Chinese History analysis pipeline.")
    print(f"Video: {VIDEO_PATH}")

    # Step 1: cut keyframes from the video.
    processor = VideoProcessor(
        video_path=VIDEO_PATH,
        output_dir=FRAMES_DIR,
    )
    frames = processor.extract_keyframe(frames_per_minute=FRAMES_PER_MINUTE)

    print(f"\nExtracted {len(frames)} keyframes.")
    print(f"Frames saved to: {FRAMES_DIR}")

    if not frames:
        print("No frames were extracted. Stop here.")
        return

    # Step 2: analyze every extracted keyframe.
    analyzer = VideoAnalyzer(
        model="qwen3-vl:4b",
        temperature=0.2,
        outdir=str(ANALYSIS_DIR),
    )

    for index, frame in enumerate(frames, start=1):
        print("\n------------------------------")
        print(f"Analyzing frame {index}/{len(frames)}")
        print(f"frame_number={frame.number}")
        print(f"timestamp={frame.timestamp:.2f}s")
        print(f"path={frame.path}")

        result = analyzer.analyze_frame(frame)

        print(f"frame_type={result.get('frame_type')}")
        print(f"teaching_activity={result.get('teaching_activity')}")
        print(f"theory_score={result.get('theory_score')}")
        print(f"hands_on_score={result.get('hands_on_score')}")
        print(f"evidence_summary={result.get('evidence_summary')}")

    print("\nFrame analysis finished.")
    print(f"Frame analyses saved to: {FRAME_ANALYSES_PATH}")

    # Step 3: aggregate all frame analyses into one course profile.
    profile = build_course_profile(
        input_path=FRAME_ANALYSES_PATH,
        output_path=COURSE_PROFILE_PATH,
        min_confidence=0.4,
    )

    print("\nCourse profile created.")
    print(f"Course profile saved to: {COURSE_PROFILE_PATH}")
    print(profile.summary)


if __name__ == "__main__":
    main()
