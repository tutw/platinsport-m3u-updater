// Bloquear anuncios y popups en la URL específica
(function() {
    // Función para eliminar elementos por selector
    function removeElementsBySelector(selector) {
        var elements = document.querySelectorAll(selector);
        elements.forEach(function(element) {
            element.remove();
        });
    }

    // Lista de selectores comunes de anuncios y popups
    var adSelectors = [
        'iframe',          // Iframes que suelen contener anuncios
        '.ad',             // Elementos con clase "ad"
        '.ads',            // Elementos con clase "ads"
        '.advertisement',  // Elementos con clase "advertisement"
        'popup',           // Elementos con clase "popup"
        '.popup',          // Elementos con clase "popup"
        '#ad',             // Elementos con id "ad"
        '#ads',            // Elementos con id "ads"
        '#advertisement',  // Elementos con id "advertisement"
    ];

    // Eliminar elementos de anuncios y popups
    adSelectors.forEach(function(selector) {
        removeElementsBySelector(selector);
    });

    // Función para bloquear nuevas ventanas emergentes
    window.open = function() {
        return null;
    };

    console.log('Anuncios y popups bloqueados');
})();
