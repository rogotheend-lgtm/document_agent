const { createApp } = Vue;

createApp({
  data() {
    return {
      reports: [], reportId: '', question: '', messages: [], loading: false, error: '', progress: '',
      samples: ['핵심 결론을 쉽게 설명해줘', '가장 중요한 위험은 뭐야?', '영업이익률이 왜 중요해?', '파이썬 게임을 만들어줘'],
    };
  },
  async mounted() {
    const response = await fetch('/api/reports');
    const data = await response.json();
    this.reports = data.reports;
    this.reportId = this.reports[0]?.id || '';
  },
  methods: {
    async ask() {
      const message = this.question.trim();
      if (message.length < 2 || this.loading) return;
      this.messages.push({ role: 'user', content: message });
      this.question = ''; this.loading = true; this.error = ''; this.progress = 'supervisor';
      try {
        const response = await fetch('/api/chat/stream', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, report_id: this.reportId || null, thread_id: 'browser-demo' }),
        });
        if (!response.ok || !response.body) throw new Error('스트리밍 연결에 실패했습니다.');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop() || '';
          for (const chunk of chunks) {
            const event = chunk.match(/^event: (.+)$/m)?.[1];
            const raw = chunk.match(/^data: (.+)$/m)?.[1];
            if (!raw) continue;
            const data = JSON.parse(raw);
            if (event === 'progress') this.progress = data.node;
            if (event === 'error') throw new Error(data.detail);
            if (event === 'result') {
              this.messages.push({
                role: 'assistant', content: data.answer.replaceAll('**', ''), route: data.route,
                routeReason: data.route_reason, sources: data.sources,
                evidenceStatus: data.evidence_status, evidenceReason: data.evidence_reason,
                evidenceConfidence: data.evidence_confidence,
              });
            }
          }
        }
      } catch (error) { this.error = error.message; }
      finally { this.loading = false; this.progress = ''; }
    },
  },
}).mount('#app');
