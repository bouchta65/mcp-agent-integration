const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const resetBtn = document.getElementById('resetBtn');
const setupHelpHtml = 'Your MCP inventory agent is not connected yet. Check Azure sign-in and your <code>.env</code> values, then restart the interface.';

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});
resetBtn.addEventListener('click', resetConversation);

sendBtn.addEventListener('keydown', (event) => {
    if (event.key === ' ' || event.key === 'Spacebar') {
        event.preventDefault();
        sendMessage();
    }
});

resetBtn.addEventListener('keydown', (event) => {
    if (event.key === ' ' || event.key === 'Spacebar') {
        event.preventDefault();
        resetConversation();
    }
});

function sendMessage() {
    const message = messageInput.value.trim();

    if (!message) {
        return;
    }

    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    addMessage(message, 'user');
    messageInput.value = '';
    setInputDisabled(true);

    const typingIndicator = addTypingIndicator();

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message }),
    })
        .then(async (response) => {
            const contentType = response.headers.get('content-type') || '';
            const data = contentType.includes('application/json')
                ? await response.json()
                : { error: await response.text() };

            if (!response.ok) {
                throw new Error(data.error || `Request failed with status ${response.status}`);
            }

            return data;
        })
        .then((data) => {
            typingIndicator.remove();

            if (data.error) {
                addMessage(`Error: ${data.error}`, 'agent');
            } else if (data.response_html) {
                addMessage(data.response_html, 'agent', { isHtml: true });
            } else {
                addMessage(data.response, 'agent');
            }

            setInputDisabled(false);
            messageInput.focus();
        })
        .catch(() => {
            typingIndicator.remove();
            addMessage(setupHelpHtml, 'agent', { isHtml: true });
            setInputDisabled(false);
            messageInput.focus();
        });
}

function addMessage(text, sender, options = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.setAttribute('role', 'article');
    messageDiv.setAttribute('aria-label', `${sender === 'user' ? 'User' : 'Agent'} message`);

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = sender === 'user' ? '' : 'MCP';

    const content = document.createElement('div');
    content.className = 'message-content';

    if (options.isHtml === true) {
        content.innerHTML = text;
    } else {
        content.innerHTML = renderMessageContent(text);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    setTimeout(scrollToBottom, 100);
}

function renderMessageContent(text) {
    const normalizedText = String(text || '').replace(/\r\n/g, '\n');
    const markedLib = resolveMarkedLibrary();
    const purifyLib = resolvePurifyLibrary();

    if (!markedLib || !purifyLib) {
        return renderFallbackMarkdown(normalizedText);
    }

    const renderer = new markedLib.Renderer();
    renderer.link = (hrefOrToken, title, textValue) => {
        let href = hrefOrToken;
        let linkTitle = title;
        let textContent = textValue;

        if (hrefOrToken && typeof hrefOrToken === 'object') {
            href = hrefOrToken.href;
            linkTitle = hrefOrToken.title;
            textContent = markedLib.Parser && hrefOrToken.tokens
                ? markedLib.Parser.parseInline(hrefOrToken.tokens)
                : hrefOrToken.text;
        }

        const safeHref = href || '#';
        const safeTitle = linkTitle ? ` title="${escapeHtml(linkTitle)}"` : '';
        return `<a href="${safeHref}"${safeTitle} target="_blank" rel="noopener noreferrer">${textContent}</a>`;
    };

    markedLib.setOptions({
        gfm: true,
        breaks: true,
        renderer,
    });

    const rawHtml = markedLib.parse(normalizedText);
    return purifyLib.sanitize(rawHtml, {
        USE_PROFILES: { html: true },
        ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'class'],
    });
}

function resolveMarkedLibrary() {
    if (typeof marked === 'undefined' && typeof window === 'undefined') {
        return null;
    }

    const candidate = typeof marked !== 'undefined' ? marked : window.marked;
    if (!candidate) {
        return null;
    }

    if (typeof candidate.parse === 'function') {
        return candidate;
    }

    if (typeof candidate.marked === 'function') {
        return {
            parse: candidate.marked,
            setOptions: candidate.setOptions ? candidate.setOptions.bind(candidate) : () => {},
            Renderer: candidate.Renderer,
            Parser: candidate.Parser,
        };
    }

    if (typeof candidate === 'function') {
        return {
            parse: candidate,
            setOptions: candidate.setOptions ? candidate.setOptions.bind(candidate) : () => {},
            Renderer: candidate.Renderer,
            Parser: candidate.Parser,
        };
    }

    return null;
}

function resolvePurifyLibrary() {
    if (typeof DOMPurify !== 'undefined') {
        return DOMPurify;
    }

    if (typeof window !== 'undefined') {
        if (window.DOMPurify) {
            return window.DOMPurify;
        }
        if (window.dompurify && typeof window.dompurify.sanitize === 'function') {
            return window.dompurify;
        }
    }

    return null;
}

function renderFallbackMarkdown(text) {
    let html = escapeHtml(text);

    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, _language, code) => {
        return `<pre><code>${code.trimEnd()}</code></pre>`;
    });
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    return html.replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    return text.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message agent';
    messageDiv.id = 'typing-indicator';
    messageDiv.setAttribute('role', 'status');
    messageDiv.setAttribute('aria-label', 'Agent is typing');
    messageDiv.setAttribute('aria-live', 'polite');

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = 'MCP';

    const content = document.createElement('div');
    content.className = 'message-content';

    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    indicator.innerHTML = '<span></span><span></span><span></span>';

    content.appendChild(indicator);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

function setInputDisabled(disabled) {
    messageInput.disabled = disabled;
    sendBtn.disabled = disabled;

    if (disabled) {
        sendBtn.setAttribute('aria-busy', 'true');
        messageInput.setAttribute('aria-busy', 'true');
    } else {
        sendBtn.removeAttribute('aria-busy');
        messageInput.removeAttribute('aria-busy');
    }
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function resetConversation() {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.className = 'sr-only';
    announcement.textContent = 'Conversation reset';
    document.body.appendChild(announcement);

    fetch('/reset', { method: 'POST' })
        .then((response) => response.json())
        .then(() => {
            chatMessages.innerHTML = '<div class="welcome-message" role="status"><span class="agent-mark" aria-hidden="true">MCP</span><div><strong>MCP Inventory Agent</strong> is ready to check inventory, compare weekly sales, and recommend restock or clearance actions using local MCP tools.</div></div>';
            messageInput.focus();
            setTimeout(() => announcement.remove(), 1000);
        })
        .catch(() => {
            announcement.textContent = 'Error resetting conversation';
            setTimeout(() => announcement.remove(), 1000);
        });
}

messageInput.focus();
