// 多人格决策机 - 前端逻辑

let ws = null;
let currentSpeaker = null;
let currentContent = '';
let isStreaming = false;

// DOM 元素
const topicInput = document.getElementById('topic-input');
const startBtn = document.getElementById('start-btn');
const statusText = document.getElementById('status-text');
const debateLog = document.getElementById('debate-log');
const resultArea = document.getElementById('result-area');
const winnerDisplay = document.getElementById('winner-display');
const downloadBtn = document.getElementById('download-btn');

// 初始化
startBtn.addEventListener('click', startDebate);
downloadBtn.addEventListener('click', downloadReport);

// 开始辩论
function startDebate() {
    const topic = topicInput.value.trim();
    if (!topic) {
        alert('请输入决策主题');
        return;
    }

    // 清空日志
    debateLog.innerHTML = '';
    resultArea.style.display = 'none';
    startBtn.disabled = true;
    statusText.textContent = '正在连接...';

    // 建立 WebSocket 连接
    const wsUrl = `ws://${location.host}/ws/debate`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        statusText.textContent = '已连接，开始辩论...';
        ws.send(JSON.stringify({ type: 'start', topic: topic }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onerror = (error) => {
        statusText.textContent = '连接错误';
        console.error('WebSocket error:', error);
        startBtn.disabled = false;
    };

    ws.onclose = () => {
        statusText.textContent = '连接已关闭';
        startBtn.disabled = false;
    };
}

// 处理消息
function handleMessage(msg) {
    switch (msg.type) {
        case 'header':
            showHeader(msg.data.topic);
            break;

        case 'persona_init':
            showPersonaInit(msg.data);
            break;

        case 'phase':
            showPhase(msg.data.name);
            break;

        case 'analysis_start':
            showAnalysisStart(msg.data);
            break;

        case 'analysis_end':
            break;

        case 'grouping':
            showGrouping(msg.data);
            break;

        case 'qa_intro':
            showQAIntro();
            break;

        case 'qa_question':
            showQAQuestion(msg.data);
            break;

        case 'speech_start':
            startSpeech(msg.data);
            break;

        case 'speech':
            showSpeech(msg.data);
            break;

        case 'speech_chunk':
            appendSpeechChunk(msg.data.text);
            break;

        case 'speech_end':
            endSpeech();
            break;

        case 'ruling':
            showRuling(msg.data.content);
            break;

        case 'winner':
            showWinner(msg.data.winner);
            break;

        case 'complete':
            showComplete(msg.data.winner);
            break;

        case 'error':
            showError(msg.data.message);
            break;

        case 'report':
            downloadReportContent(msg.data.content);
            break;
    }
}

// 显示标题
function showHeader(topic) {
    const card = document.createElement('div');
    card.className = 'phase-divider';
    card.innerHTML = `<h2>🎯 决策主题：${topic}</h2>`;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示人格初始化
function showPersonaInit(data) {
    const status = data.success ? '✓' : '✗';
    const cls = data.success ? 'success' : 'fail';
    const card = document.createElement('div');
    card.className = `persona-init ${cls}`;
    card.innerHTML = `${data.icon} ${data.name} ${status}`;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示阶段
function showPhase(name) {
    const card = document.createElement('div');
    card.className = 'phase-divider';
    card.innerHTML = `📋 ${name}`;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示分组结果
function showGrouping(data) {
    const card = document.createElement('div');
    card.className = 'grouping-card';
    card.innerHTML = `
        <h3>分组结果</h3>
        <div class="team-list">
            <div class="team-item">
                <h4>正方：${data.pros_position}</h4>
                <div class="debater-item">${data.pros_team.first.icon} 一辩：${data.pros_team.first.name}</div>
                <div class="debater-item">${data.pros_team.second.icon} 二辩：${data.pros_team.second.name}</div>
            </div>
            <div class="team-item">
                <h4>反方：${data.cons_position}</h4>
                <div class="debater-item">${data.cons_team.first.icon} 一辩：${data.cons_team.first.name}</div>
                <div class="debater-item">${data.cons_team.second.icon} 二辩：${data.cons_team.second.name}</div>
            </div>
        </div>
        <div class="judge-info">⚖️ 裁判：${data.judge.name}</div>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示问答介绍
function showQAIntro() {
    const card = document.createElement('div');
    card.className = 'phase-divider';
    card.innerHTML = '为帮助辩手理解你的情况，请回答以下问题';
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示问题并等待回答
function showQAQuestion(data) {
    const card = document.createElement('div');
    card.className = 'qa-question';
    card.id = `qa-${data.num}`;
    card.innerHTML = `
        <div class="qa-question-text">【问题${data.num}】${data.question}</div>
        <input type="text" class="qa-answer-input" id="answer-${data.num}" placeholder="输入回答（可跳过）">
        <button class="qa-submit-btn" onclick="submitAnswer(${data.num})">提交</button>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 提交回答
function submitAnswer(num) {
    const input = document.getElementById(`answer-${num}`);
    const answer = input.value.trim() || '（未回答）';

    // 禁用输入
    input.disabled = true;
    const btn = input.nextElementSibling;
    btn.disabled = true;
    btn.textContent = '已提交';

    // 发送回答
    ws.send(JSON.stringify({ type: 'qa_answer', answer: answer }));
}

// 显示发言（Markdown 渲染）
function showSpeech(data) {
    const renderedContent = typeof marked !== 'undefined' ? marked.parse(data.content) : data.content;
    const sideClass = data.side === 'pros' ? 'pros' : data.side === 'cons' ? 'cons' : 'judge';
    const card = document.createElement('div');
    card.className = `speech-card ${sideClass}`;
    card.id = `speech-${Date.now()}`;
    card.innerHTML = `
        <div class="speaker-name">
            ${getSpeakerIcon(data.side)}${data.speaker}
        </div>
        <div class="speech-content">${renderedContent}</div>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 获取发言者图标（不再显示正反方符号，已通过左右布局区分）
function getSpeakerIcon(side) {
    return '';
}

// 显示分析开始（综合人格分析辩题）
function showAnalysisStart(data) {
    const card = document.createElement('div');
    card.className = 'speech-card judge';
    card.id = 'current-speech';
    card.innerHTML = `
        <div class="speaker-name">
            ${data.icon} ${data.name} 分析辩题...
        </div>
        <div class="speech-content" id="current-content"></div>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 开始流式发言（新消息）
function startSpeech(data) {
    currentContent = '';
    isStreaming = true;

    const sideClass = data.side === 'pros' ? 'pros' : data.side === 'cons' ? 'cons' : 'judge';
    const card = document.createElement('div');
    card.className = `speech-card ${sideClass}`;
    card.id = 'current-speech';
    card.innerHTML = `
        <div class="speaker-name">
            ${getSpeakerIcon(data.side)}${data.speaker}
        </div>
        <div class="speech-content" id="current-content"></div>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 开始流式发言（旧函数，保留兼容）
function startStreamingSpeech(speaker, side) {
    startSpeech({ speaker: speaker, side: side });
}

// 追加文本片段（流式输出 + 自动滚动 + Markdown）
function appendSpeechChunk(text) {
    currentContent += text;
    const contentDiv = document.getElementById('current-content');
    if (contentDiv) {
        // 使用 Markdown 渲染
        if (typeof marked !== 'undefined') {
            contentDiv.innerHTML = marked.parse(currentContent);
        } else {
            contentDiv.textContent = currentContent;
        }
        // 自动滚动到底部
        scrollToBottom();
    }
}

// 结束发言（最终渲染）
function endSpeech() {
    isStreaming = false;
    const card = document.getElementById('current-speech');
    if (card) {
        card.removeAttribute('id');
    }
    const contentDiv = document.getElementById('current-content');
    if (contentDiv) {
        // 最终 Markdown 渲染
        if (typeof marked !== 'undefined') {
            contentDiv.innerHTML = marked.parse(currentContent);
        }
        contentDiv.removeAttribute('id');
    }
    scrollToBottom();
}

// 自动滚动到底部（滚动整个页面）
function scrollToBottom() {
    // 滚动到最新的元素
    const lastCard = debateLog.lastElementChild;
    if (lastCard) {
        lastCard.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
}

// 显示裁决（Markdown 渲染）
function showRuling(content) {
    const renderedContent = typeof marked !== 'undefined' ? marked.parse(content) : content;
    const card = document.createElement('div');
    card.className = 'speech-card judge';
    card.innerHTML = `
        <div class="speaker-name">
            ⚖️ 裁判总结
        </div>
        <div class="speech-content">${renderedContent}</div>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示胜方
function showWinner(winner) {
    let text, cls;
    if (winner === 'pros') {
        text = '🏆 正方胜出！';
        cls = 'pros-win';
    } else if (winner === 'cons') {
        text = '🏆 反方胜出！';
        cls = 'cons-win';
    } else {
        text = '🤝 平局！';
        cls = 'draw';
    }

    winnerDisplay.textContent = text;
    winnerDisplay.className = `winner-display ${cls}`;
}

// 显示完成
function showComplete(winner) {
    showWinner(winner);
    resultArea.style.display = 'block';
    statusText.textContent = '辩论完成';
    startBtn.disabled = false;
}

// 显示错误
function showError(message) {
    statusText.textContent = `错误: ${message}`;
    startBtn.disabled = false;
}

// 下载报告
function downloadReport() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'download' }));
    }
}

// 下载报告内容
function downloadReportContent(content) {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `辩论报告_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
}