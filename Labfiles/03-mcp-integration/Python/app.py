"""
Flask interface for the MCP inventory agent lab.
"""

from pathlib import Path
import re

import bleach
from flask import Flask, abort, jsonify, render_template, render_template_string, request, send_from_directory
import markdown

from mcp_agent_client import MCPInventoryAgentClient


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parents[2]
EXERCISES_DIR = ROOT_DIR / "Instructions" / "Exercises"
MEDIA_DIR = ROOT_DIR / "Instructions" / "Media"

app = Flask(
    __name__,
    template_folder=str(ROOT_DIR),
    static_folder=str(APP_DIR / "static"),
    static_url_path="/Labfiles/03-mcp-integration/Python/static",
)

AGENT_SETUP_MESSAGE = (
    "Your MCP inventory agent is not connected yet. "
    "Check Azure sign-in, PROJECT_ENDPOINT, and MODEL_DEPLOYMENT_NAME in your `.env` file, "
    "then restart this interface."
)


def _set_external_link_attributes(attrs, new=False):
    href_key = (None, "href")
    href_value = attrs.get(href_key, "")
    if isinstance(href_value, str) and href_value.startswith(("http://", "https://")):
        attrs[(None, "target")] = "_blank"
        attrs[(None, "rel")] = "noopener noreferrer nofollow"
    return attrs


def render_markdown_to_safe_html(text: str) -> str:
    raw_html = markdown.markdown(text, extensions=["extra", "sane_lists", "nl2br"])
    allowed_tags = [
        "p", "br", "hr", "blockquote",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li",
        "strong", "em", "code", "pre",
        "a",
        "table", "thead", "tbody", "tr", "th", "td",
    ]
    allowed_attrs = {
        "a": ["href", "title", "target", "rel"],
        "code": ["class"],
    }

    safe_html = bleach.clean(
        raw_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return bleach.linkify(
        safe_html,
        skip_tags=["pre", "code"],
        callbacks=[_set_external_link_attributes],
    )


def render_instruction_markdown_to_safe_html(text: str) -> str:
    text = re.sub(r"^---\s.*?---\s*", "", text, flags=re.DOTALL)
    text = text.replace(".md)", ".html)")
    text = text.replace("../Media/", "/Instructions/Media/")
    raw_html = markdown.markdown(text, extensions=["extra", "sane_lists", "nl2br"])

    allowed_tags = [
        "p", "br", "hr", "blockquote",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li",
        "strong", "em", "code", "pre",
        "a", "img",
        "table", "thead", "tbody", "tr", "th", "td",
    ]
    allowed_attrs = {
        "a": ["href", "title", "target", "rel"],
        "code": ["class"],
        "img": ["src", "alt", "title"],
    }

    return bleach.clean(
        raw_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


try:
    agent = MCPInventoryAgentClient()
except Exception as exc:
    print(f"Warning: Failed to initialize MCP inventory agent client: {exc}")
    agent = None


@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")


@app.route("/documentation.html")
def documentation():
    return render_template("documentation.html")


@app.route("/Instructions/Exercises/<path:exercise_name>.html")
def instruction_page(exercise_name):
    if Path(exercise_name).name != exercise_name:
        abort(404)

    exercise_path = EXERCISES_DIR / f"{exercise_name}.md"
    if not exercise_path.is_file():
        abort(404)

    markdown_text = exercise_path.read_text(encoding="utf-8")
    title_match = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", markdown_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Instruction page"
    content_html = render_instruction_markdown_to_safe_html(markdown_text)

    return render_template_string(
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <link rel="stylesheet" href="/static/style.css">
        </head>
        <body class="docs-body lab-doc-body">
            <header class="lab-topbar">
                <a class="lab-title-link" href="/documentation.html">
                    Extend agents with MCP tools
                </a>
                <a class="lab-home-link" href="/documentation.html">Home</a>
            </header>

            <main class="lab-shell">
                <aside id="labTocPanel" class="lab-sidebar" aria-label="Page sections">
                    <nav id="labToc" class="lab-toc"></nav>
                </aside>

                <article id="labArticle" class="docs-article lab-article">{{ content_html|safe }}</article>
            </main>
            <script>
                const article = document.getElementById('labArticle');
                const toc = document.getElementById('labToc');

                if (article && toc) {
                    const headings = [];

                    article.querySelectorAll('h2').forEach((heading) => {
                        if (!heading.id) {
                            heading.id = heading.textContent
                                .toLowerCase()
                                .trim()
                                .replace(/[^a-z0-9]+/g, '-')
                                .replace(/^-|-$/g, '');
                        }

                        const link = document.createElement('a');
                        link.href = `#${heading.id}`;
                        link.textContent = heading.textContent;
                        toc.appendChild(link);
                        headings.push({ heading, link });
                    });

                    if (headings.length) {
                        headings[0].link.classList.add('is-active');

                        const setActiveLink = (id) => {
                            headings.forEach(({ link }) => {
                                link.classList.toggle('is-active', link.getAttribute('href') === `#${id}`);
                            });
                        };

                        const observer = new IntersectionObserver((entries) => {
                            entries.forEach((entry) => {
                                if (entry.isIntersecting) {
                                    setActiveLink(entry.target.id);
                                }
                            });
                        }, {
                            rootMargin: '-18% 0px -70% 0px',
                            threshold: 0
                        });

                        headings.forEach(({ heading }) => observer.observe(heading));
                    }
                }
            </script>
        </body>
        </html>
        """,
        title=title,
        content_html=content_html,
    )


@app.route("/Instructions/Media/<path:filename>")
def instruction_media(filename):
    return send_from_directory(MEDIA_DIR, filename)


@app.route("/chat", methods=["POST"])
def chat():
    if not agent:
        response_html = render_markdown_to_safe_html(AGENT_SETUP_MESSAGE)
        return jsonify({"response": AGENT_SETUP_MESSAGE, "response_html": response_html})

    data = request.json or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    if len(user_message) > 10000:
        return jsonify({"error": "Message too long"}), 400

    try:
        response = agent.send_message(user_message)
    except RuntimeError:
        response_html = render_markdown_to_safe_html(AGENT_SETUP_MESSAGE)
        return jsonify({"response": AGENT_SETUP_MESSAGE, "response_html": response_html})

    response_html = render_markdown_to_safe_html(response)
    return jsonify({"response": response, "response_html": response_html})


@app.route("/reset", methods=["POST"])
def reset():
    if agent:
        agent.reset_conversation()
    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(debug=False, port=5001)
