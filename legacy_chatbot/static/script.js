const chatBox = document.getElementById("chatBox");
const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const typingIndicator = document.getElementById("typingIndicator");

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function currentTime() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function appendMessage(text, sender) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${sender}`;
    wrapper.innerHTML = `${escapeHtml(text)}<span class="meta">${currentTime()}</span>`;
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showTyping(visible) {
    typingIndicator.classList.toggle("hidden", !visible);
    if (visible) {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

async function sendMessage(text) {
    appendMessage(text, "user");
    userInput.value = "";
    showTyping(true);

    // Small randomized delay makes the reply feel more human than an
    // instant response, without adding noticeable latency.
    const minDelay = 500;
    const start = Date.now();

    try {
        const response = await fetch("/get?msg=" + encodeURIComponent(text));
        const data = await response.json();
        const elapsed = Date.now() - start;
        const remaining = Math.max(minDelay - elapsed, 0);

        setTimeout(() => {
            showTyping(false);
            appendMessage(data.response, "bot");
        }, remaining);
    } catch (err) {
        showTyping(false);
        appendMessage("Sorry, something went wrong reaching the server.", "bot");
        console.error(err);
    }
}

chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;
    sendMessage(text);
});

// Greet the user as soon as the page loads.
window.addEventListener("DOMContentLoaded", () => {
    appendMessage("Hi! I'm your virtual assistant. Ask me about pricing, hours, or just say hello 😊", "bot");
    userInput.focus();
});
