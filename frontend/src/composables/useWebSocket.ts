import { ref, onUnmounted } from 'vue'
import type { WsMessage } from '../types'

export function useWebSocket(url: string) {
  const status = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')
  const lastMessage = ref<WsMessage | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false

  function connect() {
    if (ws && ws.readyState <= WebSocket.OPEN) return

    intentionalClose = false
    status.value = 'connecting'

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = url.startsWith('ws') ? url : `${protocol}//${window.location.host}${url}`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      status.value = 'connected'
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    ws.onmessage = (event) => {
      try {
        lastMessage.value = JSON.parse(event.data) as WsMessage
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      status.value = 'disconnected'
      if (!intentionalClose) {
        scheduleReconnect()
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    intentionalClose = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
    status.value = 'disconnected'
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, 3000)
  }

  onUnmounted(() => {
    disconnect()
  })

  return { status, lastMessage, connect, disconnect }
}
