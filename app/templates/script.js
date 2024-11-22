// script.js

// 显示右侧页面内容的函数
function showPage(page) {
  const content = document.getElementById('content');

  if (page === 'page1') {
    content.innerHTML = `
      <h2>Page 1</h2>
      <p>This is the content of Page 1.</p>
    `;
  } else if (page === 'page2') {
    content.innerHTML = `
      <h2>Page 2</h2>
      <p>This is the content of Page 2.</p>
    `;
  }
}

// 显示隐藏按钮的函数
function showAdditionalButtons() {
  const additionalButtons = document.getElementById('additional-buttons');
  additionalButtons.classList.remove('hidden');
}
