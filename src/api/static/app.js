import WaveSurfer from 'https://unpkg.com/wavesurfer.js@7.7.3/dist/wavesurfer.esm.js';

/* ── Music Digger Dashboard ─────────────────────────── */

const STEMS = [
    { key: 'drums',   label: 'Drums',   wave: '#F43F5E', progress: '#9F1239' },
    { key: 'bass',    label: 'Bass',    wave: '#10B981', progress: '#047857' },
    { key: 'subbass', label: 'Sub Bass', wave: '#6366F1', progress: '#4338CA' },
    { key: 'other',   label: 'Other',   wave: '#EAB308', progress: '#A16207' },
];

const App = {
    tracks: [],
    currentTrackId: null,
    players: [],   // WaveSurfer instances
    isPlaying: false,
    isSeeking: false,  // guard for sync seek loops
    logInterval: null,
    genreLabels: [],

    /* ── Bootstrap ────────────────────────────────────── */
    async init() {
        this.bindNav();
        await this.loadSettings();
        this.bindButtons();
        this.renderLabelingButtons();
        await this.loadTracks();
        console.log('[Music Digger] init OK – tracks:', this.tracks.length);
    },

    bindNav() {
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const target = btn.getAttribute('data-target');
                document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
                document.getElementById(target).classList.add('active');
            });
        });
    },

    bindButtons() {
        // Run Benchmark Test
        const benchBtn = document.getElementById('btn-run-benchmark');
        if (benchBtn) benchBtn.addEventListener('click', () => {
            document.getElementById('benchmark-modal').style.display = 'flex';
            this.loadBenchmarkResults();
        });

        const closeBenchBtn = document.getElementById('btn-close-benchmark');
        if (closeBenchBtn) closeBenchBtn.addEventListener('click', () => {
            document.getElementById('benchmark-modal').style.display = 'none';
        });

        // Run AI Inference (no retraining)
        const predictBtn = document.getElementById('btn-predict-model');
        if (predictBtn) predictBtn.addEventListener('click', () => this.runInferenceOnly());

        // Train model
        const trainBtn = document.getElementById('btn-train-model');
        if (trainBtn) trainBtn.addEventListener('click', () => this.trainModel());

        // Play/pause
        const playBtn = document.getElementById('play-btn');
        if (playBtn) playBtn.addEventListener('click', () => this.togglePlayPause());

        // Pipeline
        const pipelineBtn = document.getElementById('btn-pipeline');
        if (pipelineBtn) pipelineBtn.addEventListener('click', () => this.startPipeline());
    },

    /* ── Data ─────────────────────────────────────────── */
    async loadSettings() {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            this.genreLabels = data.genre_labels || [];
        } catch (e) {
            console.error('loadSettings failed', e);
            this.genreLabels = ['tearout', 'riddim']; // fallback
        }
    },

    async loadTracks() {
        try {
            const res = await fetch('/api/tracks');
            this.tracks = await res.json();
            this.renderTable();
        } catch (e) {
            console.error('loadTracks failed', e);
        }
    },

    renderTable() {
        const tbody = document.getElementById('track-list-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        this.tracks.forEach(t => {
            const tr = document.createElement('tr');

            const status = t.separated_at
                ? '<span class="label-badge badge-neutral">Separated</span>'
                : `<span class="label-badge badge-neutral">${t.status || 'unknown'}</span>`;

            const GENRE_COLORS = {
                heavy_dubstep:    '#ef4444',
                color_bass:       '#ec4899',
                riddim:           '#f97316',
                briddim:          '#eab308',
                bass_house:       '#10b981',
                future_bass:      '#06b6d4',
                melodic_dubstep:  '#3b82f6',
                progressive_house:'#6366f1',
                drum_and_bass:    '#8b5cf6',
                trap:             '#a855f7',
            };

            let aiHtml = '-';
            if (t.ai_probabilities && Object.keys(t.ai_probabilities).length > 0) {
                const sorted = Object.entries(t.ai_probabilities)
                    .map(([g, p]) => ({ genre: g, pct: Math.round(p * 100) }))
                    .filter(item => item.pct > 0)
                    .sort((a, b) => b.pct - a.pct);
                
                if (sorted.length > 0) {
                    const topItem = sorted[0];
                    const topColor = GENRE_COLORS[topItem.genre] || '#7c5cfc';
                    
                    const barSegments = sorted.map(item => {
                        const color = GENRE_COLORS[item.genre] || '#7c5cfc';
                        return `<div style="width:${item.pct}%;height:100%;background-color:${color};" title="${item.genre.toUpperCase()}: ${item.pct}%"></div>`;
                    }).join('');
                    
                    aiHtml = `
                        <div style="display:flex;flex-direction:column;gap:4px;width:120px;">
                            <div style="font-size:0.75rem;font-weight:700;color:${topColor};display:flex;justify-content:space-between;">
                                <span>${topItem.genre.toUpperCase()}</span>
                                <span>${topItem.pct}%</span>
                            </div>
                            <div style="display:flex;width:100%;height:6px;background:rgba(255,255,255,0.07);border-radius:4px;overflow:hidden;">
                                ${barSegments}
                            </div>
                        </div>
                    `;
                }
            } else if (t.ai_label && t.ai_confidence != null) {
                const pct = Math.round(t.ai_confidence * 100);
                const isTarget = this.genreLabels[0] && t.ai_label.toLowerCase() === this.genreLabels[0].toLowerCase();
                const cls = isTarget ? 'badge-tearout' : 'badge-riddim';
                aiHtml = `<span class="label-badge ${cls}">${t.ai_label.toUpperCase()} ${pct}%</span>`;
            }

            let humanHtml = '';
            const currentHuman = (t.human_label || '').toLowerCase();
            const options = [
                { val: '', label: '— 未ラベル —' },
                ...this.genreLabels.map(g => ({ val: g.toLowerCase(), label: g.toUpperCase() }))
            ].map(opt => `<option value="${opt.val}" ${opt.val === currentHuman ? 'selected' : ''}>${opt.label}</option>`).join('');

            humanHtml = `
                <select class="genre-select" data-id="${t.track_id}" style="background:#1e293b; color:#fff; border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:6px 10px; font-weight:600; font-size:0.85rem; cursor:pointer;">
                    ${options}
                </select>
            `;

            const trackTitle = t.title || 'Unknown Title';
            const trackArtist = t.artist || 'Unknown Artist';
            const sourceLink = t.source_url
                ? `<a href="${t.source_url}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;font-weight:600;">↗ SoundCloud</a>`
                : (t.source || '-');

            const isPlayingThis = this.currentTrackId === t.track_id && this.isPlaying;

            tr.innerHTML = `
                <td>
                    <div style="font-weight:600;color:#fff;font-size:0.95rem;">${trackTitle}</div>
                    <div style="font-size:0.8rem;color:var(--muted);margin-top:2px;">
                        👤 ${trackArtist} &nbsp;|&nbsp; <span style="font-family:monospace;opacity:0.7;">ID: ${t.track_id}</span>
                    </div>
                </td>
                <td>${sourceLink}</td>
                <td>${status}</td>
                <td>${aiHtml}</td>
                <td>${humanHtml}</td>
                <td style="text-align: right; white-space: nowrap;">
                    <button class="btn-action btn-play-stems" data-id="${t.track_id}" style="margin-right: 6px; background: rgba(99, 102, 241, 0.2); border-color: rgba(99, 102, 241, 0.4);">
                        ${isPlayingThis ? '⏸ Pause' : '▶ Play Stems'}
                    </button>
                    <button class="btn-action btn-skip-track" data-id="${t.track_id}" style="background: rgba(244, 63, 94, 0.15); color: #f43f5e; border-color: rgba(244, 63, 94, 0.3);">
                        ⏭ Skip
                    </button>
                </td>
            `;

            // Select change handler
            const selectEl = tr.querySelector('.genre-select');
            selectEl.addEventListener('change', (e) => {
                const val = e.target.value;
                if (val) {
                    this.updateTrackLabelDirect(t.track_id, val);
                }
            });

            // Play Stems handler
            tr.querySelector('.btn-play-stems').addEventListener('click', () => {
                this.loadTrackForDashboardPlayer(t.track_id);
            });

            // Skip Track handler
            tr.querySelector('.btn-skip-track').addEventListener('click', () => {
                this.skipTrackFromDashboard(t.track_id);
            });

            tbody.appendChild(tr);
        });
    },

    async updateTrackLabelDirect(trackId, label) {
        try {
            const res = await fetch(`/api/tracks/${trackId}/label`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label }),
            });
            if (res.ok) {
                await this.loadTracks();
            } else {
                alert('Failed to update label.');
            }
        } catch (e) {
            console.error(e);
            alert('Network error.');
        }
    },

    async skipTrackFromDashboard(trackId) {
        if (!confirm('このトラックを削除/スキップしますか？')) return;
        try {
            const res = await fetch(`/api/labeling/skip/${trackId}`, { method: 'POST' });
            if (res.ok) {
                if (this.currentTrackId === trackId) {
                    this.destroyPlayers();
                    document.getElementById('dashboard-player-panel').style.display = 'none';
                }
                await this.loadTracks();
            } else {
                alert('スキップに失敗しました。');
            }
        } catch (e) {
            console.error(e);
            alert('通信エラー');
        }
    },

    loadTrackForDashboardPlayer(trackId) {
        const playerPanel = document.getElementById('dashboard-player-panel');
        playerPanel.style.display = 'block';

        if (this.currentTrackId === trackId && this.players.length > 0) {
            this.togglePlayPause();
            return;
        }

        this.currentTrackId = trackId;
        const track = this.tracks.find(t => t.track_id === trackId);
        const heading = track && track.title ? `${track.artist || 'Unknown'} - ${track.title}` : trackId;
        document.getElementById('dash-player-title').textContent = heading;

        const aiBadge = document.getElementById('dash-player-ai-badge');
        if (track && track.ai_probabilities && Object.keys(track.ai_probabilities).length > 0) {
            const topGenre = Object.entries(track.ai_probabilities).sort((a, b) => b[1] - a[1])[0];
            aiBadge.textContent = `AI: ${topGenre[0].toUpperCase()} (${Math.round(topGenre[1] * 100)}%)`;
            aiBadge.className = 'label-badge badge-tearout';
        } else {
            aiBadge.textContent = 'AI: Unclassified';
            aiBadge.className = 'label-badge badge-neutral';
        }

        this.initDashboardWaveforms(trackId);
    },

    initDashboardWaveforms(trackId) {
        this.destroyPlayers();

        const container = document.getElementById('dash-waveform-container');
        container.innerHTML = '';

        STEMS.forEach(stem => {
            const row = document.createElement('div');
            row.className = 'stem-row';

            const label = document.createElement('div');
            label.className = 'stem-label';
            label.textContent = stem.label;
            label.style.color = stem.wave;
            row.appendChild(label);

            const waveDiv = document.createElement('div');
            waveDiv.className = 'stem-wave';
            row.appendChild(waveDiv);

            container.appendChild(row);

            const ws = WaveSurfer.create({
                container: waveDiv,
                waveColor: stem.wave,
                progressColor: stem.progress,
                height: 48,
                barWidth: 2,
                barGap: 1,
                barRadius: 2,
                cursorColor: '#fff',
                cursorWidth: 1,
                url: `/api/audio/${trackId}/${stem.key}`,
            });

            this.players.push(ws);
        });

        // Sync seeking across stem waveforms
        this.players.forEach((ws, i) => {
            ws.on('seeking', (currentTime) => {
                if (this.isSeeking) return;
                this.isSeeking = true;
                this.players.forEach((other, j) => {
                    if (j !== i) other.setTime(currentTime);
                });
                this.isSeeking = false;
            });
        });

        const playBtn = document.getElementById('dash-play-btn');
        if (playBtn) {
            playBtn.textContent = '▶ Play All Stems';
            playBtn.onclick = () => this.togglePlayPause();
        }

        this.isPlaying = false;
    },

    /* ── Labeling ─────────────────────────────────────── */
    loadTrackForLabeling(trackId) {
        this.currentTrackId = trackId;
        const track = this.tracks.find(t => t.track_id === trackId);

        const heading = track && track.title ? `${track.artist || 'Unknown'} - ${track.title}` : trackId;
        document.getElementById('current-track-id').textContent = heading;

        const aiBadge = document.getElementById('current-ai-label');
        if (track && track.ai_label) {
            const pct = Math.round((track.ai_confidence || 0) * 100);
            aiBadge.textContent = `AI: ${track.ai_label.toUpperCase()} (${pct}%)`;
            const isTarget = this.genreLabels[0] && track.ai_label.toLowerCase() === this.genreLabels[0].toLowerCase();
            aiBadge.className = 'label-badge ' + (isTarget ? 'badge-tearout' : 'badge-riddim');
        } else {
            aiBadge.textContent = 'AI: Not classified yet';
            aiBadge.className = 'label-badge badge-neutral';
        }

        // Switch to labeling tab
        document.querySelector('[data-target="labeling"]').click();
        this.initWaveforms(trackId);
    },

    /* ── Waveform (4 × synced WaveSurfer) ─────────────── */
    initWaveforms(trackId) {
        this.destroyPlayers();

        const container = document.getElementById('waveform-container');
        container.innerHTML = '';

        STEMS.forEach(stem => {
            // Row wrapper
            const row = document.createElement('div');
            row.className = 'stem-row';

            // Label
            const label = document.createElement('div');
            label.className = 'stem-label';
            label.textContent = stem.label;
            label.style.color = stem.wave;
            row.appendChild(label);

            // Waveform target
            const waveDiv = document.createElement('div');
            waveDiv.className = 'stem-wave';
            row.appendChild(waveDiv);

            container.appendChild(row);

            // Create WaveSurfer (no deprecated 'backend' option)
            const ws = WaveSurfer.create({
                container: waveDiv,
                waveColor: stem.wave,
                progressColor: stem.progress,
                height: 64,
                barWidth: 2,
                barGap: 1,
                barRadius: 2,
                cursorColor: '#fff',
                cursorWidth: 1,
                url: `/api/audio/${trackId}/${stem.key}`,
            });

            this.players.push(ws);
        });

        // Sync seeking: when user seeks on one waveform, update all others
        this.players.forEach((ws, i) => {
            ws.on('seeking', (currentTime) => {
                if (this.isSeeking) return;
                this.isSeeking = true;
                this.players.forEach((other, j) => {
                    if (j !== i) other.setTime(currentTime);
                });
                this.isSeeking = false;
            });
        });

        const playBtn = document.getElementById('play-btn');
        if (playBtn) playBtn.textContent = '▶ Play';
        this.isPlaying = false;
    },

    destroyPlayers() {
        this.players.forEach(ws => { try { ws.destroy(); } catch (_) {} });
        this.players = [];
    },

    togglePlayPause() {
        if (this.players.length === 0) return;
        if (this.isPlaying) {
            this.players.forEach(ws => ws.pause());
            this.isPlaying = false;
            document.getElementById('play-btn').textContent = '▶ Play';
        } else {
            this.players.forEach(ws => ws.play());
            this.isPlaying = true;
            document.getElementById('play-btn').textContent = '⏸ Pause';
        }
    },

    /* ── Label Submit & Fast Labeling ─────────────────── */
    renderLabelingButtons() {
        const container = document.getElementById('labeling-actions');
        if (!container) return;
        container.innerHTML = '';

        const gridHeader = document.createElement('div');
        gridHeader.style.cssText = 'font-size: 0.8rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;';
        gridHeader.textContent = '🏷 Select Genre Label:';
        container.appendChild(gridHeader);

        const grid = document.createElement('div');
        grid.style.cssText = 'display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 16px;';

        const GENRE_EMOJIS = {
            heavy_dubstep:    '💥',
            color_bass:       '🎨',
            riddim:           '🔁',
            briddim:          '🌋',
            bass_house:       '🏠',
            future_bass:      '🌊',
            melodic_dubstep:  '✨',
            progressive_house:'🎹',
            drum_and_bass:    '🥁',
            trap:             '🔥'
        };

        this.genreLabels.forEach((genre) => {
            const btn = document.createElement('button');
            const emoji = GENRE_EMOJIS[genre.toLowerCase()] || '🎵';
            btn.className = 'btn-genre-action';
            btn.style.cssText = 'padding: 10px 8px; font-weight: 700; font-size: 0.82rem; border-radius: 10px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.15s;';
            btn.innerHTML = `<span>${emoji}</span> <span>${genre.toUpperCase()}</span>`;
            
            btn.addEventListener('mouseover', () => {
                btn.style.background = 'var(--accent-primary)';
                btn.style.borderColor = 'var(--accent-primary)';
            });
            btn.addEventListener('mouseout', () => {
                btn.style.background = 'rgba(255,255,255,0.05)';
                btn.style.borderColor = 'rgba(255,255,255,0.1)';
            });
            btn.addEventListener('click', () => this.submitLabel(genre));
            grid.appendChild(btn);
        });

        container.appendChild(grid);

        // Skip Button
        const skipBtn = document.createElement('button');
        skipBtn.className = 'btn-skip-labeling';
        skipBtn.style.cssText = 'width: 100%; padding: 14px; font-weight: 700; font-size: 0.95rem; border-radius: 12px; background: rgba(244, 63, 94, 0.15); border: 1px solid rgba(244, 63, 94, 0.3); color: #f43f5e; cursor: pointer; text-align: center; transition: all 0.2s;';
        skipBtn.innerHTML = '⏭ Skip Track (判断できない)';
        skipBtn.addEventListener('mouseover', () => {
            skipBtn.style.background = 'rgba(244, 63, 94, 0.3)';
        });
        skipBtn.addEventListener('mouseout', () => {
            skipBtn.style.background = 'rgba(244, 63, 94, 0.15)';
        });
        skipBtn.addEventListener('click', () => this.skipCurrentLabelingTrack());
        container.appendChild(skipBtn);
    },

    async submitLabel(label) {
        if (!this.currentTrackId) { alert('Select a track first.'); return; }
        try {
            const res = await fetch(`/api/tracks/${this.currentTrackId}/label`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label }),
            });
            if (res.ok) {
                await this.loadTracks();
                await this.loadNextUnlabeledTrack();
            } else {
                alert('Failed to save label.');
            }
        } catch (e) {
            console.error(e);
            alert('Network error.');
        }
    },

    async skipCurrentLabelingTrack() {
        if (!this.currentTrackId) return;
        if (!confirm('このトラックを削除/スキップしますか？')) return;
        try {
            const res = await fetch(`/api/labeling/skip/${this.currentTrackId}`, { method: 'POST' });
            if (res.ok) {
                await this.loadTracks();
                await this.loadNextUnlabeledTrack();
            } else {
                alert('スキップに失敗しました。');
            }
        } catch (e) {
            console.error(e);
            alert('通信エラー');
        }
    },

    async loadNextUnlabeledTrack() {
        try {
            const res = await fetch('/api/labeling/next');
            const data = await res.json();
            if (data && !data.done && data.track) {
                this.loadTrackForLabeling(data.track.track_id);
            } else {
                alert('🎉 全ての未ラベルトラックの処理が完了しました！');
                document.querySelector('[data-target="dashboard"]').click();
            }
        } catch (e) {
            console.error('loadNextUnlabeledTrack error', e);
        }
    },

    /* ── Pipeline ─────────────────────────────────────── */
    async startPipeline() {
        const urlInput = document.getElementById('pipeline-url').value;
        const out = document.getElementById('console-output');
        out.textContent = 'Starting pipeline...\n';

        try {
            const res = await fetch('/api/pipeline/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: urlInput }),
            });
            if (res.ok) {
                if (this.logInterval) clearInterval(this.logInterval);
                this.logInterval = setInterval(() => this.pollLogs(), 1500);
            } else {
                out.textContent = 'Failed to start pipeline.';
            }
        } catch (e) {
            out.textContent = `Error: ${e.message}`;
        }
    },

    async runInferenceOnly() {
        const btn = document.getElementById('btn-predict-model');
        if (!btn) return;
        const textSpan = btn.querySelector('.btn-text');
        const origText = textSpan.textContent;
        textSpan.textContent = '⚡ 判定実行中...';
        btn.disabled = true;
        
        try {
            const res = await fetch('/api/model/predict', { method: 'POST' });
            if (res.ok) {
                textSpan.textContent = '⚡ AI判定完了！';
                await this.loadTracks();
                setTimeout(() => {
                    textSpan.textContent = origText;
                    btn.disabled = false;
                }, 3000);
            } else {
                textSpan.textContent = '❌ 判定失敗';
                setTimeout(() => {
                    textSpan.textContent = origText;
                    btn.disabled = false;
                }, 3000);
            }
        } catch (e) {
            console.error(e);
            textSpan.textContent = '❌ 通信エラー';
            setTimeout(() => {
                textSpan.textContent = origText;
                btn.disabled = false;
            }, 3000);
        }
    },

    async trainModel() {
        const btn = document.getElementById('btn-train-model');
        const textSpan = btn.querySelector('.btn-text');
        const origText = textSpan.textContent;
        textSpan.textContent = '🤖 Training...';
        btn.disabled = true;
        
        try {
            const res = await fetch('/api/model/train', { method: 'POST' });
            if (res.ok) {
                textSpan.textContent = '🤖 Training Started!';
                setTimeout(() => {
                    textSpan.textContent = origText;
                    btn.disabled = false;
                }, 3000);
            } else {
                textSpan.textContent = '❌ Failed to start training';
                setTimeout(() => {
                    textSpan.textContent = origText;
                    btn.disabled = false;
                }, 3000);
            }
        } catch (e) {
            console.error(e);
            textSpan.textContent = '❌ Network error';
            setTimeout(() => {
                textSpan.textContent = origText;
                btn.disabled = false;
            }, 3000);
        }
    },

    async pollLogs() {
        try {
            const res = await fetch('/api/pipeline/logs');
            if (!res.ok) return;
            const data = await res.json();
            const out = document.getElementById('console-output');
            out.textContent = data.logs;
            out.scrollTop = out.scrollHeight;

            if (data.logs.includes('=== Pipeline Finished ===')) {
                clearInterval(this.logInterval);
                this.logInterval = null;
                await this.loadTracks();
            }
        } catch (e) {
            console.error('pollLogs', e);
        }
    },

    bindBenchmarkEvents() {
        const btnRun = document.getElementById('btn-run-benchmark');
        const btnClose = document.getElementById('btn-close-benchmark');
        const modal = document.getElementById('benchmark-modal');

        if (btnRun) {
            btnRun.addEventListener('click', () => {
                modal.style.display = 'flex';
                this.loadBenchmarkResults();
            });
        }

        if (btnClose) {
            btnClose.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }
    },

    async runBenchmarkTest() {
        if (!confirm('未学習曲のベンチマーク評価（各ジャンル10曲・音源分離あり・DB非保存）を開始しますか？')) return;
        try {
            const res = await fetch('/api/benchmark/run', { method: 'POST' });
            if (res.ok) {
                alert('ベンチマーク評価がバックグラウンドで開始されました！完了後、モーダルを再度開くと最新結果が表示されます。');
                document.getElementById('benchmark-modal-body').innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <p style="font-size: 1.1rem; color: #10B981; font-weight: bold;">🚀 ベンチマーク評価タスクがバックグラウンドで進行中です...</p>
                        <p style="color: var(--text-muted); font-size: 0.9rem;">(各ジャンル10曲の音源分離とAI判定を行っています。完了後に再度この画面を開いてください)</p>
                    </div>
                `;
            } else {
                alert('ベンチマーク開始に失敗しました。');
            }
        } catch (e) {
            console.error(e);
            alert('通信エラー');
        }
    },

    async loadBenchmarkResults() {
        const body = document.getElementById('benchmark-modal-body');
        body.innerHTML = '<p style="color: var(--text-muted);">最新ベンチマーク結果を読み込み中...</p>';
        try {
            const res = await fetch('/api/benchmark/results');
            const data = await res.json();

            if (!data.exists) {
                body.innerHTML = `
                    <div style="text-align: center; padding: 30px;">
                        <p style="font-size: 1rem; color: var(--text-muted); margin-bottom: 20px;">まだベンチマーク評価が実行されていません。</p>
                        <button class="btn btn-primary" onclick="App.runBenchmarkTest()" style="background: linear-gradient(135deg, #10B981, #059669); padding: 10px 24px;">
                            🎯 今すぐベンチマーク評価を実行する
                        </button>
                    </div>
                `;
                return;
            }

            // 統計計算
            const total = data.total || 0;
            const correct = data.correct || 0;
            const accuracy = data.accuracy || 0;
            const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleString('ja-JP') : '不明';

            let genreStats = {};
            (data.results || []).forEach(r => {
                const g = r.expected.toUpperCase();
                if (!genreStats[g]) genreStats[g] = { total: 0, correct: 0 };
                genreStats[g].total++;
                if (r.match) genreStats[g].correct++;
            });

            let genreRowsHtml = '';
            Object.keys(genreStats).forEach(g => {
                const st = genreStats[g];
                const rate = ((st.correct / st.total) * 100).toFixed(1);
                genreRowsHtml += `
                    <tr>
                        <td style="font-weight: bold;">${g}</td>
                        <td>${st.correct} / ${st.total}</td>
                        <td style="color: ${rate >= 70 ? '#10B981' : rate >= 40 ? '#F59E0B' : '#EF4444'}; font-weight: bold;">${rate}%</td>
                    </tr>
                `;
            });

            let itemRowsHtml = (data.results || []).map((r, i) => {
                const icon = r.match ? '✅' : '❌';
                const conf = (r.confidence * 100).toFixed(1);
                return `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="text-align: center;">${icon}</td>
                        <td style="font-weight: 500; font-size: 0.85rem;">${r.expected.toUpperCase()}</td>
                        <td style="font-weight: 600; color: ${r.match ? '#10B981' : '#F59E0B'}; font-size: 0.85rem;">${r.predicted.toUpperCase()} (${conf}%)</td>
                        <td style="font-size: 0.8rem; color: var(--text-muted);">${r.artist} - ${r.title}</td>
                    </tr>
                `;
            }).join('');

            body.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <div>
                        <div style="font-size: 0.85rem; color: var(--text-muted);">実行日時: ${timestamp}</div>
                        <div style="font-size: 1.8rem; font-weight: bold; color: #10B981; margin-top: 4px;">
                            正答率: ${accuracy}% <span style="font-size: 1rem; color: var(--text-muted); font-weight: normal;">(${correct} / ${total} 一致)</span>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="App.runBenchmarkTest()" style="background: linear-gradient(135deg, #10B981, #059669); font-size: 0.85rem; padding: 8px 16px;">
                        🔄 ベンチマーク再実行
                    </button>
                </div>

                <h4 style="margin-bottom: 10px; font-size: 1rem; border-left: 3px solid #10B981; padding-left: 8px;">ジャンル別正答率一覧</h4>
                <table class="tracks-table" style="margin-bottom: 24px;">
                    <thead>
                        <tr>
                            <th>ジャンル</th>
                            <th>一致数</th>
                            <th>正答率</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${genreRowsHtml}
                    </tbody>
                </table>

                <h4 style="margin-bottom: 10px; font-size: 1rem; border-left: 3px solid #6366F1; padding-left: 8px;">全評価トラック詳細 (計 ${total}曲)</h4>
                <div style="max-height: 300px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;">
                    <table class="tracks-table">
                        <thead>
                            <tr>
                                <th style="width: 40px;">判定</th>
                                <th>検索ジャンル</th>
                                <th>AI予測結果</th>
                                <th>楽曲名 / アーティスト</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${itemRowsHtml}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (e) {
            console.error('loadBenchmarkResults', e);
            body.innerHTML = '<p style="color: #EF4444;">結果の取得に失敗しました。</p>';
        }
    }
};

/* ── Global binding & boot ────────────────────────────── */
window.App = App;
window.runBenchmarkTest = () => App.runBenchmarkTest();
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
