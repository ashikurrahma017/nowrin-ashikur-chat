<!DOCTYPE html> 
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nowrin & Ashikur Chat</title>
  <script src="https://cdn.socket.io/4.3.2/socket.io.min.js"></script>
  <style>
    body {
      margin: 0;
      padding: 0;
      font-family: 'Segoe UI', sans-serif;
      background: linear-gradient(to right top, #fbc2eb, #a6c1ee);
      overflow-x: hidden;
      color: #fff;
    }
    .heart {
      position: absolute;
      width: 15px;
      height: 15px;
      background: pink;
      transform: rotate(45deg);
      animation: float 10s linear infinite;
      opacity: 0.7;
      border-radius: 3px;
    }
    .heart::before,
    .heart::after {
      content: '';
      position: absolute;
      width: 15px;
      height: 15px;
      background: pink;
      border-radius: 50%;
    }
    .heart::before { top: -7.5px; left: 0; }
    .heart::after { left: -7.5px; top: 0; }
    @keyframes float {
      0% { bottom: -20px; opacity: 0; }
      50% { opacity: 1; }
      100% { bottom: 100%; transform: translateX(-50px) rotate(45deg); opacity: 0; }
    }
    .heart:nth-child(1) { left: 10%; animation-duration: 9s; }
    .heart:nth-child(2) { left: 20%; animation-duration: 12s; }
    .heart:nth-child(3) { left: 30%; animation-duration: 8s; }
    .heart:nth-child(4) { left: 50%; animation-duration: 14s; }
    .heart:nth-child(5) { left: 60%; animation-duration: 11s; }
    .heart:nth-child(6) { left: 70%; animation-duration: 10s; }
    .heart:nth-child(7) { left: 80%; animation-duration: 13s; }
    .heart:nth-child(8) { left: 90%; animation-duration: 9s; }

    #login, #chat {
      display: none;
      margin: 60px auto;
      padding: 30px;
      max-width: 400px;
      border-radius: 18px;
      background: rgba(250, 182, 212, 0.25);
      backdrop-filter: blur(12px);
      text-align: center;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    #login { display: block; }
    input, button {
      padding: 12px;
      margin: 10px 0;
      font-size: 16px;
      width: 100%;
      border-radius: 10px;
      border: none;
      color: black;
    }
    #chat-box {
      height: 350px;
      overflow-y: auto;
      padding: 10px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(10px);
      color: black;
      font-size: 15px;
    }
    .message {
      margin: 10px 0;
      padding: 10px;
      border-radius: 10px;
      clear: both;
      max-width: 70%;
      position: relative;
      word-wrap: break-word;
    }
    .me { 
      float: right; 
      background: #dcf8c6; 
      color: #000; 
    }
    .other { 
      float: left; 
      background: #eee; 
      color: #000; 
    }
    .meta {
      font-size: 12px;
      color: #666;
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 6px;
      margin-top: 6px;
    }
    .tick {
      font-size: 14px;
      color: #4caf50;
    }
    #send-container {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    #file-label {
      display: inline-block;
      background: #fff3;
      color: black;
      border-radius: 50%;
      width: 32px;
      height: 32px;
      text-align: center;
      line-height: 32px;
      font-size: 26px;
      cursor: pointer;
      user-select: none;
    }
    #file {
      display: none;
    }
    #msg {
      flex-grow: 1;
      color: black;
      border-radius: 10px;
      padding: 10px;
      font-family: monospace;
      font-size: 16px;
      border: 1px solid #ccc;
    }
    button {
      width: 70px;
      background-color: #f06292;
      color: white;
      font-weight: bold;
      cursor: pointer;
      transition: background-color 0.3s ease;
    }
    button:hover {
      background-color: #ec407a;
    }
    @media(max-width: 480px) {
      #login, #chat {
        width: 90%;
        margin: 40px auto;
        padding: 20px;
      }
      #chat-box {
        height: 250px;
      }
      #file-label {
        width: 28px;
        height: 28px;
        font-size: 22px;
        line-height: 28px;
      }
      button {
        width: 60px;
        font-size: 14px;
      }
    }
  </style>
</head>
<body>
  <div class="heart"></div><div class="heart"></div><div class="heart"></div>
  <div class="heart"></div><div class="heart"></div><div class="heart"></div>
  <div class="heart"></div><div class="heart"></div>

  <div id="login">
    <h2>Nowrin... please login</h2>
    <input id="username" placeholder="Username" autocomplete="off" />
    <input id="password" type="password" placeholder="Password" autocomplete="off" />
    <button onclick="login()">Login</button>
    <p id="login-msg" style="color: pink;"></p>
  </div>

  <div id="chat">
    <h3 id="welcome"></h3>
    <div id="chat-box"></div>
    <div id="send-container">
      <label for="file" id="file-label">+</label>
      <input type="file" id="file" accept="image/*,application/pdf" />
      <input id="msg" placeholder="Type message..." />
      <button onclick="sendMsg()">Send</button>
    </div>
  </div>

  <script>
    const socket = io();
    let currentUser = "";

    function login() {
      const u = document.getElementById("username").value.trim();
      const p = document.getElementById("password").value.trim();
      if (!u || !p) {
        document.getElementById("login-msg").innerText = "Please enter username and password.";
        return;
      }
      fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p })
      }).then(res => res.json()).then(data => {
        if (data.success) {
          currentUser = u;
          document.getElementById("login").style.display = "none";
          document.getElementById("chat").style.display = "block";
          document.getElementById("welcome").innerText = `Welcome, ${u} ❤️`;
          data.history.forEach(displayMessage);
          socket.emit("seen", { user: currentUser });
        } else {
          document.getElementById("login-msg").innerText = "Invalid login.";
        }
      });
    }

    function sendMsg() {
      const msg = document.getElementById("msg").value.trim();
      const fileInput = document.getElementById("file");
      const file = fileInput.files[0];
      const reader = new FileReader();

      if (!msg && !file) return;  // Prevent sending empty message

      if (file) {
        reader.onload = () => {
          socket.emit("message", {
            user: currentUser,
            msg,
            file: reader.result,
            filename: file.name
          });
        };
        reader.readAsDataURL(file);
      } else {
        socket.emit("message", { user: currentUser, msg });
      }

      document.getElementById("msg").value = "";
      fileInput.value = "";
    }

    function displayMessage(data) {
      const div = document.createElement("div");
      div.className = "message " + (data.user === currentUser ? "me" : "other");

      if (data.msg) div.innerHTML += `<div>${escapeHtml(data.msg)}</div>`;

      if (data.file && data.filename) {
        if (data.filename.toLowerCase().endsWith(".pdf")) {
          div.innerHTML += `<a href="${data.file}" target="_blank" rel="noopener noreferrer" style="color:#3b5998;">📄 View PDF</a>`;
        } else {
          div.innerHTML += `<img src="${data.file}" style="max-width:200px; border-radius:10px; margin-top:6px;" />`;
        }
      }

      div.innerHTML += `<div class="meta">${data.time} <span class="tick">${data.user === currentUser ? (data.seen ? '✔✔' : '✔') : ''}</span></div>`;

      document.getElementById("chat-box").appendChild(div);
      document.getElementById("chat-box").scrollTop = document.getElementById("chat-box").scrollHeight;
    }

    // Prevent XSS by escaping HTML in message
    function escapeHtml(text) {
      const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      };
      return text.replace(/[&<>"']/g, m => map[m]);
    }

    socket.on("message", (data) => {
      displayMessage(data);
      if (data.user !== currentUser) {
        socket.emit("seen", { user: currentUser });
      }
    });

    socket.on("update_seen", () => {
      const messages = document.querySelectorAll(".message.me");
      messages.forEach((div) => {
        const tick = div.querySelector(".tick");
        if (tick) tick.innerText = "✔✔";
      });
    });
  </script>
</body>
</html>
