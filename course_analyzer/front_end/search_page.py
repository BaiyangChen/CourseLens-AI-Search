SEARCH_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Tutorial Search</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f5f6f8;
      margin: 0;
      padding: 32px;
      color: #222;
    }

    .container {
      max-width: 820px;
      margin: 0 auto;
      background: white;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 24px;
    }

    h1 {
      margin-top: 0;
    }

    input[type="text"] {
      width: 100%;
      padding: 10px;
      font-size: 16px;
      box-sizing: border-box;
      margin-bottom: 16px;
    }

    .filters {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }

    label {
      display: flex;
      gap: 8px;
      align-items: center;
      font-size: 15px;
    }

    button {
      padding: 10px 18px;
      font-size: 15px;
      cursor: pointer;
    }

    #result {
      margin-top: 24px;
      padding-top: 18px;
      border-top: 1px solid #ddd;
    }

    .score {
      font-size: 28px;
      font-weight: bold;
      color: #1359d8;
    }

    .section {
      margin-top: 16px;
    }

    ul {
      margin-top: 6px;
    }

    .warning {
      color: #8a4b00;
    }

    .course-result {
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Tutorial Search</h1>

    <input id="query" type="text" value="python loops" placeholder="Search topic, e.g. python loops">

    <div class="filters">
      <label><input id="theory" type="checkbox" checked> Theory-heavy</label>
      <label><input id="hands_on" type="checkbox"> Hands-on coding</label>
      <label><input id="exercise" type="checkbox"> Exercises / practice</label>
      <label><input id="project" type="checkbox"> Project-based</label>
      <label><input id="teacher_led" type="checkbox" checked> Teacher-led</label>
    </div>

    <button onclick="searchTutorial()">Search</button>

    <div id="result">
      Click Search to find matching tutorials.
    </div>
  </div>

  <script>
    function checkedValue(id) {
      // If a checkbox is checked, the user wants that feature.
      // If it is unchecked, the user does not care about that feature.
      return document.getElementById(id).checked ? 1.0 : null;
    }

    function checkedBool(id) {
      return document.getElementById(id).checked ? true : null;
    }

    function listHtml(items) {
      if (!items || items.length === 0) {
        return "<li>None</li>";
      }
      return items.map(item => `<li>${item}</li>`).join("");
    }

    async function searchTutorial() {
      const payload = {
        query: document.getElementById("query").value,
        theory: checkedValue("theory"),
        hands_on: checkedValue("hands_on"),
        exercise: checkedValue("exercise"),
        project: checkedValue("project"),
        teacher_led: checkedBool("teacher_led")
      };

      const resultBox = document.getElementById("result");
      resultBox.innerHTML = "Searching...";

      try {
        const response = await fetch("/api/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
          resultBox.innerHTML = `<p>${data.error || "Search failed."}</p>`;
          return;
        }

        resultBox.innerHTML = data.results.map(renderCourseResult).join("");
      } catch (error) {
        resultBox.innerHTML = `<p>${error.message}</p>`;
      }
    }

    function renderCourseResult(item) {
      const rec = item.recommendation;
      const profile = item.course_profile;

      return `
        <div class="course-result">
          <h2>${item.course.title}</h2>
          <div class="score">${Math.round(rec.match_score * 100)}% match</div>
          <p><strong>Match level:</strong> ${rec.match_level}</p>
          <p><strong>Course style:</strong> ${profile.dominant_learning_style}</p>
          <p><strong>Summary:</strong> ${profile.summary}</p>

          <div class="section">
            <strong>Matched topics:</strong>
            <ul>${listHtml(rec.matched_topics)}</ul>
          </div>

          <div class="section">
            <strong>Reasons:</strong>
            <ul>${listHtml(rec.reasons)}</ul>
          </div>

          <div class="section warning">
            <strong>Warnings:</strong>
            <ul>${listHtml(rec.warnings)}</ul>
          </div>
        </div>
      `;
    }
  </script>
</body>
</html>
"""
