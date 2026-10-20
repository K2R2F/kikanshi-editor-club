"use strict";

const checks = [...document.querySelectorAll('.checklist-panel input[type="checkbox"]')];
const progress = document.getElementById("check-progress");
function updateProgress() {
  progress.textContent = `確認済み ${checks.filter(check => check.checked).length} / ${checks.length}`;
}
checks.forEach(check => check.addEventListener("change", updateProgress));
window.addEventListener("pageshow", updateProgress);
updateProgress();

document.querySelectorAll("[data-copy]").forEach(button => {
  button.hidden = false;
  button.addEventListener("click", async () => {
    const prompt = document.getElementById(button.dataset.copy);
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(prompt.textContent);
      status.textContent = "依頼文をコピーしました。原稿を入れて使ってください。";
    } catch {
      const range = document.createRange();
      range.selectNodeContents(prompt);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "自動コピーを利用できません。選択した依頼文を手動でコピーしてください。";
    }
  });
});

const printButton = document.getElementById("print-page");
printButton.hidden = false;
printButton.addEventListener("click", () => {
  const details = [...document.querySelectorAll("details")];
  const previous = details.map(item => item.open);
  details.forEach(item => { item.open = true; });
  window.addEventListener("afterprint", () => {
    details.forEach((item, index) => { item.open = previous[index]; });
  }, { once: true });
  window.print();
});
