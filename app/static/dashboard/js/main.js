const { createApp } = Vue;

createApp({
  data() {
    return {
      workers: [],
      loading: true,
      isSpawning: false,
      refreshInterval: null,
    };
  },
  computed: {
    activeWorkers() {
      return this.workers.filter((w) => w.status === 0).length;
    },
    averageCpu() {
      if (this.workers.length === 0) return 0;
      const sum = this.workers.reduce((acc, worker) => acc + worker.cpu_usage, 0);
      return (sum / this.workers.length).toFixed(1);
    },
    averageMemory() {
      if (this.workers.length === 0) return 0;
      const sum = this.workers.reduce((acc, worker) => acc + worker.memory_usage, 0);
      return (sum / this.workers.length).toFixed(1);
    },
  },
  mounted() {
    this.fetchWorkers();
    // Refresh workers data every 5 seconds
    this.refreshInterval = setInterval(() => {
      this.fetchWorkers();
    }, 5000);
  },
  beforeUnmount() {
    clearInterval(this.refreshInterval);
  },
  methods: {
    async fetchWorkers() {
      try {
        const response = await axios.get("/workers");
        this.workers = response.data.workers;
        this.loading = false;
      } catch (error) {
        console.error("Error fetching workers:", error);
      }
    },
    async spawnWorker() {
      if (this.isSpawning) return;

      this.isSpawning = true;
      try {
        await axios.post("/spawn");
        await this.fetchWorkers();
      } catch (error) {
        console.error("Error spawning worker:", error);
        alert("Failed to spawn worker: " + (error.response?.data?.detail || error.message));
      } finally {
        this.isSpawning = false;
      }
    },
    async terminateWorker(workerId) {
      if (!confirm(`Are you sure you want to terminate worker ${workerId}?`)) {
        return;
      }

      try {
        await axios.delete(`/worker/${workerId}`);
        await this.fetchWorkers();
      } catch (error) {
        console.error("Error terminating worker:", error);
        alert("Failed to terminate worker: " + (error.response?.data?.detail || error.message));
      }
    },
    getStatusClass(status) {
      switch (status) {
        case 0:
          return "status-ok";
        case 1:
          return "status-not-ok";
        case 2:
          return "status-unknown";
        case 3:
          return "status-error";
        default:
          return "status-unknown";
      }
    },
    getStatusText(status) {
      switch (status) {
        case 0:
          return "OK";
        case 1:
          return "NOT OK";
        case 2:
          return "UNKNOWN";
        case 3:
          return "ERROR";
        default:
          return "UNKNOWN";
      }
    },
    getCpuColor(value) {
      if (value < 50) return "#2ecc71";
      if (value < 80) return "#f39c12";
      return "#e74c3c";
    },
    getMemoryColor(value) {
      if (value < 50) return "#3498db";
      if (value < 80) return "#f39c12";
      return "#e74c3c";
    },
    formatDate(dateStr) {
      const date = new Date(dateStr);
      return new Intl.DateTimeFormat("default", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(date);
    },
  },
}).mount("#app");
