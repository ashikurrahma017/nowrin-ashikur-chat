const messagesContainer = document.getElementById("messages");
const form = document.getElementById("message-form");
const input = document.getElementById("message-input");

const layoutEl = document.querySelector(".whatsapp-layout");
const currentUser = layoutEl ? layoutEl.dataset.username : null;

async function fetchMessages() {
    try {
        const res = await fetch("/messages");
        if (!res.ok) return;
        const data = await res.json();
        renderMessages(data);
    } catch (e) {
        console.error("Failed to fetch messages", e);
    }
}

function renderMessages(list) {
    if (!messagesContainer) return;

    messagesContainer.innerHTML = "";

    list.forEach(msg => {
        const row = document.createElement("div");
        row.classList.add("message-row");
        if (msg.username === currentUser) {
            row.classList.add("own");
        } else {
            row.classList.add("other");
        }

        const bubble = document.createElement("div");
        bubble.classList.add("message-bubble");

        if (msg.username !== currentUser) {
            const u = document.createElement("div");
            u.classList.add("message-username");
            u.textContent = msg.username;
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

        // Small double-tick icon imitation using Unicode
        if (msg.username === currentUser) {
            const ticks = document.createElement("span");
            ticks.textContent = "✓✓";
            meta.appendChild(ticks);
        }

        bubble.appendChild(meta);
        row.appendChild(bubble);
        messagesContainer.appendChild(row);
    });

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function sendMessage(text) {
    try {
        await fetch("/messages", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ text })
        });
        await fetchMessages();
    } catch (e) {
        console.error("Failed to send message", e);
    }
}

if (form && input) {
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        await sendMessage(text);
    });
}

// Poll every 2 seconds
fetchMessages();
setInterval(fetchMessages, 2000);
