import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import logging
import ollama

from course_analyzer.front_end.search_page import SEARCH_PAGE_HTML
from course_analyzer.recommender import (
    CourseRecommender,
    SearchPreference,
    load_course_profiles,
)
from typing import List
from pydantic import BaseModel, Field


HOST = "127.0.0.1"
PORT = 8000

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COURSE_PROFILE_PATH = PROJECT_ROOT / "output" / "analysis" / "course_profile.json"
PROMPT = PROJECT_ROOT / "course_analyzer" / "prompt" / "query_expansion_prompt.txt"

logger = logging.getLogger(__name__)

class QueryExpansionResult(BaseModel):
    selected_topics: List[str] = Field(
        description=(
            "Topics selected from existing_topics that are semantically relevant "
            "to the user query. Every value must exactly match one existing topic."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that the selected topics match the user query."
    )

    reason: str = Field(
        description="Short explanation of why these topics were selected."
    )

class SearchHandler(BaseHTTPRequestHandler):
    """A very small web server for the tutorial search demo."""

    def do_GET(self):
        if self.path == "/":
            self.send_html(SEARCH_PAGE_HTML)
            return

        if self.path == "/api/health":
            self.send_json({"ok": True})
            return

        self.send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        if self.path != "/api/search":
            self.send_json({"error": "Not found"}, status=404)
            return

        try:
            payload = self.read_json()

            preference = SearchPreference(
                query=payload.get("query", ""),
                theory=payload.get("theory"),
                hands_on=payload.get("hands_on"),
                exercise=payload.get("exercise"),
                project=payload.get("project"),
                teacher_led=payload.get("teacher_led"),
            )

            course_profiles = load_course_profiles(COURSE_PROFILE_PATH)
            recommender = CourseRecommender()
            existing_topics = []

            results = []

            for course_profile in course_profiles:
                for item in course_profile.get("top_topics", []) or []:
                    topic = str(item.get("topic", "")).strip()

                    if topic and topic not in existing_topics:
                        existing_topics.append(topic.lower())
            
            selected_topics = self.expand_query_with_llm(preference.query, existing_topics)

            for index, course_profile in enumerate(course_profiles):
                recommendation = recommender.recommend(
                    course_profile=course_profile,
                    preference=preference,
                    selected_topics=selected_topics
                )

                title = course_profile.get("title", f"Tutorial {index + 1}")

                results.append(
                    {
                        "course": {
                            "id": f"course_{index + 1}",
                            "title": title,
                        },
                        "course_profile": course_profile,
                        "recommendation": recommendation.model_dump(),
                    }
                )

            results.sort(
                key=lambda item: item["recommendation"]["match_score"],
                reverse=True,
            )

            best_result = results[0]

            self.send_json(
                {
                    "course": best_result["course"],
                    "course_profile": best_result["course_profile"],
                    "recommendation": best_result["recommendation"],
                    "results": results,
                }
            )

        except Exception as error:
            self.send_json({"error": str(error)}, status=400)

    def expand_query_with_llm(self, query, existing_topics):
        """Expand the user's query using a language model."""
        user_content = f"""
            User query:
            {query}

            Existing topics:
            {json.dumps(existing_topics, ensure_ascii=False, indent=2)}

            Task:
            Select the existing topics that are semantically relevant to the user query.

            Selection guidance:
            - Select direct matches.
            - Select common aliases or equivalent concepts if they appear in existing_topics.
            - Select closely related subtopics if they clearly help answer the user's query.
            - Do not select broad topics just because they share a generic word.
            - Prefer fewer high-quality topics over many weakly related topics.

            Return JSON in this exact format:
            {{
            "selected_topics": ["exact topic copied from existing_topics"],
            "confidence": 0.0,
            "reason": "short explanation"
            }}
        """
        system_prompt = PROMPT.read_text(encoding="utf-8")
        try:
            response = ollama.chat(
                model="phi4-mini:3.8b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                think=False,
                stream=False,
                format=QueryExpansionResult.model_json_schema()
            )
            parsed_content  = json.loads(response["message"]["content"])
            logger.info("Query expansion parsed response: %s", parsed_content)
            result = QueryExpansionResult.model_validate(parsed_content)
        except Exception as e:
            logger.warning("Query expansion failed: %s", {e})
            raise RuntimeError(f"Failed to expand query with LLM: {e}")
        
        return result.selected_topics
    
    def read_json(self):
        """Read JSON from the request body."""

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")

        if not body:
            return {}

        return json.loads(body)

    def send_html(self, html):
        """Send the search page."""

        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=200):
        """Send a JSON response."""

        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    """Start the search demo server."""

    if not COURSE_PROFILE_PATH.exists():
        raise FileNotFoundError(f"Course profile not found: {COURSE_PROFILE_PATH}")

    server = ThreadingHTTPServer((HOST, PORT), SearchHandler)

    print(f"Search page: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
