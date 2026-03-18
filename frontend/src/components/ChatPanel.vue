<template>
  <div class="chat-wrapper">
    <!-- Toggle button -->
    <button
      class="chat-toggle-btn"
      :class="{ active: isOpen }"
      @click="isOpen = !isOpen"
      :title="t('chat.title')"
    >
      <i :class="isOpen ? 'pi pi-times' : 'pi pi-comments'" />
    </button>

    <!-- Panel -->
    <transition name="chat-slide">
      <div v-if="isOpen" class="chat-panel">
        <!-- Header -->
        <div class="chat-header">
          <div class="chat-header-info">
            <i class="pi pi-bolt chat-header-icon" />
            <span class="chat-header-title">{{ t('chat.title') }}</span>
          </div>
          <div class="chat-header-actions">
            <span v-if="chat.usageText" class="chat-usage">
              {{ chat.usageText }} {{ t('chat.messagesUsed') }}
            </span>
            <button
              v-if="chat.hasMessages"
              class="chat-clear-btn"
              @click="chat.clearMessages()"
              :title="t('chat.clear')"
            >
              <i class="pi pi-trash" />
            </button>
          </div>
        </div>

        <!-- Messages -->
        <div class="chat-messages" ref="messagesRef">
          <div v-if="!chat.hasMessages" class="chat-empty">
            <i class="pi pi-comments chat-empty-icon" />
            <p>{{ t('chat.emptyTitle') }}</p>
            <span class="text-muted">{{ t('chat.emptyDesc') }}</span>
          </div>

          <div
            v-for="msg in chat.messages"
            :key="msg.id"
            class="chat-bubble"
            :class="`chat-bubble--${msg.role}`"
          >
            <div class="chat-bubble-content" v-html="renderMarkdown(msg.content)" />
          </div>

          <!-- Loading indicator -->
          <div v-if="chat.loading" class="chat-bubble chat-bubble--assistant">
            <div class="chat-typing">
              <span /><span /><span />
            </div>
          </div>

          <!-- Error -->
          <div v-if="chat.error" class="chat-error">
            <i class="pi pi-exclamation-circle" />
            {{ chat.error }}
          </div>
        </div>

        <!-- Input -->
        <form class="chat-input-area" @submit.prevent="handleSend">
          <input
            v-model="inputText"
            class="chat-input"
            :placeholder="t('chat.placeholder')"
            :disabled="chat.loading"
            maxlength="2000"
            ref="inputRef"
          />
          <button
            type="submit"
            class="chat-send-btn"
            :disabled="!inputText.trim() || chat.loading"
          >
            <i class="pi pi-send" />
          </button>
        </form>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '@/stores/useChatStore'

const { t } = useI18n()
const chat = useChatStore()

const isOpen = ref(false)
const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

function renderMarkdown(text: string): string {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chat.loading) return
  inputText.value = ''
  await chat.sendMessage(text)
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// Auto-scroll when messages update
watch(
  () => chat.messages.length > 0 ? chat.messages[chat.messages.length - 1]?.content : '',
  () => scrollToBottom()
)

// Focus input when panel opens
watch(isOpen, (val) => {
  if (val) {
    nextTick(() => inputRef.value?.focus())
  }
})
</script>

<style scoped>
.chat-wrapper {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 1000;
}

/* Toggle button */
.chat-toggle-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: var(--ss-accent, #6366f1);
  color: white;
  font-size: 1.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transition: all 0.2s ease;
}

.chat-toggle-btn:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
}

.chat-toggle-btn.active {
  background: var(--ss-bg-elevated, #1e1e2e);
  color: var(--ss-text-primary, #e2e8f0);
  border: 1px solid var(--ss-border-light, #2a2a3e);
}

/* Panel */
.chat-panel {
  position: absolute;
  bottom: 60px;
  right: 0;
  width: 380px;
  max-height: 520px;
  background: var(--ss-bg-surface, #1a1a2e);
  border: 1px solid var(--ss-border-light, #2a2a3e);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--ss-border-light, #2a2a3e);
  flex-shrink: 0;
}

.chat-header-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-header-icon {
  color: var(--ss-accent, #6366f1);
  font-size: 1.1rem;
}

.chat-header-title {
  font-weight: 600;
  font-size: 0.9rem;
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-usage {
  font-size: 0.7rem;
  color: var(--ss-text-muted, #64748b);
  background: var(--ss-bg-base, #0f0f1a);
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.chat-clear-btn {
  background: none;
  border: none;
  color: var(--ss-text-muted, #64748b);
  cursor: pointer;
  padding: 0.25rem;
  font-size: 0.85rem;
  border-radius: 4px;
  transition: all 0.15s;
}

.chat-clear-btn:hover {
  color: var(--ss-danger, #ef4444);
  background: rgba(239, 68, 68, 0.1);
}

/* Messages area */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 200px;
  max-height: 360px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  padding: 2rem 1rem;
  color: var(--ss-text-muted, #64748b);
}

.chat-empty-icon {
  font-size: 2rem;
  margin-bottom: 0.75rem;
  opacity: 0.5;
}

.chat-empty p {
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
  color: var(--ss-text-secondary, #94a3b8);
}

/* Bubbles */
.chat-bubble {
  max-width: 85%;
  padding: 0.6rem 0.85rem;
  border-radius: 12px;
  font-size: 0.85rem;
  line-height: 1.5;
  word-wrap: break-word;
}

.chat-bubble--user {
  align-self: flex-end;
  background: var(--ss-accent, #6366f1);
  color: white;
  border-bottom-right-radius: 4px;
}

.chat-bubble--assistant {
  align-self: flex-start;
  background: var(--ss-bg-elevated, #1e1e2e);
  color: var(--ss-text-primary, #e2e8f0);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--ss-border-light, #2a2a3e);
}

.chat-bubble-content :deep(code) {
  background: rgba(0, 0, 0, 0.2);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.8rem;
}

.chat-bubble-content :deep(strong) {
  font-weight: 600;
}

/* Typing indicator */
.chat-typing {
  display: flex;
  gap: 4px;
  padding: 0.2rem 0;
}

.chat-typing span {
  width: 6px;
  height: 6px;
  background: var(--ss-text-muted, #64748b);
  border-radius: 50%;
  animation: typing-bounce 1.4s infinite ease-in-out;
}

.chat-typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* Error */
.chat-error {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: var(--ss-danger, #ef4444);
  background: rgba(239, 68, 68, 0.08);
  border-radius: 8px;
}

/* Input area */
.chat-input-area {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border-top: 1px solid var(--ss-border-light, #2a2a3e);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  background: var(--ss-bg-base, #0f0f1a);
  border: 1px solid var(--ss-border-light, #2a2a3e);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  color: var(--ss-text-primary, #e2e8f0);
  outline: none;
  transition: border-color 0.15s;
}

.chat-input::placeholder {
  color: var(--ss-text-muted, #64748b);
}

.chat-input:focus {
  border-color: var(--ss-accent, #6366f1);
}

.chat-send-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: var(--ss-accent, #6366f1);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  transition: all 0.15s;
  flex-shrink: 0;
}

.chat-send-btn:hover:not(:disabled) {
  filter: brightness(1.15);
}

.chat-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Slide transition */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: all 0.25s ease;
}

.chat-slide-enter-from,
.chat-slide-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.95);
}

/* Mobile */
@media (max-width: 480px) {
  .chat-panel {
    width: calc(100vw - 2rem);
    right: -0.5rem;
    max-height: 70vh;
  }
}
</style>
