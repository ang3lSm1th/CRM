document.addEventListener("DOMContentLoaded", () => {
  const anchors = document.querySelectorAll(".anchor-btn");
  // pinnedLeads: array of codes that are pinned (for compatibility)
  const pinnedLeads = JSON.parse(localStorage.getItem("pinnedLeads") || "[]");
  // pinnedColors: map code -> colorName ('yellow'|'green'|'red')
  const pinnedColors = JSON.parse(localStorage.getItem("pinnedColors") || "{}");

  // Helper to apply color class to row
  function applyColorToRow(row, color) {
    row.classList.remove('row-colored-yellow','row-colored-green','row-colored-red','table-warning');
    if (!color) return;
    if (color === 'yellow') row.classList.add('row-colored-yellow');
    if (color === 'green') row.classList.add('row-colored-green');
    if (color === 'red') row.classList.add('row-colored-red');
  }

  // Initialize existing pins/colors
  anchors.forEach(btn => {
    const code = btn.dataset.code;
    const icon = btn.querySelector('i');
    const row = btn.closest('tr');

    if (pinnedLeads.includes(code)) {
      btn.classList.add('text-warning');
      if (icon) icon.classList.replace('bi-pin-angle','bi-pin-fill');
    }

    const color = pinnedColors[code];
    if (color) {
      // mark as pinned too
      if (!pinnedLeads.includes(code)) pinnedLeads.push(code);
      applyColorToRow(row, color);
    }
  });

  // Single bubble instance
  let currentBubble = null;

  function closeBubble() {
    if (currentBubble && currentBubble.parentNode) currentBubble.parentNode.removeChild(currentBubble);
    currentBubble = null;
    document.removeEventListener('click', onDocClickForBubble);
  }

  function onDocClickForBubble(e) {
    if (!currentBubble) return;
    if (e.target.closest('.color-bubble')) return;
    if (e.target.closest('.anchor-btn')) return; // allow clicking the button to re-open
    closeBubble();
  }

  // Create bubble element near button
  function showBubbleForButton(btn) {
    closeBubble();
    const code = btn.dataset.code;
    const icon = btn.querySelector('i');
    const row = btn.closest('tr');

    const bubble = document.createElement('div');
    bubble.className = 'color-bubble';

    // yellow
    const y = document.createElement('div');
    y.className = 'color-swatch sw-yellow';
    y.title = 'Amarillo';
    y.addEventListener('click', (ev) => {
      ev.stopPropagation();
      pinnedColors[code] = 'yellow';
      if (!pinnedLeads.includes(code)) pinnedLeads.push(code);
      localStorage.setItem('pinnedColors', JSON.stringify(pinnedColors));
      localStorage.setItem('pinnedLeads', JSON.stringify(pinnedLeads));
      if (icon) { icon.classList.replace('bi-pin-angle','bi-pin-fill'); btn.classList.add('text-warning'); }
      applyColorToRow(row, 'yellow');
      closeBubble();
    });
    bubble.appendChild(y);

    // green
    const g = document.createElement('div');
    g.className = 'color-swatch sw-green';
    g.title = 'Verde';
    g.addEventListener('click', (ev) => {
      ev.stopPropagation();
      pinnedColors[code] = 'green';
      if (!pinnedLeads.includes(code)) pinnedLeads.push(code);
      localStorage.setItem('pinnedColors', JSON.stringify(pinnedColors));
      localStorage.setItem('pinnedLeads', JSON.stringify(pinnedLeads));
      if (icon) { icon.classList.replace('bi-pin-angle','bi-pin-fill'); btn.classList.add('text-warning'); }
      applyColorToRow(row, 'green');
      closeBubble();
    });
    bubble.appendChild(g);

    // red
    const r = document.createElement('div');
    r.className = 'color-swatch sw-red';
    r.title = 'Rojo';
    r.addEventListener('click', (ev) => {
      ev.stopPropagation();
      pinnedColors[code] = 'red';
      if (!pinnedLeads.includes(code)) pinnedLeads.push(code);
      localStorage.setItem('pinnedColors', JSON.stringify(pinnedColors));
      localStorage.setItem('pinnedLeads', JSON.stringify(pinnedLeads));
      if (icon) { icon.classList.replace('bi-pin-angle','bi-pin-fill'); btn.classList.add('text-warning'); }
      applyColorToRow(row, 'red');
      closeBubble();
    });
    bubble.appendChild(r);

    // clear/unpin
    const c = document.createElement('div');
    c.className = 'sw-clear';
    c.title = 'Quitar color / Desanclar';
    c.innerHTML = '&times;';
    c.addEventListener('click', (ev) => {
      ev.stopPropagation();
      // remove color and pinned status
      delete pinnedColors[code];
      const idx = pinnedLeads.indexOf(code);
      if (idx !== -1) pinnedLeads.splice(idx,1);
      localStorage.setItem('pinnedColors', JSON.stringify(pinnedColors));
      localStorage.setItem('pinnedLeads', JSON.stringify(pinnedLeads));
      if (icon) { icon.classList.replace('bi-pin-fill','bi-pin-angle'); btn.classList.remove('text-warning'); }
      applyColorToRow(row, null);
      closeBubble();
    });
    bubble.appendChild(c);

    document.body.appendChild(bubble);
    currentBubble = bubble;

    // Position bubble near button
    const rect = btn.getBoundingClientRect();
    const bubbleRect = bubble.getBoundingClientRect();
    // prefer placing below the button, but keep it inside viewport
    let top = window.scrollY + rect.bottom + 6;
    let left = window.scrollX + rect.left;
    // adjust if overflow
    if (left + bubbleRect.width > window.scrollX + window.innerWidth) {
      left = window.scrollX + window.innerWidth - bubbleRect.width - 8;
    }
    bubble.style.top = top + 'px';
    bubble.style.left = left + 'px';

    // close when clicking outside
    setTimeout(() => document.addEventListener('click', onDocClickForBubble), 0);
  }

  // Attach click handlers to anchor buttons
  anchors.forEach(btn => {
    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
      // show bubble for color selection
      showBubbleForButton(btn);
    });
  });
});
