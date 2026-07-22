# CourseLens AI Search

This project is a prototype for analyzing educational videos and recommending tutorials based on course profiles and student search preferences.

## Main Features

- Extract keyframes from educational videos
- Analyze keyframes with a local vision-language model
- Generate course profiles
- Expand natural language queries into existing course topics
- Recommend tutorials with explainable match scores

## Run Search Demo

```bash
python -m course_analyzer.front_end.search_api
```

## Open
http://127.0.0.1:8000

## Run Benchmark
python tests/benchmark_search.py
