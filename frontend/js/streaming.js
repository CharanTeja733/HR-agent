/**
 * HR Q&A Agent — Streaming Module
 * Defines: window.HrStream
 * Bridges SSE events from HrApi.apiStream to HrChat UI updates.
 */

(function () {
  'use strict';

  var currentController = null;
  var pendingSources = [];

  /**
   * Start a streaming query.
   * @param {string} query — user's question
   * @param {string|null} sessionId — active session ID or null for new
   * @returns {AbortController}
   */
  function startStream(query, sessionId) {
    // Stop any existing stream
    if (currentController) {
      stopStream(currentController);
    }

    // Set streaming state
    if (window.HrApp) {
      window.HrApp.setState('chat.isStreaming', true);
    }

    // Show bot placeholder in chat
    if (window.HrChat) {
      window.HrChat.addBotMessagePlaceholder();
    }

    // Reset pending sources
    pendingSources = [];

    // Start the SSE stream
    currentController = window.HrApi.apiStream('/query/', {
      query: query,
      session_id: sessionId || null
    }, {
      onToken: function (token) {
        if (window.HrChat) {
          window.HrChat.appendToken(token);
        }
      },
      onSources: function (sources) {
        pendingSources = sources || [];
      },
      onDone: function (data) {
        _handleDone(data);
      },
      onError: function (errorData) {
        _handleError(errorData);
      }
    });

    return currentController;
  }

  /**
   * Stop an active stream.
   */
  function stopStream(controller) {
    if (controller) {
      try {
        controller.abort();
      } catch (e) {
        // ignore
      }
    }
    currentController = null;
    pendingSources = [];

    if (window.HrApp) {
      window.HrApp.setState('chat.isStreaming', false);
    }

    // Re-enable input
    if (window.HrChat) {
      window.HrChat.enableInput();
    }
  }

  /**
   * Handle successful stream completion.
   */
  function _handleDone(data) {
    // Finalize the bot message
    if (window.HrChat) {
      window.HrChat.finalizeBotMessage(
        data.message_id,
        pendingSources,
        data.confidence
      );
      // Safety net — re-enable input even if finalizeBotMessage bailed early
      window.HrChat.enableInput();
    }

    // If this was a new session, update active session ID
    if (data.session_id && window.HrApp) {
      var currentSessionId = window.HrApp.getState('chat.activeSessionId');
      if (currentSessionId !== data.session_id) {
        window.HrApp.setState('chat.activeSessionId', data.session_id);
        localStorage.setItem('hr_active_session', data.session_id);

        // Reload sessions to show new session in sidebar
        if (window.HrSessions) {
          window.HrSessions.loadSessions();
        }
      } else {
        // Just update the preview for the existing session
        if (window.HrSessions) {
          window.HrSessions.updateSessionInList(data.session_id);
        }
      }
    }

    // Reset state
    currentController = null;
    pendingSources = [];

    if (window.HrApp) {
      window.HrApp.setState('chat.isStreaming', false);
    }
  }

  /**
   * Handle stream error.
   */
  function _handleError(errorData) {
    if (window.HrChat) {
      window.HrChat.showStreamError(errorData.detail || 'An error occurred while generating a response.');
      window.HrChat.enableInput();
    }

    currentController = null;
    pendingSources = [];

    if (window.HrApp) {
      window.HrApp.setState('chat.isStreaming', false);
    }
  }

  /**
   * Check if a stream is currently active.
   */
  function isStreaming() {
    return currentController !== null;
  }

  // Expose module
  window.HrStream = {
    startStream: startStream,
    stopStream: stopStream,
    isStreaming: isStreaming
  };
})();
