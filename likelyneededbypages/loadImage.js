(function() {
    'use strict';

    var imageNode = document.createElement('img');
    imageNode.src = 'sparrow.png?inviewport-jsloaded';

    var inviewportDiv = document.getElementById('inviewport-images');
    inviewportDiv.appendChild(imageNode);
})();

function sleep(milliseconds){
  var start = new Date().getTime();
  var keep_looping = true;
  while (keep_looping) {
    if ((new Date().getTime() - start)> milliseconds) {
      keep_looping = false;
    }
  }
}

function loadStuffLate(){
  // Sleep for 100 ms
  sleep(100);

  // Tetch an out of viewport image late
  var imageNode = document.createElement('img');
  imageNode.src = 'sparrow.png?outviewport-jsloaded';

  var inviewportDiv = document.getElementById('not-inviewport-images');
  inviewportDiv.appendChild(imageNode);

  //Fetch a script late
  var scrptE = document.createElement("script");
  scrptE.setAttribute("type", "text/javascript");
  scrptE.setAttribute("language", "JavaScript");
  scrptE.setAttribute("src", "doesNothing.js?secondTime");
  document.getElementsByTagName("head")[0].appendChild(scrptE);
}
