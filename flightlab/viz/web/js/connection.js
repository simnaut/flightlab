// The WebSocket to the flightlab process. Reconnects after a drop; a new
// `flightlab run` has a new token, so a stale tab just keeps saying so.

export class Connection {
  constructor({ onMessage, onStatus }) {
    this.onMessage = onMessage;
    this.onStatus = onStatus;
    this.ws = null;
    this.retryMs = 500;
    const token = new URLSearchParams(location.search).get("token") || "";
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    this.url = `${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`;
  }

  open() {
    this.onStatus("connecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.retryMs = 500;
      this.onStatus("open");
    };
    ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      this.onMessage(msg);
    };
    ws.onclose = () => {
      if (this.ws !== ws) return;
      this.ws = null;
      this.onStatus("closed");
      setTimeout(() => this.open(), this.retryMs);
      this.retryMs = Math.min(this.retryMs * 2, 5000);
    };
  }

  send(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }
}
