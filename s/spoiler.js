(() => {
  const story = document.getElementById('spoiler-story');
  const dialog = document.getElementById('spoiler-warning');
  let completed = false;
  try {
    const progress = JSON.parse(localStorage.getItem('mquizx.archive.s01.v1') || '{}');
    completed = [true, 1].includes(progress?.finale?.finale_ending_seen);
  } catch {}
  if (completed) {
    story.hidden = false;
    return;
  }
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    location.href = 'index.html#episodes';
  });
  dialog.addEventListener('close', () => {
    if (dialog.returnValue === 'continue') story.hidden = false;
  });
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else if (window.confirm('捜査ボードの最終結末に関わる内容が含まれます。このまま読みますか？')) story.hidden = false;
  else location.href = 'index.html#episodes';
})();

