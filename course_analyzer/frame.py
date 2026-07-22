from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
import logging

@dataclass
class Frame:
    number: int
    path: Path
    timestamp: float
    score: float
    content_score: float = 0.0

class VideoProcessor:
    FRAME_DIFFERENCE_THRESHOLD = 3.0
    CONTENT_THRESHOLD = 0.03

    def __init__(self, video_path: Path, output_dir: Path):
        self.video_path = video_path
        self.output_dir = output_dir
        self.frames: list[Frame] = []

    def _save_key_frame(self, frame: np.ndarray, number:int, timestamp: float, score:int, content_score: float):
        frame_path = self.output_dir / f"frame_{number:04d}.jpg"
        cv2.imwrite(str(frame_path), frame)
        self.frames.append(
            Frame(
                number=number,
                path = frame_path,
                timestamp=timestamp,
                score=score,
                content_score=content_score
            )
        )

    def _calculate_frame_difference(self, frame1:np.ndarray, frame2:np.ndarray):
        if frame1 is None or frame2 is None:
            return 0.0

        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(gray1, gray2)
        score = np.mean(diff)

        return float(score)
    
    def _calculate_content_score(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.mean(edges > 0)
        return float(edge_ratio)

    def extract_keyframe(self, frames_per_minute:int):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {self.video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps

        if fps <= 0:
            raise ValueError("Invalid FPS value")
        
        seconds_between_check = 60 / frames_per_minute
        sample_frames_interval = int(max(1, fps * seconds_between_check))

        previous_frame = None
        frame_count = 0

        while frame_count < total_frames:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % sample_frames_interval == 0:       
                timestamp = frame_count / fps
                content_score = self._calculate_content_score(frame)
                print(f"Frame {frame_count}: Timestamp {timestamp:.2f}s, Content Score: {content_score:.4f}")
                if previous_frame is None:
                    score = 0.0
                    self._save_key_frame(frame,frame_count,timestamp,score,content_score)
                    previous_frame = frame.copy()
                else:
                    score = self._calculate_frame_difference(previous_frame, frame)
                    content_score = self._calculate_content_score(frame)
                    should_save = (score >= VideoProcessor.FRAME_DIFFERENCE_THRESHOLD and content_score >= VideoProcessor.CONTENT_THRESHOLD)
                    if should_save:
                        self._save_key_frame(frame, frame_count, timestamp, score, content_score)
                        previous_frame = frame.copy()
                print(
                    f"Frame {frame_count}: "
                    f"timestamp={timestamp:.2f}s, "
                    f"diff_score={score:.2f}, "
                    f"content_score={content_score:.4f}"
                )
            frame_count += 1

        cap.release()
        return self.frames
