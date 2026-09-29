const form = document.querySelector("#question-form");

if (form) {
  const subjectInput = form.querySelector("#subject");
  const questionInput = form.querySelector("#question");
  const submitButton = form.querySelector('button[type="submit"]');
  const status = document.querySelector("#question-status");
  const history = document.querySelector("#conversation-history");
  const entries = document.querySelector("#conversation-entries");
  const historyKey = `study-buddy-conversation-${form.dataset.userId}`;
  const defaultPlaceholder = questionInput.placeholder;
  let conversation = [];

  function appendBoldText(parent, content) {
    const boldPattern = /\*\*([\s\S]+?)\*\*/g;
    let lastIndex = 0;

    for (const match of content.matchAll(boldPattern)) {
      parent.appendChild(document.createTextNode(content.slice(lastIndex, match.index)));
      const bold = document.createElement("strong");
      bold.textContent = match[1];
      parent.appendChild(bold);
      lastIndex = match.index + match[0].length;
    }

    parent.appendChild(document.createTextNode(content.slice(lastIndex)));
  }

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
    if (contentClass === "answer-content") {
      appendBoldText(text, content);
    } else {
      text.textContent = content;
    }
    block.appendChild(text);
    parent.appendChild(block);
  }

  function renderEntry(result) {
    const entry = document.createElement("article");
    entry.className = "panel answer-panel";

    const subject = document.createElement("p");
    subject.className = "conversation-subject";
    subject.textContent = result.subject;
    entry.appendChild(subject);

    appendTextBlock(entry, "Question", result.question);
    appendTextBlock(entry, "Answer", result.answer, "answer-content");
    entries.appendChild(entry);
    return entry;
  }

  function renderConversation() {
    entries.replaceChildren();
    conversation.forEach(renderEntry);
    history.hidden = conversation.length === 0;
    questionInput.placeholder = conversation.length
      ? "Ask a follow-up question..."
      : defaultPlaceholder;
  }

  try {
    const savedConversation = JSON.parse(sessionStorage.getItem(historyKey) || "[]");
    if (Array.isArray(savedConversation)) {
      conversation = savedConversation.filter((turn) =>
        turn && typeof turn.subject === "string" &&
        typeof turn.question === "string" && typeof turn.answer === "string"
      );
    }
  } catch {
    conversation = [];
  }
  if (conversation.length && [...subjectInput.options].some((option) => option.value === conversation.at(-1).subject)) {
    subjectInput.value = conversation.at(-1).subject;
  }
  renderConversation();

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

      conversation.push(result);
      renderEntry(result);
      history.hidden = false;
      questionInput.placeholder = "Ask a follow-up question...";
      try {
        sessionStorage.setItem(historyKey, JSON.stringify(conversation));
      } catch {
        // Keep the live conversation usable if browser storage is unavailable.
      }
      status.textContent = "Answer ready.";
      questionInput.value = "";
      entries.lastElementChild.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      status.textContent = error.message;
    } finally {
      submitButton.disabled = false;
    }
  });

}