if (typeof SharedArrayBuffer === 'undefined') {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').then(() => {
      if (!navigator.serviceWorker.controller) window.location.reload();
    });
  }
}
