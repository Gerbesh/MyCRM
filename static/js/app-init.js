// РњРёРЅРёРјР°Р»СЊРЅР°СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ: СЂРµРіРёСЃС‚СЂР°С†РёСЏ Service Worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/js/sw.js');
}
