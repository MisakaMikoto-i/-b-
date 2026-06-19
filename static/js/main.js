document.addEventListener('DOMContentLoaded', () => {
    const btnParse = document.getElementById('btn-parse');
    const btnSearch = document.getElementById('btn-search');
    const btnCollect = document.getElementById('btn-collect');
    const btnSelectAll = document.getElementById('btn-select-all');
    const urlInput = document.getElementById('playlist-url');
    const parseError = document.getElementById('parse-error');

    let currentTaskId = null;
    let currentResults = null;
    let selectAllState = true;

    btnParse.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) { showError('请输入歌单链接'); return; }

        btnParse.disabled = true;
        btnParse.textContent = '解析中...';
        hideError();

        try {
            const resp = await fetch('/parse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || '解析失败');

            currentTaskId = data.task_id;
            renderSongs(data.songs);
            document.getElementById('songs-section').style.display = '';
            document.getElementById('results-section').style.display = 'none';

            const titleInput = document.getElementById('fav-title');
            if (!titleInput.value) {
                titleInput.value = '歌单转存 ' + new Date().toLocaleDateString();
            }
        } catch (e) {
            showError(e.message);
        } finally {
            btnParse.disabled = false;
            btnParse.textContent = '解析歌单';
        }
    });

    btnSearch.addEventListener('click', async () => {
        if (!currentTaskId) return;
        btnSearch.disabled = true;
        btnSearch.textContent = '搜索中...';

        const progressSection = document.getElementById('progress-section');
        const progressBar = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        progressSection.style.display = '';
        progressBar.style.width = '0%';
        progressText.textContent = '正在搜索...';

        try {
            await fetch(`/search/${currentTaskId}`, { method: 'POST' });
        } catch (e) {
            showError('启动搜索失败: ' + e.message);
            progressSection.style.display = 'none';
            btnSearch.disabled = false;
            btnSearch.textContent = '在B站搜索匹配';
            return;
        }

        const pollInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/search/${currentTaskId}/progress`);
                const data = await resp.json();
                const p = data.progress;

                const pct = p.total > 0 ? Math.round((p.done / p.total) * 100) : 0;
                progressBar.style.width = pct + '%';
                const status = p.last_found ? '✓' : '✗';
                progressText.textContent = p.done > 0
                    ? `${status} ${p.done}/${p.total} - ${p.last_song}`
                    : '正在搜索...';

                if (data.status === 'searched') {
                    clearInterval(pollInterval);
                    const resResp = await fetch(`/search/${currentTaskId}/results`);
                    const resData = await resResp.json();
                    currentResults = resData.results;
                    renderResults(resData.results);
                    document.getElementById('results-section').style.display = '';
                    progressSection.style.display = 'none';
                    btnSearch.disabled = false;
                    btnSearch.textContent = '在B站搜索匹配';
                }
            } catch (e) {
                clearInterval(pollInterval);
                progressSection.style.display = 'none';
                btnSearch.disabled = false;
                btnSearch.textContent = '在B站搜索匹配';
                showError('查询进度失败，请重试');
            }
        }, 500);
    });

    btnSelectAll.addEventListener('click', () => {
        selectAllState = !selectAllState;
        document.querySelectorAll('.result-cb').forEach(cb => {
            cb.checked = selectAllState;
        });
        btnSelectAll.textContent = selectAllState ? '取消全选' : '全选';
    });

    btnCollect.addEventListener('click', async () => {
        if (!currentTaskId || !currentResults) return;
        const title = document.getElementById('fav-title').value.trim();
        if (!title) { alert('请输入收藏夹名称'); return; }

        const selected = [];
        document.querySelectorAll('.result-cb').forEach((cb, i) => {
            if (!cb.checked) return;
            const r = currentResults[i];
            if (!r) return;
            const manualInput = document.querySelector(`#manual-${i}`);
            const manualBvid = manualInput ? manualInput.value.trim() : '';
            if (manualBvid) {
                const m = manualBvid.match(/(BV[\w]+)/i);
                selected.push({ bvid: m ? m[1] : manualBvid, aid: 0, manual: true });
            } else if (r.match) {
                selected.push({ bvid: r.match.bvid, aid: r.match.aid });
            }
        });

        if (selected.length === 0) { alert('没有勾选可添加的视频'); return; }

        btnCollect.disabled = true;
        btnCollect.textContent = '添加中...';

        const collectProgress = document.getElementById('collect-progress');
        const collectBar = document.getElementById('collect-fill');
        const collectText = document.getElementById('collect-text');
        collectProgress.style.display = '';
        collectBar.style.width = '0%';
        collectText.textContent = '正在创建收藏夹...';

        try {
            const resp = await fetch(`/collect/${currentTaskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, selected }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || '添加失败');

            const pollCollect = setInterval(async () => {
                try {
                    const r = await fetch(`/collect/${currentTaskId}/progress`);
                    const d = await r.json();
                    const p = d.progress || {};
                    const pct = p.total > 0 ? Math.round((p.done / p.total) * 100) : 0;
                    collectBar.style.width = pct + '%';
                    collectText.textContent = `添加中 ${p.done || 0}/${p.total || 0}`;

                    if (d.status === 'done') {
                        clearInterval(pollCollect);
                        const s = d.summary;
                        const resultDiv = document.getElementById('collect-result');
                        resultDiv.style.display = '';
                        resultDiv.className = 'collect-result';
                        resultDiv.innerHTML = `
                            <strong>完成！</strong>
                            成功添加 ${s.success}/${s.total} 个视频到收藏夹。
                            <a href="https://www.bilibili.com/account/fav" target="_blank">查看我的收藏夹 →</a>
                        `;
                        collectProgress.style.display = 'none';
                        btnCollect.disabled = false;
                        btnCollect.textContent = '创建收藏夹并添加';
                    }
                } catch (e) {
                    clearInterval(pollCollect);
                    collectProgress.style.display = 'none';
                    btnCollect.disabled = false;
                    btnCollect.textContent = '创建收藏夹并添加';
                }
            }, 500);
        } catch (e) {
            collectProgress.style.display = 'none';
            btnCollect.disabled = false;
            btnCollect.textContent = '创建收藏夹并添加';
            const resultDiv = document.getElementById('collect-result');
            resultDiv.style.display = '';
            resultDiv.className = 'collect-result error';
            resultDiv.textContent = '失败: ' + e.message;
        }
    });

    function renderSongs(songs) {
        const list = document.getElementById('songs-list');
        document.getElementById('song-count').textContent = `(${songs.length}首)`;
        list.innerHTML = songs.map((s, i) => `
            <div class="song-item">
                <span class="idx">${i + 1}</span>
                <span class="song-name">${esc(s.name)}</span>
                <span class="song-artist">${esc(s.artist)}</span>
            </div>
        `).join('');
    }

    function renderResults(results) {
        const list = document.getElementById('results-list');
        list.innerHTML = results.map((r, i) => {
            const s = r.song;
            const m = r.match;
            const candidates = r.candidates || [];
            const checked = m && m.score >= 15 ? 'checked' : '';
            const status = !m ? 'none' : m.score >= 15 ? 'ok' : 'low';
            const switchBtn = candidates.length > 1 ? `<button class="btn-switch" onclick="switchCandidate(${i})">换一个 (${candidates.length})</button>` : '';
            let matchHtml;
            if (m) {
                const badge = m.hires ? '<span class="badge badge-hires">Hi-Res</span>' :
                              m.score >= 15 ? '<span class="badge badge-ok">匹配</span>' :
                              '<span class="badge badge-warn">低置信</span>';
                const retryBtn = m.score < 15 ? `<button class="btn-retry" onclick="retrySearch(${i})">重新搜索</button>` : '';
                matchHtml = `
                    <div class="match-found">
                        ${badge}
                        <a class="bvid" href="https://www.bilibili.com/video/${m.bvid}" target="_blank">${m.bvid}</a>
                        <span class="title" title="${esc(m.title)}">${esc(m.title)}</span>
                        ${switchBtn}
                        ${retryBtn}
                    </div>
                    <div class="manual-input">
                        <input type="text" id="manual-${i}" placeholder="手动替换BV号(可选)">
                        <button class="btn-verify" onclick="verifyBvid(${i})">验证</button>
                    </div>
                `;
            } else {
                matchHtml = `
                    <div class="match-not-found">未找到匹配视频</div>
                    <div class="manual-input">
                        <input type="text" id="manual-${i}" placeholder="手动输入BV号">
                        <button class="btn-verify" onclick="verifyBvid(${i})">验证</button>
                        <button class="btn-retry" onclick="retrySearch(${i})">重新搜索</button>
                    </div>
                `;
            }
            return `
                <div class="result-item" id="result-${i}" data-status="${status}">
                    <input type="checkbox" class="result-cb" ${checked}>
                    <div class="result-source">
                        <span class="result-idx">${i + 1}</span>
                        <div>
                            <div class="song-label">${esc(s.name)}</div>
                            <div class="artist-label">${esc(s.artist)}</div>
                        </div>
                    </div>
                    <div class="result-match">${matchHtml}</div>
                </div>
            `;
        }).join('');

        updateFilterCounts(results);
        applyFilter('all');
    }

    function updateFilterCounts(results) {
        let all = 0, none = 0, low = 0, ok = 0;
        results.forEach(r => {
            all++;
            if (!r.match) none++;
            else if (r.match.score >= 15) ok++;
            else low++;
        });
        document.getElementById('filter-all-count').textContent = all;
        document.getElementById('filter-none-count').textContent = none;
        document.getElementById('filter-low-count').textContent = low;
        document.getElementById('filter-ok-count').textContent = ok;
        document.getElementById('filter-problem-count').textContent = none + low;
    }

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyFilter(btn.dataset.filter);
        });
    });

    function applyFilter(filter) {
        document.querySelectorAll('.result-item').forEach(item => {
            const status = item.dataset.status;
            if (filter === 'all') {
                item.style.display = '';
            } else if (filter === 'none') {
                item.style.display = status === 'none' ? '' : 'none';
            } else if (filter === 'low') {
                item.style.display = status === 'low' ? '' : 'none';
            } else if (filter === 'ok') {
                item.style.display = status === 'ok' ? '' : 'none';
            } else if (filter === 'problem') {
                item.style.display = (status === 'none' || status === 'low') ? '' : 'none';
            }
        });
    }

    window.retrySearch = async function(idx) {
        const keyword = prompt('请输入搜索关键词：');
        if (!keyword) return;

        try {
            const resp = await fetch(`/search/${currentTaskId}/retry`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: idx, keyword }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || '重搜失败');

            if (data.match) {
                currentResults[idx].match = data.match;
            } else {
                currentResults[idx].match = null;
            }
            renderResults(currentResults);
        } catch (e) {
            alert('重新搜索失败: ' + e.message);
        }
    };

    window.verifyBvid = async function(idx) {
        const input = document.querySelector(`#manual-${idx}`);
        const bvid = input.value.trim();
        if (!bvid) { alert('请输入BV号'); return; }

        try {
            const resp = await fetch('/verify_bvid', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bvid }),
            });
            const data = await resp.json();
            if (data.valid) {
                alert(`验证成功！\n标题：${data.title}\nUP主：${data.author}`);
            } else {
                alert('无效BV号: ' + (data.error || '未知错误'));
            }
        } catch (e) {
            alert('验证失败: ' + e.message);
        }
    };

    window.switchCandidate = async function(idx) {
        const candidates = currentResults[idx]?.candidates || [];
        if (candidates.length <= 1) return;

        const items = candidates.map((c, ci) =>
            `${ci + 1}. [${c.bvid}] score=${c.score} ${c.hires ? 'Hi-Res' : ''} ${c.title}`
        ).join('\n');
        const choice = prompt(`选择候选 (1-${candidates.length})：\n${items}`);
        if (!choice) return;

        const ci = parseInt(choice) - 1;
        if (isNaN(ci) || ci < 0 || ci >= candidates.length) return;

        try {
            const resp = await fetch(`/search/${currentTaskId}/switch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: idx, candidate_index: ci }),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || '切换失败');
            currentResults[idx].match = data.match;
            renderResults(currentResults);
        } catch (e) {
            alert('切换失败: ' + e.message);
        }
    };

    function showError(msg) {
        parseError.textContent = msg;
        parseError.style.display = '';
    }

    function hideError() {
        parseError.style.display = 'none';
    }

    function esc(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }
});
