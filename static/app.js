(() => {
  const downloadBtn = document.getElementById('downloadBtn');
  const clearBtn = document.getElementById('clearBtn');
  const cancelBtn = document.getElementById('cancelBtn');
  const downloadLink = document.getElementById('downloadLink');

  function setFormEnabled(enabled) {
    document.getElementById('symbol').disabled = !enabled;
    document.getElementById('timeframe').disabled = !enabled;
    document.getElementById('start').disabled = !enabled;
    document.getElementById('end').disabled = !enabled;
    downloadBtn.disabled = !enabled;
    clearBtn.disabled = !enabled;
  }

  clearBtn.addEventListener('click', () => {
    document.getElementById('symbol').value = '';
    document.getElementById('start').value = '';
    document.getElementById('end').value = '';
  });

  let currentJob = null;
  let polling = false;

  downloadBtn.addEventListener('click', async (e) => {
    e.preventDefault();
    const symbol = document.getElementById('symbol').value.trim();
    const timeframe = document.getElementById('timeframe').value;
    const start = document.getElementById('start').value;
    const end = document.getElementById('end').value;

    if (!symbol || !start || !end) {
      alert('Please fill all fields');
      return;
    }

    setFormEnabled(false);
    document.getElementById('progressArea').classList.remove('d-none');
    downloadLink.classList.add('d-none');
    cancelBtn.classList.remove('d-none');
    document.getElementById('spinner').classList.remove('d-none');

    const resp = await fetch('/start_download', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({symbol, timeframe, start, end}),
    });
    const data = await resp.json();
    if (resp.status !== 200) {
      alert(data.error || 'Failed to start');
      setFormEnabled(true);
      document.getElementById('progressArea').classList.add('d-none');
      return;
    }

    currentJob = data.job_id;
    document.getElementById('jobIdText').innerText = `Job: ${currentJob}`;
    polling = true;

    const bar = document.getElementById('progressBar');
    const text = document.getElementById('progressText');

    while (polling) {
      try {
        const r = await fetch(`/progress/${currentJob}`);
        const j = await r.json();
        if (j.error) {
          text.innerText = 'Error: ' + j.error;
          break;
        }
        bar.style.width = (j.progress || 0) + '%';
        text.innerText = `Status: ${j.status} — ${j.progress || 0}%`;

        if (j.status === 'done') {
          downloadLink.href = `/download/${currentJob}`;
          downloadLink.classList.remove('d-none');
          downloadLink.innerText = 'Download CSV';
          document.getElementById('spinner').classList.add('d-none');
          break;
        }
        if (j.status === 'error') {
          text.innerText = 'Error: ' + (j.error || 'unknown');
          document.getElementById('spinner').classList.add('d-none');
          break;
        }
      } catch (err) {
        text.innerText = 'Network error';
        break;
      }
      await new Promise(r => setTimeout(r, 1000));
    }

    polling = false;
    setFormEnabled(true);
    cancelBtn.classList.add('d-none');
  });

  cancelBtn.addEventListener('click', () => {
    polling = false;
    document.getElementById('progressText').innerText = 'Cancelled by user';
    document.getElementById('spinner').classList.add('d-none');
    setFormEnabled(true);
    cancelBtn.classList.add('d-none');
  });
})();
