/* global Vue */

const api = {
  async get(path) {
    const r = await fetch(`/api${path}`);
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },
  async post(path, body) {
    const r = await fetch(`/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },
  async put(path, body) {
    const r = await fetch(`/api${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },
  async del(path) {
    const r = await fetch(`/api${path}`, { method: "DELETE" });
    if (!r.ok) throw new Error(await r.text());
    return await r.json();
  },
};

function fmtBytes(n) {
  if (n == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

function badgeClass(status) {
  if (status === "success") return "badge ok";
  if (status === "failed") return "badge bad";
  if (status === "running") return "badge run";
  return "badge";
}

const App = {
  data() {
    return {
      tab: "dashboard",
      loading: false,
      error: "",

      dashboard: null,
      jobs: [],
      selectedJob: null,
      runs: [],

      editMode: false,
      jobForm: null,
      runLog: "",
    };
  },
  async mounted() {
    await this.refreshAll();
  },
  methods: {
    fmtBytes,
    badgeClass,
    async refreshAll() {
      // Sync jobs from config.json (if present), then refresh UI.
      try {
        await api.post("/jobs/sync-from-config", {});
      } catch (e) {
        this.error = String(e);
      }
      await Promise.all([this.loadDashboard(), this.loadJobs()]);
    },
    async loadDashboard() {
      try {
        this.dashboard = await api.get("/dashboard");
      } catch (e) {
        this.error = String(e);
      }
    },
    async loadJobs() {
      try {
        this.jobs = await api.get("/jobs");
      } catch (e) {
        this.error = String(e);
      }
    },
    async selectJob(job) {
      this.selectedJob = job;
      this.editMode = false;
      this.runLog = "";
      await this.loadRuns(job.id);
    },
    async loadRuns(jobId) {
      try {
        this.runs = await api.get(`/jobs/${jobId}/runs`);
      } catch (e) {
        this.error = String(e);
      }
    },
    editJob(job) {
      this.editMode = true;
      this.selectedJob = job;
      this.jobForm = JSON.parse(JSON.stringify(job));
      this.jobForm.postgres = this.jobForm.postgres ?? {
        host: "",
        port: 5432,
        database: "",
        user: "",
        password: "",
        sslmode: "prefer",
        format: "custom",
      };
      this.jobForm.mongo = this.jobForm.mongo ?? {
        host: "",
        port: 27017,
        database: "",
        user: "",
        password: "",
        authSource: "admin",
      };
      this.jobForm.s3 = this.jobForm.s3 ?? {
        endpoint: "",
        access_key: "",
        secret_key: "",
        bucket: "",
        region: "",
        use_ssl: true,
        path_style: true,
      };
      // Do not overwrite secrets unless user provides them
      if (this.jobForm.postgres) this.jobForm.postgres.password = "";
      if (this.jobForm.mongo) this.jobForm.mongo.password = "";
      if (this.jobForm.s3) this.jobForm.s3.secret_key = "";
    },
    async saveJob() {
      this.loading = true;
      this.error = "";
      try {
        if (this.selectedJob?.id) {
          const updated = await api.put(`/jobs/${this.selectedJob.id}`, this.jobForm);
          this.selectedJob = updated;
        } else {
          throw new Error("Создание заданий через UI отключено. Добавьте задание в config.json и нажмите «Обновить».");
        }
        this.editMode = false;
        await this.refreshAll();
      } catch (e) {
        this.error = String(e);
      } finally {
        this.loading = false;
      }
    },
    async deleteJob(job) {
      if (!confirm(`Удалить job "${job.name}"?`)) return;
      this.loading = true;
      this.error = "";
      try {
        await api.del(`/jobs/${job.id}`);
        this.selectedJob = null;
        this.editMode = false;
        await this.refreshAll();
      } catch (e) {
        this.error = String(e);
      } finally {
        this.loading = false;
      }
    },
    async runNow(job) {
      this.loading = true;
      this.error = "";
      try {
        await api.post(`/jobs/${job.id}/run-now`, {});
        await this.loadRuns(job.id);
        await this.loadDashboard();
      } catch (e) {
        this.error = String(e);
      } finally {
        this.loading = false;
      }
    },
    async openRunLog(run) {
      this.runLog = "";
      try {
        const r = await api.get(`/runs/${run.id}/log`);
        const err = (r.error_text || "").trim();
        const log = (r.log_text || "").trim();
        this.runLog = [err ? `ERROR:\n${err}` : "", log].filter(Boolean).join("\n\n");
      } catch (e) {
        this.error = String(e);
      }
    },
  },
  template: `
  <div class="container">
    <div class="header">
      <div>
        <div class="title">trio-backuper</div>
        <div class="subtitle">Централизованные бэкапы PostgreSQL / MongoDB / S3(MinIO)</div>
      </div>
      <div class="row">
        <button class="btn" @click="refreshAll" :disabled="loading">Обновить</button>
      </div>
    </div>

    <div class="tabs">
      <div class="tab" :class="{active: tab==='dashboard'}" @click="tab='dashboard'">Дашборд</div>
      <div class="tab" :class="{active: tab==='jobs'}" @click="tab='jobs'">Задания</div>
    </div>

    <div v-if="error" class="card" style="border-color: rgba(255,76,76,0.35);">
      <div class="metric-label">Ошибка</div>
      <div class="mono" style="white-space: pre-wrap;">{{ error }}</div>
    </div>

    <div v-if="tab==='dashboard'">
      <div class="grid" v-if="dashboard">
        <div class="card">
          <div class="metric-label">Всего заданий</div>
          <div class="metric-value">{{ dashboard.total_jobs }}</div>
        </div>
        <div class="card">
          <div class="metric-label">Успешно (24ч)</div>
          <div class="metric-value">{{ dashboard.success_24h }}</div>
        </div>
        <div class="card">
          <div class="metric-label">Ошибки (24ч)</div>
          <div class="metric-value">{{ dashboard.failed_24h }}</div>
        </div>
        <div class="card">
          <div class="metric-label">Диск (занято / всего)</div>
          <div class="metric-value">{{ fmtBytes(dashboard.disk_used_bytes) }} / {{ fmtBytes(dashboard.disk_total_bytes) }}</div>
        </div>
      </div>
      <div class="card" v-else>
        <div class="muted">Нет данных…</div>
      </div>
    </div>

    <div v-if="tab==='jobs'">
      <div class="split">
        <div class="card">
          <div class="metric-label" style="margin-bottom: 10px;">Список заданий</div>
          <table class="table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Источник</th>
                <th>Вкл.</th>
                <th>Последний запуск</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="j in jobs" :key="j.id" style="cursor:pointer" @click="selectJob(j)">
                <td><b>{{ j.name }}</b></td>
                <td><span class="badge">{{ j.source_type }}</span></td>
                <td>{{ j.enabled ? 'да' : 'нет' }}</td>
                <td>
                  <span v-if="j.last_run_status" :class="badgeClass(j.last_run_status)">{{ j.last_run_status }}</span>
                  <span v-else class="muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card" v-if="editMode">
          <div class="metric-label" style="margin-bottom: 10px;">
            {{ selectedJob?.id ? 'Редактирование задания' : 'Создание задания отключено' }}
          </div>

          <div class="form">
            <div class="field">
              <div class="label">Название</div>
              <input v-model="jobForm.name" placeholder="Напр. prod-postgres" />
            </div>
            <div class="field">
              <div class="label">Тип источника</div>
              <select v-model="jobForm.source_type">
                <option value="postgres">postgres</option>
                <option value="mongo">mongo</option>
                <option value="s3">s3</option>
                <option value="all">all</option>
              </select>
            </div>
            <div class="field">
              <div class="label">Cron</div>
              <input v-model="jobForm.schedule_cron" placeholder="0 2 * * *" />
            </div>
            <div class="field">
              <div class="label">Папка сохранения (внутри BACKUP_ROOT)</div>
              <input v-model="jobForm.destination_path" placeholder="default" />
            </div>
            <div class="field">
              <label><input type="checkbox" v-model="jobForm.enabled" /> Включено</label>
            </div>

            <div class="card" v-if="jobForm.source_type==='postgres' || jobForm.source_type==='all'">
              <div class="metric-label" style="margin-bottom: 8px;">PostgreSQL</div>
              <div class="split">
                <div class="field"><div class="label">host</div><input v-model="jobForm.postgres.host" /></div>
                <div class="field"><div class="label">port</div><input type="number" v-model.number="jobForm.postgres.port" /></div>
              </div>
              <div class="split">
                <div class="field"><div class="label">database</div><input v-model="jobForm.postgres.database" /></div>
                <div class="field"><div class="label">user</div><input v-model="jobForm.postgres.user" /></div>
              </div>
              <div class="split">
                <div class="field"><div class="label">password (оставьте пустым, чтобы не менять)</div><input type="password" v-model="jobForm.postgres.password" /></div>
                <div class="field">
                  <div class="label">sslmode</div>
                  <select v-model="jobForm.postgres.sslmode">
                    <option>disable</option><option>allow</option><option>prefer</option><option>require</option><option>verify-ca</option><option>verify-full</option>
                  </select>
                </div>
              </div>
              <div class="field">
                <div class="label">format</div>
                <select v-model="jobForm.postgres.format">
                  <option value="custom">custom (.dump)</option>
                  <option value="plain">plain (.sql)</option>
                </select>
              </div>
            </div>

            <div class="card" v-if="jobForm.source_type==='mongo' || jobForm.source_type==='all'">
              <div class="metric-label" style="margin-bottom: 8px;">MongoDB</div>
              <div class="split">
                <div class="field"><div class="label">host</div><input v-model="jobForm.mongo.host" /></div>
                <div class="field"><div class="label">port</div><input type="number" v-model.number="jobForm.mongo.port" /></div>
              </div>
              <div class="split">
                <div class="field"><div class="label">database</div><input v-model="jobForm.mongo.database" /></div>
                <div class="field"><div class="label">authSource</div><input v-model="jobForm.mongo.authSource" /></div>
              </div>
              <div class="split">
                <div class="field"><div class="label">user</div><input v-model="jobForm.mongo.user" /></div>
                <div class="field"><div class="label">password (оставьте пустым, чтобы не менять)</div><input type="password" v-model="jobForm.mongo.password" /></div>
              </div>
            </div>

            <div class="card" v-if="jobForm.source_type==='s3' || jobForm.source_type==='all'">
              <div class="metric-label" style="margin-bottom: 8px;">S3 (MinIO)</div>
              <div class="field"><div class="label">endpoint</div><input v-model="jobForm.s3.endpoint" placeholder="https://minio:9000" /></div>
              <div class="split">
                <div class="field"><div class="label">bucket</div><input v-model="jobForm.s3.bucket" /></div>
                <div class="field"><div class="label">region (опц.)</div><input v-model="jobForm.s3.region" /></div>
              </div>
              <div class="split">
                <div class="field"><div class="label">access_key</div><input v-model="jobForm.s3.access_key" /></div>
                <div class="field"><div class="label">secret_key (оставьте пустым, чтобы не менять)</div><input type="password" v-model="jobForm.s3.secret_key" /></div>
              </div>
              <div class="split">
                <div class="field">
                  <div class="label">use_ssl</div>
                  <select v-model="jobForm.s3.use_ssl">
                    <option :value="true">true</option>
                    <option :value="false">false</option>
                  </select>
                </div>
                <div class="field">
                  <div class="label">path_style</div>
                  <select v-model="jobForm.s3.path_style">
                    <option :value="true">true</option>
                    <option :value="false">false</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="row">
              <button class="btn primary" @click="saveJob" :disabled="loading">Сохранить</button>
              <button class="btn" @click="editMode=false" :disabled="loading">Отмена</button>
            </div>
          </div>
        </div>

        <div class="card" v-else-if="selectedJob">
          <div class="row" style="justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight:700">{{ selectedJob.name }}</div>
              <div class="muted">cron: <span class="mono">{{ selectedJob.schedule_cron }}</span></div>
            </div>
            <div class="row">
              <button class="btn" @click="editJob(selectedJob)" :disabled="loading">Редактировать</button>
              <button class="btn primary" @click="runNow(selectedJob)" :disabled="loading">Запустить сейчас</button>
              <button class="btn danger" @click="deleteJob(selectedJob)" :disabled="loading">Удалить</button>
            </div>
          </div>

          <div style="margin-top: 14px;">
            <div class="metric-label" style="margin-bottom: 8px;">История запусков</div>
            <table class="table">
              <thead>
                <tr>
                  <th>Старт</th>
                  <th>Окончание</th>
                  <th>Статус</th>
                  <th>Размер</th>
                  <th>Файл</th>
                  <th>Лог</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in runs" :key="r.id">
                  <td class="mono">{{ r.started_at }}</td>
                  <td class="mono">{{ r.finished_at || '—' }}</td>
                  <td><span :class="badgeClass(r.status)">{{ r.status }}</span></td>
                  <td class="mono">{{ fmtBytes(r.size_bytes) }}</td>
                  <td class="mono">{{ r.output_path || '—' }}</td>
                  <td><button class="btn" @click="openRunLog(r)">Открыть</button></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="card" v-if="runLog" style="margin-top: 12px;">
            <div class="metric-label" style="margin-bottom: 8px;">Лог выполнения</div>
            <div class="mono" style="white-space: pre-wrap;">{{ runLog }}</div>
          </div>
        </div>

        <div class="card" v-else>
          <div class="muted">Выберите задание слева. Новые задания добавляются через <span class="mono">config.json</span>.</div>
        </div>
      </div>
    </div>
  </div>
  `,
};

Vue.createApp(App).mount("#app");
