const { createApp } = Vue;

createApp({
  data() {
    return {
      reports: [], reportId: '', question: '', messages: [], loading: false, error: '',
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
      this.question = ''; this.loading = true; this.error = '';
      try {
        const response = await fetch('/api/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, report_id: this.reportId || null, thread_id: 'browser-demo' }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || '답변 생성에 실패했습니다.');
        this.messages.push({ role: 'assistant', content: data.answer, route: data.route, sources: data.sources });
      } catch (error) { this.error = error.message; }
      finally { this.loading = false; }
    },
  },
}).mount('#app');

