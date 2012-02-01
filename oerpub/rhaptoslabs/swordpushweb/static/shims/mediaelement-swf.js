jQuery.webshims.register("mediaelement-swf",function(d,f,m,u,s,j){var g=f.mediaelement,z=m.swfobject,w=Modernizr.audio&&Modernizr.video,A=z.hasFlashPlayerVersion("9.0.115"),t=0,m={paused:!0,ended:!1,currentSrc:"",duration:m.NaN,readyState:0,networkState:0,videoHeight:0,videoWidth:0,error:null,buffered:{start:function(a){if(a)f.error("buffered index size error");else return 0},end:function(a){if(a)f.error("buffered index size error");else return 0},length:0}},J=Object.keys(m),B={currentTime:0,volume:1,
muted:!1};Object.keys(B);var C=d.extend({isActive:"html5",activating:"html5",wasSwfReady:!1,_bufferedEnd:0,_bufferedStart:0,_metadata:!1,_durationCalcs:-1,_callMeta:!1,currentTime:0,_ppFlag:s},m,B),D=/^jwplayer-/,l=function(a){if(a=u.getElementById(a.replace(D,"")))return a=f.data(a,"mediaelement"),a.isActive=="flash"?a:null},n=function(a){return(a=f.data(a,"mediaelement"))&&a.isActive=="flash"?a:null},h=function(a,b){b=d.Event(b);b.preventDefault();d.event.trigger(b,s,a)},K=j.playerPath||f.cfg.basePath+
"jwplayer/"+(j.playerName||"player.swf"),E=j.pluginPath||f.cfg.basePath+"swf/jwwebshims.swf";f.extendUNDEFProp(j.jwParams,{allowscriptaccess:"always",allowfullscreen:"true",wmode:"transparent"});f.extendUNDEFProp(j.jwVars,{screencolor:"ffffffff"});f.extendUNDEFProp(j.jwAttrs,{bgcolor:"#000000"});var x=function(a,b){var c=a.duration;if(!(c&&a._durationCalcs>0)){try{if(a.duration=a.jwapi.getPlaylist()[0].duration,!a.duration||a.duration<=0||a.duration===a._lastDuration)a.duration=c}catch(e){}a.duration&&
a.duration!=a._lastDuration?(h(a._elem,"durationchange"),(a._elemNodeName=="audio"||a._callMeta)&&g.jwEvents.Model.META(d.extend({duration:a.duration},b),a),a._durationCalcs--):a._durationCalcs++}},k=function(a,b){a<3&&clearTimeout(b._canplaythroughTimer);if(a>=3&&b.readyState<3)b.readyState=a,h(b._elem,"canplay"),clearTimeout(b._canplaythroughTimer),b._canplaythroughTimer=setTimeout(function(){k(4,b)},4E3);if(a>=4&&b.readyState<4)b.readyState=a,h(b._elem,"canplaythrough");b.readyState=a};g.jwEvents=
{View:{PLAY:function(a){var b=l(a.id);if(b&&!b.stopPlayPause&&(b._ppFlag=!0,b.paused==a.state)){b.paused=!a.state;if(b.ended)b.ended=!1;h(b._elem,a.state?"play":"pause")}}},Model:{BUFFER:function(a){var b=l(a.id);if(b&&"percentage"in a&&b._bufferedEnd!=a.percentage){b.networkState=a.percentage==100?1:2;(isNaN(b.duration)||a.percentage>5&&a.percentage<25||a.percentage===100)&&x(b,a);if(b.ended)b.ended=!1;if(b.duration){a.percentage>2&&a.percentage<20?k(3,b):a.percentage>20&&k(4,b);if(b._bufferedEnd&&
b._bufferedEnd>a.percentage)b._bufferedStart=b.currentTime||0;b._bufferedEnd=a.percentage;b.buffered.length=1;if(a.percentage==100)b.networkState=1,k(4,b);d.event.trigger("progress",s,b._elem,!0)}}},META:function(a,b){if(b=b&&b.networkState?b:l(a.id))if("duration"in a){if(!b._metadata||!((!a.height||b.videoHeight==a.height)&&a.duration===b.duration)){b._metadata=!0;var c=b.duration;if(a.duration)b.duration=a.duration;b._lastDuration=b.duration;if(a.height||a.width)b.videoHeight=a.height||0,b.videoWidth=
a.width||0;if(!b.networkState)b.networkState=2;b.readyState<1&&k(1,b);b.duration&&c!==b.duration&&h(b._elem,"durationchange");h(b._elem,"loadedmetadata")}}else b._callMeta=!0},TIME:function(a){var b=l(a.id);if(b&&b.currentTime!==a.position){b.currentTime=a.position;b.duration&&b.duration<b.currentTime&&x(b,a);b.readyState<2&&k(2,b);if(b.ended)b.ended=!1;h(b._elem,"timeupdate")}},STATE:function(a){var b=l(a.id);if(b)switch(a.newstate){case "BUFFERING":if(b.ended)b.ended=!1;k(1,b);h(b._elem,"waiting");
break;case "PLAYING":b.paused=!1;b._ppFlag=!0;b.duration||x(b,a);b.readyState<3&&k(3,b);if(b.ended)b.ended=!1;h(b._elem,"playing");break;case "PAUSED":if(!b.paused&&!b.stopPlayPause)b.paused=!0,b._ppFlag=!0,h(b._elem,"pause");break;case "COMPLETED":b.readyState<4&&k(4,b),b.ended=!0,h(b._elem,"ended")}}},Controller:{ERROR:function(a){var b=l(a.id);b&&g.setError(b._elem,a.message)},SEEK:function(a){var b=l(a.id);if(b){if(b.ended)b.ended=!1;if(b.paused)try{b.jwapi.sendEvent("play","false")}catch(c){}if(b.currentTime!=
a.position)b.currentTime=a.position,h(b._elem,"timeupdate")}},VOLUME:function(a){var b=l(a.id);if(b&&(a=a.percentage/100,b.volume!=a))b.volume=a,h(b._elem,"volumechange")},MUTE:function(a){if(!a.state){var b=l(a.id);if(b&&b.muted!=a.state)b.muted=a.state,h(b._elem,"volumechange")}}}};var L=function(a){d.each(g.jwEvents,function(b,c){d.each(c,function(c){a.jwapi["add"+b+"Listener"](c,"jQuery.webshims.mediaelement.jwEvents."+b+"."+c)})})},F=function(a){a&&(a._ppFlag===s&&d.prop(a._elem,"autoplay")||
!a.paused)&&setTimeout(function(){if(a.isActive=="flash"&&(a._ppFlag===s||!a.paused))try{d(a._elem).play()}catch(b){}},1)},M=function(a){if(a&&a._elemNodeName=="video"){var b,c,e,f,o,i,h,j,g=function(p,q){if(q&&p&&!(q<1||p<1||a.isActive!="flash"))if(b&&(b.remove(),b=!1),f=p,o=q,clearTimeout(h),c=a._elem.style.width=="auto",e=a._elem.style.height=="auto",c||e){i=i||d(a._elem).getShadowElement();var g;c&&!e?(g=i.height(),p*=g/q,q=g):!c&&e&&(g=i.width(),q*=g/p,p=g);j=!0;setTimeout(function(){j=!1},9);
i.css({width:p,height:q})}},l=function(){if(!(a.isActive!="flash"||d.prop(a._elem,"readyState")&&d.prop(this,"videoWidth"))){var i=d.prop(a._elem,"poster");if(i&&(c=a._elem.style.width=="auto",e=a._elem.style.height=="auto",c||e))b&&(b.remove(),b=!1),b=d('<img style="position: absolute; height: auto; width: auto; top: 0px; left: 0px; visibility: hidden;" />'),b.bind("load error alreadycomplete",function(){clearTimeout(h);var a=this,c=a.naturalWidth||a.width||a.offsetWidth,i=a.naturalHeight||a.height||
a.offsetHeight;i&&c?(g(c,i),a=null):setTimeout(function(){c=a.naturalWidth||a.width||a.offsetWidth;i=a.naturalHeight||a.height||a.offsetHeight;g(c,i);b&&(b.remove(),b=!1);a=null},9);d(this).unbind()}).prop("src",i).appendTo("body").each(function(){this.complete||this.error?d(this).triggerHandler("alreadycomplete"):(clearTimeout(h),h=setTimeout(function(){d(a._elem).triggerHandler("error")},9999))})}};d(a._elem).bind("loadedmetadata",function(){g(d.prop(this,"videoWidth"),d.prop(this,"videoHeight"))}).bind("emptied",
l).bind("swfstageresize",function(){j||g(f,o)}).bind("emptied",function(){f=void 0;o=void 0}).triggerHandler("swfstageresize");l();d.prop(a._elem,"readyState")&&g(d.prop(a._elem,"videoWidth"),d.prop(a._elem,"videoHeight"))}};g.playerResize=function(a){a&&(a=u.getElementById(a.replace(D,"")))&&d(a).triggerHandler("swfstageresize")};d(u).bind("emptied",function(a){a=n(a.target);F(a)});var v;g.jwPlayerReady=function(a){var b=l(a.id);if(b&&b.jwapi){clearTimeout(v);b.jwData=a;b.shadowElem.removeClass("flashblocker-assumed");
b.wasSwfReady?d(b._elem).mediaLoad():(a=parseFloat(a.version,10),(a<5.6||a>=6)&&f.warn("mediaelement-swf is only testet with jwplayer 5.6+"),d.prop(b._elem,"volume",b.volume),d.prop(b._elem,"muted",b.muted),L(b));b.wasSwfReady=!0;var a=b.actionQueue.length,c=0,e;if(a&&b.isActive=="flash")for(;b.actionQueue.length&&a>c;)c++,e=b.actionQueue.shift(),b.jwapi[e.fn].apply(b.jwapi,e.args);if(b.actionQueue.length)b.actionQueue=[];F(b)}};var y=d.noop;if(w){var N={play:1,playing:1},G="play,pause,playing,canplay,progress,waiting,ended,loadedmetadata,durationchange,emptied".split(","),
H=G.map(function(a){return a+".webshimspolyfill"}).join(" "),O=function(a){var b=f.data(a.target,"mediaelement");b&&(a.originalEvent&&a.originalEvent.type===a.type)==(b.activating=="flash")&&(a.stopImmediatePropagation(),N[a.type]&&b.isActive!=b.activating&&d(a.target).pause())},y=function(a){d(a).unbind(H).bind(H,O);G.forEach(function(b){f.moveToFirstEvent(a,b)})};y(u)}g.setActive=function(a,b,c){c||(c=f.data(a,"mediaelement"));if(c&&c.isActive!=b){b!="html5"&&b!="flash"&&f.warn("wrong type for mediaelement activating: "+
b);var e=f.data(a,"shadowData");c.activating=b;d(a).pause();c.isActive=b;b=="flash"?(e.shadowElement=e.shadowFocusElement=c.shadowElem[0],d(a).hide().getShadowElement().show()):(d(a).show().getShadowElement().hide(),e.shadowElement=e.shadowFocusElement=!1)}};var P=function(){var a="_bufferedEnd,_bufferedStart,_metadata,_ppFlag,currentSrc,currentTime,duration,ended,networkState,paused,videoHeight,videoWidth,_callMeta,_durationCalcs".split(","),b=a.length;return function(c){if(c){var d=b,f=c.networkState;
for(k(0,c);--d;)delete c[a[d]];c.actionQueue=[];c.buffered.length=0;f&&h(c._elem,"emptied")}}}(),I=function(a,b){var c=a._elem,e=a.shadowElem;d(c)[b?"addClass":"removeClass"]("webshims-controls");a._elemNodeName=="audio"&&!b?e.css({width:0,height:0}):e.css({width:c.style.width||d(c).width(),height:c.style.height||d(c).height()})};g.createSWF=function(a,b,c){if(A){t<1?t=1:t++;var e=d.extend({},j.jwVars,{image:d.prop(a,"poster")||"",file:b.srcProp}),h=d(a).data("jwvars")||{};if(c&&c.swfCreated)g.setActive(a,
"flash",c),P(c),c.currentSrc=b.srcProp,d.extend(e,h),j.changeJW(e,a,b,c,"load"),r(a,"sendEvent",["LOAD",e]);else{var o=d.prop(a,"controls"),i="jwplayer-"+f.getID(a),l=d.extend({},j.jwParams,d(a).data("jwparams")),k=a.nodeName.toLowerCase(),n=d.extend({},j.jwAttrs,{name:i,id:i},d(a).data("jwattrs")),m=d('<div class="polyfill-'+k+' polyfill-mediaelement" id="wrapper-'+i+'"><div id="'+i+'"></div>').css({position:"relative",overflow:"hidden"}),c=f.data(a,"mediaelement",f.objectCreate(C,{actionQueue:{value:[]},
shadowElem:{value:m},_elemNodeName:{value:k},_elem:{value:a},currentSrc:{value:b.srcProp},swfCreated:{value:!0},buffered:{value:{start:function(a){if(a>=c.buffered.length)f.error("buffered index size error");else return 0},end:function(a){if(a>=c.buffered.length)f.error("buffered index size error");else return(c.duration-c._bufferedStart)*c._bufferedEnd/100+c._bufferedStart},length:0}}}));I(c,o);m.insertBefore(a);w&&d.extend(c,{volume:d.prop(a,"volume"),muted:d.prop(a,"muted")});d.extend(e,{id:i,
controlbar:o?j.jwVars.controlbar||(k=="video"?"over":"bottom"):k=="video"?"none":"bottom",icons:""+(o&&k=="video")},h,{playerready:"jQuery.webshims.mediaelement.jwPlayerReady"});e.plugins?e.plugins+=","+E:e.plugins=E;f.addShadowDom(a,m);y(a);g.setActive(a,"flash",c);j.changeJW(e,a,b,c,"embed");M(c);z.embedSWF(K,i,"100%","100%","9.0.0",!1,e,l,n,function(b){if(b.success)c.jwapi=b.ref,o||d(b.ref).attr("tabindex","-1").css("outline","none"),setTimeout(function(){if(!b.ref.parentNode&&m[0].parentNode||
b.ref.style.display=="none")m.addClass("flashblocker-assumed"),d(a).trigger("flashblocker"),f.warn("flashblocker assumed");d(b.ref).css({minHeight:"2px",minWidth:"2px",display:"block"})},9),v||(clearTimeout(v),v=setTimeout(function(){var a=d(b.ref);a[0].offsetWidth>1&&a[0].offsetHeight>1&&location.protocol.indexOf("file:")===0?f.warn("Add your local development-directory to the local-trusted security sandbox:  http://www.macromedia.com/support/documentation/en/flashplayer/help/settings_manager04.html"):
(a[0].offsetWidth<2||a[0].offsetHeight<2)&&f.info("JS-SWF connection can't be established on hidden or unconnected flash objects")},8E3))})}}else setTimeout(function(){d(a).mediaLoad()},1)};var r=function(a,b,c,d){return(d=d||n(a))?(d.jwapi&&d.jwapi[b]?d.jwapi[b].apply(d.jwapi,c||[]):(d.actionQueue.push({fn:b,args:c}),d.actionQueue.length>10&&setTimeout(function(){d.actionQueue.length>5&&d.actionQueue.shift()},99)),d):!1};["audio","video"].forEach(function(a){var b={},c,e=function(d){a=="audio"&&
(d=="videoHeight"||d=="videoWidth")||(b[d]={get:function(){var a=n(this);return a?a[d]:w&&c[d].prop._supget?c[d].prop._supget.apply(this):C[d]},writeable:!1})},g=function(a,c){e(a);delete b[a].writeable;b[a].set=c};g("volume",function(a){var b=n(this);if(b){if(a*=100,!isNaN(a)){var d=b.muted;(a<0||a>100)&&f.error("volume greater or less than allowed "+a/100);r(this,"sendEvent",["VOLUME",a],b);if(d)try{b.jwapi.sendEvent("mute","true")}catch(e){}a/=100;if(!(b.volume==a||b.isActive!="flash"))b.volume=
a,h(b._elem,"volumechange")}}else if(c.volume.prop._supset)return c.volume.prop._supset.apply(this,arguments)});g("muted",function(a){var b=n(this);if(b){if(a=!!a,r(this,"sendEvent",["mute",""+a],b),!(b.muted==a||b.isActive!="flash"))b.muted=a,h(b._elem,"volumechange")}else if(c.muted.prop._supset)return c.muted.prop._supset.apply(this,arguments)});g("currentTime",function(a){var b=n(this);if(b){if(a*=1,!isNaN(a)){if(b.paused)clearTimeout(b.stopPlayPause),b.stopPlayPause=setTimeout(function(){b.paused=
!0;b.stopPlayPause=!1},50);r(this,"sendEvent",["SEEK",""+a],b);if(b.paused){if(b.readyState>0)b.currentTime=a,h(b._elem,"timeupdate");try{b.jwapi.sendEvent("play","false")}catch(d){}}}}else if(c.currentTime.prop._supset)return c.currentTime.prop._supset.apply(this,arguments)});["play","pause"].forEach(function(a){b[a]={value:function(){var b=n(this);if(b)b.stopPlayPause&&clearTimeout(b.stopPlayPause),r(this,"sendEvent",["play",a=="play"],b),setTimeout(function(){if(b.isActive=="flash"&&(b._ppFlag=
!0,b.paused!=(a!="play")))b.paused=a!="play",h(b._elem,a)},1);else if(c[a].prop._supvalue)return c[a].prop._supvalue.apply(this,arguments)}}});J.forEach(e);f.onNodeNamesPropertyModify(a,"controls",function(b,c){var e=n(this);d(this)[c?"addClass":"removeClass"]("webshims-controls");if(e){try{r(this,c?"showControls":"hideControls",[a],e)}catch(g){f.warn("you need to generate a crossdomain.xml")}a=="audio"&&I(e,c);d(e.jwapi).attr("tabindex",c?"0":"-1")}});c=f.defineNodeNameProperties(a,b,"prop")});if(A){var Q=
d.cleanData,R=d.browser.msie&&f.browserVersion<9,S={object:1,OBJECT:1};d.cleanData=function(a){var b,c,d;if(a&&(c=a.length)&&t)for(b=0;b<c;b++)if(S[a[b].nodeName]){if("sendEvent"in a[b]){t--;try{a[b].sendEvent("play",!1)}catch(f){}}if(R)try{for(d in a[b])typeof a[b][d]=="function"&&(a[b][d]=null)}catch(g){}}return Q.apply(this,arguments)}}});
