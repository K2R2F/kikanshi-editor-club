document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', async () => {
    const text = document.getElementById(button.dataset.copy).textContent;
    const status = document.getElementById('copy-status');
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = 'コピー済み';
      status.textContent = '依頼例をコピーしました。';
      setTimeout(() => { button.textContent = 'コピー'; }, 2000);
    } catch {
      status.textContent = 'コピーできませんでした。依頼例の文章を選択してコピーしてください。';
      button.textContent = '文章を選択してください';
    }
  });
});
