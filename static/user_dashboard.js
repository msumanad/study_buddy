const form = document.querySelector("#question-form");

if (form) {
  const questionInput = form.querySelector("#question");
  const submitButton = form.querySelector('button[type="submit"]');
  const status = document.querySelector("#question-status");
  const history = document.querySelector("#conversation-history");
  const entries = document.querySelector("#conversation-entries");
  const askMoreButton = document.querySelector("#ask-more");

  function appendTextBlock(parent, headingText, content, contentClass = "") {
    const block = document.createElement("div");
    block.className = "qa-block";

    const heading = document.createElement("h4");
    heading.textContent = headingText;
    block.appendChild(heading);

    const text = document.createElement(contentClass ? "div" : "p");
    if (contentClass) {
      text.className = contentClass;
    }
    text.textContent = content;
    block.appendChild(text);
    parent.appendChild(block);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.textContent = "Generating answer...";
    submitButton.disabled = true;

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
      });

      if (response.redirected) {
        window.location.assign(response.url);
        return;
      }

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Unable to answer right now.");
      }

      const entry = document.createElement("article");
      entry.className = "panel answer-panel";

      const subject = document.createElement("p");
      subject.className = "conversation-subject";
      subject.textContent = result.subject;
      entry.appendChild(subject);

      appendTextBlock(entry, "Question", result.question);
      appendTextBlock(entry, "Answer", result.answer, "answer-content");
      entries.appendChild(entry);

      history.hidden = false;
      askMoreButton.hidden = false;
      status.textContent = "Answer ready.";
      questionInput.value = "";
      askMoreButton.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      status.textContent = error.message;
    } finally {
      submitButton.disabled = false;
    }
  });

  askMoreButton.addEventListener("click", () => {
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    questionInput.focus({ preventScroll: true });
  });
}