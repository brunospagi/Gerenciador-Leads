// Importa a biblioteca idb-keyval (necessária para o Background Sync)
importScripts('https://cdn.jsdelivr.net/npm/idb-keyval@6/dist/umd.js');

var staticCacheName = "django-pwa-v" + new Date().getTime();
var filesToCache = [
    // URLs da Aplicação
    '/',
    '/offline',
    
    // Manifest e Ícones
    '/static/images/logo-spagi.png',
    
    // CSS (CDNs)
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/lightbox2/2.11.4/css/lightbox.min.css',
    
    // JS (CDNs)
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
    'https://unpkg.com/imask',
    'https://cdnjs.cloudflare.com/ajax/libs/lightbox2/2.11.4/js/lightbox.min.js',
    'https://cdn.jsdelivr.net/npm/idb-keyval@6/dist/umd.js' // Adiciona a própria lib ao cache
];

// Função para atualizar o cache
const updateCache = () => {
    return caches.open(staticCacheName).then(cache => {
        return cache.addAll(filesToCache);
    });
};

// Cache on install
self.addEventListener("install", event => {
    this.skipWaiting();
    event.waitUntil(
        caches.open(staticCacheName)
            .then(cache => {
                return cache.addAll(filesToCache);
            })
    )
});

// Clear cache on activate
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(cacheName => (cacheName.startsWith("django-pwa-")))
                    .filter(cacheName => (cacheName !== staticCacheName))
                    .map(cacheName => caches.delete(cacheName))
            );
        })
    );
});

// Serve from Cache
self.addEventListener("fetch", event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                return response || fetch(event.request);
            })
            .catch(() => {
                return caches.match('offline');
            })
    )
});

// Evento: Periodic Sync (para atualizar o cache)
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'update-cache-daily') {
        console.log('Periodic Sync: Atualizando cache...');
        event.waitUntil(updateCache());
    }
});

// Evento: Background Sync (para enviar dados offline)
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-new-client') {
        console.log('Sync: Tentando enviar clientes offline...');
        event.waitUntil(sendOfflineClients());
    }
    // NOTA: Você pode adicionar mais tags aqui, ex: 'sync-new-avaliacao'
});

async function sendOfflineClients() {
    let outbox = (await idbKeyval.get('client-outbox')) || [];
    if (outbox.length === 0) {
        return;
    }

    console.log(`Sync: Enviando ${outbox.length} clientes...`);

    const sendPromises = outbox.map(clientEntry => {
        const formData = new FormData();
        
        // Remonta o FormData a partir do objeto salvo
        for (const key in clientEntry.data) {
            formData.append(key, clientEntry.data[key]);
        }
        
        // Adiciona o CSRF token que salvamos
        formData.append('csrfmiddlewaretoken', clientEntry.csrfToken);

        // Envia para a URL de criação do Django
        return fetch('/cliente/novo/', {
            method: 'POST',
            body: formData
            // Não defina Content-Type, o browser faz isso por nós com FormData
        }).then(response => {
            if (response.ok) {
                console.log('Sync: Cliente enviado com sucesso:', clientEntry.data.nome_cliente);
                // Retorna o item para que possamos removê-lo do outbox
                return clientEntry;
            } else {
                console.error('Sync: Falha ao enviar cliente. Status:', response.status);
                // Retorna null para manter o item no outbox
                return null;
            }
        }).catch(err => {
            console.error('Sync: Erro de rede ao enviar cliente.', err);
            // Retorna null para manter o item no outbox
            return null;
        });
    });

    try {
        const results = await Promise.all(sendPromises);
        
        // Filtra o outbox, mantendo apenas os que falharam (null)
        const successfulItems = results.filter(result => result !== null);
        
        if (successfulItems.length > 0) {
            // Remove os itens bem-sucedidos do outbox
            let currentOutbox = (await idbKeyval.get('client-outbox')) || [];
            const successfulIds = new Set(successfulItems.map(item => item.id)); // Assumindo que temos um ID
            
            // Recriamos o outbox apenas com os itens que falharam
            const newOutbox = currentOutbox.filter(item => !successfulIds.has(item.id));
            await idbKeyval.set('client-outbox', newOutbox);

            if (newOutbox.length === 0) {
                console.log('Sync: Todos os clientes offline foram enviados.');
            } else {
                console.log(`Sync: ${newOutbox.length} clientes falharam e permanecem no outbox.`);
            }
        }
    } catch (error) {
        console.error('Sync: Erro ao processar resultados do outbox.', error);
    }
}


// --- NOVO: Listener para PUSH NOTIFICATIONS ---
self.addEventListener('push', (event) => {
    console.log('Push recebido!');
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data = { head: 'Notificação', body: event.data.text() };
        }
    }

    const title = data.head || "Nova Notificação";
    const options = {
        body: data.body || "Você tem uma nova atualização.",
        icon: data.icon || "/static/images/logo-spagi-192x192.png",
        badge: data.badge || "/static/images/logo-spagi-192x192.png",
        data: {
            url: data.url || '/'
        }
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

// --- NOVO: Listener para CLIQUE NA NOTIFICAÇÃO ---
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const urlToOpen = event.notification.data.url || '/';
    
    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then((clientList) => {
            // Se o PWA já estiver aberto, foca nele
            if (clientList.length > 0) {
                let client = clientList[0];
                for (let i = 0; i < clientList.length; i++) {
                    if (clientList[i].focused) {
                        client = clientList[i];
                    }
                }
                return client.focus().then(c => c.navigate(urlToOpen));
            }
            // Se o PWA não estiver aberto, abre uma nova janela
            return clients.openWindow(urlToOpen);
        })
    );
});