    (function () {
        const cfg = window.whatsAppInboxConfig || {};
        const conversationsEndpoint = cfg.conversationsEndpoint || '';
        let activeConversationId = cfg.activeConversationId || '';
        const messagesEndpointTemplate = cfg.messagesEndpointTemplate || '';
        const forwardMessagesBulkEndpoint = cfg.forwardMessagesBulkEndpoint || '';
        const markReadEndpointTemplate = cfg.markReadEndpointTemplate || '';
        const archiveConversationEndpointTemplate = cfg.archiveConversationEndpointTemplate || '';
        const deleteConversationEndpointTemplate = cfg.deleteConversationEndpointTemplate || '';
        const editMessageEndpointTemplate = cfg.editMessageEndpointTemplate || '';
        const deleteMessageEndpointTemplate = cfg.deleteMessageEndpointTemplate || '';
        const listEl = document.getElementById('conversation-list');
        const messagesEl = document.getElementById('message-list');
        let currentQuery = cfg.currentQuery || '';
        const activeNameEl = document.getElementById('active-contact-name');
        const activeAvatarEl = document.getElementById('active-contact-avatar');
        const activeLabelsEl = document.getElementById('active-contact-labels');
        const activePresenceEl = document.getElementById('active-contact-presence');
        const imagePreviewModal = document.getElementById('imagePreviewModal');
        const imagePreviewTarget = document.getElementById('imagePreviewTarget');
        const imagePreviewClose = document.getElementById('imagePreviewClose');
        const composeMediaModal = document.getElementById('composeMediaModal');
        const composeMediaPreview = document.getElementById('composeMediaPreview');
        const composeMediaPreviewWrap = document.getElementById('composeMediaPreviewWrap');
        const composeMediaTitle = document.getElementById('composeMediaTitle');
        const composeMediaCount = document.getElementById('composeMediaCount');
        const composeMediaFiles = document.getElementById('composeMediaFiles');
        const composeMediaCaption = document.getElementById('composeMediaCaption');
        const composeMediaClose = document.getElementById('composeMediaClose');
        const composeMediaCancelBtn = document.getElementById('composeMediaCancelBtn');
        const composeMediaSendBtn = document.getElementById('composeMediaSendBtn');
        const composeMediaAddBtn = document.getElementById('composeMediaAddBtn');
        const composeMediaAddInput = document.getElementById('composeMediaAddInput');
        const forwardTargetModal = document.getElementById('forwardTargetModal');
        const forwardTargetClose = document.getElementById('forwardTargetClose');
        const forwardTargetSearch = document.getElementById('forwardTargetSearch');
        const forwardTargetList = document.getElementById('forwardTargetList');
        const forwardTargetCount = document.getElementById('forwardTargetCount');
        const forwardTargetCancelBtn = document.getElementById('forwardTargetCancelBtn');
        const forwardTargetSendBtn = document.getElementById('forwardTargetSendBtn');
        const editMessageModal = document.getElementById('editMessageModal');
        const editMessageClose = document.getElementById('editMessageClose');
        const editMessageCancelBtn = document.getElementById('editMessageCancelBtn');
        const editMessageSaveBtn = document.getElementById('editMessageSaveBtn');
        const editMessageInput = document.getElementById('editMessageInput');
        const editMessagePreviewBubble = document.getElementById('editMessagePreviewBubble');
        const forwardSelectionBar = document.getElementById('forwardSelectionBar');
        const forwardSelectionCount = document.getElementById('forwardSelectionCount');
        const forwardCancelBtn = document.getElementById('forwardCancelBtn');
        const forwardSendBtn = document.getElementById('forwardSendBtn');
        const defaultAvatar = 'https://ui-avatars.com/api/?name=Contato&background=e2e8f0&color=64748b&size=256&rounded=true';
        const AUTO_SCROLL_THRESHOLD = 90;
        let firstMessagesRender = true;
        let lastConversationsSignature = '';
        let lastMessagesSignature = '';
        let pollConversationsRunning = false;
        let pollMessagesRunning = false;
        let pollingEnabled = true;
        let messagesRequestSeq = 0;
        let conversationsRequestSeq = 0;
        let activeMenuMessageId = null;
        let forwardSelectionMode = false;
        const selectedForwardMessageIds = new Set();
        let latestConversationsCache = [];
        const selectedForwardTargets = new Set();
        let editingMessageId = null;

        function esc(str) {
            return (str || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
        }

        function normalizeMediaUrl(url) {
            const raw = String(url || '').trim();
            if (!raw) return '';
            const low = raw.toLowerCase();
            if (low.startsWith('data:')) return raw;
            if (raw.startsWith('//')) return `https:${raw}`;
            if (low.startsWith('http://') || low.startsWith('https://')) return raw;
            if (raw.startsWith('/')) return `https://mmg.whatsapp.net${raw}`;
            return raw;
        }

        function mediaMarkup(mediaUrl, mediaKind) {
            const normalizedUrl = normalizeMediaUrl(mediaUrl);
            if (!normalizedUrl) return '';
            const kind = (mediaKind || '').toLowerCase();
            if (kind === 'audio') return `<span class="bubble-media"><audio controls><source src="${normalizedUrl}"></audio></span>`;
            if (kind === 'video') return `<span class="bubble-media media-video"><video controls preload="metadata"><source src="${normalizedUrl}"></video></span>`;
            if (kind === 'sticker') return `<span class="bubble-media media-sticker"><img src="${normalizedUrl}" alt="figurinha" class="js-chat-image" data-full-src="${normalizedUrl}"></span>`;
            if (kind === 'image') return `<span class="bubble-media media-image"><img src="${normalizedUrl}" alt="midia" class="js-chat-image" data-full-src="${normalizedUrl}"></span>`;
            const url = normalizedUrl.toLowerCase();
            if (url.startsWith('data:image/')) return `<span class="bubble-media media-image"><img src="${normalizedUrl}" alt="midia" class="js-chat-image" data-full-src="${normalizedUrl}"></span>`;
            if (url.startsWith('data:video/')) return `<span class="bubble-media media-video"><video controls preload="metadata"><source src="${normalizedUrl}"></video></span>`;
            if (url.startsWith('data:audio/')) return `<span class="bubble-media"><audio controls><source src="${normalizedUrl}"></audio></span>`;
            if (url.includes('.mp3') || url.includes('.ogg') || url.includes('.wav') || url.includes('.opus') || url.includes('.m4a') || url.includes('.aac')) return `<span class="bubble-media"><audio controls><source src="${normalizedUrl}"></audio></span>`;
            if (url.includes('.mp4') || url.includes('.webm') || url.includes('.mov')) return `<span class="bubble-media media-video"><video controls preload="metadata"><source src="${normalizedUrl}"></video></span>`;
            if (url.includes('.jpg') || url.includes('.jpeg') || url.includes('.png') || url.includes('.gif') || url.includes('.webp')) return `<span class="bubble-media media-image"><img src="${normalizedUrl}" alt="midia" class="js-chat-image" data-full-src="${normalizedUrl}"></span>`;
            return `<span class="bubble-media"><a href="${normalizedUrl}" target="_blank" class="btn btn-sm btn-outline-secondary">Abrir arquivo</a></span>`;
        }

        function reactionMarkup(messageId) {
            return `<div class="reaction-row reaction-hidden" id="reaction-row-${messageId}"><button type="button" class="reaction-btn" onclick="sendReaction(${messageId}, '\\uD83D\\uDC4D')">&#128077;</button><button type="button" class="reaction-btn" onclick="sendReaction(${messageId}, '\\u2764\\uFE0F')">&#10084;&#65039;</button><button type="button" class="reaction-btn" onclick="sendReaction(${messageId}, '\\uD83D\\uDE02')">&#128514;</button><button type="button" class="reaction-btn" onclick="sendReaction(${messageId}, '\\uD83D\\uDE4F')">&#128591;</button></div>`;
        }

        function reactionBadgeMarkup(emoji) {
            const value = String(emoji || '').trim();
            if (!value) return '';
            return `<div class="message-reaction-badge">${esc(value)}</div>`;
        }

        function statusIconMarkup(message) {
            if (!message || message.direcao !== 'OUT') return '';
            const statusCode = (message.status_code || '').toLowerCase();
            const statusText = esc(message.status || '');
            if (statusCode === 'read') {
                return `<span class="message-status-icon read" title="${statusText}"><i class="fa-solid fa-check-double"></i></span>`;
            }
            if (statusCode === 'delivered') {
                return `<span class="message-status-icon" title="${statusText}"><i class="fa-solid fa-check-double"></i></span>`;
            }
            if (statusCode === 'failed') {
                return `<span class="message-status-icon text-danger" title="${statusText}"><i class="fa-solid fa-triangle-exclamation"></i></span>`;
            }
            return `<span class="message-status-icon" title="${statusText}"><i class="fa-solid fa-check"></i></span>`;
        }

        function menuMarkup(message) {
            const mediaUrl = normalizeMediaUrl(message.media_url || '');
            const text = message.conteudo || '';
            const noMedia = mediaUrl ? '' : 'disabled';
            const encMedia = encodeURIComponent(mediaUrl);
            const encText = encodeURIComponent(text);
            const editBtn = message.direcao === 'OUT'
                ? `<button type="button" onclick="messageAction(event, 'edit', ${message.id}, '${encText}')">Editar</button>`
                : '';
            return `<button type="button" class="message-menu-trigger" onclick="toggleMessageMenu(event, ${message.id})">&#8942;</button>
                <div class="message-menu" id="msg-menu-${message.id}">
                    <button type="button" onclick="messageAction(event, 'forward', ${message.id}, '')">Encaminhar</button>
                    <button type="button" onclick="messageAction(event, 'download', ${message.id}, '${encMedia}')" ${noMedia}>Download</button>
                    <button type="button" onclick="messageAction(event, 'reply', ${message.id}, '${encText}')">Responder</button>
                    <button type="button" onclick="messageAction(event, 'react', ${message.id}, '', this)">Reagir</button>
                    ${editBtn}
                    <button type="button" class="text-danger" onclick="messageAction(event, 'delete', ${message.id}, '')">Excluir</button>
                </div>`;
        }

        function updateHeaderByConversation(c) {
            if (!c) return;
            if (activeNameEl) {
                activeNameEl.innerHTML = `${esc(c.nome || c.wa_id_display || c.wa_id || 'Contato')}<br><span id="active-contact-jid">${esc(c.wa_id_display || c.wa_id || '')}</span>`;
            }
            if (activeAvatarEl) {
                activeAvatarEl.src = c.avatar_url || defaultAvatar;
            }
            if (activeLabelsEl) {
                activeLabelsEl.innerHTML = (c.etiquetas || []).map((t) => `<span class="label-chip">${esc(t)}</span>`).join('');
            }
            if (activePresenceEl) {
                activePresenceEl.textContent = c.presence_text || '';
            }
            if (archiveConversationActionInput) {
                archiveConversationActionInput.value = c.arquivada ? 'unarchive' : 'archive';
            }
            if (archiveConversationBtn) {
                archiveConversationBtn.textContent = c.arquivada ? 'Desarquivar' : 'Arquivar';
            }
        }

        function endpointFromTemplate(template, conversationId) {
            if (!conversationId) return '';
            return template.replace('/0/', `/${conversationId}/`);
        }

        function setActiveConversationId(conversationId) {
            activeConversationId = String(conversationId || '');
            document.querySelectorAll('#conversation-list .chat-box').forEach((el) => {
                el.classList.toggle('active', String(el.dataset.conversationId || '') === activeConversationId);
            });
            if (sendMessageForm) {
                const input = sendMessageForm.querySelector('input[name="conversa_id"]');
                if (input) input.value = activeConversationId;
            }
            if (markReadForm) {
                markReadForm.setAttribute('action', endpointFromTemplate(markReadEndpointTemplate, activeConversationId));
            }
            if (deleteConversationForm) {
                deleteConversationForm.setAttribute('action', endpointFromTemplate(deleteConversationEndpointTemplate, activeConversationId));
            }
            if (archiveConversationForm) {
                archiveConversationForm.setAttribute('action', endpointFromTemplate(archiveConversationEndpointTemplate, activeConversationId));
            }
        }

        function renderConversations(conversas) {
            if (!listEl) return;
            latestConversationsCache = Array.isArray(conversas) ? conversas : [];
            const signature = JSON.stringify((conversas || []).map((c) => ({
                id: c.id,
                nome: c.nome || '',
                avatar_url: c.avatar_url || '',
                ultima_mensagem: c.ultima_mensagem || '',
                ultima_mensagem_em: c.ultima_mensagem_em || '',
                nao_lidas: Number(c.nao_lidas || 0),
                arquivada: !!c.arquivada,
                presence_text: c.presence_text || '',
                etiquetas: c.etiquetas || [],
            })));
            const activeConversation = (conversas || []).find((c) => String(c.id) === String(activeConversationId));
            updateHeaderByConversation(activeConversation);
            if (signature === lastConversationsSignature) return;
            lastConversationsSignature = signature;

            const previousScrollTop = listEl.scrollTop;
            const baseUrl = cfg.inboxBaseUrl || '/whatsapp/';
            const activeItems = (conversas || []).filter((c) => !c.arquivada);
            const archivedItems = (conversas || []).filter((c) => !!c.arquivada);
            const renderItem = (c, archived) => {
                const activeClass = String(c.id) === String(activeConversationId) ? 'active' : '';
                const unreadCount = Number(c.nao_lidas || 0);
                const unreadClass = unreadCount > 0 ? 'unread' : '';
                const unreadBadge = unreadCount > 0 ? `<b>${unreadCount}</b>` : '';
                const avatar = c.avatar_url ? c.avatar_url : defaultAvatar;
                const tags = (c.etiquetas || []).slice(0, 3).map((t) => `<span class="label-chip">${esc(t)}</span>`).join('');
                const tagsRow = tags ? `<div class="label-row">${tags}</div>` : '';
                return `<a class="chat-box ${archived ? 'archived' : ''} ${activeClass}" href="${baseUrl}?c=${c.id}" data-conversation-id="${c.id}"><div class="img-box"><img class="dp" src="${avatar}" alt="Contato"></div><div class="chat-details"><div class="text-head"><h4>${esc(c.nome)}</h4><p class="time ${unreadClass}">${esc(c.ultima_mensagem_em)}</p></div><div class="text-message"><p>${esc((c.ultima_mensagem || '').slice(0, 42))}</p>${unreadBadge}</div>${tagsRow}</div></a>`;
            };
            const activeHtml = activeItems.map((c) => renderItem(c, false)).join('');
            const archivedHtml = archivedItems.length
                ? `<div class="archive-divider"><span><i class="fa-regular fa-box-archive"></i> Arquivadas</span><b>${archivedItems.length}</b></div>${archivedItems.map((c) => renderItem(c, true)).join('')}`
                : '';
            listEl.innerHTML = `${activeHtml}${archivedHtml}` || '<div class="p-3 text-muted">Nenhuma conversa encontrada.</div>';
            listEl.scrollTop = previousScrollTop;
        }

        function renderMessages(mensagens) {
            if (!messagesEl) return;
            const distanceFromBottom = messagesEl.scrollHeight - (messagesEl.scrollTop + messagesEl.clientHeight);
            const shouldStickToBottom = firstMessagesRender || distanceFromBottom <= AUTO_SCROLL_THRESHOLD;
            const sanitizeText = (value) => String(value || '').replace(/[\u200B-\u200D\uFEFF\u200E\u200F]/g, '').trim();
            const safeMessages = (mensagens || []).filter((m) => {
                const hasText = !!sanitizeText(m && m.conteudo);
                const hasMedia = !!(m && m.media_url && String(m.media_url).trim());
                return hasText || hasMedia || m.direcao === 'SYSTEM';
            });
            const signature = JSON.stringify((safeMessages || []).map((m) => ({
                id: m.id,
                d: m.direcao,
                c: m.conteudo || '',
                u: m.media_url || '',
                k: m.media_kind || '',
                s: m.status_code || '',
                r: m.reaction_emoji || '',
                e: !!m.is_edited,
                t: m.criado_em || '',
            })));
            if (signature === lastMessagesSignature) return;
            lastMessagesSignature = signature;
            messagesEl.innerHTML = safeMessages.map((m) => {
                const side = m.direcao === 'OUT' ? 'my-message' : (m.direcao === 'SYSTEM' ? 'system-message' : 'friend-message');
                const kind = String(m.media_kind || '').toLowerCase();
                let cleanedText = sanitizeText(m.conteudo);
                if ((kind === 'document') && (cleanedText === '[DOCUMENT]' || cleanedText === '[ARQUIVO]')) {
                    cleanedText = '';
                }
                if ((kind === 'image' || kind === 'video' || kind === 'audio' || kind === 'sticker') && (cleanedText === '[IMAGEM]' || cleanedText === '[VIDEO]' || cleanedText === '[AUDIO]' || cleanedText === '[FIGURINHA]' || cleanedText === '[DOCUMENTO]')) {
                    cleanedText = '';
                }
                const textHtml = esc(cleanedText).replaceAll('\n', '<br>');
                const reactionRow = reactionMarkup(m.id);
                const reactionBadge = reactionBadgeMarkup(m.reaction_emoji);
                const timeText = esc((m.criado_em || '').split(' ')[1] || m.criado_em || '');
                const messageText = textHtml ? `<div class="message-text">${textHtml}</div>` : '';
                const hasMedia = !!m.media_url;
                const isVisualMedia = kind === 'image' || kind === 'video' || kind === 'sticker';
                const mediaOnly = hasMedia && !cleanedText && isVisualMedia;
                const bubbleClass = `message-bubble${hasMedia ? ' has-media' : ''}${mediaOnly ? ' media-only' : ''}`;
                const editedBadge = m.is_edited ? '<span class="message-edited">editada</span>' : '';
                const isSelected = selectedForwardMessageIds.has(Number(m.id));
                const selectedClass = isSelected ? 'is-selected' : '';
                const checkClass = isSelected ? 'selected' : '';
                return `<div class="message-box ${side} ${selectedClass}" data-message-id="${m.id}"><button type="button" class="forward-check ${checkClass}" onclick="toggleForwardMessageSelection(event, ${m.id})"><i class="fa-solid fa-check"></i></button><div class="${bubbleClass}">${menuMarkup(m)}${mediaMarkup(m.media_url, m.media_kind)}${messageText}<div class="message-meta">${editedBadge}<span class="message-time">${timeText}</span>${statusIconMarkup(m)}</div>${reactionBadge}${reactionRow}</div></div>`;
            }).join('');
            updateForwardSelectionUi();
            if (shouldStickToBottom) {
                messagesEl.scrollTop = messagesEl.scrollHeight;
            }
            firstMessagesRender = false;
        }

        function updateForwardSelectionUi() {
            if (!messagesEl) return;
            messagesEl.classList.toggle('forward-mode', !!forwardSelectionMode);
            const rightContainer = messagesEl.closest('.right-container');
            if (rightContainer) rightContainer.classList.toggle('forward-selection-active', !!forwardSelectionMode);
            if (forwardSelectionBar) forwardSelectionBar.classList.toggle('show', !!forwardSelectionMode);
            if (forwardSelectionCount) {
                const total = selectedForwardMessageIds.size;
                forwardSelectionCount.textContent = `${total} selecionada${total === 1 ? '' : 's'}`;
            }
            document.querySelectorAll('#message-list .message-box').forEach((box) => {
                const id = Number(box.getAttribute('data-message-id') || '0');
                const selected = selectedForwardMessageIds.has(id);
                box.classList.toggle('is-selected', selected);
                const check = box.querySelector('.forward-check');
                if (check) check.classList.toggle('selected', selected);
            });
        }

        function exitForwardSelectionMode() {
            forwardSelectionMode = false;
            selectedForwardMessageIds.clear();
            updateForwardSelectionUi();
        }

        function enterForwardSelectionMode(initialMessageId) {
            forwardSelectionMode = true;
            if (initialMessageId) selectedForwardMessageIds.add(Number(initialMessageId));
            closeAllMessageMenus();
            updateForwardSelectionUi();
        }

        window.toggleForwardMessageSelection = function (event, messageId) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            const id = Number(messageId || 0);
            if (!id) return;
            if (!forwardSelectionMode) forwardSelectionMode = true;
            if (selectedForwardMessageIds.has(id)) {
                selectedForwardMessageIds.delete(id);
            } else {
                selectedForwardMessageIds.add(id);
            }
            if (!selectedForwardMessageIds.size) {
                exitForwardSelectionMode();
                return;
            }
            updateForwardSelectionUi();
        };

        function closeAllMessageMenus(exceptMessageId = null) {
            document.querySelectorAll('.message-menu.open').forEach((menu) => {
                if (exceptMessageId && menu.id === `msg-menu-${exceptMessageId}`) return;
                menu.classList.remove('open');
            });
            document.querySelectorAll('.message-bubble.has-open-menu').forEach((bubble) => bubble.classList.remove('has-open-menu'));
            document.querySelectorAll('.message-menu-trigger.force-show').forEach((btn) => btn.classList.remove('force-show'));
            if (!exceptMessageId) activeMenuMessageId = null;
        }

        function normalizeRenderedMediaUrls() {
            document.querySelectorAll('#message-list img[src], #message-list video source[src], #message-list audio source[src], #message-list a[href]').forEach((el) => {
                const attr = el.hasAttribute('src') ? 'src' : 'href';
                const current = el.getAttribute(attr) || '';
                const normalized = normalizeMediaUrl(current);
                if (normalized && normalized !== current) {
                    el.setAttribute(attr, normalized);
                    if (el.classList && el.classList.contains('js-chat-image')) {
                        el.setAttribute('data-full-src', normalized);
                    }
                }
            });
        }

        window.toggleMessageMenu = function (event, messageId) {
            event.preventDefault();
            event.stopPropagation();
            const menu = document.getElementById(`msg-menu-${messageId}`);
            const trigger = event.currentTarget;
            const bubble = trigger ? trigger.closest('.message-bubble') : null;
            if (!menu) return;
            const willOpen = !menu.classList.contains('open');
            closeAllMessageMenus();
            if (willOpen) {
                menu.classList.add('open');
                if (trigger) trigger.classList.add('force-show');
                if (bubble) bubble.classList.add('has-open-menu');
                activeMenuMessageId = messageId;
            }
        };

        window.messageAction = async function (eventOrAction, actionOrMessageId, messageIdOrPayload, payloadOrSourceEl, maybeSourceEl) {
            let event = null;
            let action = '';
            let messageId = '';
            let payload = '';
            let sourceEl = null;

            if (typeof eventOrAction === 'string') {
                // Compatibilidade com assinatura antiga: messageAction(action, messageId, payload, sourceEl)
                action = eventOrAction;
                messageId = actionOrMessageId;
                payload = messageIdOrPayload;
                sourceEl = payloadOrSourceEl || null;
            } else {
                // Assinatura nova: messageAction(event, action, messageId, payload, sourceEl)
                event = eventOrAction;
                action = actionOrMessageId;
                messageId = messageIdOrPayload;
                payload = payloadOrSourceEl;
                sourceEl = maybeSourceEl || null;
            }

            if (event && typeof event.preventDefault === 'function') {
                event.preventDefault();
            }
            if (event && typeof event.stopPropagation === 'function') {
                event.stopPropagation();
            }
            const decodePayload = (val) => {
                try {
                    return decodeURIComponent(val || '');
                } catch (e) {
                    return val || '';
                }
            };
            if (action === 'react') {
                openEmojiPicker(messageId, sourceEl || null);
            } else if (action === 'download') {
                const decoded = normalizeMediaUrl(decodePayload(payload));
                if (decoded) {
                    window.open(decoded, '_blank');
                } else {
                    alert('Esta mensagem nao possui arquivo para download.');
                }
            } else if (action === 'reply') {
                const decoded = decodePayload(payload);
                const input = document.querySelector('.chatbox-input input[name="mensagem"]');
                if (input) {
                    const base = (decoded || '').replace(/\s+/g, ' ').trim().slice(0, 80);
                    input.value = base ? `Respondendo: ${base}\n` : 'Respondendo:\n';
                    input.focus();
                }
            } else if (action === 'edit') {
                const decoded = decodePayload(payload);
                openEditMessageModal(messageId, decoded);
            } else if (action === 'forward') {
                enterForwardSelectionMode(messageId);
            } else if (action === 'delete') {
                const ok = window.confirm('Deseja excluir esta mensagem?');
                if (!ok) {
                    closeAllMessageMenus();
                    return;
                }
                try {
                    const endpoint = deleteMessageEndpointTemplate.replace('/0/', `/${messageId}/`);
                    const formData = new URLSearchParams();
                    formData.append('ajax', '1');
                    const resp = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json',
                        },
                        body: formData.toString(),
                    });
                    const data = await resp.json();
                    if (!resp.ok || !data || !data.ok) {
                        alert((data && data.error) ? data.error : 'Nao foi possivel excluir a mensagem.');
                    } else {
                        lastMessagesSignature = '';
                        lastConversationsSignature = '';
                        await pollMessages();
                        await pollConversations();
                    }
                } catch (e) {
                    alert('Erro ao excluir mensagem.');
                }
            }
            closeAllMessageMenus();
        };

        function closeImagePreview() {
            if (!imagePreviewModal || !imagePreviewTarget) return;
            imagePreviewModal.classList.remove('show');
            imagePreviewModal.setAttribute('aria-hidden', 'true');
            imagePreviewTarget.src = '';
        }

        function openImagePreview(src) {
            if (!imagePreviewModal || !imagePreviewTarget || !src) return;
            imagePreviewTarget.src = normalizeMediaUrl(src);
            imagePreviewModal.classList.add('show');
            imagePreviewModal.setAttribute('aria-hidden', 'false');
        }

        function clearComposeDraft() {
            composeDraftFiles = [];
            composeDraftPreviewUrls.forEach((url) => {
                try { URL.revokeObjectURL(url); } catch (e) {}
            });
            composeDraftPreviewUrls = [];
        }

        function fileGroupKind(file) {
            const type = String((file && file.type) || '').toLowerCase();
            if (type.startsWith('image/') || type.startsWith('video/')) return 'media';
            return 'document';
        }

        function renderComposeMediaModal() {
            if (!composeMediaModal) return;
            const total = composeDraftFiles.length;
            if (composeMediaCount) composeMediaCount.textContent = `${total} arquivo(s) selecionado(s)`;
            if (composeMediaTitle) composeMediaTitle.textContent = composeDraftKind === 'document' ? 'Pré-visualização de documentos' : 'Pré-visualização de mídia';
            if (composeMediaFiles) {
                composeMediaFiles.innerHTML = composeDraftFiles.map((f, idx) => {
                    const sizeKb = Math.max(1, Math.round((Number(f.size || 0) / 1024)));
                    return `<div class="compose-media-file"><div class="name">${esc(f.name || `arquivo_${idx + 1}`)}</div><small>${sizeKb} KB</small></div>`;
                }).join('');
            }
            const firstFile = composeDraftFiles[0] || null;
            const firstUrl = composeDraftPreviewUrls[0] || '';
            const canPreviewImage = !!firstFile && String(firstFile.type || '').toLowerCase().startsWith('image/');
            if (composeMediaPreview && composeMediaPreviewWrap) {
                if (canPreviewImage && firstUrl) {
                    composeMediaPreviewWrap.style.display = '';
                    composeMediaPreview.src = firstUrl;
                } else {
                    composeMediaPreviewWrap.style.display = 'none';
                    composeMediaPreview.src = '';
                }
            }
        }

        function closeComposeMediaModal() {
            if (!composeMediaModal) return;
            composeMediaModal.classList.remove('show');
            composeMediaModal.setAttribute('aria-hidden', 'true');
            clearComposeDraft();
            if (composeMediaPreview) composeMediaPreview.src = '';
            if (composeMediaFiles) composeMediaFiles.innerHTML = '';
            if (composeMediaCount) composeMediaCount.textContent = '0 arquivo(s) selecionado(s)';
            if (composeMediaCaption) composeMediaCaption.value = '';
        }

        function openComposeMediaModal(files, kind, appendMode) {
            const incoming = Array.isArray(files) ? files.filter(Boolean) : [];
            if (!incoming.length || !composeMediaModal) return;
            const baseKind = kind || fileGroupKind(incoming[0]);
            const allowed = incoming.filter((f) => fileGroupKind(f) === baseKind);
            if (!allowed.length) return;

            if (!appendMode || composeDraftKind !== baseKind) {
                clearComposeDraft();
                composeDraftKind = baseKind;
            }
            const currentNames = new Set(composeDraftFiles.map((f) => `${f.name}|${f.size}|${f.type}`));
            allowed.forEach((file) => {
                const signature = `${file.name}|${file.size}|${file.type}`;
                if (currentNames.has(signature)) return;
                composeDraftFiles.push(file);
                composeDraftPreviewUrls.push(URL.createObjectURL(file));
                currentNames.add(signature);
            });
            renderComposeMediaModal();
            composeMediaModal.classList.add('show');
            composeMediaModal.setAttribute('aria-hidden', 'false');
            if (composeMediaCaption) composeMediaCaption.focus();
        }

        function normalizeForwardNumber(rawWaId) {
            const digits = String(rawWaId || '').replace(/\D/g, '');
            if (!digits) return '';
            return digits.startsWith('55') ? digits : `55${digits}`;
        }

        function updateForwardTargetCount() {
            if (!forwardTargetCount) return;
            forwardTargetCount.textContent = `${selectedForwardTargets.size} contato(s) selecionado(s)`;
        }

        function renderForwardTargetsList(searchTerm) {
            if (!forwardTargetList) return;
            const query = String(searchTerm || '').trim().toLowerCase();
            const items = (latestConversationsCache || []).filter((c) => {
                const wa = String(c.wa_id || '').toLowerCase();
                const nome = String(c.nome || '').toLowerCase();
                const display = String(c.wa_id_display || '').toLowerCase();
                const isDirect = wa.includes('@s.whatsapp.net');
                if (!isDirect) return false;
                if (!query) return true;
                return nome.includes(query) || display.includes(query) || wa.includes(query);
            }).slice(0, 200);

            if (!items.length) {
                forwardTargetList.innerHTML = '<div class="p-3 text-muted">Nenhum contato encontrado.</div>';
                return;
            }

            forwardTargetList.innerHTML = items.map((c) => {
                const number = normalizeForwardNumber(c.wa_id || c.wa_id_display || '');
                const selected = selectedForwardTargets.has(number);
                const avatar = c.avatar_url || defaultAvatar;
                return `<div class="forward-target-item ${selected ? 'selected' : ''}" data-forward-number="${number}">
                    <span class="check"><i class="fa-solid fa-check"></i></span>
                    <img class="avatar" src="${avatar}" alt="contato">
                    <div class="meta"><strong>${esc(c.nome || c.wa_id_display || 'Contato')}</strong><small>${esc(c.wa_id_display || '')}</small></div>
                </div>`;
            }).join('');
        }

        function closeForwardTargetModal() {
            if (!forwardTargetModal) return;
            forwardTargetModal.classList.remove('show');
            forwardTargetModal.setAttribute('aria-hidden', 'true');
            selectedForwardTargets.clear();
            updateForwardTargetCount();
            if (forwardTargetSearch) forwardTargetSearch.value = '';
            if (forwardTargetList) forwardTargetList.innerHTML = '';
        }

        function closeEditMessageModal() {
            if (!editMessageModal) return;
            editMessageModal.classList.remove('show');
            editMessageModal.setAttribute('aria-hidden', 'true');
            editingMessageId = null;
            if (editMessageInput) editMessageInput.value = '';
            if (editMessagePreviewBubble) editMessagePreviewBubble.textContent = '';
        }

        function openEditMessageModal(messageId, originalText) {
            if (!editMessageModal) return;
            editingMessageId = Number(messageId || 0);
            const text = String(originalText || '');
            if (editMessageInput) editMessageInput.value = text;
            if (editMessagePreviewBubble) editMessagePreviewBubble.textContent = text || '(sem texto)';
            editMessageModal.classList.add('show');
            editMessageModal.setAttribute('aria-hidden', 'false');
            if (editMessageInput) {
                editMessageInput.focus();
                editMessageInput.setSelectionRange(editMessageInput.value.length, editMessageInput.value.length);
            }
        }

        async function openForwardTargetModal() {
            if (!forwardTargetModal) return;
            if (!latestConversationsCache.length) {
                try {
                    const resp = await fetch(`${conversationsEndpoint}?q=${encodeURIComponent(currentQuery)}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                    if (resp.ok) {
                        const data = await resp.json();
                        if (data && data.ok && Array.isArray(data.conversas)) {
                            latestConversationsCache = data.conversas;
                        }
                    }
                } catch (e) {}
            }
            renderForwardTargetsList('');
            updateForwardTargetCount();
            forwardTargetModal.classList.add('show');
            forwardTargetModal.setAttribute('aria-hidden', 'false');
            if (forwardTargetSearch) forwardTargetSearch.focus();
        }

        function getCsrfToken() {
            const name = 'csrftoken=';
            const parts = document.cookie.split(';');
            for (let i = 0; i < parts.length; i++) {
                const c = parts[i].trim();
                if (c.startsWith(name)) return c.substring(name.length, c.length);
            }
            return '';
        }

        window.sendReaction = async function (messageId, emoji) {
            try {
                const urlTemplate = cfg.reactMessageEndpointTemplate || '';
                const endpoint = urlTemplate.replace('/0/', `/${messageId}/`);
                const formData = new URLSearchParams();
                formData.append('emoji', emoji);
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData.toString()
                });
                const data = await resp.json();
                if (!data.ok) {
                    alert('Erro ao reagir: ' + (data.error || 'falha'));
                    return;
                }
                pollMessages();
            } catch (e) {
                alert('Erro ao enviar reacao.');
            }
        };

        async function pollConversations() {
            if (!pollingEnabled) return;
            if (pollConversationsRunning) return;
            pollConversationsRunning = true;
            const requestSeq = ++conversationsRequestSeq;
            try {
                const resp = await fetch(`${conversationsEndpoint}?q=${encodeURIComponent(currentQuery)}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!resp.ok) return;
                const data = await resp.json();
                if (!pollingEnabled || requestSeq !== conversationsRequestSeq) return;
                if (data.ok) renderConversations(data.conversas || []);
            } catch (e) {
            } finally {
                pollConversationsRunning = false;
            }
        }

        async function pollMessages() {
            if (!pollingEnabled) return;
            const messagesEndpoint = endpointFromTemplate(messagesEndpointTemplate, activeConversationId);
            if (!messagesEndpoint) return;
            if (pollMessagesRunning) return;
            pollMessagesRunning = true;
            const requestSeq = ++messagesRequestSeq;
            const conversationSnapshot = String(activeConversationId || '');
            try {
                const resp = await fetch(messagesEndpoint, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!resp.ok) return;
                const data = await resp.json();
                if (!pollingEnabled || requestSeq !== messagesRequestSeq) return;
                if (conversationSnapshot !== String(activeConversationId || '')) return;
                if (data.ok) renderMessages(data.mensagens || []);
            } catch (e) {
            } finally {
                pollMessagesRunning = false;
            }
        }

        const btnOpenNewChat = document.getElementById('btnOpenNewChat');
        const conversationSearchForm = document.getElementById('conversationSearchForm');
        const conversationSearchInput = document.getElementById('conversationSearchInput');
        const newChatCard = document.getElementById('newChatCard');
        const numeroInput = newChatCard ? newChatCard.querySelector('input[name="numero"]') : null;
        const attachTrigger = document.getElementById('attachTrigger');
        const attachMenu = document.getElementById('attachMenu');
        const chatFileInput = document.getElementById('chatFileInput');
        const chatCameraInput = document.getElementById('chatCameraInput');
        const selectedFileName = document.getElementById('selectedFileName');
        const sendMessageForm = document.getElementById('sendMessageForm');
        const composeEmojiTrigger = document.getElementById('composeEmojiTrigger');
        const markReadForm = document.getElementById('markReadForm');
        const archiveConversationForm = document.getElementById('archiveConversationForm');
        const archiveConversationActionInput = archiveConversationForm ? archiveConversationForm.querySelector('input[name="archive_action"]') : null;
        const archiveConversationBtn = archiveConversationForm ? archiveConversationForm.querySelector('button[type="submit"]') : null;
        const deleteConversationForm = document.getElementById('deleteConversationForm');
        const startConversationForm = document.getElementById('startConversationForm');
        const micRecordBtn = document.getElementById('micRecordBtn');
        const recordingHint = document.getElementById('recordingHint');
        const sendRecordedAudioBtn = document.getElementById('sendRecordedAudioBtn');
        const emojiPickerPanel = document.createElement('div');
        emojiPickerPanel.className = 'emoji-picker-panel';
        emojiPickerPanel.id = 'emojiPickerPanel';
        const composeEmojiPickerPanel = document.createElement('div');
        composeEmojiPickerPanel.className = 'emoji-picker-panel';
        composeEmojiPickerPanel.id = 'composeEmojiPickerPanel';
        let emojiPickerMessageId = null;
        const composeInput = sendMessageForm ? sendMessageForm.querySelector('input[name="mensagem"]') : null;
        let mediaRecorder = null;
        let recordingStream = null;
        let recordingChunks = [];
        let recordingStartedAt = 0;
        let recordingTimer = null;
        let isRecordingAudio = false;
        let composeDraftKind = 'media';
        let composeDraftFiles = [];
        let composeDraftPreviewUrls = [];
        let attachPickerKind = 'media';
        ['👍', '❤️', '😂', '🙏', '😮', '😢', '👏', '🔥'].forEach((emoji) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = emoji;
            btn.addEventListener('click', () => {
                if (!emojiPickerMessageId) return;
                sendReaction(emojiPickerMessageId, emoji);
                closeEmojiPicker();
            });
            emojiPickerPanel.appendChild(btn);
        });
        document.body.appendChild(emojiPickerPanel);
        ['😀', '😁', '😂', '🤣', '😊', '😍', '😘', '😎', '😢', '🙏', '👍', '🔥', '❤️'].forEach((emoji) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = emoji;
            btn.addEventListener('click', () => {
                if (!composeInput) return;
                const start = Number(composeInput.selectionStart || composeInput.value.length);
                const end = Number(composeInput.selectionEnd || composeInput.value.length);
                const current = composeInput.value || '';
                composeInput.value = `${current.slice(0, start)}${emoji}${current.slice(end)}`;
                const nextPos = start + emoji.length;
                composeInput.focus();
                composeInput.setSelectionRange(nextPos, nextPos);
                closeComposeEmojiPicker();
            });
            composeEmojiPickerPanel.appendChild(btn);
        });
        document.body.appendChild(composeEmojiPickerPanel);

        function closeEmojiPicker() {
            emojiPickerPanel.classList.remove('show');
            emojiPickerMessageId = null;
        }

        function closeComposeEmojiPicker() {
            composeEmojiPickerPanel.classList.remove('show');
        }

        function openEmojiPicker(messageId, anchorEl) {
            emojiPickerMessageId = messageId;
            const rect = anchorEl ? anchorEl.getBoundingClientRect() : { left: window.innerWidth / 2, top: window.innerHeight / 2 };
            const top = Math.max(12, rect.top - 58);
            const left = Math.max(12, Math.min(rect.left - 8, window.innerWidth - 320));
            emojiPickerPanel.style.top = `${top}px`;
            emojiPickerPanel.style.left = `${left}px`;
            emojiPickerPanel.classList.add('show');
        }

        function openComposeEmojiPicker(anchorEl) {
            if (!composeInput) return;
            const rect = anchorEl ? anchorEl.getBoundingClientRect() : { left: 20, top: window.innerHeight - 90 };
            const top = Math.max(12, rect.top - 58);
            const left = Math.max(12, Math.min(rect.left - 8, window.innerWidth - 320));
            composeEmojiPickerPanel.style.top = `${top}px`;
            composeEmojiPickerPanel.style.left = `${left}px`;
            composeEmojiPickerPanel.classList.add('show');
        }

        if (composeEmojiTrigger) {
            composeEmojiTrigger.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                closeEmojiPicker();
                if (composeEmojiPickerPanel.classList.contains('show')) {
                    closeComposeEmojiPicker();
                } else {
                    openComposeEmojiPicker(composeEmojiTrigger);
                }
            });
        }

        function applyBrPhoneMask(value) {
            const digits = (value || '').replace(/\D/g, '').slice(0, 11);
            if (!digits) return '';
            if (digits.length <= 2) return `(${digits}`;
            if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
            if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
            return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
        }

        if (numeroInput) {
            numeroInput.addEventListener('input', function () {
                this.value = applyBrPhoneMask(this.value);
            });
        }

        if (btnOpenNewChat && newChatCard) {
            btnOpenNewChat.addEventListener('click', function (e) {
                e.preventDefault();
                newChatCard.classList.toggle('show');
                if (newChatCard.classList.contains('show') && numeroInput) {
                    numeroInput.focus();
                }
            });
            document.addEventListener('click', function (e) {
                if (!newChatCard.contains(e.target) && !btnOpenNewChat.contains(e.target)) {
                    newChatCard.classList.remove('show');
                }
            });
        }

        function closeAttachMenu() {
            if (attachMenu) attachMenu.classList.remove('show');
        }

        function setAudioReadyState(isReady) {
            if (!sendRecordedAudioBtn) return;
            sendRecordedAudioBtn.classList.toggle('show', !!isReady);
        }

        function clearAttachmentInputs() {
            if (chatFileInput) chatFileInput.value = '';
            if (chatCameraInput) chatCameraInput.value = '';
            setAudioReadyState(false);
        }

        function setAttachmentFile(file, options) {
            if (!chatFileInput || !file) return;
            const dt = new DataTransfer();
            dt.items.add(file);
            chatFileInput.files = dt.files;
            if (selectedFileName) selectedFileName.textContent = `Arquivo: ${file.name}`;
            const audioReady = options && options.audioReady;
            setAudioReadyState(!!audioReady);
        }

        function triggerCameraCapture() {
            const triggerPicker = (inputEl) => {
                if (!inputEl) return;
                try {
                    if (typeof inputEl.showPicker === 'function') {
                        inputEl.showPicker();
                        return;
                    }
                } catch (e) {}
                inputEl.click();
            };
            const bindChange = (inputEl, removeAfterUse) => {
                if (!inputEl) return;
                inputEl.addEventListener('change', function onCameraChange() {
                    const file = inputEl.files && inputEl.files[0] ? inputEl.files[0] : null;
                    if (file) {
                        setAttachmentFile(file);
                    }
                    inputEl.value = '';
                    if (removeAfterUse && inputEl.parentNode) {
                        inputEl.parentNode.removeChild(inputEl);
                    }
                    inputEl.removeEventListener('change', onCameraChange);
                }, { once: true });
            };

            if (chatCameraInput) {
                chatCameraInput.setAttribute('accept', 'image/*;capture=camera');
                chatCameraInput.setAttribute('capture', 'environment');
                bindChange(chatCameraInput, false);
                triggerPicker(chatCameraInput);
                return;
            }

            // Fallback para navegadores que bloqueiam input fixo para captura.
            const tempInput = document.createElement('input');
            tempInput.type = 'file';
            tempInput.accept = 'image/*;capture=camera';
            tempInput.setAttribute('capture', 'environment');
            tempInput.className = 'camera-file-input';
            document.body.appendChild(tempInput);
            bindChange(tempInput, true);
            triggerPicker(tempInput);
        }

        if (attachTrigger && attachMenu) {
            attachTrigger.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                attachMenu.classList.toggle('show');
            });
        }

        if (chatFileInput) {
            chatFileInput.addEventListener('change', function () {
                if (!selectedFileName) return;
                const file = this.files && this.files[0] ? this.files[0] : null;
                if (!file) {
                    selectedFileName.textContent = '';
                    setAudioReadyState(false);
                    return;
                }
                const files = Array.from(this.files || []);
                const lowerName = (file.name || '').toLowerCase();
                const isRecordedAudio = lowerName.startsWith('audio_') && (String(file.type || '').startsWith('audio/') || ['.ogg', '.opus', '.webm', '.m4a', '.mp3', '.wav', '.aac'].some((ext) => lowerName.endsWith(ext)));
                if (isRecordedAudio) {
                    selectedFileName.textContent = `Arquivo: ${file.name}`;
                    setAudioReadyState(true);
                    return;
                }
                this.value = '';
                selectedFileName.textContent = '';
                setAudioReadyState(false);
                const modalKind = attachPickerKind === 'document' ? 'document' : 'media';
                openComposeMediaModal(files, modalKind, false);
            });
        }
        if (chatCameraInput) {
            chatCameraInput.addEventListener('change', function () {
                const file = this.files && this.files[0] ? this.files[0] : null;
                if (!file) return;
                openComposeMediaModal([file], 'media', false);
                this.value = '';
            });
        }

        function formatRecordingTime(ms) {
            const totalSec = Math.max(0, Math.floor(ms / 1000));
            const mm = String(Math.floor(totalSec / 60)).padStart(2, '0');
            const ss = String(totalSec % 60).padStart(2, '0');
            return `${mm}:${ss}`;
        }

        function stopRecordingTimer() {
            if (recordingTimer) {
                clearInterval(recordingTimer);
                recordingTimer = null;
            }
        }

        function resetRecordingUi() {
            if (micRecordBtn) micRecordBtn.classList.remove('recording');
            if (recordingHint) {
                recordingHint.style.display = 'none';
                recordingHint.textContent = 'Gravando 00:00';
            }
        }

        async function startAudioRecording() {
            if (isRecordingAudio) return;
            if (!navigator.mediaDevices || !window.MediaRecorder) {
                alert('Gravacao de audio nao suportada neste navegador.');
                return;
            }
            try {
                recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                recordingChunks = [];
                let options = {};
                const preferredTypes = [
                    'audio/ogg;codecs=opus',
                    'audio/ogg',
                    'audio/webm;codecs=opus',
                    'audio/webm',
                ];
                const supportedType = preferredTypes.find((t) => {
                    return window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(t);
                });
                if (supportedType) {
                    options = { mimeType: supportedType };
                }
                mediaRecorder = new MediaRecorder(recordingStream, options);
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) recordingChunks.push(event.data);
                };
                mediaRecorder.onstop = () => {
                    const blobType = (recordingChunks[0] && recordingChunks[0].type) || 'audio/webm';
                    const blob = new Blob(recordingChunks, { type: blobType });
                    if (blob.size > 0) {
                        clearAttachmentInputs();
                        const ext = blobType.includes('ogg') ? 'ogg' : (blobType.includes('mp4') ? 'm4a' : 'webm');
                        const file = new File([blob], `audio_${Date.now()}.${ext}`, { type: blobType });
                        setAttachmentFile(file, { audioReady: true });
                    }
                    if (recordingStream) {
                        recordingStream.getTracks().forEach((track) => track.stop());
                    }
                    recordingStream = null;
                    mediaRecorder = null;
                    recordingChunks = [];
                    isRecordingAudio = false;
                    stopRecordingTimer();
                    resetRecordingUi();
                };
                mediaRecorder.start();
                isRecordingAudio = true;
                recordingStartedAt = Date.now();
                if (micRecordBtn) micRecordBtn.classList.add('recording');
                if (recordingHint) {
                    recordingHint.style.display = 'inline';
                    recordingHint.textContent = 'Gravando 00:00';
                }
                recordingTimer = setInterval(() => {
                    if (!recordingHint || !isRecordingAudio) return;
                    recordingHint.textContent = `Gravando ${formatRecordingTime(Date.now() - recordingStartedAt)}`;
                }, 250);
            } catch (err) {
                isRecordingAudio = false;
                stopRecordingTimer();
                resetRecordingUi();
                alert('Nao foi possivel acessar o microfone.');
            }
        }

        function stopAudioRecording() {
            if (!isRecordingAudio) return;
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                return;
            }
            if (recordingStream) {
                recordingStream.getTracks().forEach((track) => track.stop());
            }
            isRecordingAudio = false;
            stopRecordingTimer();
            resetRecordingUi();
        }

        if (micRecordBtn) {
            const begin = (e) => {
                e.preventDefault();
                startAudioRecording();
            };
            const end = (e) => {
                e.preventDefault();
                stopAudioRecording();
            };
            micRecordBtn.addEventListener('mousedown', begin);
            micRecordBtn.addEventListener('touchstart', begin, { passive: false });
            micRecordBtn.addEventListener('mouseup', end);
            micRecordBtn.addEventListener('mouseleave', end);
            micRecordBtn.addEventListener('touchend', end);
            micRecordBtn.addEventListener('touchcancel', end);
        }
        if (sendRecordedAudioBtn && sendMessageForm) {
            sendRecordedAudioBtn.addEventListener('click', function () {
                const hasFile = !!(chatFileInput && chatFileInput.files && chatFileInput.files.length);
                if (!hasFile) return;
                sendMessageForm.requestSubmit();
            });
        }
        if (sendMessageForm) {
            sendMessageForm.addEventListener('paste', function (e) {
                const clipboard = e.clipboardData || window.clipboardData;
                if (!clipboard || !clipboard.items) return;
                for (const item of clipboard.items) {
                    if (item && item.type && item.type.startsWith('image/')) {
                        const file = item.getAsFile ? item.getAsFile() : null;
                        if (!file) return;
                        e.preventDefault();
                        openComposeMediaModal([file], 'media', false);
                        return;
                    }
                }
            });
        }
        async function sendComposeDraftFiles() {
            if (!sendMessageForm || !composeDraftFiles.length) return;
            const endpoint = (sendMessageForm.getAttribute('action') || '').trim() || (window.location.pathname + window.location.search);
            const conversaInput = sendMessageForm.querySelector('input[name="conversa_id"]');
            const conversaId = (conversaInput && conversaInput.value) ? conversaInput.value : String(activeConversationId || '');
            if (!conversaId) throw new Error('Conversa invalida.');
            const caption = composeMediaCaption ? String(composeMediaCaption.value || '').trim() : '';
            for (let i = 0; i < composeDraftFiles.length; i++) {
                const file = composeDraftFiles[i];
                const body = new FormData();
                body.append('ajax', '1');
                body.append('action', 'send_message');
                body.append('conversa_id', conversaId);
                body.append('arquivo', file, file.name || `arquivo_${Date.now()}_${i + 1}`);
                if (caption && i === 0) body.append('mensagem', caption);
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCsrfToken(),
                        'Accept': 'application/json'
                    },
                    body
                });
                const contentType = (resp.headers.get('content-type') || '').toLowerCase();
                if (!contentType.includes('application/json')) {
                    throw new Error('Resposta invalida do servidor.');
                }
                const data = await resp.json().catch(() => ({ ok: false, error: 'Resposta invalida do servidor.' }));
                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || 'Falha ao enviar arquivo.');
                }
            }
        }
        if (composeMediaSendBtn) {
            composeMediaSendBtn.addEventListener('click', async function () {
                if (!composeDraftFiles.length) return;
                try {
                    await sendComposeDraftFiles();
                    closeComposeMediaModal();
                    clearAttachmentInputs();
                    if (selectedFileName) selectedFileName.textContent = '';
                    await pollMessages();
                    await pollConversations();
                } catch (err) {
                    alert(err.message || 'Falha ao enviar arquivos.');
                }
            });
        }
        if (composeMediaAddBtn) {
            composeMediaAddBtn.addEventListener('click', function () {
                if (!composeMediaAddInput) return;
                composeMediaAddInput.value = '';
                composeMediaAddInput.setAttribute('multiple', 'multiple');
                if (composeDraftKind === 'document') {
                    composeMediaAddInput.setAttribute('accept', '.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip,.rar');
                } else {
                    composeMediaAddInput.setAttribute('accept', 'image/*,video/*');
                }
                composeMediaAddInput.click();
            });
        }
        if (composeMediaAddInput) {
            composeMediaAddInput.addEventListener('change', function () {
                const files = Array.from(this.files || []);
                if (!files.length) return;
                openComposeMediaModal(files, composeDraftKind, true);
                this.value = '';
            });
        }
        if (composeMediaCancelBtn) {
            composeMediaCancelBtn.addEventListener('click', closeComposeMediaModal);
        }
        if (composeMediaClose) {
            composeMediaClose.addEventListener('click', closeComposeMediaModal);
        }
        if (editMessageCancelBtn) {
            editMessageCancelBtn.addEventListener('click', closeEditMessageModal);
        }
        if (editMessageClose) {
            editMessageClose.addEventListener('click', closeEditMessageModal);
        }
        if (editMessageInput && editMessagePreviewBubble) {
            editMessageInput.addEventListener('input', function () {
                editMessagePreviewBubble.textContent = this.value || '(sem texto)';
            });
        }
        if (editMessageSaveBtn) {
            editMessageSaveBtn.addEventListener('click', async function () {
                const id = Number(editingMessageId || 0);
                const novoTexto = editMessageInput ? String(editMessageInput.value || '').trim() : '';
                if (!id) return;
                if (!novoTexto) {
                    alert('Informe o novo texto da mensagem.');
                    return;
                }
                try {
                    const endpoint = editMessageEndpointTemplate.replace('/0/', `/${id}/`);
                    const formData = new URLSearchParams();
                    formData.append('ajax', '1');
                    formData.append('mensagem', novoTexto);
                    const resp = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json',
                        },
                        body: formData.toString(),
                    });
                    const data = await resp.json();
                    if (!resp.ok || !data || !data.ok) {
                        alert((data && data.error) ? data.error : 'Nao foi possivel editar a mensagem.');
                        return;
                    }
                    closeEditMessageModal();
                    lastMessagesSignature = '';
                    lastConversationsSignature = '';
                    await pollMessages();
                    await pollConversations();
                } catch (e) {
                    alert('Erro ao editar mensagem.');
                }
            });
        }
        window.forwardSelectionCancel = function () {
            exitForwardSelectionMode();
        };
        window.forwardSelectionProceed = function () {
            const ids = Array.from(selectedForwardMessageIds.values());
            if (!ids.length) {
                alert('Selecione ao menos uma mensagem.');
                return;
            }
            openForwardTargetModal();
        };
        window.forwardTargetCancel = function () {
            closeForwardTargetModal();
        };
        async function performForwardSelectedMessages() {
            const ids = Array.from(selectedForwardMessageIds.values());
            if (!ids.length) {
                alert('Selecione ao menos uma mensagem.');
                return;
            }
            const targets = Array.from(selectedForwardTargets.values());
            if (!targets.length) {
                alert('Selecione ao menos um contato.');
                return;
            }

            let forwardedTotal = 0;
            let firstError = '';
            for (const numeroDestino of targets) {
                const formData = new URLSearchParams();
                formData.append('numero', numeroDestino);
                formData.append('ids', ids.join(','));
                try {
                    const resp = await fetch(forwardMessagesBulkEndpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json',
                        },
                        body: formData.toString(),
                    });
                    const data = await resp.json().catch(() => ({}));
                    if (data && data.ok) {
                        forwardedTotal += Number(data.forwarded_count || 0);
                    } else if (!firstError) {
                        firstError = data.error || `Falha HTTP ${resp.status}`;
                    }
                } catch (e) {
                    if (!firstError) firstError = 'Erro de comunicacao ao encaminhar.';
                }
            }

            if (!forwardedTotal) {
                alert(firstError || 'Nao foi possivel encaminhar as mensagens para os contatos selecionados.');
                return;
            }
            closeForwardTargetModal();
            exitForwardSelectionMode();
            alert(`${forwardedTotal} mensagem(ns) encaminhada(s).`);
            await pollConversations();
        }
        window.forwardTargetSend = function () {
            performForwardSelectedMessages();
        };
        if (forwardCancelBtn) {
            forwardCancelBtn.addEventListener('click', window.forwardSelectionCancel);
        }

        let searchDebounceTimer = null;
        function applyConversationSearch(nextQuery) {
            const normalized = String(nextQuery || '').trim();
            if (normalized === String(currentQuery || '').trim()) return;
            currentQuery = normalized;
            lastConversationsSignature = '';
            pollConversations();
            const url = new URL(window.location.href);
            if (currentQuery) {
                url.searchParams.set('q', currentQuery);
            } else {
                url.searchParams.delete('q');
            }
            history.replaceState(history.state || {}, '', url.toString());
        }

        if (conversationSearchForm) {
            conversationSearchForm.addEventListener('submit', function (e) {
                e.preventDefault();
                applyConversationSearch(conversationSearchInput ? conversationSearchInput.value : '');
            });
        }
        if (conversationSearchInput) {
            conversationSearchInput.addEventListener('input', function () {
                const value = this.value || '';
                if (searchDebounceTimer) {
                    clearTimeout(searchDebounceTimer);
                }
                searchDebounceTimer = setTimeout(function () {
                    applyConversationSearch(value);
                }, 280);
            });
        }
        if (forwardSendBtn) {
            forwardSendBtn.addEventListener('click', window.forwardSelectionProceed);
        }
        // Fallback por delegacao para cobrir re-render/polling e garantir clique.
        document.addEventListener('click', function (e) {
            const cancelBtn = e.target.closest('#forwardCancelBtn');
            if (cancelBtn) {
                e.preventDefault();
                window.forwardSelectionCancel();
                return;
            }
            const sendBtn = e.target.closest('#forwardSendBtn');
            if (sendBtn) {
                e.preventDefault();
                window.forwardSelectionProceed();
            }
        });
        if (forwardTargetSearch) {
            forwardTargetSearch.addEventListener('input', function () {
                renderForwardTargetsList(this.value || '');
            });
        }
        if (forwardTargetList) {
            forwardTargetList.addEventListener('click', function (e) {
                const item = e.target.closest('.forward-target-item[data-forward-number]');
                if (!item) return;
                const number = item.getAttribute('data-forward-number') || '';
                if (!number) return;
                if (selectedForwardTargets.has(number)) {
                    selectedForwardTargets.delete(number);
                } else {
                    selectedForwardTargets.add(number);
                }
                item.classList.toggle('selected', selectedForwardTargets.has(number));
                updateForwardTargetCount();
            });
        }
        if (forwardTargetCancelBtn) {
            forwardTargetCancelBtn.addEventListener('click', window.forwardTargetCancel);
        }
        if (forwardTargetClose) {
            forwardTargetClose.addEventListener('click', window.forwardTargetCancel);
        }
        document.addEventListener('click', function (e) {
            const cancelTargetBtn = e.target.closest('#forwardTargetCancelBtn, #forwardTargetClose');
            if (cancelTargetBtn) {
                e.preventDefault();
                window.forwardTargetCancel();
            }
        });
        if (forwardTargetSendBtn) {
            forwardTargetSendBtn.addEventListener('click', window.forwardTargetSend);
        }

        async function submitFormAjax(formEl) {
            const actionAttr = (formEl.getAttribute('action') || '').trim();
            const endpoint = actionAttr || (window.location.pathname + window.location.search);
            const body = new FormData(formEl);
            if (!body.get('ajax')) body.append('ajax', '1');
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                    'Accept': 'application/json'
                },
                body
            });
            const contentType = (resp.headers.get('content-type') || '').toLowerCase();
            if (!contentType.includes('application/json')) {
                if (resp.redirected || /\/login/i.test(resp.url || '')) {
                    throw new Error('Sessao expirada. Faca login novamente e tente de novo.');
                }
                if (resp.status === 403) {
                    throw new Error('Sessao expirada ou sem permissao. Atualize a pagina e tente novamente.');
                }
                const rawText = await resp.text().catch(() => '');
                const snippet = (rawText || '').replace(/\s+/g, ' ').trim().slice(0, 160);
                throw new Error(`Resposta invalida do servidor (HTTP ${resp.status}). ${snippet ? 'Detalhe: ' + snippet : ''}`);
            }
            const data = await resp.json().catch(() => ({ ok: false, error: 'Resposta invalida do servidor.' }));
            if (!resp.ok || !data.ok) {
                throw new Error(data.error || 'Falha na requisicao.');
            }
            return data;
        }

        if (sendMessageForm) {
            sendMessageForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                try {
                    await submitFormAjax(sendMessageForm);
                    const textInput = sendMessageForm.querySelector('input[name="mensagem"]');
                    if (textInput) textInput.value = '';
                    clearAttachmentInputs();
                    if (selectedFileName) selectedFileName.textContent = '';
                    closeAttachMenu();
                    pollMessages();
                    pollConversations();
                } catch (err) {
                    alert(err.message || 'Erro ao enviar mensagem.');
                }
            });
        }

        if (markReadForm) {
            markReadForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                try {
                    await submitFormAjax(markReadForm);
                    pollConversations();
                } catch (err) {
                    alert(err.message || 'Erro ao marcar conversa como lida.');
                }
            });
        }

        if (startConversationForm) {
            startConversationForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                try {
                    const data = await submitFormAjax(startConversationForm);
                    const targetConversationId = data.conversation_id;
                    if (targetConversationId) {
                        await activateConversation(targetConversationId, true);
                        if (newChatCard) newChatCard.classList.remove('show');
                        return;
                    }
                    pollConversations();
                    if (newChatCard) newChatCard.classList.remove('show');
                } catch (err) {
                    alert(err.message || 'Erro ao iniciar conversa.');
                }
            });
        }

        if (deleteConversationForm) {
            deleteConversationForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                const ok = window.confirm('Deseja realmente deletar esta conversa? Esta acao nao pode ser desfeita.');
                if (!ok) return;
                try {
                    await submitFormAjax(deleteConversationForm);
                    const url = new URL(window.location.href);
                    url.searchParams.delete('c');
                    window.location.href = url.toString();
                } catch (err) {
                    alert(err.message || 'Erro ao deletar conversa.');
                }
            });
        }

        async function activateConversation(conversationId, pushState) {
            if (!conversationId) return;
            exitForwardSelectionMode();
            // Quando a tela iniciou sem conversa ativa, o painel de mensagens nao existe.
            // Nesse caso, abre a URL normal para montar o layout completo.
            if (!messagesEl || !sendMessageForm) {
                const baseUrl = cfg.inboxBaseUrl || '/whatsapp/';
                window.location.href = `${baseUrl}?c=${conversationId}`;
                return;
            }
            setActiveConversationId(conversationId);
            await pollConversations();
            await pollMessages();
            if (markReadForm) {
                try { await submitFormAjax(markReadForm); } catch (e) {}
            }
            if (pushState) {
                const url = new URL(window.location.href);
                url.searchParams.set('c', String(conversationId));
                history.pushState({ c: String(conversationId) }, '', url.toString());
            }
        }

        if (listEl) {
            listEl.addEventListener('click', async function (e) {
                const link = e.target.closest('.chat-box[data-conversation-id]');
                if (!link) return;
                e.preventDefault();
                try {
                    await activateConversation(link.dataset.conversationId, true);
                } catch (err) {
                    window.location.href = link.href;
                }
            });
        }

        window.addEventListener('popstate', async function () {
            const params = new URLSearchParams(window.location.search);
            const c = params.get('c');
            if (c) {
                await activateConversation(c, false);
            }
        });

        window.openAttachment = function (kind) {
            if (chatFileInput) chatFileInput.removeAttribute('capture');
            if (kind === 'media') {
                if (!chatFileInput) return;
                attachPickerKind = 'media';
                chatFileInput.setAttribute('accept', 'image/*,video/*');
                chatFileInput.setAttribute('multiple', 'multiple');
                chatFileInput.click();
            } else if (kind === 'camera') {
                attachPickerKind = 'media';
                clearAttachmentInputs();
                triggerCameraCapture();
            } else if (kind === 'document') {
                if (!chatFileInput) return;
                attachPickerKind = 'document';
                chatFileInput.setAttribute('accept', '.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip,.rar');
                chatFileInput.setAttribute('multiple', 'multiple');
                chatFileInput.click();
            } else if (kind === 'contact') {
                alert('Envio de contato sera habilitado em breve.');
            } else if (kind === 'video_call') {
                alert('Video chamada nao esta disponivel nesta versao.');
            } else if (kind === 'buttons') {
                alert('Envio de botoes sera habilitado em breve.');
            }
            closeAttachMenu();
        };

        document.addEventListener('click', function (e) {
            const imageEl = e.target.closest('.js-chat-image');
            if (imageEl) {
                e.preventDefault();
                openImagePreview(imageEl.getAttribute('data-full-src') || imageEl.getAttribute('src') || '');
                return;
            }
            if (!e.target.closest('.message-menu') && !e.target.closest('.message-menu-trigger')) {
                closeAllMessageMenus();
            }
            if (!e.target.closest('.attach-box')) {
                closeAttachMenu();
            }
            if (!e.target.closest('#emojiPickerPanel')) {
                closeEmojiPicker();
            }
            if (!e.target.closest('#composeEmojiPickerPanel') && !e.target.closest('#composeEmojiTrigger')) {
                closeComposeEmojiPicker();
            }
            if (imagePreviewModal && e.target === imagePreviewModal) {
                closeImagePreview();
            }
            if (composeMediaModal && e.target === composeMediaModal) {
                closeComposeMediaModal();
            }
            if (forwardTargetModal && e.target === forwardTargetModal) {
                closeForwardTargetModal();
            }
            if (editMessageModal && e.target === editMessageModal) {
                closeEditMessageModal();
            }
        });

        if (imagePreviewClose) {
            imagePreviewClose.addEventListener('click', closeImagePreview);
        }
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && imagePreviewModal && imagePreviewModal.classList.contains('show')) {
                closeImagePreview();
                return;
            }
            if (e.key === 'Escape' && composeMediaModal && composeMediaModal.classList.contains('show')) {
                closeComposeMediaModal();
                return;
            }
            if (e.key === 'Escape' && forwardTargetModal && forwardTargetModal.classList.contains('show')) {
                closeForwardTargetModal();
                exitForwardSelectionMode();
                return;
            }
            if (e.key === 'Escape' && editMessageModal && editMessageModal.classList.contains('show')) {
                closeEditMessageModal();
                return;
            }
            if (e.key === 'Escape' && composeEmojiPickerPanel.classList.contains('show')) {
                closeComposeEmojiPicker();
                return;
            }
            if (e.key === 'Escape' && forwardSelectionMode) {
                exitForwardSelectionMode();
            }
        });

        if (cfg.openNewChat && newChatCard) {
            newChatCard.classList.add('show');
            if (numeroInput) numeroInput.focus();
        }
        if (archiveConversationForm) {
            archiveConversationForm.addEventListener('submit', async function (e) {
                e.preventDefault();
                try {
                    const data = await submitFormAjax(archiveConversationForm);
                    const hiddenAction = archiveConversationForm.querySelector('input[name="archive_action"]');
                    const btn = archiveConversationForm.querySelector('button[type="submit"]');
                    const isArchived = !!(data && data.arquivada);
                    if (hiddenAction) hiddenAction.value = isArchived ? 'unarchive' : 'archive';
                    if (btn) btn.textContent = isArchived ? 'Desarquivar' : 'Arquivar';
                    await pollConversations();
                } catch (err) {
                    alert(err.message || 'Erro ao arquivar conversa.');
                }
            });
        }

        if (activeConversationId) {
            setActiveConversationId(activeConversationId);
        }
        normalizeRenderedMediaUrls();

        document.addEventListener('visibilitychange', function () {
            if (document.hidden) {
                pollingEnabled = false;
                return;
            }
            pollingEnabled = true;
            pollConversations();
            pollMessages();
        });

        pollConversations();
        pollMessages();
        setInterval(pollConversations, 2000);
        setInterval(pollMessages, 2500);
    })();
