document.getElementById('downloadBtn').addEventListener('click', async () => {
  const symbol = document.getElementById('symbol').value.trim();
  const timeframe = document.getElementById('timeframe').value;
  const start = document.getElementById('start').value;
  const end = document.getElementById('end').value;

  if (!symbol || !start || !end) {
    alert('Please fill all fields');
    return;
  }

  const resp = await fetch('/start_download', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol, timeframe, start, end}),
  });
  const data = await resp.json();
  if (resp.status !== 200) {
    alert(data.error || 'Failed to start');
    return;
  }

  const jobId = data.job_id;
  document.getElementById('progressArea').classList.remove('hidden');
  const bar = document.getElementById('progressBar');
  const text = document.getElementById('progressText');
  const link = document.getElementById('downloadLink');

  let done = false;
  while (!done) {
    const r = await fetch(`/progress/${jobId}`);
    const j = await r.json();
    if (j.error) {
      text.innerText = 'Error: ' + j.error;
      break;
    }
    bar.style.width = (j.progress || 0) + '%';
    text.innerText = `Status: ${j.status} - ${j.progress || 0}%`;
    if (j.status === 'done') {
      link.href = `/download/${jobId}`;
      link.classList.remove('hidden');
      link.innerText = 'Click to download CSV';
      done = true;
      break;
    }
    if (j.status === 'error') {
      text.innerText = 'Error: ' + (j.error || 'unknown');
      done = true;
      break;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
});
