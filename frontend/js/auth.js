/**
 * HR Q&A Agent — Authentication Module
 * Defines: window.HrAuth
 * Login, register, logout, token storage, token refresh scheduling.
 */

(function () {
  'use strict';

  var refreshTimer = null;

  // ---- Token Storage ----

  function storeAuth(accessToken, refreshToken, user) {
    localStorage.setItem('hr_auth_token', accessToken);
    localStorage.setItem('hr_auth_refresh', refreshToken);
    localStorage.setItem('hr_auth_user', JSON.stringify({
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      department: user.department
    }));
  }

  function clearAuth() {
    localStorage.removeItem('hr_auth_token');
    localStorage.removeItem('hr_auth_refresh');
    localStorage.removeItem('hr_auth_user');
    localStorage.removeItem('hr_active_session');
  }

  function getStoredAuth() {
    var token = localStorage.getItem('hr_auth_token');
    var refreshToken = localStorage.getItem('hr_auth_refresh');
    var userJson = localStorage.getItem('hr_auth_user');
    var user = null;
    if (userJson) {
      try {
        user = JSON.parse(userJson);
      } catch (e) {
        user = null;
      }
    }
    return { token: token, refreshToken: refreshToken, user: user };
  }

  // ---- Validation ----

  function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function validatePassword(password) {
    var errors = [];
    if (!password || password.length < 8) errors.push('At least 8 characters');
    if (!/[A-Z]/.test(password)) errors.push('One uppercase letter');
    if (!/[a-z]/.test(password)) errors.push('One lowercase letter');
    if (!/[0-9]/.test(password)) errors.push('One digit');
    return { valid: errors.length === 0, errors: errors };
  }

  // ---- UI Helpers ----

  function showFormError(elementId, message) {
    var el = document.getElementById(elementId);
    if (el) {
      el.textContent = message || '';
      el.classList.toggle('hidden', !message);
    }
  }

  function showAuthError(message) {
    var el = document.getElementById('auth-error');
    if (el) {
      el.textContent = message;
      el.classList.remove('hidden');
    }
  }

  function hideAuthError() {
    var el = document.getElementById('auth-error');
    if (el) el.classList.add('hidden');
  }

  function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    var textEl = btn.querySelector('.btn-text');
    var spinnerEl = btn.querySelector('.btn-spinner');
    btn.disabled = isLoading;
    if (textEl) textEl.classList.toggle('hidden', isLoading);
    if (spinnerEl) spinnerEl.classList.toggle('hidden', !isLoading);
  }

  // ---- Login ----

  async function handleLogin(email, password) {
    hideAuthError();

    // Client-side validation
    if (!email || !password) {
      showAuthError('Please enter your email and password.');
      return;
    }

    var btn = document.getElementById('login-btn');
    setButtonLoading(btn, true);

    try {
      var res = await window.HrApi.apiPost('/auth/login', {
        email: email,
        password: password
      });

      // Success — store tokens and switch to chat
      storeAuth(res.access_token, res.refresh_token, res.user);
      window.HrApi.setToken(res.access_token);

      // Update app state
      if (window.HrApp) {
        window.HrApp.setState('auth', {
          user: res.user,
          isAuthenticated: true
        });
        window.HrApp.showChatPage();
      }

      // Start token refresh timer
      scheduleTokenRefresh();

    } catch (e) {
      if (e instanceof window.HrApi.HrApiError) {
        showAuthError(e.detail);
      } else {
        showAuthError('Login failed. Please try again.');
      }
    } finally {
      setButtonLoading(btn, false);
    }
  }

  // ---- Register ----

  async function handleRegister(name, email, department, role, password, confirmPassword) {
    hideAuthError();

    // Client-side validations
    if (!name || name.trim().length < 2) {
      showAuthError('Please enter your full name (at least 2 characters).');
      return;
    }
    if (!validateEmail(email)) {
      showAuthError('Please enter a valid email address.');
      return;
    }
    if (!department) {
      showAuthError('Please select your department.');
      return;
    }
    if (!role) {
      showAuthError('Please select your role.');
      return;
    }

    var pwCheck = validatePassword(password);
    if (!pwCheck.valid) {
      showAuthError('Password requirements: ' + pwCheck.errors.join(', ') + '.');
      return;
    }
    if (password !== confirmPassword) {
      showAuthError('Passwords do not match.');
      return;
    }

    var btn = document.querySelector('#register-form button[type="submit"]');
    setButtonLoading(btn, true);

    try {
      await window.HrApi.apiPost('/auth/register', {
        email: email,
        password: password,
        full_name: name.trim(),
        role: role,
        department: department
      });

      // Show success and switch back to login
      var successEl = document.getElementById('auth-success');
      if (successEl) {
        successEl.textContent = 'Account created successfully! Please sign in.';
        successEl.classList.remove('hidden');
      }

      // Switch to login form
      showLoginForm();

      // Clear registration fields
      var form = document.getElementById('register-form');
      if (form) form.reset();

    } catch (e) {
      if (e instanceof window.HrApi.HrApiError) {
        if (e.status === 409) {
          showAuthError('This email is already registered. Please use a different email or sign in.');
        } else {
          showAuthError(e.detail);
        }
      } else {
        showAuthError('Registration failed. Please try again.');
      }
    } finally {
      setButtonLoading(btn, false);
    }
  }

  // ---- Logout ----

  function handleLogout() {
    if (window.HrStream && window.HrStream.isStreaming()) {
      window.HrStream.stopStream();
    }

    clearAuth();
    window.HrApi.setToken(null);
    _stopTokenRefresh();

    if (window.HrApp) {
      window.HrApp.setState('auth', { user: null, isAuthenticated: false });
      window.HrApp.setState('chat', { activeSessionId: null, sessions: [], messages: [], isStreaming: false });
      window.HrApp.showLoginPage();
    }
  }

  // ---- Token Refresh ----

  async function refreshAccessToken() {
    var refreshToken = localStorage.getItem('hr_auth_refresh');
    if (!refreshToken) {
      handleLogout();
      return null;
    }

    try {
      // Use raw fetch — don't use HrApi which would use the expired token
      var response = await fetch(window.HrApi.BASE_URL + '/auth/refresh', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + refreshToken,
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        // Refresh failed — force logout
        handleLogout();
        return null;
      }

      var data = await response.json();
      var newAccessToken = data.access_token;

      // Store new access token
      localStorage.setItem('hr_auth_token', newAccessToken);
      window.HrApi.setToken(newAccessToken);

      // Reschedule
      scheduleTokenRefresh();

      return newAccessToken;

    } catch (e) {
      // Network error during refresh — don't logout, just fail silently
      // The next API call will retry
      console.warn('Token refresh failed:', e);
      return null;
    }
  }

  function scheduleTokenRefresh() {
    _stopTokenRefresh();
    // Refresh every 55 minutes (token lifetime is 60 min)
    refreshTimer = setInterval(refreshAccessToken, 55 * 60 * 1000);
  }

  function _stopTokenRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  // ---- UI Toggle (Login ↔ Register) ----

  function showLoginForm() {
    var loginForm = document.getElementById('login-form');
    var regSection = document.getElementById('register-section');
    var authError = document.getElementById('auth-error');
    var authSuccess = document.getElementById('auth-success');

    if (loginForm) loginForm.parentElement.style.display = '';
    if (regSection) regSection.classList.add('hidden');
    if (authError) authError.classList.add('hidden');
    if (authSuccess) authSuccess.classList.add('hidden');
  }

  function showRegisterForm() {
    var loginForm = document.getElementById('login-form');
    var regSection = document.getElementById('register-section');
    var authError = document.getElementById('auth-error');
    var authSuccess = document.getElementById('auth-success');

    if (loginForm) loginForm.parentElement.style.display = 'none';
    if (regSection) regSection.classList.remove('hidden');
    if (authError) authError.classList.add('hidden');
    if (authSuccess) authSuccess.classList.add('hidden');
  }

  // ---- Form Binding ----

  function bindLoginForm(formEl) {
    if (!formEl) return;

    formEl.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = document.getElementById('login-email').value.trim();
      var password = document.getElementById('login-password').value;
      handleLogin(email, password);
    });
  }

  function bindRegisterForm(formEl) {
    if (!formEl) return;

    formEl.addEventListener('submit', function (e) {
      e.preventDefault();
      var name = document.getElementById('reg-name').value;
      var email = document.getElementById('reg-email').value.trim();
      var department = document.getElementById('reg-department').value;
      var role = document.getElementById('reg-role').value;
      var password = document.getElementById('reg-password').value;
      var confirmPassword = document.getElementById('reg-confirm').value;
      handleRegister(name, email, department, role, password, confirmPassword);
    });
  }

  // ---- Expose Module ----

  window.HrAuth = {
    handleLogin: handleLogin,
    handleRegister: handleRegister,
    handleLogout: handleLogout,
    storeAuth: storeAuth,
    clearAuth: clearAuth,
    getStoredAuth: getStoredAuth,
    refreshAccessToken: refreshAccessToken,
    scheduleTokenRefresh: scheduleTokenRefresh,
    validateEmail: validateEmail,
    validatePassword: validatePassword,
    bindLoginForm: bindLoginForm,
    bindRegisterForm: bindRegisterForm,
    showLoginForm: showLoginForm,
    showRegisterForm: showRegisterForm
  };
})();
