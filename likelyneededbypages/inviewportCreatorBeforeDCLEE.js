(function() {
    'use strict';

    // Fetch the javascript that will fetch the inviewport image
    var scriptLoader = document.createElement('script');
    scriptLoader.type = 'application/javascript';
    scriptLoader.src = 'inviewportCreatorAfterDCLEE.js';
    document.body.appendChild(scriptLoader);

    scriptLoader = document.createElement("script");
    scriptLoader.setAttribute("type", "application/javascript");
    scriptLoader.setAttribute("src", "date.js");
    document.body.appendChild(scriptLoader);
})();
