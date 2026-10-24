'use strict';

(() => {
  const query = new URLSearchParams(window.location.search);
  // Remove the one-use code from browser history before showing a link.
  window.history.replaceState(null, '', window.location.pathname);
  const status = document.getElementById('status');
  const link = document.getElementById('return');
  const state = query.getAll('state');
  const code = query.getAll('code');
  const error = query.getAll('error');
  const validState = state.length === 1 &&
    /^(desktop|android)\.[A-Za-z0-9_-]{43}$/.test(state[0]);
  const validResult = (code.length === 1 && code[0].length > 0 &&
    code[0].length <= 4096 && error.length === 0) ||
    (error.length === 1 && error[0].length > 0 &&
      error[0].length <= 128 && code.length === 0);
  if (!validState || !validResult) {
    status.textContent = 'Start browser sign-in from SWHub to use this page.';
    return;
  }
  // Destinations are fixed. No caller can supply a redirect host, path or port.
  const destination = new URL(state[0].startsWith('android.')
    ? 'in.soumyak4.swhub://ogs/oauth/callback'
    : 'http://127.0.0.1:48765/ogs/oauth/callback');
  destination.searchParams.set('state', state[0]);
  destination.searchParams.set(code.length ? 'code' : 'error',
    code.length ? code[0] : error[0]);
  link.href = destination.href;
  link.hidden = false;
  status.textContent = 'Return to SWHub to finish signing in. If it does not open automatically, use the link below.';
  // A visible link also works when the browser requires a user gesture.
  window.location.replace(destination.href);
})();
