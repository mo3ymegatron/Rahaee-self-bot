// ================================================================
// فایل اسکریپت اصلی رهایی - Rahaei Script
// ================================================================

(function() {
    'use strict';

    // ============================================================
    // مدیریت نوار کناری
    // ============================================================
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('toggleSidebar');
    const mainContent = document.getElementById('mainContent');

    if (toggleBtn && sidebar && mainContent) {
        toggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
            
            // ذخیره وضعیت در localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        });

        // بازیابی وضعیت از localStorage
        const savedState = localStorage.getItem('sidebarCollapsed');
        if (savedState === 'true') {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('expanded');
        }
    }

    // بستن نوار کناری در موبایل با کلیک خارج
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 768) {
            if (sidebar && sidebar.classList.contains('open')) {
                if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                    sidebar.classList.remove('open');
                }
            }
        }
    });

    // باز کردن نوار کناری در موبایل
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                e.stopPropagation();
                sidebar.classList.toggle('open');
            }
        });
    }

    // ============================================================
    // ساعت زنده
    // ============================================================
    function updateClock() {
        const clockElement = document.getElementById('headerTime');
        if (clockElement) {
            const now = new Date();
            const time = now.toLocaleTimeString('fa-IR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            clockElement.textContent = time;
        }
    }

    // راه‌اندازی ساعت
    updateClock();
    setInterval(updateClock, 1000);

    // ============================================================
    // WebSocket
    // ============================================================
    let socket = null;
    let socketConnected = false;

    function initSocket() {
        try {
            socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: 5,
                reconnectionDelay: 1000
            });

            socket.on('connect', function() {
                console.log('🔌 WebSocket connected');
                socketConnected = true;
                updateConnectionStatus(true);
            });

            socket.on('disconnect', function() {
                console.log('🔌 WebSocket disconnected');
                socketConnected = false;
                updateConnectionStatus(false);
            });

            socket.on('reconnect', function() {
                console.log('🔌 WebSocket reconnected');
                socketConnected = true;
                updateConnectionStatus(true);
            });

            socket.on('realtime_stats', function(data) {
                updateRealtimeStats(data);
            });

            socket.on('notification', function(data) {
                showNotification(data.type || 'info', data.message);
            });

        } catch (error) {
            console.error('WebSocket initialization error:', error);
        }
    }

    function updateConnectionStatus(connected) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-text');
        
        if (statusDot && statusText) {
            if (connected) {
                statusDot.className = 'status-dot online';
                statusText.textContent = 'آنلاین';
            } else {
                statusDot.className = 'status-dot offline';
                statusText.textContent = 'آفلاین';
            }
        }
    }

    function updateRealtimeStats(data) {
        if (data.online_users !== undefined) {
            const el = document.getElementById('onlineUsers');
            if (el) el.textContent = data.online_users;
        }
        if (data.uptime !== undefined) {
            const el = document.getElementById('uptime');
            if (el) el.textContent = data.uptime;
        }
        if (data.total_users !== undefined) {
            const el = document.getElementById('totalUsers');
            if (el) el.textContent = data.total_users;
        }
        if (data.messages_today !== undefined) {
            const el = document.getElementById('messagesToday');
            if (el) el.textContent = data.messages_today;
        }
        if (data.commands_today !== undefined) {
            const el = document.getElementById('commandsToday');
            if (el) el.textContent = data.commands_today;
        }
    }

    // راه‌اندازی WebSocket
    if (typeof io !== 'undefined') {
        initSocket();
    }

    // ============================================================
    // مدیریت اعلان‌ها
    // ============================================================
    const notificationContainer = document.createElement('div');
    notificationContainer.id = 'notificationContainer';
    notificationContainer.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        direction: rtl;
        max-width: 400px;
        width: 100%;
        pointer-events: none;
    `;
    document.body.appendChild(notificationContainer);

    window.showNotification = function(type, message, duration = 5000) {
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            background: ${colors[type] || '#3b82f6'};
            color: white;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideInRight 0.3s ease;
            pointer-events: auto;
            font-family: 'Vazirmatn', sans-serif;
            font-size: 14px;
            min-width: 280px;
        `;
        
        notification.innerHTML = `
            <i class="fas ${icons[type] || 'fa-info-circle'}" style="font-size: 20px;"></i>
            <span style="flex: 1;">${message}</span>
            <button class="notification-close" style="
                background: none;
                border: none;
                color: rgba(255,255,255,0.7);
                cursor: pointer;
                font-size: 16px;
                padding: 0 5px;
                transition: color 0.2s;
                pointer-events: auto;
            ">
                <i class="fas fa-times"></i>
            </button>
        `;

        notification.querySelector('.notification-close').addEventListener('click', function() {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        });

        notificationContainer.appendChild(notification);

        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, duration);
    };

    // اضافه کردن استایل‌های انیمیشن اعلان‌ها
    const notificationStyles = document.createElement('style');
    notificationStyles.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(notificationStyles);

    // ============================================================
    // مدیریت فرم‌ها (Ajax)
    // ============================================================
    document.querySelectorAll('form[data-ajax]').forEach(form => {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const url = this.action || window.location.href;
            const method = this.method || 'POST';
            const formData = new FormData(this);
            
            // نمایش لودینگ
            const submitBtn = this.querySelector('[type="submit"]');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner spin"></i> در حال ارسال...';
                submitBtn.disabled = true;
            }

            try {
                const response = await fetch(url, {
                    method: method,
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const data = await response.json();

                if (data.success) {
                    showNotification('success', data.message || 'عملیات با موفقیت انجام شد');
                    if (data.redirect) {
                        setTimeout(() => window.location.href = data.redirect, 1000);
                    }
                    if (data.reset) {
                        this.reset();
                    }
                } else {
                    showNotification('error', data.error || 'خطا در انجام عملیات');
                }
            } catch (error) {
                console.error('Form submission error:', error);
                showNotification('error', 'خطا در ارتباط با سرور');
            } finally {
                if (submitBtn) {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            }
        });
    });

    // ============================================================
    // مدیریت کشیدن و رها کردن (Drag & Drop)
    // ============================================================
    document.querySelectorAll('[data-draggable]').forEach(element => {
        let isDragging = false;
        let startX, startY, originalX, originalY;

        element.addEventListener('mousedown', function(e) {
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = this.getBoundingClientRect();
            originalX = rect.left;
            originalY = rect.top;
            this.style.cursor = 'grabbing';
        });

        document.addEventListener('mousemove', function(e) {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            element.style.left = (originalX + dx) + 'px';
            element.style.top = (originalY + dy) + 'px';
            element.style.position = 'fixed';
            element.style.zIndex = 1000;
        });

        document.addEventListener('mouseup', function() {
            if (isDragging) {
                isDragging = false;
                element.style.cursor = 'grab';
            }
        });
    });

    // ============================================================
    // مدیریت کلیدهای میانبر
    // ============================================================
    document.addEventListener('keydown', function(e) {
        // Ctrl + / برای نمایش راهنما
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            showNotification('info', '📖 برای مشاهده راهنما از دکمه Help استفاده کنید');
        }

        // Escape برای بستن مودال‌ها
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
        }
    });

    // ============================================================
    // توابع عمومی
    // ============================================================
    
    // تابع کپی کردن متن
    window.copyToClipboard = function(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => showNotification('success', '✅ متن کپی شد'))
                .catch(() => fallbackCopy(text));
        } else {
            fallbackCopy(text);
        }
    };

    function fallbackCopy(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            showNotification('success', '✅ متن کپی شد');
        } catch (err) {
            showNotification('error', '❌ خطا در کپی کردن متن');
        }
        document.body.removeChild(textarea);
    }

    // تابع تبدیل تاریخ
    window.formatDate = function(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('fa-IR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateString;
        }
    };

    // تابع تبدیل عدد به فارسی
    window.toPersianNumber = function(num) {
        const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
        return String(num).replace(/\d/g, d => persianDigits[parseInt(d)]);
    };

    // ============================================================
    // مقداردهی اولیه
    // ============================================================
    console.log('🚀 Rahaei Web Panel v1.0.0');
    console.log('📱 Developer: @UXlor');
    console.log('✨ Ready to serve!');

})();
