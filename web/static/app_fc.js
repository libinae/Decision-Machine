// 多人格决策机 - SSE 版前端逻辑
// 适配阿里云函数计算

let currentTaskId = null;
let eventSource = null;
let currentContent = '';
let waitingForAnswer = false;

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
async function startDebate() {
    const topic = topicInput.value.trim();
    if (!topic) {
        alert('请输入决策主题');
        return;
    }

    // 清空日志
    debateLog.innerHTML = '';
    resultArea.style.display = 'none';
    startBtn.disabled = true;
    statusText.textContent = '正在启动...';

    try {
        // 启动任务
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({topic: topic})
        });

        if (!res.ok) {
            throw new Error('启动失败: ' + res.statusText);
        }

        const data = await res.json();
        currentTaskId = data.task_id;
        statusText.textContent = '已连接，辩论进行中...';

        // 建立 SSE 连接
        connectSSE(currentTaskId);

    } catch (error) {
        statusText.textContent = '错误: ' + error.message;
        startBtn.disabled = false;
    }
}

// 建立 SSE 连接
function connectSSE(taskId) {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/stream/' + taskId);

    eventSource.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        } catch (e) {
            console.error('Parse error:', e);
        }
    };

    eventSource.addEventListener('qa', (event) => {
        try {
            const data = JSON.parse(event.data);
            showQAQuestion(data);
        } catch (e) {
            console.error('QA parse error:', e);
        }
    });

    eventSource.addEventListener('complete', (event) => {
        try {
            const data = JSON.parse(event.data);
            showComplete(data.winner);
        } catch (e) {
            console.error('Complete parse error:', e);
        }
        eventSource.close();
    });

    eventSource.addEventListener('error', (event) => {
        try {
            const data = JSON.parse(event.data);
            showError(data.message);
        } catch (e) {
            statusText.textContent = '连接已关闭';
        }
        eventSource.close();
    });

    eventSource.onerror = () => {
        statusText.textContent = '连接错误，尝试重连...';
        // 自动重连
        setTimeout(() => {
            if (currentTaskId) {
                connectSSE(currentTaskId);
            }
        }, 3000);
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

        case 'grouping':
            showGrouping(msg.data);
            break;

        case 'qa_intro':
            showQAIntro();
            break;

        case 'qa_question':
            showQAQuestion(msg.data);
            break;

        case 'answer_received':
            showAnswerReceived(msg.data);
            break;

        case 'speech_start':
            startSpeech(msg.data);
            break;

        case 'speech':
            showSpeech(msg.data);
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
    card.innerHTML = name;
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

    // 聚焦输入框
    document.getElementById(`answer-${data.num}`).focus();
}

// 提交回答
async function submitAnswer(num) {
    const input = document.getElementById(`answer-${num}`);
    const answer = input.value.trim() || '（未回答）';

    // 禁用输入
    input.disabled = true;
    const btn = input.nextElementSibling;
    btn.disabled = true;
    btn.textContent = '已提交';

    // 发送回答
    try {
        await fetch(`/api/answer/${currentTaskId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({num: num, answer: answer})
        });
    } catch (error) {
        console.error('Submit answer error:', error);
    }
}

// 显示回答已收到
function showAnswerReceived(data) {
    const card = document.getElementById(`qa-${data.num}`);
    if (card) {
        card.innerHTML = `
            <div class="qa-question-text">【问题${data.num}】已收到回答</div>
            <div class="qa-answer">${data.answer}</div>
        `;
    }
}

// 开始发言
function startSpeech(data) {
    currentContent = '';

    const sideClass = data.side === 'pros' ? 'pros' : data.side === 'cons' ? 'cons' : 'judge';
    const card = document.createElement('div');
    card.className = `speech-card ${sideClass}`;
    card.id = 'current-speech';
    card.innerHTML = `
        <div class="speaker-name">
            ${data.speaker}
        </div>
        <div class="speech-content" id="current-content"><span class="typing-cursor"></span></div>
    `;
    debateLog.appendChild(card);
    scrollToBottom();
}

// 显示发言
function showSpeech(data) {
    const contentDiv = document.getElementById('current-content');
    if (contentDiv) {
        currentContent = data.content;
        // 使用 Markdown 渲染
        if (typeof marked !== 'undefined') {
            contentDiv.innerHTML = marked.parse(currentContent);
        } else {
            contentDiv.textContent = currentContent;
        }
    }
    scrollToBottom();
}

// 显示裁决
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

    // 清理当前发言
    const currentSpeech = document.getElementById('current-speech');
    if (currentSpeech) {
        currentSpeech.removeAttribute('id');
    }
    const currentContentDiv = document.getElementById('current-content');
    if (currentContentDiv) {
        currentContentDiv.removeAttribute('id');
    }
}

// 显示错误
function showError(message) {
    statusText.textContent = `错误: ${message}`;
    startBtn.disabled = false;
}

// 自动滚动到底部
function scrollToBottom() {
    const lastCard = debateLog.lastElementChild;
    if (lastCard) {
        lastCard.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
}

// 下载报告
async function downloadReport() {
    if (!currentTaskId) return;

    try {
        const res = await fetch(`/api/report/${currentTaskId}`);
        const data = await res.json();

        const blob = new Blob([data.report], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `辩论报告_${new Date().toISOString().slice(0, 10)}.md`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Download report error:', error);
    }
}