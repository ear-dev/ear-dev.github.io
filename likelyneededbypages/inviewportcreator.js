(function() {
    'use strict';
    document.addEventListener('DOMContentLoaded', function() {
        var scriptLoader = document.createElement('script');
        scriptLoader.type = 'application/javascript';
        scriptLoader.src = 'loadAfterDCLEE.js';

        document.body.appendChild(scriptLoader);
    });
})();
