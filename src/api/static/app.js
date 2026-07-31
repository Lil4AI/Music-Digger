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
        // Train model
        const trainBtn = document.getElementById('btn-train-model');
        if (trainBtn) trainBtn.addEventListener('click', () => this.trainModel());

        // Note: Label buttons are now dynamically generated in renderLabelingButtons()

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

            let aiHtml = '-';
            if (t.ai_label && t.ai_confidence != null) {
                const pct = Math.round(t.ai_confidence * 100);
                const isTarget = this.genreLabels[0] && t.ai_label.toLowerCase() === this.genreLabels[0].toLowerCase();
                const cls = isTarget ? 'badge-tearout' : 'badge-riddim';
                aiHtml = `<span class="label-badge ${cls}">${t.ai_label.toUpperCase()} ${pct}%</span>`;
            }

            let humanHtml = '-';
            if (t.human_label) {
                const isTarget = this.genreLabels[0] && t.human_label.toLowerCase() === this.genreLabels[0].toLowerCase();
                const cls = isTarget ? 'badge-tearout' : 'badge-riddim';
                humanHtml = `<span class="label-badge ${cls}">${t.human_label.toUpperCase()}</span>`;
            }

            tr.innerHTML = `
                <td style="font-family:monospace;font-size:.85em">${t.track_id}</td>
                <td>${t.source || '-'}</td>
                <td>${status}</td>
                <td>${aiHtml}</td>
                <td>${humanHtml}</td>
                <td><button class="btn-action" data-id="${t.track_id}">Analyze &amp; Label</button></td>
            `;

            tr.querySelector('.btn-action').addEventListener('click', () => {
                this.loadTrackForLabeling(t.track_id);
            });

            tbody.appendChild(tr);
        });
    },

    /* ── Labeling ─────────────────────────────────────── */
    loadTrackForLabeling(trackId) {
        this.currentTrackId = trackId;
        const track = this.tracks.find(t => t.track_id === trackId);

        document.getElementById('current-track-id').textContent = trackId;

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

    /* ── Label Submit ─────────────────────────────────── */
    renderLabelingButtons() {
        const container = document.getElementById('labeling-actions');
        if (!container) return;
        container.innerHTML = '';
        this.genreLabels.forEach((genre, idx) => {
            const btn = document.createElement('button');
            // Class index 0: btn-primary (high priority equivalent), index 1: btn-secondary (second class)
            btn.className = `btn ${idx === 0 ? 'btn-primary btn-tearout' : 'btn-secondary btn-riddim'}`;
            btn.id = `btn-${genre}`;
            btn.innerHTML = `
                <span class="glow"></span>
                <span class="btn-text">${genre.toUpperCase()}</span>
            `;
            btn.addEventListener('click', () => this.submitLabel(genre));
            container.appendChild(btn);
        });
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
                // Update only the .btn-text span to preserve the glow span
                const btn = document.getElementById(`btn-${label}`);
                if (btn) {
                    const textSpan = btn.querySelector('.btn-text');
                    if (textSpan) {
                        textSpan.textContent = '✓ SAVED';
                        setTimeout(() => { textSpan.textContent = label.toUpperCase(); }, 1200);
                    }
                }
                await this.loadTracks();
            } else {
                alert('Failed to save label.');
            }
        } catch (e) {
            console.error(e);
            alert('Network error.');
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
};

/* ── Global binding & boot ────────────────────────────── */
window.app = App;
document.addEventListener('DOMContentLoaded', () => App.init());
