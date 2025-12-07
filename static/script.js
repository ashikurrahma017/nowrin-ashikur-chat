const layout = document.querySelector(".whatsapp-layout");
const messagesContainer = document.getElementById("messages");
const form = document.getElementById("message-form");
const input = document.getElementById("message-input");
const searchInput = document.getElementById("user-search");
const userList = document.getElementById("user-list");

const currentUser = layout ? layout.dataset.current : null;
let activeUser = layout ? layout.dataset.active : null;

async function fetchMessages() {
    if (!activeUser || !messagesContainer) return;

    try {
        const res = await fetch(`/api/messages/${encodeURIComponent(activeUser)}`);
        if (!res.ok) return;
        const data = await res.json();
        renderMessages(data);
    } catch (err) {
        console.error("Error fetching messages", err);
    }
}

function renderMessages(list) {
    if (!messagesContainer) return;
    messagesContainer.innerHTML = "";

    list.forEach(msg => {
        const row = document.createElement("div");
        row.classList.add("message-row");
        row.classList.add(msg.sender === currentUser ? "own" : "other");

        const bubble = document.createElement("div");
        bubble.classList.add("message-bubble");

        // Only show name for the other person (useful in future group chats)
        if (msg.sender !== currentUser) {
            const u = document.createElement("div");
            u.classList.add("message-username");
            u.textContent = msg.sender;
            bubble.appendChild(u);
        }

        const textEl = document.createElement("div");
        textEl.textContent = msg.text;
        bubble.appendChild(textEl);

        const meta = document.createElement("div");
        meta.classList.add("message-meta");

        const time = document.createElement("span");
        time.textContent = msg.created_at;
        meta.appendChild(time);

        if (msg.sender === currentUser) {
            const ticks = document.createElement("span");
            ticks.textContent = "✓✓"; // fake seen ticks
            meta.appendChild(ticks);
        }

        bubble.appendChild(meta);
        row.appendChild(bubble);
        messagesContainer.appendChild(row);
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function sendMessage(text) {
    if (!activeUser) return;

    try {
        await fetch(`/api/messages/${encodeURIComponent(activeUser)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text })
        });
        await fetchMessages();
    } catch (err) {
        console.error("Error sending message", err);
    }
}

if (form && input) {
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!activeUser) return;

        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        await sendMessage(text);
    });
}

// Poll conversation every 2 seconds
if (activeUser) {
    fetchMessages();
    setInterval(fetchMessages, 2000);
}

// Simple client-side username search filter
if (searchInput && userList) {
    searchInput.addEventListener("input", () => {
        const term = searchInput.value.toLowerCase();
        const items = userList.querySelectorAll(".chat-list-item");

        items.forEach(item => {
            const nameEl = item.querySelector(".username-text");
            const name = nameEl ? nameEl.textContent.toLowerCase() : "";
            item.style.display = name.includes(term) ? "" : "none";
        });
    });
}
