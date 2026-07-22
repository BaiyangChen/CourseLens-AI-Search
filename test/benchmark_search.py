import json
import time
import urllib.request


API_URL = "http://127.0.0.1:8000/api/search"


TEST_CASES = [
    {
        "query": "I want a beginner-friendly tutorial where the teacher explains Python loops clearly before showing examples.",
        "expected_course": "Branching Iteration",
        "payload": {
            "theory": 1.0,
            "hands_on": None,
            "exercise": None,
            "project": None,
            "teacher_led": True,
        },
    },
    {
        "query": "I learn best by watching someone write and run code step by step, especially when they show errors and debugging.",
        "expected_course": "Hands-on Python Coding",
        "payload": {
            "theory": None,
            "hands_on": 1.0,
            "exercise": None,
            "project": None,
            "teacher_led": None,
        },
    },
    {
        "query": "I want to follow a complete tutorial that builds a small web application with frontend, backend, API calls, and a database.",
        "expected_course": "Web App Project Tutorial",
        "payload": {
            "theory": None,
            "hands_on": 1.0,
            "exercise": None,
            "project": 1.0,
            "teacher_led": None,
        },
    },
    {
        "query": "I need an introductory course that explains machine learning concepts such as training data, neural networks, and model evaluation.",
        "expected_course": "AI and Machine Learning Fundamentals",
        "payload": {
            "theory": 1.0,
            "hands_on": None,
            "exercise": None,
            "project": None,
            "teacher_led": None,
        },
    },
    {
        "query": "I want to practice Python with quizzes, coding exercises, and worked solutions instead of only listening to lectures.",
        "expected_course": "Exercise-Based Python Learning",
        "payload": {
            "theory": None,
            "hands_on": None,
            "exercise": 1.0,
            "project": None,
            "teacher_led": None,
        },
    },
]


def call_search_api(test_case):
    payload = {"query": test_case["query"], **test_case["payload"]}

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start_time = time.perf_counter()

    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    response_time = time.perf_counter() - start_time
    return data, response_time


def main():
    total_tests = len(TEST_CASES)
    successful_requests = 0
    correct_answers = 0
    response_times = []

    for test_case in TEST_CASES:
        try:
            data, response_time = call_search_api(test_case)

            top_course = data["results"][0]["course"]["title"]

            successful_requests += 1
            response_times.append(response_time)

            if top_course == test_case["expected_course"]:
                correct_answers += 1

        except Exception:
            pass

    precision = correct_answers / total_tests
    automation_rate = successful_requests / total_tests

    if response_times:
        average_response_time = sum(response_times) / len(response_times)
    else:
        average_response_time = 0.0

    print("Benchmark results")
    print("-----------------")
    print(f"Précision des réponses: {precision * 100:.1f}%")
    print(f"Temps de réponse moyen: {average_response_time:.2f} seconds")
    print(f"Taux d'automatisation: {automation_rate * 100:.1f}%")


if __name__ == "__main__":
    main()